import json
import logging
import boto3
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EventBridgeClient:
    """Cliente para publicar eventos a AWS EventBridge"""

    def __init__(self, event_bus_name: str = 'vera-workflows-bus', region_name: Optional[str] = None):
        """
        Inicializa el cliente de EventBridge

        Args:
            event_bus_name: Nombre del Event Bus (default: 'vera-workflows-bus')
            region_name: Región de AWS (opcional, usa la configuración por defecto si no se especifica)
        """
        self.event_bus_name = event_bus_name
        self.client = boto3.client('events', region_name=region_name) if region_name else boto3.client('events')

    def publish_event(
        self,
        source: str,
        detail_type: str,
        detail: Dict[str, Any],
        event_bus_name: Optional[str] = None
    ) -> bool:
        """
        Publica un evento a EventBridge

        Args:
            source: Origen del evento (ej: 'vera.businesses', 'vera.loans')
            detail_type: Tipo de evento (ej: 'business.created', 'business.updated')
            detail: Detalles del evento como diccionario
            event_bus_name: Nombre del Event Bus (opcional, usa el configurado por defecto)

        Returns:
            True si se publicó correctamente, False en caso contrario
        """
        try:
            event_bus = event_bus_name or self.event_bus_name
            
            response = self.client.put_events(
                Entries=[
                    {
                        'Source': source,
                        'DetailType': detail_type,
                        'Detail': json.dumps(detail, default=str),
                        'EventBusName': event_bus
                    }
                ]
            )

            # Verificar si hubo errores
            failed_count = response.get('FailedEntryCount', 0)
            if failed_count > 0:
                error_msg = f"Error publicando evento: {response.get('Entries', [{}])[0].get('ErrorMessage', 'Unknown error')}"
                logger.error(error_msg)
                print("=" * 80)
                print(f" ERROR PUBLICANDO EVENTO A EVENTBRIDGE")
                print(f"   {error_msg}")
                print("=" * 80)
                return False

            logger.info(f"Evento '{detail_type}' publicado desde '{source}'")
            return True

        except Exception as e:
            logger.error(f"Error publicando evento a EventBridge: {e}", exc_info=True)
            print("=" * 80)
            print(f" ERROR PUBLICANDO EVENTO A EVENTBRIDGE: {e}")
            print("=" * 80)
            return False

    def publish_events_batch(
        self,
        events: List[Dict[str, Any]],
        event_bus_name: Optional[str] = None
    ) -> bool:
        """
        Publica múltiples eventos a EventBridge en un solo lote

        Args:
            events: Lista de diccionarios con las claves: 'source', 'detail_type', 'detail'
            event_bus_name: Nombre del Event Bus (opcional)

        Returns:
            True si todos se publicaron correctamente, False en caso contrario
        """
        try:
            event_bus = event_bus_name or self.event_bus_name
            
            entries = []
            for event in events:
                entries.append({
                    'Source': event['source'],
                    'DetailType': event['detail_type'],
                    'Detail': json.dumps(event['detail'], default=str),
                    'EventBusName': event_bus
                })

            response = self.client.put_events(Entries=entries)

            failed_count = response.get('FailedEntryCount', 0)
            if failed_count > 0:
                logger.error(f"Error publicando {failed_count} de {len(events)} eventos")
                return False

            logger.info(f"Publicados {len(events)} eventos exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error publicando eventos en lote: {e}", exc_info=True)
            return False

