import json
import logging
import uuid
import base64
from datetime import date, datetime
from typing import Dict, Any, Optional, List
import boto3
from services.service_credit_proposal_coril.src.repositories.credit_proposal_coril_repository import CreditProposalCorilRepository
from .pdf_generator_coril_service import PDFGeneratorCorilService
from .word_generator_coril_service import WordGeneratorCorilService
from services.service_credit_proposal_coril.src.models.credit_proposal_coril import CreditProposalCoril, ProposalStatus
from services.service_credit_proposal_coril.src.utils.appsync_status import (
    notify_iniciado,
    notify_creado,
    notify_completado,
    notify_eliminado,
    notify_eliminados_lote,
)
from common.exceptions.exceptions import BusinessValidationError, ServiceError, NotFoundError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _s3_key_base_for_db(s3_key: str) -> str:
    """Devuelve el s3_key sin extensión para guardar en BD. PDF y Word comparten la misma base."""
    if not s3_key:
        return s3_key
    if s3_key.endswith(".pdf"):
        return s3_key[:-4]
    if s3_key.endswith(".docx"):
        return s3_key[:-5]
    return s3_key


class CreditProposalCorilService:
    """Servicio para gestionar propuestas de crédito coril."""
    
    def __init__(
        self,
        repository: CreditProposalCorilRepository,
        pdf_generator: PDFGeneratorCorilService,
        word_generator: WordGeneratorCorilService = None,
        s3_client=None,
        business_repository=None
    ):
        self.repository = repository
        self.pdf_generator = pdf_generator
        self.word_generator = word_generator
        self.s3_client = s3_client
        self.business_repository = business_repository

    def init_proposal(
        self,
        business_id: str,
        user_name: str,
        deal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Inicializa una propuesta de crédito CORIL (registro en BD sin proposal_data).
        Notifica INICIADO y CREADO a AppSync. No envía mensaje a ninguna cola SQS.
        (El flujo que envía a SQS FIFO y llama al listener/Step Function está en
         service_credit_proposal: init_credit_proposal.py → tabla credit_proposals.)
        Retorna credit_memo_id, proposal_number y datos para el handler.
        """
        credit_proposal_data = {
            "id": str(uuid.uuid4()),
            "business_id": business_id,
            "deal_id": deal_id,
            "user_name": user_name,
            "proposal_date": date.today(),
            "status": ProposalStatus.INICIADO,
            "pdf_s3_key": None,
            "proposal_data": None,
        }
        credit_proposal = self.repository.create(credit_proposal_data)
        credit_memo_id = str(credit_proposal.id)
        proposal_number = credit_proposal.proposal_number

        notify_iniciado(f"Propuesta {proposal_number} iniciada", credit_memo_id)
        created_summary = self.repository.get_proposal_summary_by_id(credit_memo_id)
        notify_creado(
            f"Propuesta {proposal_number} creada",
            credit_memo_id=credit_memo_id,
            created_proposal=created_summary,
        )

        return {
            "credit_memo_id": credit_memo_id,
            "proposal_number": proposal_number,
            "business_id": business_id,
            "deal_id": deal_id,
            "user_name": user_name,
            "status": ProposalStatus.INICIADO,
        }

    def get_proposal_summary_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene resumen de propuesta por ID (para notificación CREADO)."""
        return self.repository.get_proposal_summary_by_id(proposal_id)

    def update_credit_memo_status(self, credit_memo_id: str, status: str) -> bool:
        """Actualiza el status de una propuesta en BD (para appsync_status)."""
        return self.repository.update_status(credit_memo_id, status)

    def create_credit_proposal_coril(
        self,
        proposal_data: Dict[str, Any],
        business_id: str,
        user_name: str,
        deal_id: Optional[str] = None,
        proposal_number: Optional[str] = None,
        total_amount: Optional[float] = None,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Crea una nueva propuesta de crédito coril y genera su PDF.
        
        Args:
            proposal_data: Datos completos de la propuesta (JSON como sample_cover.json)
            business_id: ID del negocio
            user_name: Nombre del usuario que crea la propuesta
            deal_id: ID del deal (opcional)
            proposal_number: Número de propuesta (opcional, se genera si no se proporciona)
            total_amount: Monto total (opcional)
            currency: Moneda (default: USD)
            
        Returns:
            Dict con la información de la propuesta creada y el PDF generado
        """
        try:
            logger.info(f"Creando propuesta de crédito coril para business_id: {business_id}")
            
            # Validar datos requeridos
            if not business_id:
                raise BusinessValidationError("business_id es requerido")
            if not user_name:
                raise BusinessValidationError("user_name es requerido")
            if not proposal_data:
                raise BusinessValidationError("proposal_data es requerido")
            
            # Validar que el business_id exista
            self._validate_business_exists(business_id)
            
            # El proposal_number se genera automáticamente por trigger en la BD si es NULL
            # Solo se usa si se proporciona explícitamente
            
            # Generar PDF
            logger.info("Generando PDF de la propuesta coril...")
            pdf_result = self.pdf_generator.generate_pdf_from_json(proposal_data)
            
            # Generar Word también (si está disponible); en este flujo aún no hay created_at en BD, usamos utcnow
            word_result: Optional[Dict[str, Any]] = None
            if self.word_generator:
                logger.info("Generando documento Word de la propuesta coril...")
                try:
                    word_result = self.word_generator.generate_word_document(
                        proposal_data,
                        created_at_utc=datetime.utcnow(),
                    )
                    logger.info("Word generado exitosamente")
                except Exception as word_err:
                    logger.warning(f"Error generando Word (continuando solo con PDF): {str(word_err)}")
                    # No fallar si el Word no se puede generar, solo continuar con PDF
            
            # Usar transacción para crear registro y subir a S3
            # Si falla S3, se hace rollback de la creación en BD
            with self.repository.transaction() as tx:
                # Crear registro en BD dentro de la transacción
                credit_proposal_data = {
                    "id": str(uuid.uuid4()),
                    "business_id": business_id,
                    "deal_id": deal_id,
                    "user_name": user_name,
                    "proposal_date": date.today(),
                    "total_amount": total_amount,
                    "currency": currency,
                    "pdf_s3_key": None,  # Se actualizará después de subir a S3
                    "proposal_data": proposal_data
                }
                
                # Solo incluir proposal_number si se proporciona explícitamente
                if proposal_number:
                    credit_proposal_data["proposal_number"] = proposal_number
                
                credit_proposal = tx.create(credit_proposal_data)
                logger.info(f"Propuesta coril creada con ID: {credit_proposal.id}")
                
                # Subir PDF a S3 si está configurado (dentro de la transacción)
                # Si falla, la transacción hará rollback
                s3_pdf_result = self._upload_pdf_to_s3(
                    pdf_result=pdf_result,
                    proposal_id=str(credit_proposal.id),
                    business_id=business_id
                )
                
                # Subir Word a S3 si está disponible (dentro de la transacción)
                s3_word_result = None
                if word_result and self.s3_client:
                    try:
                        s3_word_result = self._upload_word_to_s3(
                            word_result=word_result,
                            proposal_id=str(credit_proposal.id),
                            business_id=business_id
                        )
                        logger.info(f"Word subido a S3: {s3_word_result['key']}")
                    except Exception as word_upload_err:
                        logger.warning(f"Error subiendo Word a S3 (continuando): {str(word_upload_err)}")
                        # No fallar si el Word no se puede subir, solo continuar con PDF
                
                # Si S3 fue exitoso, actualizar la clave S3 en la BD (sin extensión: PDF y Word comparten base)
                if s3_pdf_result:
                    key_for_db = _s3_key_base_for_db(s3_pdf_result["key"])
                    credit_proposal = tx.update(str(credit_proposal.id), {"pdf_s3_key": key_for_db})
                    logger.info(f"PDF S3 key actualizado en BD: {s3_pdf_result['key']}")
            
            # Obtener el objeto actualizado después de la transacción
            credit_proposal = self.repository.find_by_id(str(credit_proposal.id))
            
            return {
                "credit_proposal_coril": {
                    "id": str(credit_proposal.id),
                    "proposal_number": credit_proposal.proposal_number,
                    "business_id": str(credit_proposal.business_id),
                    "deal_id": str(credit_proposal.deal_id) if credit_proposal.deal_id else None,
                    "user_name": credit_proposal.user_name,
                    "proposal_date": credit_proposal.proposal_date.isoformat(),
                    "total_amount": credit_proposal.total_amount,
                    "currency": credit_proposal.currency,
                    "created_at": credit_proposal.created_at.isoformat()
                },
                "s3": {
                    "pdf": s3_pdf_result,
                    "word": s3_word_result
                }
            }
            
        except BusinessValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creando propuesta de crédito coril: {str(e)}", exc_info=True)
            raise ServiceError(f"Error al crear propuesta de crédito coril: {str(e)}") from e
    
    def generate_documents_for_proposal(
        self,
        proposal_id: str,
        proposal_data: Dict[str, Any],
        total_amount: Optional[float] = None,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Genera PDF y Word para una propuesta existente y actualiza el registro.
        Actualiza status en BD: EN_PROGRESO al inicio, COMPLETADO al éxito, FALLIDO en error.
        
        Args:
            proposal_id: ID de la propuesta existente (credit_memo_id)
            proposal_data: Datos completos de la propuesta (generados por análisis)
            total_amount: Monto total (opcional)
            currency: Moneda (default: USD)
            
        Returns:
            Dict con la información del PDF/Word generado
        """
        self.repository.update_status(proposal_id, ProposalStatus.EN_PROGRESO)
        try:
            logger.info(f"Generando documentos para propuesta existente: {proposal_id}")
            
            # Verificar que la propuesta existe
            credit_proposal = self.repository.find_by_id(proposal_id)
            if not credit_proposal:
                raise NotFoundError(f"Propuesta con ID {proposal_id} no encontrada")
            
            # Validar proposal_data
            if not proposal_data:
                raise BusinessValidationError("proposal_data es requerido")
            
            # Generar PDF
            logger.info("Generando PDF de la propuesta coril...")
            pdf_result = self.pdf_generator.generate_pdf_from_json(proposal_data)
            
            # Generar Word también (si está disponible); fecha_hora_creacion desde BD (UTC → Perú)
            word_result: Optional[Dict[str, Any]] = None
            if self.word_generator:
                logger.info(
                    "[fecha_hora_creacion] generate_documents_for_proposal: credit_proposal.created_at=%s (tipo=%s)",
                    getattr(credit_proposal, "created_at", None),
                    type(getattr(credit_proposal, "created_at", None)).__name__,
                )
                logger.info("Generando documento Word de la propuesta coril...")
                try:
                    word_result = self.word_generator.generate_word_document(
                        proposal_data,
                        created_at_utc=credit_proposal.created_at,
                    )
                    logger.info("Word generado exitosamente")
                except Exception as word_err:
                    logger.warning(f"Error generando Word (continuando solo con PDF): {str(word_err)}")
            
            # Subir PDF a S3
            s3_pdf_result = self._upload_pdf_to_s3(
                pdf_result=pdf_result,
                proposal_id=proposal_id,
                business_id=str(credit_proposal.business_id)
            )
            
            # Subir Word a S3 si está disponible
            s3_word_result = None
            if word_result and self.s3_client:
                try:
                    s3_word_result = self._upload_word_to_s3(
                        word_result=word_result,
                        proposal_id=proposal_id,
                        business_id=str(credit_proposal.business_id)
                    )
                    logger.info(f"Word subido a S3: {s3_word_result['key']}")
                except Exception as word_upload_err:
                    logger.warning(f"Error subiendo Word a S3: {str(word_upload_err)}")
            
            # Actualizar registro en BD con proposal_data y S3 keys
            update_data = {
                "proposal_data": proposal_data,
                "updated_at": datetime.utcnow()
            }
            
            if total_amount is not None:
                update_data["total_amount"] = total_amount
            if currency:
                update_data["currency"] = currency
            if s3_pdf_result:
                update_data["pdf_s3_key"] = _s3_key_base_for_db(s3_pdf_result["key"])
            
            # Log del proposal_data que se guarda en BD (para inspección en CloudWatch/consola)
            logger.info(
                "Proposal data que se guarda en BD | proposal_id=%s | payload=%s",
                proposal_id,
                json.dumps(proposal_data, ensure_ascii=False, default=str),
            )
            
            # Esta línea guarda en BD: UPDATE credit_proposals_coril SET proposal_data = ..., pdf_s3_key = ..., etc.
            logger.info("Guardando en BD: repository.update(proposal_id=%s, update_data) -> persiste proposal_data y S3 keys", proposal_id)
            self.repository.update(proposal_id, update_data)
            self.repository.update_status(proposal_id, ProposalStatus.COMPLETADO)
            notify_completado("Memo de crédito generado exitosamente", proposal_id)

            # Obtener el objeto actualizado
            credit_proposal = self.repository.find_by_id(proposal_id)
            
            return {
                "credit_proposal_coril": {
                    "id": str(credit_proposal.id),
                    "proposal_number": credit_proposal.proposal_number,
                    "business_id": str(credit_proposal.business_id),
                    "deal_id": str(credit_proposal.deal_id) if credit_proposal.deal_id else None,
                    "user_name": credit_proposal.user_name,
                    "status": getattr(credit_proposal, 'status', None),
                    "updated_at": credit_proposal.updated_at.isoformat() if credit_proposal.updated_at else None
                },
                "s3": {
                    "pdf": s3_pdf_result,
                    "word": s3_word_result
                }
            }
            
        except (NotFoundError, BusinessValidationError):
            self.repository.update_status(proposal_id, ProposalStatus.FALLIDO)
            raise
        except Exception as e:
            self.repository.update_status(proposal_id, ProposalStatus.FALLIDO)
            logger.error(f"Error generando documentos para propuesta: {str(e)}", exc_info=True)
            raise ServiceError(f"Error al generar documentos: {str(e)}") from e

    def create_credit_proposal_coril_word(
        self,
        proposal_data: Dict[str, Any],
        business_id: str,
        user_name: str,
        deal_id: Optional[str] = None,
        proposal_number: Optional[str] = None,
        total_amount: Optional[float] = None,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Crea una nueva propuesta de crédito coril y genera su documento Word.
        
        Args:
            proposal_data: Datos completos de la propuesta (JSON como sample_cover.json)
            business_id: ID del negocio
            user_name: Nombre del usuario que crea la propuesta
            deal_id: ID del deal (opcional)
            proposal_number: Número de propuesta (opcional, se genera si no se proporciona)
            total_amount: Monto total (opcional)
            currency: Moneda (default: USD)
            
        Returns:
            Dict con la información de la propuesta creada y el documento Word generado
        """
        try:
            logger.info(f"Creando propuesta de crédito coril (Word) para business_id: {business_id}")
            
            # Validar que word_generator esté disponible
            if not self.word_generator:
                raise ServiceError("WordGeneratorService no está disponible")
            
            # Validar datos requeridos
            if not business_id:
                raise BusinessValidationError("business_id es requerido")
            if not user_name:
                raise BusinessValidationError("user_name es requerido")
            if not proposal_data:
                raise BusinessValidationError("proposal_data es requerido")
            
            # Validar que el business_id exista
            self._validate_business_exists(business_id)
            
            # Generar documento Word (aún no hay created_at en BD, usamos utcnow)
            logger.info("Generando documento Word de la propuesta coril...")
            word_result = self.word_generator.generate_word_document(
                proposal_data,
                created_at_utc=datetime.utcnow(),
            )
            
            # Usar transacción para crear registro y subir a S3
            with self.repository.transaction() as tx:
                # Crear registro en BD dentro de la transacción
                credit_proposal_data = {
                    "id": str(uuid.uuid4()),
                    "business_id": business_id,
                    "deal_id": deal_id,
                    "user_name": user_name,
                    "proposal_date": date.today(),
                    "total_amount": total_amount,
                    "currency": currency,
                    "pdf_s3_key": None,  # Se actualizará después de subir a S3 (usamos mismo campo)
                    "proposal_data": proposal_data
                }
                
                # Solo incluir proposal_number si se proporciona explícitamente
                if proposal_number:
                    credit_proposal_data["proposal_number"] = proposal_number
                
                credit_proposal = tx.create(credit_proposal_data)
                logger.info(f"Propuesta coril (Word) creada con ID: {credit_proposal.id}")
                
                # Subir Word a S3 si está configurado (dentro de la transacción)
                s3_result = self._upload_word_to_s3(
                    word_result=word_result,
                    proposal_id=str(credit_proposal.id),
                    business_id=business_id
                )
                
                # Si S3 fue exitoso, actualizar la clave S3 en la BD
                if s3_result:
                    credit_proposal = tx.update(str(credit_proposal.id), {"pdf_s3_key": s3_result["key"]})
                    logger.info(f"Word S3 key actualizado en BD: {s3_result['key']}")
            
            # Obtener el objeto actualizado después de la transacción
            credit_proposal = self.repository.find_by_id(str(credit_proposal.id))
            
            return {
                "credit_proposal_coril": {
                    "id": str(credit_proposal.id),
                    "proposal_number": credit_proposal.proposal_number,
                    "business_id": str(credit_proposal.business_id),
                    "deal_id": str(credit_proposal.deal_id) if credit_proposal.deal_id else None,
                    "user_name": credit_proposal.user_name,
                    "proposal_date": credit_proposal.proposal_date.isoformat(),
                    "total_amount": credit_proposal.total_amount,
                    "currency": credit_proposal.currency,
                    "created_at": credit_proposal.created_at.isoformat()
                },
                "word": {
                    "filename": word_result["filename"],
                    "size_bytes": word_result["size_bytes"],
                    "size_kb": word_result["size_kb"]
                },
                "s3": s3_result
            }
            
        except BusinessValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creando propuesta de crédito coril (Word): {str(e)}", exc_info=True)
            raise ServiceError(f"Error al crear propuesta de crédito coril (Word): {str(e)}") from e
    
    def get_by_evaluator_id(self, evaluator_id: str, business_id: str = None, limit: int = 100, offset: int = 0):
        """Obtiene todas las propuestas coril de un evaluator, opcionalmente filtradas por business_id."""
        return self.repository.find_by_evaluator_id(evaluator_id, business_id, limit, offset)
    
    def get_detail_by_id(self, proposal_id: str, evaluator_id: str) -> Dict[str, Any]:
        """
        Obtiene el detalle completo de una propuesta (incluyendo proposal_data).
        """
        try:
            logger.info(f"Obteniendo detalle de propuesta coril {proposal_id}")

            credit_proposal = self.repository.find_by_id(proposal_id)
            if not credit_proposal:
                raise NotFoundError(
                    f"Propuesta de crédito coril con ID {proposal_id} no encontrada"
                )

            deal_id = str(credit_proposal.deal_id) if credit_proposal.deal_id else None
            user_name = credit_proposal.user_name
            proposal_date = (
                credit_proposal.proposal_date.isoformat()
                if hasattr(credit_proposal.proposal_date, "isoformat")
                else credit_proposal.proposal_date
            )
            created_at = (
                credit_proposal.created_at.isoformat() if credit_proposal.created_at else None
            )
            updated_at = (
                credit_proposal.updated_at.isoformat() if credit_proposal.updated_at else None
            )

            return {
                "id": str(credit_proposal.id),
                "proposal_number": credit_proposal.proposal_number,
                "business_id": str(credit_proposal.business_id),
                "deal_id": deal_id,
                "user_name": user_name,
                "proposal_date": proposal_date,
                "total_amount": credit_proposal.total_amount,
                "currency": credit_proposal.currency,
                "pdf_s3_key": credit_proposal.pdf_s3_key,
                "proposal_data": credit_proposal.proposal_data,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        except (NotFoundError, BusinessValidationError):
            raise
        except Exception as e:
            logger.error(
                f"Error obteniendo detalle de propuesta de crédito coril: {str(e)}",
                exc_info=True,
            )
            raise ServiceError(
                f"Error al obtener detalle de propuesta de crédito coril: {str(e)}"
            ) from e
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge recursivo: overlay se fusiona sobre base.
        - Si overlay[key] es dict y base[key] es dict: merge recursivo.
        - Si overlay[key] es list (o no-dict): reemplaza base[key] (listas, strings, números, etc.).
        """
        result = dict(base)
        for key, val in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = CreditProposalCorilService._deep_merge(result[key], val)
            else:
                result[key] = val
        return result

    def patch_credit_proposal_coril(
        self,
        proposal_id: str,
        evaluator_id: str,
        partial_data: Dict[str, Any],
        total_amount: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Actualización parcial (PATCH): merge de partial_data sobre proposal_data existente.
        Permite editar solo lo que se envía (ej: {"header": {"date": "..."}} o {"financial_results": {...}}).
        - Objetos anidados: merge recursivo.
        - Listas: se reemplazan completas si se envían (ej: financial_results.financial_results_list).
        Regenera PDF y Word en S3 con el resultado mergado.
        """
        credit_proposal = self.repository.find_by_id(proposal_id)
        if not credit_proposal:
            raise NotFoundError(f"Propuesta de crédito coril con ID {proposal_id} no encontrada")

        current = credit_proposal.proposal_data or {}
        if not isinstance(current, dict):
            current = {}
        merged = self._deep_merge(current, partial_data)
        return self.update_credit_proposal_coril(
            proposal_id=proposal_id,
            evaluator_id=evaluator_id,
            proposal_data=merged,
            total_amount=total_amount,
            currency=currency,
        )

    def update_credit_proposal_coril(
        self,
        proposal_id: str,
        evaluator_id: str,
        proposal_data: Dict[str, Any],
        total_amount: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Actualiza una propuesta existente
        IMPORTANTE: Replaces 'proposal_data' COMPLETAMENTE (no hace merge, sobrescribe todo el JSON).
        Regenera PDF y Word en S3 (sobrescribiendo los archivos).
        """
        try:
            logger.info(f"Actualizando propuesta de crédito coril: {proposal_id}")

            credit_proposal = self.repository.find_by_id(proposal_id)
            if not credit_proposal:
                raise NotFoundError(
                    f"Propuesta de crédito coril con ID {proposal_id} no encontrada"
                )

            # Generar nuevo PDF desde el proposal_data actualizado
            logger.info("Generando nuevo PDF de la propuesta coril (update)...")
            pdf_result = self.pdf_generator.generate_pdf_from_json(proposal_data)

            # Generar nuevo Word si el generador está disponible; fecha_hora_creacion desde BD (UTC → Perú)
            word_result: Optional[Dict[str, Any]] = None
            if self.word_generator:
                logger.info("Generando nuevo documento Word de la propuesta coril (update)...")
                word_result = self.word_generator.generate_word_document(
                    proposal_data,
                    created_at_utc=credit_proposal.created_at,
                )

            # Determinar path base en S3 a partir del pdf_s3_key actual (si existe)
            base_dir = None
            base_name = None
            if credit_proposal.pdf_s3_key:
                parts = credit_proposal.pdf_s3_key.rsplit("/", 1)
                if len(parts) == 2:
                    base_dir = parts[0]
                    original_filename = parts[1]
                else:
                    base_dir = f"credit-proposals-coril/{credit_proposal.business_id}/{proposal_id}"
                    original_filename = credit_proposal.pdf_s3_key

                # Remover cualquier extensión (.pdf o .docx) para obtener el base_name
                if "." in original_filename:
                    base_name = original_filename.rsplit(".", 1)[0]
                else:
                    base_name = original_filename
            else:
                # Fallback si no hay pdf_s3_key aún
                base_dir = f"credit-proposals-coril/{credit_proposal.business_id}/{proposal_id}"
                base_name = (
                    f"credit_proposal_coril_{credit_proposal.proposal_number or proposal_id}"
                )

            # Construir filenames consistentes
            pdf_filename = f"{base_name}.pdf"
            word_filename = f"{base_name}.docx"

            pdf_s3_key = f"{base_dir}/{pdf_filename}"
            word_s3_key = f"{base_dir}/{word_filename}"

            # Subir nuevos archivos a S3 (sobrescriben si ya existen)
            s3_pdf_result = None
            s3_word_result = None

            if self.s3_client:
                # Subir PDF
                pdf_bytes = base64.b64decode(pdf_result["pdfBase64"])
                self.s3_client.put_object(
                    Bucket=self.s3_client.bucket_name,
                    Key=pdf_s3_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                )
                s3_pdf_result = {"key": pdf_s3_key, "bucket": self.s3_client.bucket_name}
                logger.info(f"PDF actualizado en S3: {pdf_s3_key}")

                # Subir Word si está disponible
                if word_result:
                    word_bytes = word_result["content"]
                    self.s3_client.put_object(
                        Bucket=self.s3_client.bucket_name,
                        Key=word_s3_key,
                        Body=word_bytes,
                        ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                    s3_word_result = {
                        "key": word_s3_key,
                        "bucket": self.s3_client.bucket_name,
                    }
                    logger.info(f"Word actualizado en S3: {word_s3_key}")
            else:
                logger.warning(
                    "S3 client no configurado, se actualizará solo la información en BD"
                )

            # Actualizar registro en BD
            update_data: Dict[str, Any] = {
                "proposal_data": proposal_data,
                "updated_at": datetime.utcnow(),
            }

            if total_amount is not None:
                update_data["total_amount"] = total_amount
            if currency is not None:
                update_data["currency"] = currency

            # Guardar siempre el key base en BD (sin extensión: PDF y Word comparten la misma base)
            if s3_pdf_result:
                update_data["pdf_s3_key"] = _s3_key_base_for_db(s3_pdf_result["key"])

            credit_proposal = self.repository.update(proposal_id, update_data)

            return {
                "credit_proposal_coril": {
                    "id": str(credit_proposal.id),
                    "proposal_number": credit_proposal.proposal_number,
                    "business_id": str(credit_proposal.business_id),
                    "deal_id": str(credit_proposal.deal_id)
                    if credit_proposal.deal_id
                    else None,
                    "user_name": credit_proposal.user_name,
                    "proposal_date": credit_proposal.proposal_date.isoformat()
                    if hasattr(credit_proposal.proposal_date, "isoformat")
                    else credit_proposal.proposal_date,
                    "total_amount": credit_proposal.total_amount,
                    "currency": credit_proposal.currency,
                    "pdf_s3_key": credit_proposal.pdf_s3_key,
                    "updated_at": credit_proposal.updated_at.isoformat()
                    if credit_proposal.updated_at
                    else None,
                },
                "s3": {
                    "pdf": s3_pdf_result,
                    "word": s3_word_result,
                },
            }
        except (NotFoundError, BusinessValidationError):
            raise
        except Exception as e:
            logger.error(
                f"Error actualizando propuesta de crédito coril: {str(e)}", exc_info=True
            )
            raise ServiceError(
                f"Error al actualizar propuesta de crédito coril: {str(e)}"
            ) from e
    
    def delete_credit_proposal_coril(self, proposal_id: str) -> bool:
        """
        Elimina una propuesta de crédito coril y su PDF de S3.
        
        Args:
            proposal_id: ID de la propuesta a eliminar
            
        Returns:
            bool: True si se eliminó exitosamente
            
        Raises:
            NotFoundError: Si la propuesta no existe
            ServiceError: Si hay error al eliminar
        """
        try:
            logger.info(f"Eliminando propuesta de crédito coril: {proposal_id}")
            
            # Obtener la propuesta para verificar que existe y obtener el pdf_s3_key
            credit_proposal = self.repository.find_by_id(proposal_id)
            if not credit_proposal:
                raise NotFoundError(f"Propuesta de crédito coril con ID {proposal_id} no encontrada")
            
            # Eliminar PDF de S3 si existe. pdf_s3_key en BD viene sin extensión.
            if credit_proposal.pdf_s3_key and self.s3_client:
                try:
                    base = credit_proposal.pdf_s3_key
                    pdf_key = base if base.endswith(".pdf") else base + ".pdf"
                    self._delete_pdf_from_s3(pdf_key)
                    logger.info(f"PDF eliminado de S3: {pdf_key}")
                except Exception as s3_error:
                    # Log el error pero continuar con la eliminación en BD
                    logger.warning(f"Error eliminando PDF de S3 (continuando con eliminación en BD): {str(s3_error)}")
            
            # Eliminar registro de la BD
            deleted = self.repository.delete(proposal_id)
            if not deleted:
                raise ServiceError(f"No se pudo eliminar la propuesta coril con ID: {proposal_id}")
            
            logger.info(f"Propuesta de crédito coril eliminada exitosamente: {proposal_id}")
            notify_eliminado(f"Propuesta {credit_proposal.proposal_number} eliminada", credit_memo_id=proposal_id)

            return True
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error eliminando propuesta de crédito coril: {str(e)}", exc_info=True)
            raise ServiceError(f"Error al eliminar propuesta de crédito coril: {str(e)}") from e

    def delete_credit_proposals_coril_batch(self, proposal_ids: List[str]) -> Dict[str, Any]:
        """
        Elimina varias propuestas de crédito coril por ID.
        Por cada ID intenta eliminar (S3 + BD); los que fallen se reportan en failed.

        Args:
            proposal_ids: Lista de IDs de propuestas a eliminar

        Returns:
            Dict con "deleted" (lista de IDs eliminados) y "failed" (lista de {id, error})
        """
        if not proposal_ids:
            return {"deleted": [], "failed": []}
        deleted = []
        failed = []
        for proposal_id in proposal_ids:
            pid = (proposal_id or "").strip()
            if not pid:
                continue
            try:
                self.delete_credit_proposal_coril(pid)
                deleted.append(pid)
            except Exception as e:
                logger.warning(f"Error eliminando propuesta {pid}: {e}")
                failed.append({"id": pid, "error": str(e)})
        if deleted:
            notify_eliminados_lote(
                message=f"{len(deleted)} propuesta(s) eliminada(s)",
                deleted_ids=deleted,
            )
        return {"deleted": deleted, "failed": failed}

    def get_download_url(self, proposal_id: str, evaluator_id: str, expiration: int = 3600) -> Dict[str, Any]:
        """
        Genera URL de descarga presignada para el PDF de una propuesta.
        
        Args:
            proposal_id: ID de la propuesta
            evaluator_id: ID del evaluator que solicita la descarga
            expiration: Tiempo de expiración en segundos (default: 3600 = 1 hora)
            
        Returns:
            Dict con información de descarga
            
        Raises:
            NotFoundError: Si la propuesta no existe
        """
        try:
            logger.info(f"Generando URL de descarga para propuesta coril {proposal_id}")
            
            # Obtener la propuesta
            credit_proposal = self.repository.find_by_id(proposal_id)
            if not credit_proposal:
                raise NotFoundError(f"Propuesta de crédito coril con ID {proposal_id} no encontrada")
            
            # Generar URL presignada si existe PDF en S3
            if credit_proposal.pdf_s3_key and self.s3_client:
                # s3_key en BD viene sin extensión → agregar .pdf para la URL
                base_key = credit_proposal.pdf_s3_key
                if base_key.endswith(('.pdf', '.docx')):
                    base_key = base_key.rsplit('.', 1)[0]
                pdf_s3_key = base_key + '.pdf'
                download_url = self._generate_presigned_url(
                    s3_key=pdf_s3_key,
                    expiration=expiration
                )
                
                return {
                    "proposal_id": str(credit_proposal.id),
                    "proposal_number": credit_proposal.proposal_number,
                    "download_url": download_url,
                    "expires_in": expiration,
                    "filename": f"credit_proposal_coril_{credit_proposal.proposal_number}.pdf"
                }
            else:
                raise BusinessValidationError("PDF no disponible para esta propuesta")
                
        except (NotFoundError, BusinessValidationError):
            raise
        except Exception as e:
            logger.error(f"Error generando URL de descarga: {str(e)}", exc_info=True)
            raise ServiceError(f"Error al generar URL de descarga: {str(e)}") from e
    
    def get_download_url_word(self, proposal_id: str, evaluator_id: str, expiration: int = 3600) -> Dict[str, Any]:
        """
        Genera URL de descarga presignada para el archivo Word (DOCX) de una propuesta.
        
        Args:
            proposal_id: ID de la propuesta
            evaluator_id: ID del evaluator que solicita la descarga (no se valida actualmente)
            expiration: Tiempo de expiración en segundos (default: 3600 = 1 hora)
            
        Returns:
            Dict con información de descarga
            
        Raises:
            NotFoundError: Si la propuesta no existe
            BusinessValidationError: Si el archivo no está disponible
        """
        try:
            logger.info(f"Generando URL de descarga Word para propuesta coril {proposal_id}")
            
            # Obtener la propuesta
            credit_proposal = self.repository.find_by_id(proposal_id)
            if not credit_proposal:
                raise NotFoundError(f"Propuesta de crédito coril con ID {proposal_id} no encontrada")
            
            # Generar URL presignada para archivo Word (.docx) en S3
            # s3_key en BD viene sin extensión → agregar .docx para la URL
            if credit_proposal.pdf_s3_key and self.s3_client:
                base_key = credit_proposal.pdf_s3_key
                if base_key.endswith(('.pdf', '.docx')):
                    base_key = base_key.rsplit('.', 1)[0]
                word_s3_key = base_key + '.docx'
                word_filename = word_s3_key.rsplit('/', 1)[-1]
                # Generar URL presignada usando el s3_key del Word (.docx)
                download_url = self._generate_presigned_url(
                    s3_key=word_s3_key,
                    expiration=expiration
                )
                
                return {
                    "proposal_id": str(credit_proposal.id),
                    "proposal_number": credit_proposal.proposal_number,
                    "download_url": download_url,
                    "expires_in": expiration,
                    "filename": word_filename
                }
            else:
                raise BusinessValidationError("Word no disponible para esta propuesta")
                
        except (NotFoundError, BusinessValidationError):
            raise
        except Exception as e:
            logger.error(f"Error generando URL de descarga Word: {str(e)}", exc_info=True)
            raise ServiceError(f"Error al generar URL de descarga Word: {str(e)}") from e
    
    def _validate_business_exists(self, business_id: str):
        """Valida que el business exista."""
        if self.business_repository:
            business = self.business_repository.find_by_id(business_id)
            if not business:
                raise BusinessValidationError(f"Business con ID {business_id} no encontrado")
    
    def _validate_evaluator_access(self, business_id: str, evaluator_id: str):
        """Valida que el evaluator tenga acceso al business."""
        if self.business_repository:
            business = self.business_repository.find_by_id(business_id)
            if not business or business.evaluator_id != evaluator_id:
                raise BusinessValidationError("No tienes acceso a esta propuesta")
    
    def _upload_pdf_to_s3(self, pdf_result: Dict[str, Any], proposal_id: str, business_id: str) -> Optional[Dict[str, Any]]:
        """Sube el PDF a S3 y retorna la información."""
        if not self.s3_client:
            logger.warning("S3 client no configurado, omitiendo subida de PDF")
            return None
        
        try:
            # Decodificar PDF de base64
            pdf_bytes = base64.b64decode(pdf_result["pdfBase64"])
            
            # Generar key para S3
            s3_key = f"credit-proposals-coril/{business_id}/{proposal_id}/{pdf_result['filename']}"
            
            # Subir a S3
            self.s3_client.put_object(
                Bucket=self.s3_client.bucket_name,
                Key=s3_key,
                Body=pdf_bytes,
                ContentType='application/pdf'
            )
            
            logger.info(f"PDF subido a S3: {s3_key}")
            return {"key": s3_key, "bucket": self.s3_client.bucket_name}
            
        except Exception as e:
            logger.error(f"Error subiendo PDF a S3: {str(e)}")
            raise ServiceError(f"Error al subir PDF a S3: {str(e)}") from e
    
    def _upload_word_to_s3(self, word_result: Dict[str, Any], proposal_id: str, business_id: str) -> Optional[Dict[str, Any]]:
        """Sube el documento Word a S3 y retorna la información."""
        if not self.s3_client:
            logger.warning("S3 client no configurado, omitiendo subida de Word")
            return None
        
        try:
            # Obtener bytes del documento Word
            word_bytes = word_result["content"]
            
            # Generar key para S3
            s3_key = f"credit-proposals-coril/{business_id}/{proposal_id}/{word_result['filename']}"
            
            # Subir a S3
            self.s3_client.put_object(
                Bucket=self.s3_client.bucket_name,
                Key=s3_key,
                Body=word_bytes,
                ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            
            logger.info(f"Word subido a S3: {s3_key}")
            return {"key": s3_key, "bucket": self.s3_client.bucket_name}
            
        except Exception as e:
            logger.error(f"Error subiendo Word a S3: {str(e)}")
            raise ServiceError(f"Error subiendo Word a S3: {str(e)}") from e
    
    def _delete_pdf_from_s3(self, s3_key: str):
        """Elimina el PDF de S3."""
        if not self.s3_client:
            return
        
        try:
            self.s3_client.delete_object(
                Bucket=self.s3_client.bucket_name,
                Key=s3_key
            )
        except Exception as e:
            logger.error(f"Error eliminando PDF de S3: {str(e)}")
            raise ServiceError(f"Error al eliminar PDF de S3: {str(e)}") from e
    
    def _generate_presigned_url(self, s3_key: str, expiration: int) -> str:
        """Genera URL presignada para descarga."""
        if not self.s3_client:
            raise ServiceError("S3 client no configurado")
        
        try:
           
            s3 = boto3.client('s3')
            return s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.s3_client.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
        except Exception as e:
            logger.error(f"Error generando URL presignada: {str(e)}")
            raise ServiceError(f"Error al generar URL de descarga: {str(e)}") from e
