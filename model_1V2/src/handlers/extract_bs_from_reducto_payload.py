import json
import logging
from typing import Any, Dict

from models.model_1V2.src.config.dependencies import create_financial_statement_ia_service
from models.model_1V2.src.schemas.extract_bs_request import ExtractBsRequest

logger = logging.getLogger()
logger.setLevel(logging.INFO)

service = create_financial_statement_ia_service()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio de procesamiento BS (model_1V2)")

    try:
        try:
            dto = ExtractBsRequest.from_direct_payload(event)
        except ValueError as e:
            msg = f"Payload inválido: {e}"
            logger.error(msg)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,
            }

        if not dto.tables and not dto.years:
            msg = "No había datos de tablas ni de años para 'bs'; se omitió el procesamiento."
            logger.warning(msg)
            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "message": msg,
                **dto.base_response_fields,
            }

        if not dto.tables:
            msg = "No se encontraron tablas para 'bs'; no se puede generar JSON."
            logger.error(msg)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,
                **dto.base_response_fields,
            }

        if not dto.years:
            logger.warning("No se encontraron años para 'bs'; el JSON puede estar incompleto.")

        result = service.generate_accounts_bs_with_retries(
            tables_text=dto.tables,
            year_list=dto.years,
            job_id=dto.job_id,
        )
        logger.info("JSON de BS generado correctamente")
        return {
            "statusCode": 200,
            "status": "ok",
            "request_id": request_id,
            "data": result,
            **dto.base_response_fields,
        }

    except Exception as e:
        msg = f"Excepción no controlada: {e}"
        logger.exception(msg)
        return {
            "statusCode": 200,
            "status": "error",
            "request_id": request_id,
            "error": msg,
        }