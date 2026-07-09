"""
Lambda para analizar rentabilidad y generación de caja de un negocio. Invocado desde Step Function.
"""
import logging
import json
from typing import Dict, Any

from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError, NotFoundError
from services.service_credit_proposal_coril.src.config.dependencies import get_financial_analysis_service
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_en_progreso, notify_fallido

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

financial_analysis_service = get_financial_analysis_service()


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Invocado desde Step Function. Event: business_id (requerido), credit_memo_id (opcional).
    Retorna { business_id, analysis: { rentabilidad, generacion_caja }, metadata, request_id }.
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio análisis financiero - Request ID: %s", request_id)

    try:
        business_id = event.get("business_id")
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        credit_memo_id = event.get("credit_memo_id")
        user_id = (event.get("user") or {}).get("sub") or "system"

        notify_en_progreso("Analizando rentabilidad y generación de caja", credit_memo_id)

        if not financial_analysis_service.is_available():
            raise BadRequestError("Servicio de análisis financiero no disponible.")

        result = financial_analysis_service.analyze_financial_by_business_id(business_id)

        return {
            "business_id": business_id,
            "analysis": {
                "rentabilidad": {
                    "contenido": result.profitability_analysis,
                    "caracteres": len(result.profitability_analysis),
                },
                "generacion_caja": {
                    "contenido": result.cash_generation_analysis,
                    "caracteres": len(result.cash_generation_analysis),
                },
            },
            "metadata": {
                "analizado_por": user_id,
                "servicio": financial_analysis_service.get_service_info(),
                "request_id": request_id,
            },
            "request_id": request_id,
        }
    except (BadRequestError, NotFoundError):
        raise
    except Exception as err:
        logger.error("Error en analyze_financial_handler: %s - Request ID: %s", err, request_id, exc_info=True)
        if "business_id" in locals() and business_id:
            notify_fallido("Error en análisis financiero: %s" % err, credit_memo_id if "credit_memo_id" in locals() else None)
        return handle_exception(err, request_id)


if __name__ == "__main__":
    ev = {"business_id": "833bb9fa-9213-46b7-b0f8-f170b8aa1023"}
    print(json.dumps(lambda_handler(ev, None), indent=2, ensure_ascii=False))
