import logging
from common.response import Response
from services.service_outputs.src.config.dependencies import get_derived_cashflow_service
from common.exceptions.handler_exception import handle_exception
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from common.exceptions.exceptions import BadRequestError
from services.service_outputs.src.schemas.response import CalculatedDerivedCashflowResponseSchema

derived_cashflow_service = get_derived_cashflow_service()
logger = logging.getLogger(__name__)
dto_response = CalculatedDerivedCashflowResponseSchema(many=True)


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

        path_params = event.get("pathParameters") or {}
        business_id = path_params.get("business_id")
        if not business_id:
            raise BadRequestError("El parámetro 'business_id' es requerido en la ruta")

        query_params = event.get("queryStringParameters") or {}
        multi_params = event.get("multiValueQueryStringParameters") or {}

        categories = multi_params.get("categories") or (
            [query_params["category"]] if query_params.get("category") else None
        )
        names = multi_params.get("names") or (
            [query_params["name"]] if query_params.get("name") else None
        )
        period_types = multi_params.get("period_types") or (
            [query_params["period_type"]] if query_params.get("period_type") else None
        )
        period_identifiers = multi_params.get("period_identifiers") or (
            [query_params["period_identifier"]] if query_params.get("period_identifier") else None
        )

        try:
            page = max(0, int(query_params.get("page", 0)))
        except (ValueError, TypeError):
            page = 0
        try:
            size = max(1, min(int(query_params.get("size", 100)), 1000))
        except (ValueError, TypeError):
            size = 100

        results = derived_cashflow_service.get_calculated(
            user=user,
            business_id=business_id,
            evaluator_id=evaluator_id,
            categories=categories,
            names=names,
            period_types=period_types,
            period_identifiers=period_identifiers,
            page=page,
            size=size
        )

        data = dto_response.dump(results)

        return Response(
            status_code=200,
            body={
                "success": True,
                "code": "FETCH_CALCULATED_DERIVED_CASHFLOWS_SUCCESS",
                "message": f"{len(data)} calculated derived cashflows para business {business_id}",
                "data": data,
                "count": len(data)
            }
        ).to_dict()

    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event = {
        "user": {"sub": "test-user", "evaluator_id": "some-evaluator-uuid", "roles": ["ANALYST"]},
        "pathParameters": {"business_id": "some-business-uuid"},
        "queryStringParameters": {}
    }
    print(lambda_handler(event, None))
