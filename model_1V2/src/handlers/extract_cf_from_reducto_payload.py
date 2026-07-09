import json
import logging
from typing import Any, Dict

from models.model_1V2.src.config.dependencies import create_financial_statement_ia_service
from models.model_1V2.src.schemas.extract_cf_request import ExtractCfRequest

logger = logging.getLogger()
logger.setLevel(logging.INFO)

service = create_financial_statement_ia_service()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio de procesamiento CF (model_1V2)")

    try:
        try:
            dto = ExtractCfRequest.from_direct_payload(event)
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
            msg = "No había datos de tablas ni de años para 'CF'; se omitió el procesamiento."
            logger.warning(msg)
            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "message": msg,
                **dto.base_response_fields,
            }

        if not dto.tables:
            msg = "No se encontraron tablas para 'CF'; no se puede generar JSON."
            logger.error(msg)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": msg,
                **dto.base_response_fields,
            }

        if not dto.years:
            logger.warning("No se encontraron años para 'CF'; el JSON puede estar incompleto.")

        try:
            result = service.generate_accounts_cf_main_with_retries(
                tables_text=dto.tables,
                year_list=dto.years,
                job_id=dto.job_id,
            )
            logger.info(
                "JSON de CF generado correctamente. Total de elementos: %s",
                len(result) if hasattr(result, "__len__") else "n/a",
            )
            return {
                "statusCode": 200,
                "status": "ok",
                "request_id": request_id,
                "data": result,
                **dto.base_response_fields,
            }
        except Exception as err:
            logger.error("Error al extraer flujos de CF: %s", err)
            return {
                "statusCode": 200,
                "status": "error",
                "request_id": request_id,
                "error": f"Error al extraer flujos de CF: {err}",
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