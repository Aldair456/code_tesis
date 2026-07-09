from models.model_1.ia.src.repositories.financial_datapoint import FinancialDataPointRepository
from models.model_1.ia.src.repositories.account import AccountRepository
from models.model_1.ia.src.repositories.financial_statement import FinancialStatementRepository
from models.model_1.ia.src.repositories.business import BusinessRepository
from models.model_1.ia.src.repositories.match_account_extracts import MatchAccountExtractsRepository
from models.model_1.ia.src.repositories.financial_cashflow_datapoint import FinancialCashflowDatapointRepository
import logging
import json
from typing import List, Dict, Any, Tuple, Optional, Set
import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID
from common.database.database import DatabaseSingletonConnection
from psycopg2.extras import execute_values, Json as PsycopgJson

from common_job.job import JobService
from common_websocket import notify_watching
from datetime import timezone
from common.utils.datapoint_account_resolve import (
    DATAPOINT_UPSERT_CONFLICT_COLUMNS,
    consolidate_datapoints_by_account_period,
    resolve_bank_account_ids,
)

# Configuración de logging más detallada
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constantes para evitar valores mágicos
YEAR_MIN = 1900
YEAR_MAX = 2100
MAX_ACCOUNTS_FETCH = 500
MAI_CONTRIBUTING_TAGS = frozenset(["gm", "om", "ebt"])
PERIOD_MAPPINGS = {
    "PL": {"Q4A": "", "Q1A": "Q1", "Q2A": "Q2", "Q3A": "Q3"},
    "BS": {"Q4A": "", "Q4": "", "Q1A": "Q1", "Q2A": "Q2", "Q3A": "Q3"}
}


@dataclass
class ProcessingStats:
    """Estadísticas del procesamiento para mejor tracking"""
    processed_items: int = 0
    skipped_items: int = 0
    error_items: int = 0
    mai_calculated: int = 0
    taxes_processed: int = 0
    total_inserted: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FinancialDataPointService:
    DATAPOINT_UPSERT_CONFLICT_COLUMNS = DATAPOINT_UPSERT_CONFLICT_COLUMNS

    def __init__(
            self,
            financial_datapoint_repository: FinancialDataPointRepository,
            account_repository: AccountRepository,
            financial_statement_repository: FinancialStatementRepository,
            job_service: JobService,
            business_repository: Optional[BusinessRepository] = None,
            match_account_extracts_repository: Optional[MatchAccountExtractsRepository] = None,
    ):
        self.financial_datapoint_repository = financial_datapoint_repository
        self.account_repository = account_repository
        self.financial_statement_repository = financial_statement_repository
        self.job_service = job_service
        self.business_repository = business_repository or BusinessRepository()
        self.match_account_extracts_repository = (
            match_account_extracts_repository or MatchAccountExtractsRepository()
        )
        # Cache temporal para la ejecución (se limpia en cada invocación)
        self._account_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._processing_stats: Optional[ProcessingStats] = None

    def _reset_state(self):
        """Limpia el estado para asegurar que Lambda no reutilice datos entre invocaciones"""
        self._account_cache = None
        self._processing_stats = ProcessingStats()
        logger.info("Estado interno reiniciado para nueva ejecución")

    def _log_error(self, message: str, exception: Optional[Exception] = None):
        """Registra un error tanto en el logger como en las estadísticas"""
        error_msg = f"{message}: {str(exception)}" if exception else message
        logger.error(error_msg, exc_info=exception is not None)
        if self._processing_stats:
            self._processing_stats.errors.append(error_msg)
            self._processing_stats.error_items += 1

    def _log_warning(self, message: str):
        """Registra una advertencia tanto en el logger como en las estadísticas"""
        logger.warning(message)
        if self._processing_stats:
            self._processing_stats.warnings.append(message)

    def _extract_evaluator_id_from_draft(self, draft: Any) -> Optional[str]:
        if not draft:
            return None
        bid = getattr(draft, "business_id_str", None)
        if not bid and getattr(draft, "business_id", None) is not None:
            bid = str(draft.business_id)
        if not bid:
            self._log_warning(
                "Draft sin business_id: no se puede resolver evaluator_id para account_id"
            )
            return None
        try:
            business = self.business_repository.find_by_id(bid)
            if not business:
                self._log_warning(
                    f"Business {bid} no encontrado; account_id quedará sin resolver"
                )
                return None
            ev = getattr(business, "evaluator_id_str", None)
            if not ev and getattr(business, "evaluator_id", None) is not None:
                ev = str(business.evaluator_id)
            return ev
        except Exception as e:
            self._log_warning(f"Error leyendo business {bid} para evaluator_id: {e}")
            return None

    # ================================================================
    # ===================== Validaciones Mejoradas ==================
    # ================================================================

    def _validate_event_data(self, event: List[dict]) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Valida la estructura del evento con mayor robustez.
        Returns: (is_valid, error_message, statement_id, request_id)
        """
        try:
            if not event:
                return False, "El evento está vacío o es None", None, None

            if not isinstance(event, list):
                return False, f"El evento debe ser una lista, recibido: {type(event).__name__}", None, None

            if len(event) == 0:
                return False, "La lista del evento está vacía", None, None

            # Buscar statement_id y request_id con tolerancia a errores
            statement_id = None
            request_id = None

            for idx, ev in enumerate(event):
                try:
                    if not isinstance(ev, dict):
                        self._log_warning(f"Elemento {idx} del evento no es dict: {type(ev).__name__}")
                        continue

                    if not statement_id and ev.get("statement_id"):
                        statement_id = str(ev.get("statement_id"))

                    if not request_id and ev.get("request_id"):
                        request_id = str(ev.get("request_id"))

                    if statement_id and request_id:
                        break

                except Exception as e:
                    self._log_warning(f"Error procesando elemento {idx} del evento: {e}")

            if not statement_id:
                return False, "No se encontró statement_id en ningún elemento del evento", None, request_id

            logger.info(f"Evento validado - Statement ID: {statement_id}, Request ID: {request_id or 'N/A'}")
            return True, "", statement_id, request_id

        except Exception as e:
            self._log_error("Error crítico validando evento", e)
            return False, f"Error inesperado validando evento: {str(e)}", None, None

    def _safe_get_value(self, obj: Any, attr: str, default: Any = None) -> Any:
        """Obtiene un atributo de forma segura sin lanzar excepciones"""
        try:
            return getattr(obj, attr, default) if hasattr(obj, attr) else default
        except Exception:
            return default

    def _validate_and_convert_numeric(self, value: Any, field_name: str, default: float = 0) -> float:
        """Convierte valores a numérico de forma segura"""
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value.strip())
            return default
        except (ValueError, TypeError) as e:
            self._log_warning(f"Valor no numérico para {field_name}: {value} (tipo: {type(value).__name__})")
            return default

    def _validate_year(self, year_value: Any, context: str = "") -> Optional[int]:
        """Valida y convierte año con mejor logging"""
        try:
            if year_value is None:
                return None

            year_int = None
            if isinstance(year_value, int):
                year_int = year_value
            elif isinstance(year_value, str) and year_value.strip().isdigit():
                year_int = int(year_value.strip())
            else:
                self._log_warning(
                    f"Formato de año inválido {context}: {year_value} (tipo: {type(year_value).__name__})")
                return None

            if YEAR_MIN <= year_int <= YEAR_MAX:
                return year_int
            else:
                self._log_warning(f"Año fuera de rango válido {context}: {year_int}")
                return None

        except Exception as e:
            self._log_warning(f"Error convirtiendo año {context}: {year_value} - {e}")
            return None

    # ================================================================
    # ===================== Mapeo de Cuentas Optimizado =============
    # ================================================================

    def _get_or_create_account_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene el mapeo de cuentas con cache y validación mejorada"""
        try:
            # Usar cache si existe (dentro de la misma ejecución)
            if self._account_cache is not None:
                logger.info(f"Usando cache de cuentas: {len(self._account_cache)} cuentas")
                return self._account_cache

            accounts = self.account_repository.find_all(limit=MAX_ACCOUNTS_FETCH)
            if not accounts:
                self._log_error("No se encontraron cuentas en la base de datos")
                return {}

            account_mapping = {}
            valid_accounts = 0
            invalid_accounts = 0

            for acc in accounts:
                try:
                    name = self._safe_get_value(acc, 'name')
                    if not name:
                        invalid_accounts += 1
                        continue

                    acc_id = self._safe_get_value(acc, 'id_str')
                    acc_type = self._safe_get_value(acc, 'type')
                    acc_tags = self._safe_get_value(acc, 'tags', [])

                    if not acc_id or not acc_type:
                        self._log_warning(f"Cuenta '{name}' incompleta - ID: {acc_id}, Type: {acc_type}")
                        invalid_accounts += 1
                        continue

                    account_mapping[name] = {
                        "id": acc_id,
                        "type": acc_type,
                        "tags": acc_tags if isinstance(acc_tags, list) else []
                    }
                    valid_accounts += 1

                except Exception as e:
                    self._log_warning(f"Error procesando cuenta: {e}")
                    invalid_accounts += 1

            logger.info(f"Mapeo de cuentas completado - Válidas: {valid_accounts}, Inválidas: {invalid_accounts}")

            # Guardar en cache para esta ejecución
            self._account_cache = account_mapping
            return account_mapping

        except Exception as e:
            self._log_error("Error crítico obteniendo mapeo de cuentas", e)
            return {}

    # ================================================================
    # ===================== Cálculo MAI Mejorado ====================
    # ================================================================

    def _calculate_mai_values(self, normalized_data: List[dict], account_mapping: Dict[str, Dict[str, Any]]) -> Dict[
        Tuple[int, str], float]:
        """Calcula valores MAI con mejor manejo de errores"""
        logger.info("Calculando valores MAI")
        mai_values = defaultdict(float)
        items_with_mai_tags = 0

        for idx, item in enumerate(normalized_data):
            try:
                name = item.get("name")
                if not name or name not in account_mapping:
                    continue

                year = self._validate_year(item.get("year"), f"para cuenta '{name}'")
                if not year:
                    continue

                period = str(item.get("period", ""))
                tags = item.get("tags", [])

                if not isinstance(tags, list):
                    tags = []

                # Verificar si tiene tags MAI
                if any(tag in MAI_CONTRIBUTING_TAGS for tag in tags):
                    value = self._validate_and_convert_numeric(
                        item.get("value"),
                        f"MAI cuenta '{name}'"
                    )

                    key = (year, period)
                    mai_values[key] += value
                    items_with_mai_tags += 1

                    if self._processing_stats:
                        self._processing_stats.mai_calculated += 1

            except Exception as e:
                self._log_warning(f"Error procesando item {idx} para MAI: {e}")

        logger.info(f"MAI calculado - Items procesados: {items_with_mai_tags}, Períodos únicos: {len(mai_values)}")
        return dict(mai_values)

    def _create_mai_datapoints(self, mai_values: Dict[Tuple[int, str], float],
                               account_mapping: Dict[str, Dict[str, Any]],
                               statement_id: str) -> List[Dict[str, Any]]:
        """Crea datapoints MAI con validación mejorada"""
        try:
            if "MAI" not in account_mapping:
                self._log_error("La cuenta 'MAI' no existe en el mapeo")
                return []

            mai_account_id = account_mapping["MAI"].get("id")
            if not mai_account_id:
                self._log_error("La cuenta MAI no tiene ID válido")
                return []

            mai_datapoints = []
            current_time = datetime.datetime.utcnow()

            for (year, period), value in mai_values.items():
                try:
                    datapoint = {
                        "value": value,
                        "details": json.dumps([]),
                        "_catalog_extract_id": str(mai_account_id),
                        "financial_statement_id": statement_id,
                        "year": year,
                        "period": period,
                        "created_at": current_time,
                        "updated_at": current_time
                    }
                    mai_datapoints.append(datapoint)

                except Exception as e:
                    self._log_warning(f"Error creando datapoint MAI para {year}/{period}: {e}")

            logger.info(f"Creados {len(mai_datapoints)} datapoints MAI")
            return mai_datapoints

        except Exception as e:
            self._log_error("Error creando datapoints MAI", e)
            return []

    # ================================================================
    # ===================== Procesamiento TAXES Mejorado ============
    # ================================================================

    def _process_taxes_with_mai_adjustment(self, taxes_data: Dict[Tuple[int, str], Dict[str, Any]],
                                           mai_values: Dict[Tuple[int, str], float]) -> List[Dict[str, Any]]:
        """Procesa TAXES con ajuste de signo basado en MAI"""
        logger.info(f"Procesando {len(taxes_data)} datapoints de TAXES")
        processed_taxes = []

        for key, tax_data in taxes_data.items():
            try:
                year, period = key
                original_value = self._validate_and_convert_numeric(
                    tax_data.get("value"),
                    f"TAXES {year}/{period}"
                )
                mai_value = mai_values.get(key, 0)

                # Lógica de ajuste
                if mai_value < 0:
                    adjusted_value = abs(original_value)
                else:
                    adjusted_value = -abs(original_value)

                tax_data_copy = tax_data.copy()
                tax_data_copy["value"] = adjusted_value
                processed_taxes.append(tax_data_copy)

                if self._processing_stats:
                    self._processing_stats.taxes_processed += 1

                logger.debug(
                    f"TAXES ajustado - {year}/{period}: {original_value} -> {adjusted_value} (MAI: {mai_value})")

            except Exception as e:
                self._log_warning(f"Error procesando TAXES para {key}: {e}")
                processed_taxes.append(tax_data)  # Usar original si falla

        return processed_taxes

    # ================================================================
    # ===================== Normalización Mejorada ==================
    # ================================================================

    def _normalize_period(self, period: Any, acc_type: str, is_annual: bool = False) -> Optional[str]:
        """Normaliza período con mejor manejo de casos edge"""
        try:
            if period is None:
                return None

            period_str = str(period).strip()
            if not period_str:
                return None

            # Si es solo dígitos (año), devolverlo
            if period_str.isdigit():
                return period_str

            # Si es anual sin período, retornar None (se manejará después)
            if is_annual and not period_str:
                return None

            # Aplicar mapeos si corresponde
            if len(period_str) >= 4 and acc_type in PERIOD_MAPPINGS:
                year_part = period_str[:4]
                suffix = period_str[4:] if len(period_str) > 4 else ""

                mappings = PERIOD_MAPPINGS[acc_type]
                if suffix in mappings:
                    mapped = mappings[suffix]
                    return f"{year_part}{mapped}" if mapped else year_part

            return period_str

        except Exception as e:
            self._log_warning(f"Error normalizando período '{period}': {e}")
            return str(period) if period else None

    # ================================================================
    # ===================== Método Principal Optimizado =============
    # ================================================================

    def process_financial_data(self, event: List[dict]) -> dict:
        """
        Procesa datos financieros con máxima robustez y continuidad ante errores.
        Optimizado para Lambda con limpieza de estado.
        """
        # Limpiar estado para evitar reutilización en Lambda
        self._reset_state()

        logger.info("=" * 60)
        logger.info("INICIANDO PROCESAMIENTO DE DATOS FINANCIEROS")
        logger.info(f"Timestamp: {datetime.datetime.utcnow().isoformat()}")
        logger.info("=" * 60)

        statement_id = None
        request_id = None

        try:
            # FASE 1: Validación inicial
            is_valid, error_msg, statement_id, request_id = self._validate_event_data(event)
            if not is_valid:
                return self._create_error_response(400, error_msg, statement_id, request_id)

            logger.info(f"Procesando - Request: {request_id or 'N/A'}, Statement: {statement_id}")

            # FASE 2: Obtener y validar financial statement
            draft = None
            try:
                draft = self.financial_statement_repository.find_by_id(statement_id)
                if not draft:
                    return self._create_error_response(404, f"Financial statement {statement_id} no encontrado",
                                                       statement_id, request_id)
            except Exception as e:
                self._log_error(f"Error accediendo a financial statement", e)
                return self._create_error_response(500, f"Error de base de datos: {str(e)}",
                                                   statement_id, request_id)

            # Determinar si es anual
            is_annual = self._safe_get_value(draft, 'statement_periodicity') == "anual"
            logger.info(f"Tipo de statement: {'Anual' if is_annual else 'Periódico'}")

            # FASE 3: Obtener mapeo de cuentas
            account_mapping = self._get_or_create_account_mapping()
            if not account_mapping:
                return self._create_error_response(500, "No se pudo obtener el mapeo de cuentas",
                                                   statement_id, request_id)

            # FASE 4: Normalizar y procesar datos
            normalized = self._extract_and_normalize_data(event)

            if not normalized:
                return self._create_error_response(400, "No hay datos válidos para procesar",
                                                   statement_id, request_id)

            logger.info(f"Datos normalizados: {len(normalized)} elementos")

            # FASE 5: Procesar datapoints
            processing_result = self._process_all_datapoints(
                normalized, account_mapping, statement_id, draft, is_annual
            )

            if not processing_result["success"]:
                return self._create_error_response(500, processing_result["error"],
                                                   statement_id, request_id)

            evaluator_id = self._extract_evaluator_id_from_draft(draft)
            resolved_datapoints = resolve_bank_account_ids(
                processing_result["datapoints"],
                evaluator_id,
                self.match_account_extracts_repository.find_bank_account_id_for_extract,
                on_warning=self._log_warning,
                on_error=self._log_error,
            )
            if not resolved_datapoints:
                return self._create_error_response(
                    400,
                    "Ningún datapoint pudo resolverse a account_id vía match_account_extracts",
                    statement_id,
                    request_id,
                )
            processing_result["datapoints"] = consolidate_datapoints_by_account_period(
                resolved_datapoints
            )

            # FASE 6: Insertar en base de datos
            insertion_result = self._bulk_insert_datapoints(processing_result["datapoints"])



            if not insertion_result["success"]:
                # Marcar como fallido pero devolver información parcial
                self._update_statement_status(statement_id, "FAILED")
                return self._create_partial_success_response(
                    insertion_result, statement_id, request_id, self._processing_stats
                )


            # FASE 7: Actualizar financial statement
            update_result = self._update_financial_statement(
                statement_id, draft,
                processing_result["years"],
                processing_result["periods"]
            )

            # FASE 8: Preparar respuesta exitosa

            return self._create_success_response(
                processing_result, update_result, statement_id, request_id, self._processing_stats
            )

        except Exception as e:
            self._log_error("ERROR CRÍTICO en procesamiento", e)

            # Intentar marcar como fallido
            if statement_id:
                self._update_statement_status(statement_id, "FAILED")

            return self._create_error_response(
                500, f"Error interno: {str(e)}", statement_id, request_id
            )



    def _job_run(self, statement_id: str):
        """Inicia un job marcándolo como RUNNING"""
        try:
            logger.info(f"Iniciando job para statement_id: {statement_id}")

            response = self.job_service.start_job(UUID(statement_id), "EXTRACT_FS")

            if response.get('success'):
                logger.info(f"Job iniciado exitosamente: {statement_id}")
            else:
                logger.error(f"Error iniciando job: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en statement_id '{statement_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado iniciando job para statement_id '{statement_id}': {e}")

    def _job_complete(self, statement_id: str, result_data: Dict[str, Any] = None):
        """Marca un job como completado exitosamente"""
        try:
            logger.info(f"Completando job para statement_id: {statement_id}")

            response = self.job_service.complete_job(UUID(statement_id), "EXTRACT_FS", result_data=result_data)

            if response.get('success'):
                logger.info(f"Job completado exitosamente: {statement_id}")
            else:
                logger.error(f"Error completando job: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en statement_id '{statement_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado completando job para statement_id '{statement_id}': {e}")

    def _job_retry(self, statement_id: str, current_retries: int = 0):
        """Incrementa el contador de reintentos del job"""
        try:
            logger.info(f"Incrementando reintento para statement_id: {statement_id}, intento: {current_retries + 1}")

            response = self.job_service.increment_retry(
                resource_id=UUID(statement_id),
                job_type="EXTRACT_FS",
                current_retry_count=current_retries
            )

            if response.get('success'):
                logger.info(f"Reintento incrementado exitosamente: {statement_id}")
            else:
                logger.error(f"Error incrementando reintento: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en statement_id '{statement_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado incrementando reintento para statement_id '{statement_id}': {e}")

    def _job_failed(self, statement_id: str, msg_error: str = "", should_retry: bool = False,  result_data: Dict[str, Any] = None):
        """Marca un job como fallido"""
        try:
            logger.info(f"Marcando job como fallido: {statement_id}, retry={should_retry}")

            if msg_error:
                logger.warning(f"Error reportado: {msg_error}")

            response = self.job_service.fail_job(
                resource_id=UUID(statement_id),
                job_type="EXTRACT_FS",
                error_message=msg_error,
                should_retry=should_retry,
                result_data=result_data
            )

            if response.get('success'):
                logger.info(f"Job marcado como fallido: {statement_id}")
            else:
                logger.error(f"Error marcando job como fallido: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en statement_id '{statement_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado marcando job como fallido para statement_id '{statement_id}': {e}")

    def _extract_and_normalize_data(self, event: List[dict]) -> List[dict]:
        """Extrae y normaliza datos del evento con tolerancia a errores"""
        normalized = []

        for ev_idx, ev in enumerate(event):
            try:
                data = ev.get("data", [])
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            normalized.append(item)
                        elif isinstance(item, list):
                            normalized.extend([i for i in item if isinstance(i, dict)])
                elif isinstance(data, dict):
                    normalized.append(data)

            except Exception as e:
                self._log_warning(f"Error extrayendo datos del evento {ev_idx}: {e}")

        return normalized

    def _merge_raw_datapoints(self, normalized: List[dict]) -> List[dict]:
        """
        Merge puro de datapoints duplicados antes del procesamiento.
        Consolida por (year, period, name) sumando valores y combinando details.
        """
        logger.info(f"Iniciando merge de {len(normalized)} datapoints")

        merge_dict = {}
        duplicates_found = 0

        for idx, dp in enumerate(normalized):
            try:
                year = dp.get("year")
                period = dp.get("period", "")
                name = dp.get("name", "").strip()

                if not name:
                    self._log_warning(f"Datapoint {idx} sin nombre, saltando")
                    continue

                # Clave de merge
                key = (year, period, name)

                if key in merge_dict:
                    # Duplicado encontrado - mergear
                    existing = merge_dict[key]
                    duplicates_found += 1

                    # Sumar valores
                    existing_value = self._validate_and_convert_numeric(existing.get("value"), "existing")
                    new_value = self._validate_and_convert_numeric(dp.get("value"), "new")
                    existing["value"] = existing_value + new_value

                    # Combinar details
                    existing_details = existing.get("details", [])
                    new_details = dp.get("details", [])

                    if not isinstance(existing_details, list):
                        existing_details = []
                    if not isinstance(new_details, list):
                        new_details = []

                    existing["details"] = existing_details + new_details

                else:
                    # Primer datapoint con esta clave
                    merge_dict[key] = dp.copy()

            except Exception as e:
                self._log_warning(f"Error en merge datapoint {idx}: {e}")
                continue

        merged_list = list(merge_dict.values())

        logger.info(
            f"Merge completado - Original: {len(normalized)}, Final: {len(merged_list)}, Duplicados mergeados: {duplicates_found}")

        return merged_list

    def _process_all_datapoints(self, normalized: List[dict], account_mapping: Dict[str, Dict[str, Any]],
                                statement_id: str, draft: Any, is_annual: bool) -> Dict[str, Any]:
        """
        Procesa todos los datapoints con merge inicial y deduplicación post-procesamiento.
        """
        try:
            # PASO 1: Merge de datos raw duplicados
            merged_normalized = self._merge_raw_datapoints(normalized)

            raw_bulk = []
            years: Set[int] = set(self._safe_get_value(draft, 'years', []) or [])
            periods: Set[str] = set(self._safe_get_value(draft, 'periods', []) or [])
            taxes_data = {}

            # PASO 2: Set para deduplicación post-procesamiento
            # (evita duplicados que surgen durante _process_single_item)
            processed_keys = set()

            # PASO 3: Procesar cada elemento
            for idx, item in enumerate(merged_normalized):
                try:
                    result = self._process_single_item(
                        item, account_mapping, statement_id, is_annual, idx
                    )

                    if result:
                        # Clave post-procesamiento para evitar duplicados
                        post_process_key = (
                            result.get("year"),
                            result.get("period"),
                            result.get("account_id")
                        )

                        if post_process_key in processed_keys:
                            self._log_warning(f"Duplicado post-procesamiento detectado: {post_process_key}")
                            if self._processing_stats:
                                self._processing_stats.skipped_items += 1
                            continue

                        # Marcar como procesado
                        processed_keys.add(post_process_key)

                        if result["is_taxes"]:
                            taxes_data[result["key"]] = result["datapoint"]
                        else:
                            raw_bulk.append(result["datapoint"])
                            if self._processing_stats:
                                self._processing_stats.processed_items += 1

                        if result["year"]:
                            years.add(result["year"])
                        if result["period"]:
                            periods.add(result["period"])

                except Exception as e:
                    self._log_warning(f"Error procesando item {idx}: {e}")
                    if self._processing_stats:
                        self._processing_stats.skipped_items += 1

            # PASO 4: Calcular y agregar MAI
            mai_values = self._calculate_mai_values(merged_normalized, account_mapping)
            if mai_values:
                mai_datapoints = self._create_mai_datapoints(mai_values, account_mapping, statement_id)
                raw_bulk.extend(mai_datapoints)

            # PASO 5: Procesar TAXES con ajuste MAI
            if taxes_data:
                processed_taxes = self._process_taxes_with_mai_adjustment(taxes_data, mai_values)
                raw_bulk.extend(processed_taxes)

            logger.info(
                f"Procesamiento final - Merged: {len(merged_normalized)}, Procesados únicos: {len(processed_keys)}, Total datapoints: {len(raw_bulk)}")

            return {
                "success": True,
                "datapoints": raw_bulk,
                "years": sorted(years),
                "periods": sorted(periods),
                "mai_count": len(mai_values),
                "taxes_count": len(taxes_data)
            }

        except Exception as e:
            self._log_error("Error en procesamiento de datapoints", e)
            return {
                "success": False,
                "error": str(e),
                "datapoints": [],
                "years": [],
                "periods": []
            }


    # def _process_all_datapoints(self, normalized: List[dict], account_mapping: Dict[str, Dict[str, Any]],
    #                             statement_id: str, draft: Any, is_annual: bool) -> Dict[str, Any]:
    #     """Procesa todos los datapoints con continuidad ante errores"""
    #     try:
    #         raw_bulk = []
    #         years: Set[int] = set(self._safe_get_value(draft, 'years', []) or [])
    #         periods: Set[str] = set(self._safe_get_value(draft, 'periods', []) or [])
    #         taxes_data = {}
    #
    #         set_exist = {}
    #
    #         # Procesar cada elemento
    #         for idx, item in enumerate(normalized):
    #             try:
    #                 result = self._process_single_item(
    #                     item, account_mapping, statement_id, is_annual, idx
    #                 )
    #
    #                 if result:
    #                     key = (result.get("year"), result.get("period"), result.get("account_id"))
    #                     if key  in set_exist:
    #                         continue
    #                     else:
    #                         set_exist[key] = True
    #
    #                     if result["is_taxes"]:
    #                         taxes_data[result["key"]] = result["datapoint"]
    #                     else:
    #                         raw_bulk.append(result["datapoint"])
    #                         if self._processing_stats:
    #                             self._processing_stats.processed_items += 1
    #
    #                     if result["year"]:
    #                         years.add(result["year"])
    #                     if result["period"]:
    #                         periods.add(result["period"])
    #
    #             except Exception as e:
    #                 self._log_warning(f"Error procesando item {idx}: {e}")
    #                 if self._processing_stats:
    #                     self._processing_stats.skipped_items += 1
    #
    #         # Calcular y agregar MAI
    #         mai_values = self._calculate_mai_values(normalized, account_mapping)
    #         if mai_values:
    #             mai_datapoints = self._create_mai_datapoints(mai_values, account_mapping, statement_id)
    #             raw_bulk.extend(mai_datapoints)
    #
    #         # Procesar TAXES con ajuste MAI
    #         if taxes_data:
    #             processed_taxes = self._process_taxes_with_mai_adjustment(taxes_data, mai_values)
    #             raw_bulk.extend(processed_taxes)
    #
    #         return {
    #             "success": True,
    #             "datapoints": raw_bulk,
    #             "years": sorted(years),
    #             "periods": sorted(periods),
    #             "mai_count": len(mai_values),
    #             "taxes_count": len(taxes_data)
    #         }
    #
    #     except Exception as e:
    #         self._log_error("Error en procesamiento de datapoints", e)
    #         return {
    #             "success": False,
    #             "error": str(e),
    #             "datapoints": [],
    #             "years": [],
    #             "periods": []
    #         }

    def _process_single_item(self, item: dict, account_mapping: Dict[str, Dict[str, Any]],
                             statement_id: str, is_annual: bool, idx: int) -> Optional[Dict[str, Any]]:
        """Procesa un elemento individual con validación completa"""
        try:
            name = item.get("name")
            if not name:
                self._log_warning(f"Item {idx} sin nombre")
                return None

            account_info = account_mapping.get(name)
            if not account_info:
                self._log_warning(f"Cuenta '{name}' no mapeada (item {idx})")
                return None

            acc_id = account_info.get("id")
            acc_type = account_info.get("type")

            if not acc_id or not acc_type:
                self._log_warning(f"Cuenta '{name}' incompleta (item {idx})")
                return None

            year = self._validate_year(item.get("year"), f"cuenta '{name}'")
            if not year:
                return None

            # Normalizar período
            raw_period = item.get("period")
            period = self._normalize_period(raw_period, acc_type, is_annual)

            if not period and is_annual:
                period = str(year)

            # Preparar datapoint
            value = self._validate_and_convert_numeric(item.get("value"), f"cuenta '{name}'")
            details = json.dumps(item.get("details", []))

            datapoint = {
                "value": value,
                "details": details,
                "_catalog_extract_id": str(acc_id),
                "financial_statement_id": statement_id,
                "year": year,
                "period": period
            }

            # Agregar tags al item para cálculo de MAI
            item["tags"] = account_info.get("tags", [])

            return {
                "datapoint": datapoint,
                "is_taxes": name == "TAXES",
                "key": (year, period or str(year)),
                "account_id": acc_id,
                "year": year,
                "period": period
            }

        except Exception as e:
            self._log_warning(f"Error procesando item {idx}: {e}")
            return None

    def _bulk_insert_datapoints(self, datapoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert de datapoints con conflicto por account_extract_id."""
        if not datapoints:
            return {"success": False, "error": "No hay datapoints para insertar"}

        try:
            logger.info(f"Upsert de {len(datapoints)} datapoints")
            self.financial_datapoint_repository.upsert_many(
                datapoints,
                conflict_columns=self.DATAPOINT_UPSERT_CONFLICT_COLUMNS,
            )

            if self._processing_stats:
                self._processing_stats.total_inserted = len(datapoints)

            return {"success": True, "inserted": len(datapoints)}

        except Exception as e:
            self._log_error(f"Error en upsert masivo", e)

            # Intentar inserción por lotes más pequeños
            try:
                batch_size = 100
                inserted = 0

                for i in range(0, len(datapoints), batch_size):
                    batch = datapoints[i:i + batch_size]
                    try:
                        self.financial_datapoint_repository.upsert_many(
                            batch,
                            conflict_columns=self.DATAPOINT_UPSERT_CONFLICT_COLUMNS,
                        )
                        inserted += len(batch)
                    except Exception as batch_error:
                        self._log_error(f"Error en upsert lote {i // batch_size}", batch_error)

                if inserted > 0:
                    if self._processing_stats:
                        self._processing_stats.total_inserted = inserted
                    return {"success": True, "inserted": inserted, "partial": True}

            except Exception as retry_error:
                self._log_error("Error en reintentos de upsert", retry_error)

            return {"success": False, "error": str(e)}

    def _update_financial_statement(self, statement_id: str, draft: Any,
                                    years: List[int], periods: List[str]) -> Dict[str, Any]:
        """Actualiza el financial statement con manejo de errores"""
        try:
            updates = {
                "years": years,
                "periods": periods,
                "status": "COMPLETE"
            }

            self.financial_statement_repository.update(statement_id, updates)
            logger.info(f"Statement actualizado - Años: {years}, Períodos: {periods}")

            # Notificar vía WebSocket cuando el estado cambia a COMPLETE
            try:
                updated_at = datetime.datetime.now(timezone.utc).isoformat()
                
                message = {
                    "event": "draft:updated",
                    "draft_id": statement_id,
                    "status": "COMPLETE",
                    "updated_at": updated_at
                }
                
                # Agregar doc_type si está disponible en el draft
                if draft and hasattr(draft, 'doc_type') and draft.doc_type:
                    message["doc_type"] = draft.doc_type
                
                # Agregar statement_periodicity si está disponible en el draft
                if draft and hasattr(draft, 'statement_periodicity') and draft.statement_periodicity:
                    message["statement_periodicity"] = draft.statement_periodicity
                
                # Notificar a los que están viendo este draft específico
                notify_watching(
                    watch_type="draft",
                    watch_id=statement_id,
                    message=message
                )
                # También notificar a los que están viendo la lista de drafts
                notify_watching(
                    watch_type="draft",
                    watch_id=None,  # Notifica a los que ven la lista (sin id específico)
                    message=message
                )
                logger.info(f"Notificación WebSocket enviada para draft actualizado: {statement_id} - Status: COMPLETE")
            except Exception as ws_error:
                logger.warning(f"Error enviando notificación WebSocket (no crítico): {ws_error}")

            return {"success": True, "years": years, "periods": periods}

        except Exception as e:
            self._log_error("Error actualizando financial statement", e)
            return {"success": False, "error": str(e)}

    def _update_statement_status(self, statement_id: str, status: str):
        """Actualiza solo el estado del statement"""
        try:
            self.financial_statement_repository.update(statement_id, {"status": status})
            logger.info(f"Statement {statement_id} marcado como {status}")
            
            # Notificar vía WebSocket cuando el estado cambia a FAILED
            if status == "FAILED":
                try:
                    # Obtener el draft para incluir doc_type y statement_periodicity si están disponibles
                    draft = None
                    try:
                        draft = self.financial_statement_repository.find_by_id(statement_id)
                    except Exception:
                        pass  # Si no se puede obtener, continuar sin esos campos
                    
                    updated_at = datetime.datetime.now(timezone.utc).isoformat()
                    
                    message = {
                        "event": "draft:updated",
                        "draft_id": statement_id,
                        "status": "FAILED",
                        "updated_at": updated_at
                    }
                    
                    # Agregar doc_type si está disponible en el draft
                    if draft and hasattr(draft, 'doc_type') and draft.doc_type:
                        message["doc_type"] = draft.doc_type
                    
                    # Agregar statement_periodicity si está disponible en el draft
                    if draft and hasattr(draft, 'statement_periodicity') and draft.statement_periodicity:
                        message["statement_periodicity"] = draft.statement_periodicity
                    
                    # Notificar a los que están viendo este draft específico
                    notify_watching(
                        watch_type="draft",
                        watch_id=statement_id,
                        message=message
                    )
                    # También notificar a los que están viendo la lista de drafts
                    notify_watching(
                        watch_type="draft",
                        watch_id=None,  # Notifica a los que ven la lista (sin id específico)
                        message=message
                    )
                    logger.info(f"Notificación WebSocket enviada para draft actualizado: {statement_id} - Status: FAILED")
                except Exception as ws_error:
                    logger.warning(f"Error enviando notificación WebSocket (no crítico): {ws_error}")
                    
        except Exception as e:
            self._log_error(f"Error actualizando estado a {status}", e)

    # ================================================================
    # ================ Métodos de Respuesta Mejorados ===============
    # ================================================================

    def _create_error_response(self, status_code: int, error: str,
                               statement_id: Optional[str], request_id: Optional[str]) -> dict:
        """Crea una respuesta de error estructurada"""
        logger.error(f"Respuesta de error {status_code}: {error}")

        response_body = {
            "error": error,
            "statement_id": statement_id or "N/A",
            "request_id": request_id or "N/A",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        if self._processing_stats and self._processing_stats.errors:
            response_body["error_details"] = self._processing_stats.errors[:10]  # Limitar a 10 errores
            response_body["warnings"] = self._processing_stats.warnings[:10]  # Limitar a 10 warnings

        self._job_failed(statement_id, error)

        return {
            "statusCode": status_code,
            "body": json.dumps(response_body)
        }

    def _create_success_response(self, processing_result: dict, update_result: dict,
                                 statement_id: str, request_id: Optional[str],
                                 stats: ProcessingStats) -> dict:
        """Crea una respuesta exitosa con estadísticas completas"""
        logger.info("=" * 60)
        logger.info("PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        logger.info(f"Total insertados: {stats.total_inserted if stats else 0}")
        logger.info("=" * 60)

        response_body = {
            "message": "Procesamiento completado exitosamente",
            "statement_id": statement_id,
            "request_id": request_id or "N/A",
            "years": processing_result.get("years", []),
            "periods": processing_result.get("periods", []),
            "statistics": {
                "datapoints_inserted": stats.total_inserted if stats else 0,
                "items_processed": stats.processed_items if stats else 0,
                "items_skipped": stats.skipped_items if stats else 0,
                "items_with_errors": stats.error_items if stats else 0,
                "mai_datapoints": processing_result.get("mai_count", 0),
                "taxes_datapoints": processing_result.get("taxes_count", 0)
            },
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "statement_updated": update_result.get("success", False)
        }

        # Agregar warnings si existen (limitadas)
        if stats and stats.warnings:
            response_body["warnings"] = stats.warnings[:5]  # Solo primeras 5 warnings
            response_body["total_warnings"] = len(stats.warnings)

        # Agregar errores no críticos si existen
        if stats and stats.errors:
            response_body["non_critical_errors"] = stats.errors[:5]  # Solo primeros 5 errores
            response_body["total_errors"] = len(stats.errors)

        self._job_complete(statement_id, response_body)

        return {
            "statusCode": 200,
            "body": json.dumps(response_body)
        }

    def _create_partial_success_response(self, insertion_result: dict, statement_id: str,
                                         request_id: Optional[str], stats: ProcessingStats) -> dict:
        """Crea una respuesta de éxito parcial cuando hay algunos errores"""
        logger.warning("Procesamiento completado con errores parciales")

        response_body = {
            "message": "Procesamiento completado con algunos errores",
            "statement_id": statement_id,
            "request_id": request_id or "N/A",
            "partial_success": True,
            "datapoints_inserted": insertion_result.get("inserted", 0),
            "statistics": {
                "items_processed": stats.processed_items if stats else 0,
                "items_skipped": stats.skipped_items if stats else 0,
                "items_with_errors": stats.error_items if stats else 0
            },
            "timestamp": datetime.datetime.utcnow().isoformat()
        }



        if stats and stats.errors:
            response_body["errors"] = stats.errors[:10]

        self._job_complete(statement_id, response_body)
        self._job_failed(statement_id,msg_error="Procesamiento completado con algunos errores",should_retry=False,result_data=response_body)


        return {
            "statusCode": 207,  # Multi-Status para indicar éxito parcial
            "body": json.dumps(response_body)
        }

    def process_cashflow_data(self, event: dict) -> dict:
        """
        Procesa y guarda datos de Cash Flow (CF) en financial_cashflow_datapoints
        """
        try:
            if not isinstance(event, dict):
                return self._create_error_response(400, "El evento debe ser un diccionario", None, None)
            
            data = event.get("data", [])
            statement_id = event.get("statement_id")
            request_id = event.get("request_id")
            
            if not data or not isinstance(data, list):
                return self._create_error_response(400, "El campo 'data' debe ser una lista", statement_id, request_id)
            
            if not statement_id:
                return self._create_error_response(400, "El campo 'statement_id' es requerido", None, request_id)
            
            # Validar que el financial statement exista
            draft = self.financial_statement_repository.find_by_id(statement_id)
            if not draft:
                return self._create_error_response(404, f"Financial statement {statement_id} no encontrado", 
                                                   statement_id, request_id)
            
            # Preparar datos para insertar
            datapoints_to_insert = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                # Validar campos requeridos
                if not item.get("name") or item.get("value") is None:
                    logger.warning(f"Item inválido omitido: {item}")
                    continue
                
                details_value = item.get("details", [])
                # Convertir details a Json de psycopg2 si es lista o dict
                if isinstance(details_value, (list, dict)):
                    details_json = PsycopgJson(details_value)
                else:
                    details_json = details_value
                
                datapoints_to_insert.append({
                    "name": item.get("name"),
                    "value": float(item.get("value", 0)),
                    "year": item.get("year"),
                    "period": item.get("period"),
                    "details": details_json
                })
            
            if not datapoints_to_insert:
                return self._create_error_response(400, "No hay datos válidos para insertar", 
                                                   statement_id, request_id)
            
            # Guardar en la base de datos usando ON CONFLICT DO UPDATE
            
            
            inserted_count = 0
            conn = DatabaseSingletonConnection.get_connection()
            try:
                with conn.cursor() as cursor:
                    columns = ['name', 'value', 'financial_statement_id', 'details', 'year', 'period']
                    columns_str = ', '.join(columns)
                    
                    # Construir la parte de UPDATE para ON CONFLICT
                    # Nota: No hay constraint único definido en la tabla, pero podemos usar ON CONFLICT
                    # Por ahora, si hay duplicados, los actualizamos
                    update_columns = ['value', 'details', 'updated_at']
                    update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
                    
                    # Usar una constraint única basada en (financial_statement_id, name, year, period)
                    # Si no existe, usamos INSERT con manejo de errores
                    query = f"""
                        INSERT INTO financial_cashflow_datapoints ({columns_str}, updated_at)
                        VALUES %s
                        ON CONFLICT (financial_statement_id, name, year, period)
                        DO UPDATE SET {update_set}
                    """
                    
                    values_list = [
                        (
                            item['name'],
                            item['value'],
                            statement_id,
                            item['details'],
                            item.get('year'),
                            item.get('period'),
                            datetime.datetime.utcnow()
                        )
                        for item in datapoints_to_insert
                    ]
                    
                    execute_values(cursor, query, values_list)
                    conn.commit()
                    inserted_count = cursor.rowcount
                    
                    logger.info(f"Guardados {inserted_count} cashflow datapoints para statement {statement_id}")
                    
            except Exception as db_error:
                conn.rollback()
                # Si falla por constraint, intentar sin ON CONFLICT (si la constraint no existe)
                if "constraint" in str(db_error).lower():
                    logger.warning(f"Constraint no encontrado, intentando INSERT simple: {db_error}")
                    try:
                        cf_repository = FinancialCashflowDatapointRepository()
                        inserted_count = cf_repository.bulk_create_for_statement(statement_id, datapoints_to_insert)
                        logger.info(f"Guardados {inserted_count} cashflow datapoints (sin ON CONFLICT)")
                    except Exception as e2:
                        logger.error(f"Error al insertar CF datapoints: {e2}")
                        return self._create_error_response(500, f"Error guardando cashflow data: {str(e2)}", 
                                                          statement_id, request_id)
                else:
                    logger.error(f"Error en base de datos: {db_error}")
                    return self._create_error_response(500, f"Error guardando cashflow data: {str(db_error)}", 
                                                      statement_id, request_id)
            # No cerramos la conexión porque DatabaseSingletonConnection maneja la conexión singleton
            
            # Retornar respuesta exitosa
            response_body = {
                "message": f"Se guardaron {inserted_count} cashflow datapoints exitosamente",
                "statement_id": statement_id,
                "request_id": request_id or "N/A",
                "count": inserted_count,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            
            return {
                "statusCode": 200,
                "body": json.dumps(response_body)
            }
            
        except Exception as e:
            self._log_error("Error procesando datos de flujo de caja", e)
            return self._create_error_response(500, f"Error procesando cashflow data: {str(e)}", 
                                              event.get("statement_id") if isinstance(event, dict) else None,
                                              event.get("request_id") if isinstance(event, dict) else None)