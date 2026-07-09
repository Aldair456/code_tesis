import logging
import json
from typing import Dict, Any
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError, NotFoundError
from services.service_credit_proposal_coril.src.config.dependencies import get_business_analysis_service
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_en_progreso, notify_fallido

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

business_analysis_service = get_business_analysis_service()


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda para analizar solo el sector económico. Invocado desde Step Function.
    Event: business_id (requerido), credit_memo_id (opcional).
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio análisis de sector económico - Request ID: %s", request_id)

    try:
        business_id = event.get("business_id")
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        credit_memo_id = event.get("credit_memo_id")
        user_id = (event.get("user") or {}).get("sub") or "system"

        logger.info("Analizando sector económico del business_id: %s", business_id)
        notify_en_progreso("Analizando sector económico", credit_memo_id)

        if not business_analysis_service.is_available():
            raise BadRequestError("Servicio de análisis no disponible.")

        result = business_analysis_service.analyze_sector_only(business_id)

        return {
            "business_id": business_id,
            "analysis": {
                "sector_economico": {
                    "contenido": result["sector_analysis"],
                    "caracteres": result["caracteres"],
                },
            },
            "metadata": {
                "analizado_por": user_id,
                "servicio": business_analysis_service.get_service_info(),
                "request_id": request_id,
            },
            "request_id": request_id,
        }
    except (BadRequestError, NotFoundError):
        raise
    except Exception as err:
        logger.error("Error en lambda_handler análisis sector económico: %s - Request ID: %s", err, request_id, exc_info=True)
        if "business_id" in locals() and business_id:
            notify_fallido("Error en análisis sector económico: %s" % err, credit_memo_id if "credit_memo_id" in locals() else None)
        return handle_exception(err, request_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    event = {"business_id": "38690970-2252-4f74-8c3b-cc14adf16a13"}
    
    print("\n=== INICIANDO PRUEBA DE HANDLER SECTOR ECONÓMICO ===")
    print(f"API Key disponible: {'SÍ' if business_analysis_service.is_available() else 'NO'}")
    print(f"Info servicio: {business_analysis_service.get_service_info()}")
    
    print("\nEjecutando lambda_handler de análisis de sector económico...\n")
    result = lambda_handler(event, None)
    print("\n=== RESULTADO ===")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))

