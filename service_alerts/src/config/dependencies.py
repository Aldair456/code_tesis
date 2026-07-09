from services.service_alerts.src.services.alert_services import AlertService
from services.service_alerts.src.repositories.alert_repository import AlertRepository

def get_alert_service() -> AlertService:
    """
    Crea y retorna una instancia del servicio de alertas con sus dependencias
    """
    alert_repository = AlertRepository()
    
    return AlertService(
        alert_repository=alert_repository
    )
