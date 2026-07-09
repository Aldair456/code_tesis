import logging
from common.response import Response
from services.service_outputs.src.config.dependencies import get_output_service
from common.exceptions.handler_exception import handle_exception
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from common.exceptions.exceptions import BadRequestError
from services.service_outputs.src.schemas.response import OutputResponseSchema

output_service = get_output_service()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dto_response = OutputResponseSchema(many=True)

@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio procesamiento get_outputs - Request ID: {request_id}")

    try:
        user = event.get("user")
        if not user:
            logger.error("Usuario pasó la seguridad pero no se pudieron obtener datos de él")
            raise BadRequestError("Es necesario que esté presente el usuario")

        user_id = user.get('sub', 'unknown')
        logger.info(f"Request por usuario: {user_id}")

        query_params = event.get("queryStringParameters") or {}

        # Aplicar filtros si existen
        filters = {}
        if query_params.get('category'):
            filters['category'] = query_params['category']

        evaluator_id = user.get('custom:evaluator_id') or user.get('evaluator_id')
        if evaluator_id:
            filters['evaluator_id'] = evaluator_id

        # Obtener outputs usando el servicio
        outputs = output_service.get_outputs(filters)
        
        # Calcular el total de outputs
        data_return = dto_response.dump(outputs)
        
        logger.info(f"Respuesta exitosa: Con {len(data_return)} outputs totales")
        
        return Response(
            status_code=200,
            body={
                "success": True,
                "code": "FETCH_OUTPUTS_SUCCESS",
                "message": f"Outputs obtenidos correctamente.Con {len(data_return)} outputs totales",
                "data": data_return,
                "count": len(data_return)
            }
        ).to_dict()
        
    except Exception as err:
        logger.error(f"Error en get_outputs: {str(err)}")
        return handle_exception(err, request_id)
