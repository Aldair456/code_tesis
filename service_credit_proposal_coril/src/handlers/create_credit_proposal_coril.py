"""
Handler Lambda para generar PDF/Word de una propuesta de crédito coril existente.
Recibe credit_memo_id (ya creado previamente) y proposal_data para generar los documentos.
Por defecto el memo usa un título por defecto si no se envía report_title/reportTitle
(ver credit_memo_builder_service.build_from_event → report_title = ... "ALFIN BANCO | INFORME DE RIESGOS").
"""
import logging
import json
from typing import Dict, Any
from common.exceptions.exceptions import BadRequestError, NotFoundError
from services.service_credit_proposal_coril.src.config.dependencies import get_credit_proposal_coril_service
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_fallido

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_coril_service = get_credit_proposal_coril_service()


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda para generar PDF/Word de una propuesta de crédito coril existente.
    
    Invocación desde Step Function: recibe body_for_create con credit_memo_id.
    
    Input esperado:
    {
        "credit_memo_id": "uuid-de-la-propuesta-existente",  # REQUERIDO
        "business_id": "...",
        "proposal_data": { ... },  # Contenido generado por análisis
        "user_id": "uuid-del-usuario",
        "deal_id": "uuid-del-deal",
        "total_amount": ...,
        "currency": "USD"
    }
    
    Output: resultado de la generación del PDF/Word con URL de descarga.
    """
    request_id = getattr(context, "aws_request_id", "unknown") if context else "unknown"
    logger.info("Inicio generación PDF/Word propuesta coril - Request ID: %s", request_id)

    credit_memo_id = None
    business_id = None
    
    try:
        # Validar que el credit memo _id 
        credit_memo_id = event.get("credit_memo_id")
        if not credit_memo_id:
            raise BadRequestError("credit_memo_id es requerido.")
        
        business_id = event.get("business_id")
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        
        proposal_data = event.get("proposal_data")
        if not proposal_data:
            raise BadRequestError("proposal_data es requerido.")

        total_amount = event.get("total_amount")
        currency = event.get("currency", "USD")

        logger.info("Generando documentos para credit_memo_id: %s, business_id: %s", credit_memo_id, business_id)


        # Generar PDF/Word y actualizar la propuesta (el servicio actualiza status en BD)
        result = credit_proposal_coril_service.generate_documents_for_proposal(
            proposal_id=credit_memo_id,
            proposal_data=proposal_data,
            total_amount=total_amount,
            currency=currency,
        )

        logger.info("Documentos generados exitosamente para credit_memo_id: %s - Request ID: %s", credit_memo_id, request_id)

        return {
            "success": True,
            "message": "Documentos de propuesta de crédito generados exitosamente",
            "data": {
                "credit_memo_id": credit_memo_id,
                **result
            },
            "request_id": request_id,
        }

    except BadRequestError:
        raise
    except NotFoundError:
        raise
    except Exception as err:
        logger.error(
            "Error en lambda_handler: %s - Request ID: %s", err, request_id, exc_info=True
        )
        # Notificar FALLIDO (si tenemos credit_memo_id para reportar)
        if credit_memo_id:
            notify_fallido(f"Error al generar memo: {str(err)}", credit_memo_id)
        raise
"""
if __name__ == "__main__":
  # El JSON a veces viene guardado como UTF-16 en Windows; 0xff al inicio = UTF-16 LE
  with open("debug_payload.json", "rb") as f:
    raw = f.read()
  if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
    text = raw.decode("utf-16")
  else:
    text = raw.decode("utf-8")
  evento_2 = json.loads(text)
  print("json load")

  result = lambda_handler(evento_2, None)
  print("\nResultado S3 keys:")
  if "data" in result and "s3" in result["data"]:
      print(json.dumps(result["data"]["s3"], indent=2))
  else:
      print("No se encontró data.s3 en el resultado")
  
  print("\nResultado Completo:")
  print(json.dumps(result, indent=2, ensure_ascii=False))
"""