# services/service_alerts/src/services/alert_service.py
import json
import logging
from typing import List, Dict, Optional, Any
from uuid import UUID
from services.service_alerts.src.repositories.alert_repository import AlertRepository
from services.service_alerts.src.schemas.request import SQSMessageRequest
from services.service_alerts.src.services.alert_rules_engine import AlertRulesEngine
from common.exceptions.exceptions import ServiceDataValidationError, ServiceError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class AlertService:
    """
    Servicio para generar alertas financieras basadas en datos calculados
    Configurado como consumer de SQS: financial-alerts-queue
    """

    def __init__(self, alert_repository: AlertRepository):
        self.alert_repository = alert_repository
        self.rules_engine = AlertRulesEngine()
        self.processed_messages = 0
        self.failed_messages = 0

    def process_sqs_message(self, sqs_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un mensaje individual de SQS de financial-alerts-queue
        """
        try:
            # Extraer el cuerpo del mensaje
            message_body = json.loads(sqs_record['body'])
            message_id = sqs_record.get('messageId', 'unknown')

            logger.info(f"Procesando mensaje SQS ID: {message_id}")

            # Usar el schema para validar automáticamente
            try:
                validated_message = SQSMessageRequest(**message_body)
            except Exception as e:
                raise ServiceDataValidationError(f"Validación de mensaje SQS falló: {str(e)}")

            # Extraer datos del mensaje validado
            financial_statement_id = validated_message.financialStatementId

            logger.info(f"Procesando alertas para financial_statement: {financial_statement_id}")

            # Generar alertas usando el financial_statement_id
            alerts_created = self.generate_alerts_from_financial_statement(financial_statement_id)

            # Actualizar contadores
            self.processed_messages += 1

            logger.info(f"Procesamiento exitoso: {alerts_created} alertas creadas")

            return {
                'success': True,
                'message_id': message_id,
                'financial_statement_id': financial_statement_id,
                'alerts_created': alerts_created
            }

        except json.JSONDecodeError as e:
            raise ServiceDataValidationError(f"Error parseando JSON del mensaje SQS: {str(e)}")
        except ServiceDataValidationError:
            # Re-lanzar excepciones de validación
            raise
        except Exception as e:
            raise ServiceError(f"Error procesando mensaje SQS: {str(e)}")

    def generate_alerts_from_financial_statement(self, financial_statement_id: str) -> int:
        """Genera alertas usando el financial_statement_id para obtener datos de la base de datos"""
        alerts_created = 0
        try:
            # Obtener business_id desde el financial_statement_id
            business_id = self.alert_repository.get_business_id_from_financial_statement(UUID(financial_statement_id))
            print(f" BUSINESS_ID OBTENIDO: {business_id}")
            logger.info(f"Business ID obtenido: {business_id}")

            # Obtener outputs calculados con nombres desde la base de datos
            calculated_outputs = self.alert_repository.get_calculated_outputs_with_names(UUID(financial_statement_id))
            years = self.alert_repository.get_financial_statement_years(UUID(financial_statement_id))

            logger.info(f"Outputs obtenidos: {len(calculated_outputs)} registros")
            logger.info(f"Años disponibles: {years}")

            if not calculated_outputs:
                logger.warning("No se encontraron outputs calculados para el estado financiero")
                return 0

            # Extraer valores de los ratios específicos que nos interesan
            ratios = self.extract_ratios_from_database_outputs(calculated_outputs)
            logger.info(f"Ratios extraídos: {list(ratios.keys())}")

            if len(years) >= 2:
                # Usar los últimos dos años disponibles
                current_year = max(years)
                previous_year = max([y for y in years if y < current_year])

                logger.info(f"Comparando año {current_year} vs {previous_year}")

                # Verificar caídas de EBITDA
                if 'EBITDA' in ratios:
                    alert_data = self.rules_engine.check_ebitda_drop(ratios['EBITDA'], current_year, previous_year)
                    if alert_data:
                        if self.create_alert(business_id, alert_data):
                            alerts_created += 1

                # Verificar caídas de ventas
                if 'Ventas Totales' in ratios:
                    alert_data = self.rules_engine.check_sales_drop(ratios['Ventas Totales'], current_year,
                                                                    previous_year)
                    if alert_data:
                        if self.create_alert(business_id, alert_data):
                            alerts_created += 1

                # Verificar aumento de apalancamiento
                if 'Apalancamiento' in ratios:
                    alert_data = self.rules_engine.check_debt_equity_increase(ratios['Apalancamiento'], current_year,
                                                                              previous_year)
                    if alert_data:
                        if self.create_alert(business_id, alert_data):
                            alerts_created += 1

            # Verificar covenant breach (solo año actual)
            if 'DSCR' in ratios:
                current_dscr = self._get_latest_value_from_database(ratios['DSCR'])
                if current_dscr is not None:
                    alert_data = self.rules_engine.check_covenant_breach(current_dscr)
                    if alert_data:
                        if self.create_alert(business_id, alert_data):
                            alerts_created += 1

            logger.info(f"Alertas creadas: {alerts_created}")
            return alerts_created

        except Exception as e:
            raise ServiceError(f"Error generando alertas: {str(e)}")

    def extract_ratios_from_database_outputs(self, calculated_outputs: List[Dict]) -> Dict[str, Dict[int, float]]:
        """Extrae los ratios específicos de los outputs de la base de datos"""
        ratios = {}

        # Mapeo de nombres de indicadores que nos interesan para alertas
        target_indicators = {
            'EBITDA': 'EBITDA',
            'Ventas Totales': 'Ventas Totales',
            'DSCR': 'DSCR',
            'Apalancamiento': 'Apalancamiento',
            'Debt_Equity_Ratio': 'Apalancamiento',
            'Ventas': 'Ventas Totales',
        }

        for output in calculated_outputs:
            output_name = output.get('name', '')
            display_name = output.get('display_name', output_name)
            year = output.get('year')
            value = output.get('value')

            # Usar el nombre del indicador si está en nuestros targets
            if output_name in target_indicators:
                key = target_indicators[output_name]
                if key not in ratios:
                    ratios[key] = {}

                if year is not None and value is not None:
                    ratios[key][year] = value
                    logger.info(f"  - {output_name} -> {key}: {year} = {value}")

        return ratios

    def _get_latest_data_index(self, ratios: Dict[str, List[float]], max_years: int) -> int:
        """Encuentra el índice del año más reciente con datos"""
        for i in range(max_years - 1, -1, -1):
            # Verificar si hay datos válidos en este índice
            has_data = False
            for values in ratios.values():
                if i < len(values) and values[i] is not None:
                    has_data = True
                    break
            if has_data:
                return i
        return max_years - 1  # Fallback al último índice

    def _get_latest_value(self, values: List[float]) -> Optional[float]:
        """Obtiene el último valor no nulo de una lista"""
        for i in range(len(values) - 1, -1, -1):
            if values[i] is not None:
                return values[i]
        return None

    def _get_latest_value_from_database(self, year_values: Dict[int, float]) -> Optional[float]:
        """Obtiene el último valor no nulo de un diccionario año-valor"""
        if not year_values:
            return None
        latest_year = max(year_values.keys())
        return year_values.get(latest_year)

    def create_alert(self, business_id: str, alert_data: Dict[str, Any]) -> bool:
        """
        Crea una nueva alerta

        Args:
            business_id: ID del business
            alert_data: Diccionario con los datos de la alerta del rules engine

        Returns:
            bool: True si se creó la alerta, False si no
        """
        try:
            # Crear nueva alerta usando los datos del rules engine
            alert_payload = {
                'business_id': UUID(business_id),
                'indicator': alert_data['indicator'],
                'previous_value': alert_data['previous_value'],
                'current_value': alert_data['current_value'],
                'description': alert_data['description'],
                'is_archived': False
            }

            self.alert_repository.create_alert(alert_payload)

            logger.info(f"Alerta creada: {alert_data['indicator']} | Business: {business_id}")
            if alert_data['description']:
                logger.info(f"   Descripción: {alert_data['description']}")

            return True

        except Exception as e:
            raise ServiceError(f"Error creando alerta: {str(e)}")

    def get_total_active_alerts_by_evaluator(self, evaluator_id: str) -> int:
        """
        Obtiene el total de alertas activas para un evaluador específico
        """
        try:
            logger.info(f"Obteniendo total de alertas activas para evaluator_id: {evaluator_id}")

            total_alerts = self.alert_repository.get_total_active_alerts_by_evaluator(evaluator_id)

            logger.info(f"Total de alertas activas encontradas: {total_alerts}")
            return total_alerts

        except Exception as e:
            logger.error(f"Error obteniendo total de alertas activas: {str(e)}")
            raise ServiceError(f"Error obteniendo total de alertas activas: {str(e)}")

    def get_active_alerts_by_business_id(self, business_id: str, limit: int = 100, offset: int = 0) -> List[
        Dict[str, Any]]:
        """
        Obtiene solo las alertas activas para un business específico con paginación

        Args:
            business_id: ID del business
            limit: Número máximo de alertas a retornar (default: 100)
            offset: Número de alertas a omitir para paginación (default: 0)

        Returns:
            List[Dict]: Lista de alertas activas
        """
        try:
            logger.info(
                f"Obteniendo alertas activas para business_id: {business_id} (limit: {limit}, offset: {offset})")

            alerts = self.alert_repository.get_active_alerts_by_business_id(business_id, limit, offset)

            logger.info(f"Alertas activas encontradas: {len(alerts)}")
            return alerts

        except Exception as e:
            logger.error(f"Error obteniendo alertas activas por business_id: {str(e)}")
            raise ServiceError(f"Error obteniendo alertas activas por business_id: {str(e)}")

    def archive_alert(self, alert_id: str) -> bool:
        """
        Archiva una alerta específica cambiando is_archived a True

        Args:
            alert_id: ID de la alerta a archivar

        Returns:
            bool: True si se archivó exitosamente, False si no se encontró
        """
        try:
            logger.info(f"Archivando alerta con ID: {alert_id}")

            success = self.alert_repository.archive_alert(alert_id)

            if success:
                logger.info(f"Alerta {alert_id} archivada exitosamente")
            else:
                logger.warning(f"No se pudo archivar la alerta {alert_id}")

            return success

        except Exception as e:
            logger.error(f"Error archivando alerta {alert_id}: {str(e)}")
            raise ServiceError(f"Error archivando alerta: {str(e)}")

    def get_archived_alerts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Obtiene todas las alertas archivadas con paginación

        Args:
            limit: Número máximo de alertas a retornar (default: 100)
            offset: Número de alertas a omitir para paginación (default: 0)

        Returns:
            List[Dict]: Lista de alertas archivadas
        """
        try:
            logger.info(f"Obteniendo alertas archivadas (limit: {limit}, offset: {offset})")

            alerts = self.alert_repository.get_archived_alerts(limit, offset)

            logger.info(f"Alertas archivadas encontradas: {len(alerts)}")
            return alerts

        except Exception as e:
            logger.error(f"Error obteniendo alertas archivadas: {str(e)}")
            raise ServiceError(f"Error obteniendo alertas archivadas: {str(e)}")

    def get_archived_alerts_by_business(self, business_id: str, limit: int = 100, offset: int = 0) -> List[
        Dict[str, Any]]:
        """
        Obtiene las alertas archivadas para un business específico con paginación

        Args:
            business_id: ID del business
            limit: Número máximo de alertas a retornar (default: 100)
            offset: Número de alertas a omitir para paginación (default: 0)

        Returns:
            List[Dict]: Lista de alertas archivadas para el business
        """
        try:
            logger.info(
                f"Obteniendo alertas archivadas para business_id: {business_id} (limit: {limit}, offset: {offset})")

            alerts = self.alert_repository.get_archived_alerts_by_business(business_id, limit, offset)

            logger.info(f"Alertas archivadas encontradas para business {business_id}: {len(alerts)}")
            return alerts

        except Exception as e:
            logger.error(f"Error obteniendo alertas archivadas por business_id: {str(e)}")
            raise ServiceError(f"Error obteniendo alertas archivadas por business_id: {str(e)}")