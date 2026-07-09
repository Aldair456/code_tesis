import logging
from common.response import Response
from services.service_outputs.src.config.dependencies import get_derived_cashflow_service
from common.exceptions.handler_exception import handle_exception
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from common.exceptions.exceptions import BadRequestError
from services.service_outputs.src.schemas.response import DerivedCashflowResponseSchema

derived_cashflow_service = get_derived_cashflow_service()
logger = logging.getLogger(__name__)
dto_response = DerivedCashflowResponseSchema(many=True)


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    try:
        user = event.get("user")
        if not user:
            raise BadRequestError("Usuario requerido")

        evaluator_id = user.get("evaluator_id")
        if not evaluator_id:
            raise BadRequestError("El usuario autenticado no tiene evaluador asignado")

        definitions = derived_cashflow_service.get_definitions(evaluator_id)
        data = dto_response.dump(definitions)

        return Response(
            status_code=200,
            body={
                "success": True,
                "code": "FETCH_DERIVED_CASHFLOWS_SUCCESS",
                "message": f"{len(data)} derived cashflows para evaluador {evaluator_id}",
                "data": data,
                "count": len(data)
            }
        ).to_dict()

    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event = {
        "user": {"sub": "test-user", "evaluator_id": "some-evaluator-uuid", "roles": ["ANALYST"]},
    }
    print(lambda_handler(event, None))
