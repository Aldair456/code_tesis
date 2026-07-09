import logging
import json
from typing import Dict, Any
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError, NotFoundError
from services.service_credit_proposal_coril.src.config.dependencies import get_solvency_liquidity_service
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_en_progreso, notify_fallido

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

solvency_liquidity_service = get_solvency_liquidity_service()


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda para analizar solvencia y liquidez. Invocado desde Step Function.
    Event: business_id (requerido), credit_memo_id (opcional).
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio análisis de solvencia y liquidez - Request ID: %s", request_id)

    try:
        business_id = event.get("business_id")
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        credit_memo_id = event.get("credit_memo_id")
        user_id = (event.get("user") or {}).get("sub") or "system"

        logger.info("Analizando solvencia y liquidez del business_id: %s", business_id)
        notify_en_progreso("Analizando solvencia y liquidez", credit_memo_id)

        if not solvency_liquidity_service.is_available():
            raise BadRequestError("Servicio de análisis de solvencia y liquidez no disponible.")

        result = solvency_liquidity_service.analyze_solvency_liquidity_by_business_id(business_id)

        return {
            "business_id": business_id,
            "analysis": {
                "solvencia": {
                    "contenido": result.solvency_analysis,
                    "caracteres": len(result.solvency_analysis),
                },
                "liquidez": {
                    "contenido": result.liquidity_analysis,
                    "caracteres": len(result.liquidity_analysis),
                },
            },
            "metadata": {
                "analizado_por": user_id,
                "servicio": solvency_liquidity_service.get_service_info(),
                "request_id": request_id,
            },
            "request_id": request_id,
        }
    except (BadRequestError, NotFoundError):
        raise
    except Exception as err:
        logger.error("Error en lambda_handler: %s - Request ID: %s", err, request_id, exc_info=True)
        if "business_id" in locals() and business_id:
            notify_fallido("Error en análisis solvencia/liquidez: %s" % err, credit_memo_id if "credit_memo_id" in locals() else None)
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event = {"business_id": "833bb9fa-9213-46b7-b0f8-f170b8aa1023"}
    
    print("\n=== INICIANDO PRUEBA DE HANDLER DE SOLVENCIA Y LIQUIDEZ ===")
    print(f"API Key disponible: {'SÍ' if solvency_liquidity_service.is_available() else 'NO'}")
    print(f"Info servicio: {solvency_liquidity_service.get_service_info()}")
    
    print("\nEjecutando lambda_handler de análisis de solvencia y liquidez...\n")
    result = lambda_handler(event, None)
    print("\n=== RESULTADO ===")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))

