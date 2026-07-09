import logging
import json
from typing import Dict, Any
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError, NotFoundError
from services.service_credit_proposal_coril.src.config.dependencies import get_financial_analysis_service
from services.service_credit_proposal_coril.src.utils.appsync_status import publish_financial_analysis_result
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
financial_analysis_service = get_financial_analysis_service()

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda para AppSync - Puede:
    1. Recibir requests de GraphQL (analyzeFinancial mutation)
    2. Recibir invocaciones de otros lambdas para publicar resultados (publish_result)
    
    Event (AppSync GraphQL):
    - arguments: { input: { business_id: "..." } }
    - identity: Información del usuario autenticado
    
    Event (Invocación Lambda):
    - action: "publish_result"
    - business_id: "..."
    - result: { ... resultado completo ... }
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio handler AppSync - Request ID: {request_id}")
    
    # Verificar si es una invocación para devolver resultado directamente (desde resolver simplificado)
    if event.get('action') == 'return_result':
        result = event.get('result')
        if not result:
            logger.error("Falta result en evento de retorno")
            return {
                "success": False,
                "message": "Datos incompletos",
                "data": {},
                "request_id": "unknown"
            }
        logger.info(f"Devolviendo resultado directamente para notificar suscripciones")
        return result
    
    # Si no, es un request normal de AppSync GraphQL
    try:
        # Extraer datos del evento AppSync
        arguments = event.get('arguments', {})
        input_data = arguments.get('input', {})
        business_id = input_data.get('business_id')
        
        # Extraer user_id del identity (puede venir de API Key o Cognito)
        identity = event.get('identity', {})
        user_id = identity.get('sub') or identity.get('username') or 'system'
        
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        
        logger.info(f"Analizando finanzas del business_id: {business_id}")
        
        # Validar que el servicio esté disponible
        if not financial_analysis_service.is_available():
            raise BadRequestError("Servicio de análisis financiero no disponible. Verifique configuración de API.")
        
        # Realizar análisis financiero
        result = financial_analysis_service.analyze_financial_by_business_id(business_id)
        
        # Construir respuesta - MISMO FORMATO que el handler HTTP original
        response_data = {
            "business_id": business_id,
            "analysis": {
                "rentabilidad": {
                    "contenido": result.profitability_analysis,
                    "caracteres": len(result.profitability_analysis)
                },
                "generacion_caja": {
                    "contenido": result.cash_generation_analysis,
                    "caracteres": len(result.cash_generation_analysis)
                }
            },
            "metadata": {
                "analizado_por": user_id,
                "servicio": financial_analysis_service.get_service_info(),
                "request_id": request_id
            }
        }
        
        final_response = {
            "success": True,
            "message": "Análisis financiero completado exitosamente",
            "data": response_data,
            "request_id": request_id
        }
        
        # Retornar en el mismo formato que el handler HTTP original
        return final_response
        
    except (BadRequestError, NotFoundError):
        raise
    except Exception as err:
        logger.error(f"Error en lambda_handler AppSync: {str(err)} - Request ID: {request_id}", exc_info=True)
        return handle_exception(err, request_id)


if __name__ == "__main__":
    # Evento de prueba (formato AppSync)
    event = {
        "arguments": {
            "input": {
                "business_id": "833bb9fa-9213-46b7-b0f8-f170b8aa1023"
            }
        },
        "identity": {
            "sub": "6438c468-1091-701d-6dc5-b6a04fbd33aa",
            "username": "test-user"
        },
        "request": {}
    }
    
    print("\n=== INICIANDO PRUEBA DE HANDLER FINANCIERO (AppSync) ===")
    print(f"API Key disponible: {'SÍ' if financial_analysis_service.is_available() else 'NO'}")
    print(f"Info servicio: {financial_analysis_service.get_service_info()}")
    
    print("\nEjecutando lambda_handler de análisis financiero desde AppSync...\n")
    result = lambda_handler(event, None)
    print("\n=== RESULTADO ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

