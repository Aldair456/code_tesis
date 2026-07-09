"""
PATCH credit-proposals-coril/{proposal_id}: actualización parcial del proposal_data.

Permite editar determinadas partes sin enviar todo el JSON.
- Body: objeto con las claves a actualizar (ej: {"header": {"date": "..."}}, {"financial_results": {...}}).
- Merge recursivo: los objetos anidados se fusionan; las listas se reemplazan completas.
- Regenera PDF y Word en S3 con el resultado mergado.

Base de datos:
  - BD: PostgreSQL (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD desde env)
  - Tabla: credit_proposals_coril (vía CreditProposalCorilRepository)
  - Opera sobre: proposal_data (JSONB), pdf_s3_key, total_amount, currency, updated_at

Request:
  PATCH /credit-proposals-coril/{proposal_id}
  Body: { "header": {...}, "financial_results": {...} }  (cualquier subset)
"""
import logging
import json as json_module
from typing import Dict, Any

from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from services.service_credit_proposal_coril.src.config.dependencies import (
    get_credit_proposal_coril_service,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_coril_service = get_credit_proposal_coril_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    PATCH: actualización parcial de proposal_data.
    Body: objeto con las claves a editar (header, cover, financial_results, balance_general, etc.).
    No se requiere proposal_data completo; se hace merge con el existente.
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio PATCH propuesta crédito coril - Request ID: %s", request_id)

    try:
        user = event.get("user")
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        evaluator_id = user.get("evaluator_id")
        if not evaluator_id:
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")

        path_params = event.get("pathParameters") or {}
        proposal_id = path_params.get("proposal_id")
        if not proposal_id or not str(proposal_id).strip():
            raise BadRequestError("El parámetro 'proposal_id' es requerido en la ruta.")

        body = event.get("body")
        if not body:
            raise BadRequestError("El body es requerido.")
        if isinstance(body, str):
            body = json_module.loads(body)

        # PA: puede venir como body directo o dentro de "patch" / "partial_data"
        partial_data = body.get("patch") or body.get("partial_data") or body
        if not isinstance(partial_data, dict):
            raise BadRequestError("El body debe ser un objeto JSON con las claves a editar (ej: header, financial_results).")

        total_amount = body.get("total_amount")
        currency = body.get("currency")

        logger.info("PATCH propuesta coril %s: claves a actualizar: %s", proposal_id, list(partial_data.keys()))

        result = credit_proposal_coril_service.patch_credit_proposal_coril(
            proposal_id=proposal_id,
            evaluator_id=evaluator_id,
            partial_data=partial_data,
            total_amount=total_amount,
            currency=currency,
        )

        response = Response(
            status_code=200,
            body={
                "success": True,
                "message": "Propuesta de crédito actualizada parcialmente (PATCH)",
                "data": result,
                "request_id": request_id,
            },
        )

        return {
            "statusCode": response.status_code,
            "headers": response.headers,
            "body": json_module.dumps(response.body, ensure_ascii=False),
        }

    except BadRequestError:
        raise
    except Exception as err:
        logger.error(
            "Error en PATCH propuesta coril: %s - Request ID: %s",
            str(err),
            request_id,
            exc_info=True,
        )
        return handle_exception(err, request_id)


if __name__ == "__main__":
    import os
    # Body desde edit_json.json (lo que envía el frontend al PATCH)
    edit_json_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "edit_json.json")
    body = None
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            with open(edit_json_path, "r", encoding=enc) as f:
                body = json_module.load(f)
            break
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            break
    if body is None:
        body = {"header": {"date": "20 de febrero del 2026"}, "company": {"name": "CEMENTOS PACASMAYO S.A.A.", "ruc": "20419387658"}}
    event = {
        "user": {"sub": "uuid", "roles": ["ANALYST"], "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28"},
        "pathParameters": {"proposal_id": "3ba75415-d1e1-4f50-a095-5b7ce9d90192"},
        "body": body,
    }
    print("Ejecutando lambda_handler PATCH (body desde edit_json.json)...")
    result = lambda_handler(event, type("ctx", (), {"aws_request_id": "local-test"})())
    print(json_module.dumps(result, indent=2, ensure_ascii=False))
