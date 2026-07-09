"""
Helper para publicar status a AppSync y actualizar en BD.
Envía notificaciones de estado durante el ciclo de vida del análisis de crédito.
Usa common_appsync.AppSyncClient para la llamada HTTP a AppSync.
"""
import logging
import json
from typing import Optional, List, Dict, Any, Union

from common_appsync import AppSyncClient
from services.service_credit_proposal_coril.src.config.config import (
    APPSYNC_ENDPOINT,
    APPSYNC_API_KEY,
    APPSYNC_MUTATION_PUBLISH_STATUS,
    APPSYNC_MUTATION_PUBLISH_FINANCIAL_ANALYSIS,
)

logger = logging.getLogger(__name__)

_client: Optional[AppSyncClient] = None


def _get_appsync_client() -> Optional[AppSyncClient]:
    """Obtiene el cliente AppSync (lazy)."""
    global _client
    if _client is None and APPSYNC_ENDPOINT and APPSYNC_API_KEY:
        _client = AppSyncClient(endpoint=APPSYNC_ENDPOINT, api_key=APPSYNC_API_KEY)
    return _client

# Importación lazy para evitar dependencias circulares
_service = None


def _get_credit_proposal_service():
    """Obtiene el servicio de propuesta coril de forma lazy."""
    global _service
    if _service is None:
        try:
            from services.service_credit_proposal_coril.src.config.dependencies import (
                get_credit_proposal_coril_service,
            )

            _service = get_credit_proposal_coril_service()
        except Exception as e:
            logger.warning(f"No se pudo obtener servicio: {e}")
            _service = None
    return _service


def update_status_in_db(credit_memo_id: str, status: str) -> bool:
    """Actualiza el status en la base de datos vía servicio."""
    if not credit_memo_id:
        return False
    try:
        svc = _get_credit_proposal_service()
        if not svc:
            return False
        ok = svc.update_credit_memo_status(credit_memo_id, status)
        if ok:
            logger.info(f"Status actualizado en BD: credit_memo_id={credit_memo_id}, status={status}")
        return bool(ok)
    except Exception as e:
        logger.warning(f"Error actualizando status en BD: {e}")
    return False


class StatusType:
    INICIADO = "INICIADO"
    EN_PROGRESO = "EN_PROGRESO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"
    CREADO = "CREADO"
    ELIMINADO = "ELIMINADO"
    ELIMINADOS_LOTE = "ELIMINADOS_LOTE"


def publish_status(
    status: str,
    message: Optional[str] = None,
    credit_memo_id: Optional[str] = None,
    deleted_ids: Optional[List[str]] = None,
    created_proposal: Optional[Union[Dict[str, Any], str]] = None,
    update_db: bool = True
) -> bool:
    """
    Publica un status a AppSync para notificar suscripciones.
    created_proposal: objeto con datos de la propuesta creada (mismo shape que GET lista); solo para CREADO.
    """
    if update_db and credit_memo_id:
        update_status_in_db(credit_memo_id, status)

    client = _get_appsync_client()
    if not client:
        logger.warning("AppSync no configurado. APPSYNC_ENDPOINT o APPSYNC_API_KEY no disponibles.")
        return False

    created_proposal_str = None
    if created_proposal is not None:
        created_proposal_str = json.dumps(created_proposal, ensure_ascii=False) if isinstance(created_proposal, dict) else created_proposal

    variables = {
        "status": status,
        "message": message,
        "credit_memo_id": credit_memo_id,
        "deleted_ids": deleted_ids,
        "created_proposal": created_proposal_str,
    }
    ok = client.execute(APPSYNC_MUTATION_PUBLISH_STATUS, variables, timeout=10)
    if ok:
        logger.info("Status publicado: status=%s, credit_memo_id=%s", status, credit_memo_id)
    return ok


def notify_iniciado(message: str = "Proceso de análisis iniciado", credit_memo_id: Optional[str] = None) -> bool:
    return publish_status(StatusType.INICIADO, message, credit_memo_id)


def notify_en_progreso(message: str, credit_memo_id: Optional[str] = None) -> bool:
    return publish_status(StatusType.EN_PROGRESO, message, credit_memo_id)


def notify_completado(message: str = "Proceso completado exitosamente", credit_memo_id: Optional[str] = None) -> bool:
    return publish_status(StatusType.COMPLETADO, message, credit_memo_id)


def notify_fallido(message: str = "Error en el proceso", credit_memo_id: Optional[str] = None) -> bool:
    return publish_status(StatusType.FALLIDO, message, credit_memo_id)


def notify_creado(
    message: str = "Propuesta creada",
    credit_memo_id: Optional[str] = None,
    created_proposal: Optional[Union[Dict[str, Any], str]] = None
) -> bool:
    """Notifica que se creó una propuesta. Si se pasa created_proposal (mismo shape que GET lista), la UI puede pintar la fila sin llamar al GET."""
    return publish_status(
        StatusType.CREADO,
        message,
        credit_memo_id,
        deleted_ids=None,
        created_proposal=created_proposal,
        update_db=False
    )


def notify_eliminado(message: str = "Propuesta eliminada", credit_memo_id: Optional[str] = None) -> bool:
    return publish_status(StatusType.ELIMINADO, message, credit_memo_id, update_db=False)


def notify_eliminados_lote(message: str, deleted_ids: Optional[List[str]] = None) -> bool:
    return publish_status(
        StatusType.ELIMINADOS_LOTE,
        message,
        credit_memo_id=None,
        deleted_ids=deleted_ids,
        update_db=False
    )


def publish_financial_analysis_result(business_id: str, result: Dict[str, Any]) -> bool:
    """
    Publica el resultado del análisis financiero a AppSync para notificar suscripciones.

    Args:
        business_id: ID del negocio
        result: Resultado completo del análisis (success, message, data, request_id)

    Returns:
        True si se publicó exitosamente, False en caso contrario
    """
    client = _get_appsync_client()
    if not client:
        logger.warning("AppSync no configurado. No se puede publicar resultado de análisis financiero.")
        return False

    variables = {"business_id": business_id, "result": result}
    ok = client.execute(APPSYNC_MUTATION_PUBLISH_FINANCIAL_ANALYSIS, variables, timeout=30)
    if ok:
        logger.info("Resultado de análisis financiero publicado a AppSync para business_id=%s", business_id)
    return ok
