import json
import logging
from typing import Any, Dict

from models.model_1V2.src.config.dependencies import create_financial_statement_ia_service
from models.model_1V2.src.schemas.extract_pl_request import ExtractPlRequest

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_MAX_RETRIES = 3

service = create_financial_statement_ia_service()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio de procesamiento PL (model_1V2)")

    try:
        try:
            dto = ExtractPlRequest.from_direct_payload(event)
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
            msg = "No había datos de tablas ni de años para 'pl'; se omitió el procesamiento."
            logger.warning(msg)
            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "message": msg,
                **dto.base_response_fields,
            }

        if not dto.tables:
            msg = "No se encontraron tablas para 'pl'; no se puede generar JSON."
            logger.error(msg)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,
                **dto.base_response_fields,
            }

        if not dto.years:
            logger.warning("No se encontraron años para 'pl'; el JSON puede estar incompleto.")

        try:
            result = service.generate_accounts_pl_with_retries(
                tables_text=dto.tables,
                year_list=dto.years,
                job_id=dto.job_id,
            )
            logger.info("JSON de PL generado correctamente")
            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "data": result,
                **dto.base_response_fields,
            }
        except Exception as err:
            logger.error("Error al intentar extraer la cuenta PL con reintentos: %s", err)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": f"Agotados {_MAX_RETRIES} intentos: {err}",
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