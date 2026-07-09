
import logging
import json
from typing import Dict, Any
from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from common_aws_clients.sqs_client import SQSClient
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_iniciado, notify_fallido
from services.service_credit_proposal_coril.src.config.config import (
    FINANCIAL_ANALYSIS_QUEUE_URL,
    CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL,
    QUEUE_URL_CREDIT_MEMO_ANALYSIS_CM,
    QUEUE_URL_INTERBANK_COMPANY_PROFILE_MEMO,
)
from services.service_credit_proposal_coril.src.config.dependencies import get_credit_proposal_coril_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_service = get_credit_proposal_coril_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda emisor que recibe request HTTP y envía mensaje a SQS para análisis financiero asíncrono.
    
    Body:
    - business_id: ID del negocio a analizar financieramente
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio emisión de análisis financiero a SQS - Request ID: {request_id}")

    try:
        # Validar usuario autenticado
        user = event.get('user')
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")
        
        user_id = user.get('sub')
        if not user_id:
            raise BadRequestError("El usuario no tiene un ID válido.")
        
        # Obtener body
        body = event.get('body')
        if not body:
            raise BadRequestError("El body es requerido.")
        
        # Parsear body si es string
        if isinstance(body, str):
            body = json.loads(body)
        
        # Validar business_id
        business_id = body.get('business_id')
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        
        # Obtener credit_memo_id (requerido para el nuevo flujo)
        credit_memo_id = body.get('credit_memo_id')
        if not credit_memo_id:
            raise BadRequestError("credit_memo_id es requerido. Use /init primero para crear la propuesta.")
        
        # Obtener deal_id (opcional)
        deal_id = body.get('deal_id')
        
        logger.info(f"Enviando análisis financiero del business_id: {business_id}, credit_memo_id: {credit_memo_id} a SQS")
        
        # Lógica de enrutamiento por evaluator_id
        target_queue_url = FINANCIAL_ANALYSIS_QUEUE_URL
        evaluator_id = user.get("evaluator_id")

        if evaluator_id:
            try:
                repo = credit_proposal_service.repository
                print(repo)
                print(".............")
                if hasattr(repo, "get_evaluator_route"):
                    route = repo.get_evaluator_route(evaluator_id)
                    print("....................")
                    print("Entre 3")
                    print(route)
                    if route:
                        print("route")
                        proposal_type = route.get("proposal_type")
                        route_target_queue = route.get("target_queue_url")
                        print(f"Ruta encontrada para evaluator {evaluator_id}: {proposal_type}")
                        logger.info(f"Ruta encontrada para evaluator {evaluator_id}: {proposal_type}")
                        if proposal_type == "GC":
                            if CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL:
                                print(CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL)
                                target_queue_url = CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL
                        if proposal_type == "CM":
                            if QUEUE_URL_CREDIT_MEMO_ANALYSIS_CM:
                                print(QUEUE_URL_CREDIT_MEMO_ANALYSIS_CM)
                                target_queue_url = QUEUE_URL_CREDIT_MEMO_ANALYSIS_CM
                            else:
                                logger.warning(" proposal_type='GC' pero CREDIT_PROPOSAL_ANALYSIS_QUEUE_URL no está configurada.")
                        if proposal_type == "IB":
                            if QUEUE_URL_INTERBANK_COMPANY_PROFILE_MEMO:
                                target_queue_url = QUEUE_URL_INTERBANK_COMPANY_PROFILE_MEMO
                            else:
                                logger.warning(
                                    "proposal_type='IB' pero QUEUE_URL_INTERBANK_COMPANY_PROFILE_MEMO no está configurada."
                                )

                        # Si tiene una cola específica en DB, la usamos (sobreescribe logic anterior si aplica)
                        elif route_target_queue:
                            target_queue_url = route_target_queue
                            logger.info(f"Redirigiendo a cola específica por DB ({proposal_type}): {target_queue_url}")
            except Exception as e:
                logger.error(f"Error al intentar enrutar por evaluator: {e}")

        # Validar que la URL de SQS esté configurada
        if not target_queue_url:
            raise BadRequestError("URL de cola SQS no configurada.")
        
        # Crear cliente SQS
        sqs_client = SQSClient(queue_url=target_queue_url)
        
        # Preparar mensaje para SQS (incluye credit_memo_id, user_id y deal_id para la Step Function)
        message = {
            "business_id": business_id,
            "credit_memo_id": credit_memo_id,
            "user_id": user_id,
            "deal_id": deal_id,
            "request_id": request_id,
            "timestamp": context.get("request_time", "") if hasattr(context, "request_time") else ""
        }
        
        # Enviar mensaje a SQS FIFO
        # Para FIFO necesitamos MessageGroupId (usamos business_id para agrupar por negocio)
        sqs_response = sqs_client.send_message(
            message=message,
            message_group_id=business_id  # Agrupa mensajes del mismo business_id
        )
        message_id = sqs_response.get('MessageId')
        
        logger.info(f"Mensaje enviado exitosamente a SQS. MessageId: {message_id}, BusinessId: {business_id}")
        
        # Notificar INICIADO a AppSync
        notify_iniciado("Análisis de crédito iniciado", credit_memo_id)
        
        # Construir respuesta
        response = Response(
            status_code=202,  # Accepted - procesamiento asíncrono
            body={
                "success": True,
                "message": "Análisis financiero encolado exitosamente. Procesamiento asíncrono iniciado.",
                "data": {
                    "business_id": business_id,
                    "message_id": message_id,
                    "queue_url": FINANCIAL_ANALYSIS_QUEUE_URL,
                    "status": "queued"
                },
                "request_id": request_id
            }
        )
        
        # Convertir a dict manualmente para asegurar encoding correcto
        return {
            "statusCode": response.status_code,
            "headers": response.headers,
            "body": json.dumps(response.body, ensure_ascii=False)
        }
        
    except BadRequestError:
        raise
    except Exception as err:
        logger.error(f"Error en lambda_handler emisor: {str(err)} - Request ID: {request_id}", exc_info=True)
        # Notificar FALLIDO si tenemos business_id
        if 'business_id' in locals() and business_id:
            notify_fallido(f"Error al iniciar análisis: {str(err)}", credit_memo_id if 'credit_memo_id' in locals() else None)
        return handle_exception(err, request_id)

event = {
    "body": {
        "business_id": "5e6d6cbb-de9c-4086-a373-dd2ab3caefc2",
        "credit_memo_id": "9ae5bf9a-e064-46c1-b998-f9cd9a3c6484",
    },
    "user": {
        "sub": "a4485478-3081-7075-b902-f79b896f0c8c",
        "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28",
        "role": "ANALYST"  
    }
}
print(lambda_handler(event,None))