"""
Persistencia unificada (BD + S3) tras los extractores BS/PL/CF.

El Step Function suele invocar esta Lambda con **una lista** de respuestas de las
Lambdas `extract_*` (mismo contrato que `models/model_1/ia/src/handlers/subir_bd.py`).
No importa si el texto vino de Textract (model_1) o del payload Reducto (model_1V2):
`process_financial_data` solo concatena `data` y usa `object_key_json_output`,
`periodicity`, `type`, `job_id`, etc.
"""

import json
import logging
from typing import Any, Dict, List

from models.model_1V2.src.config.dependencies import create_financial_statement_ia_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

service = create_financial_statement_ia_service()


def lambda_handler(event: List[Dict[str, Any]], context: Any) -> Dict[str, Any]:
    """
    Misma firma y comportamiento que `subir_bd.lambda_handler`.

    :param event: Lista de dicts (salidas de extract_bs / extract_pl / extract_cf).
    """
    try:
        if not isinstance(event, list):
            logger.error("Formato inválido de event: %s", type(event).__name__)
            return {
                "status": "FAIL",
                "statusCode": 400,
                "body": json.dumps({"error": "El evento debe ser una lista"}),
            }

        result = service.process_financial_data(event)

        if result.get("statusCode") != 200:
            return {"status": "FAIL", **result}

        return {"status": "SUCCESS", **result}

    except Exception as e:
        logger.exception("Error inesperado en handler subir_bd (model_1V2)")
        return {
            "status": "FAIL",
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }

