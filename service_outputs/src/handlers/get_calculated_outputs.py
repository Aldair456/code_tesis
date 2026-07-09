import logging
from typing import List, Optional, Dict, Any
from common.response import Response
from services.service_outputs.src.config.dependencies import get_output_service
from common.exceptions.handler_exception import handle_exception
from services.service_outputs.src.schemas.response import CalculatedOutputResponseSchema
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from common.exceptions.exceptions import BadRequestError

output_service = get_output_service()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
dto_response = CalculatedOutputResponseSchema(many=True)



@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio procesamiento get_calculated_outputs - Request ID: {request_id}")

    try:
        user = event.get("user")
        if not user:
            logger.error("Usuario pasó la seguridad pero no se pudieron obtener datos de él")
            raise BadRequestError("Es necesario que esté presente el usuario")

        user_id = user.get('sub', 'unknown')
        logger.info(f"Request por usuario: {user_id}")

        path_params = event.get("pathParameters") or {}
        business_id = path_params.get("business_id")
        if not business_id:
            logger.error("Falta parámetro 'business_id' en pathParameters")
            raise BadRequestError("El parámetro 'business_id' es requerido en la ruta")

        query_params = event.get("queryStringParameters") or {}
        multi_value_params = event.get("multiValueQueryStringParameters") or {}

        filters = _parse_query_parameters(query_params, multi_value_params)
        logger.info(f"Filtros aplicados: {_get_applied_filters_summary(filters)}")

        evaluator_id = user.get('custom:evaluator_id') or user.get('evaluator_id')

        result = output_service.get_calculated_outputs(
            user=user,
            business_id=business_id,
            output_names=filters.get('output_names'),
            output_categories=filters.get('output_categories'),
            years=filters.get('years'),
            period_types=filters.get('period_types'),
            period_identifiers=filters.get('period_identifiers'),
            covenant_metrics_only=filters.get('covenant_metrics_only'),
            evaluator_id=evaluator_id,
            page=filters.get('page'),
            size=filters.get('size'),
            required_all=filters.get('required_all')
        )

        data_return = dto_response.dump(result["calculated_outputs"])

        logger.info(f"Respuesta exitosa: {len(data_return)} calculated outputs para business {business_id}")

        return Response(
            status_code=200,
            body={
                "success": True,
                "code": "FETCH_CALCULATED_OUTPUTS_SUCCESS",
                "message": f"Calculated outputs del Business {business_id} obtenidos correctamente",
                "data": data_return,
                "count": len(data_return),
                "filters": filters,
                "type_currency": result["type_currency"],
            }
        ).to_dict()

    except Exception as err:
        logger.error(f"error : {str(err)}")
        return handle_exception(err, request_id)



def _parse_query_parameters(query_params: dict, multi_value_params: dict) -> dict:
    """
    Parsea los parámetros de query para calculated outputs (ACTUALIZADO CON LTM)
    """
    filters = {}

    # Filtro por nombre de output individual
    if query_params.get('output_name'):
        filters['output_names'] = [query_params['output_name']]

    # Filtro por categoría de output individual
    if query_params.get('output_category'):
        filters['output_categories'] = [query_params['output_category']]

    # Filtro por año individual (backward compatibility)
    if query_params.get('year'):
        try:
            filters['years'] = [int(query_params['year'])]
        except (ValueError, TypeError):
            logger.warning(f"Invalid year parameter: {query_params.get('year')}")

    # NUEVO: Filtro por tipo de período individual
    if query_params.get('period_type'):
        period_type = query_params['period_type'].lower()
        if period_type in ['annual', 'quarterly', 'ltm', 'monthly_annualized']:
            filters['period_types'] = [period_type]
        else:
            logger.warning(f"Invalid period_type parameter: {query_params.get('period_type')}")

    # NUEVO: Filtro por identificador de período individual
    if query_params.get('period_identifier'):
        filters['period_identifiers'] = [query_params['period_identifier']]

    # Filtros múltiples
    if multi_value_params.get('output_names'):
        filters['output_names'] = multi_value_params['output_names']

    if multi_value_params.get('output_categories'):
        filters['output_categories'] = multi_value_params['output_categories']

    if multi_value_params.get('years'):
        try:
            years = [int(y) for y in multi_value_params['years'] if y.isdigit()]
            if years:
                filters['years'] = years
        except (ValueError, TypeError):
            logger.warning(f"Invalid years parameter: {multi_value_params.get('years')}")

    # NUEVO: Filtros múltiples para period_types
    if multi_value_params.get('period_types'):
        valid_types = [pt.lower() for pt in multi_value_params['period_types']
                      if pt.lower() in ['annual', 'quarterly', 'ltm', 'monthly_annualized']]
        if valid_types:
            filters['period_types'] = valid_types

    # NUEVO: Filtros múltiples para period_identifiers
    if multi_value_params.get('period_identifiers'):
        filters['period_identifiers'] = multi_value_params['period_identifiers']

    # NUEVO: Flag para solo métricas covenant
    filters['covenant_metrics_only'] = query_params.get('covenant_only', '').lower() in ('true', '1', 'yes')

    # Paginación
    try:
        filters['page'] = max(0, int(query_params.get('page', 0)))
    except (ValueError, TypeError):
        filters['page'] = 0

    try:
        size = int(query_params.get('size', 100))
        filters['size'] = max(1, min(size, 1000))
    except (ValueError, TypeError):
        filters['size'] = 100

    # Flag para obtener todos los resultados
    filters['required_all'] = query_params.get('all', '').lower() in ('true', '1', 'yes')
    if filters['required_all']:
        logger.info("Se solicitó obtener TODOS los calculated outputs (required_all=True)")

    return filters


def _get_applied_filters_summary(filters: dict) -> str:
    """
    Genera un resumen de los filtros aplicados para logging (ACTUALIZADO)
    """
    summary_parts = []

    if filters.get('output_names'):
        summary_parts.append(f"outputs({len(filters['output_names'])})")

    if filters.get('output_categories'):
        summary_parts.append(f"categories({','.join(filters['output_categories'])})")

    if filters.get('years'):
        summary_parts.append(f"years({','.join(map(str, filters['years']))})")

    # NUEVO: Summary para filtros LTM
    if filters.get('period_types'):
        summary_parts.append(f"period_types({','.join(filters['period_types'])})")

    if filters.get('period_identifiers'):
        summary_parts.append(f"period_ids({len(filters['period_identifiers'])})")

    if filters.get('covenant_metrics_only'):
        summary_parts.append("covenant_only")

    if filters.get('required_all'):
        summary_parts.append("ALL")
    else:
        summary_parts.append(f"page={filters.get('page', 0)},size={filters.get('size', 100)}")

    return ', '.join(summary_parts) if summary_parts else 'sin filtros'

if __name__ == '__main__':
    # Ejemplo de evento para testing
    event = {
        "user": {
            "sub": "9ca49e78-dec4-4046-a48a-8fc661110b28",
            "roles": ["ANALYST"]
        },
        "pathParameters": {
            "business_id": "b79ab712-b66e-4c03-8d3b-7e3679280ab5"
        },
        "queryStringParameters": {
            "period_type": "ltm"
        }
    }

    print(lambda_handler(event, None))