import logging
from common.response import Response
from services.service_outputs.src.config.dependencies import get_output_service
from common.exceptions.handler_exception import handle_exception
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from common.exceptions.exceptions import BadRequestError

output_service = get_output_service()
logger = logging.getLogger(__name__)


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")

    try:
        path_params = event.get("pathParameters") or {}
        business_id = path_params.get("business_id")
        if not business_id:
            raise BadRequestError("El parámetro 'business_id' es requerido en la ruta")

        result = output_service.recalculate_all(business_id=business_id)

        all_success = all(r.get("success") for r in result["results"].values())

        return Response(
            status_code=200,
            body={
                "success": all_success,
                "code": "RECALCULATE_OUTPUTS_COMPLETED",
                "message": f"Recálculo de outputs completado para business {business_id}",
                "statement_id": result["statement_id"],
                "results": result["results"]
            }
        ).to_dict()

    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event = {
        "user": {"sub": "test-user", "roles": ["ADMIN"]},
        "pathParameters": {"business_id": "4effc18a-8f29-4cc5-8539-c9f993dbefcb"},
    }
    print(lambda_handler(event, None))
