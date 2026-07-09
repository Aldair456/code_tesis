# services/service_alerts/src/services/alert_rules_engine.py
import logging
from typing import Dict, Optional, Any
from uuid import UUID

logger = logging.getLogger(__name__)


class AlertRulesEngine:
    """
    Motor de reglas para verificar condiciones financieras y generar alertas
    Contiene todas las lógicas de verificación y reglas de negocio
    """

    def __init__(self):
        # Umbrales de configuración
        self.ebitda_drop_threshold = 0.10  # 10%
        self.sales_drop_threshold = 0.10  # 10%
        self.dscr_covenant_threshold = 1.2

    def check_ebitda_drop(self, ebitda_values: Dict[int, float],
                          current_year: int, previous_year: int) -> Optional[Dict[str, Any]]:
        """
        Verifica caída significativa en EBITDA

        Args:
            ebitda_values: Diccionario con valores de EBITDA por año
            current_year: Año actual
            previous_year: Año anterior

        Returns:
            Dict con datos de la alerta si se detecta caída, None si no
        """
        current = ebitda_values.get(current_year)
        previous = ebitda_values.get(previous_year)

        if current is None or previous is None:
            logger.info(f"Datos de EBITDA faltantes: current={current}, previous={previous}")
            return None

        variation = self.calculate_variation(current, previous)
        logger.info(f"EBITDA: {previous} -> {current}, variación: {variation}")

        if variation is not None and variation < -self.ebitda_drop_threshold:
            return {
                'indicator': 'EBITDA',
                'previous_value': previous,
                'current_value': current,
                'description': f"EBITDA cayó {abs(variation) * 100:.1f}% de {previous_year} a {current_year}",
                'variation': variation
            }

        return None

    def check_sales_drop(self, sales_values: Dict[int, float],
                         current_year: int, previous_year: int) -> Optional[Dict[str, Any]]:
        """
        Verifica caída significativa en ventas

        Args:
            sales_values: Diccionario con valores de ventas por año
            current_year: Año actual
            previous_year: Año anterior

        Returns:
            Dict con datos de la alerta si se detecta caída, None si no
        """
        current = sales_values.get(current_year)
        previous = sales_values.get(previous_year)

        if current is None or previous is None:
            logger.info(f"Datos de ventas faltantes: current={current}, previous={previous}")
            return None

        variation = self.calculate_variation(current, previous)
        logger.info(f"Ventas: {previous} -> {current}, variación: {variation}")

        if variation is not None and variation < -self.sales_drop_threshold:
            return {
                'indicator': 'Ventas Totales',
                'previous_value': previous,
                'current_value': current,
                'description': f"Ventas cayeron {abs(variation) * 100:.1f}% de {previous_year} a {current_year}",
                'variation': variation
            }

        return None

    def check_debt_equity_increase(self, debt_equity_values: Dict[int, float],
                                   current_year: int, previous_year: int) -> Optional[Dict[str, Any]]:
        """
        Verifica aumento significativo en apalancamiento

        Args:
            debt_equity_values: Diccionario con valores de apalancamiento por año
            current_year: Año actual
            previous_year: Año anterior

        Returns:
            Dict con datos de la alerta si se detecta aumento, None si no
        """
        current = debt_equity_values.get(current_year)
        previous = debt_equity_values.get(previous_year)

        if current is None or previous is None:
            logger.info(f"Datos de apalancamiento faltantes: current={current}, previous={previous}")
            return None

        logger.info(f"Apalancamiento: {previous} -> {current}")

        if current > previous:
            variation = current - previous
            return {
                'indicator': 'Apalancamiento',
                'previous_value': previous,
                'current_value': current,
                'description': f"Apalancamiento aumentó {variation:.1f} puntos de {previous_year} a {current_year}",
                'variation': variation
            }

        return None

    def check_covenant_breach(self, dscr_value: float) -> Optional[Dict[str, Any]]:
        """
        Verifica violación de covenant DSCR

        Args:
            dscr_value: Valor actual del DSCR

        Returns:
            Dict con datos de la alerta si se detecta violación, None si no
        """
        if dscr_value < self.dscr_covenant_threshold:
            return {
                'indicator': 'DSCR',
                'previous_value': None,
                'current_value': dscr_value,
                'description': f"DSCR ({dscr_value:.2f}) está por debajo del covenant mínimo ({self.dscr_covenant_threshold})",
                'variation': None
            }

        return None

    def calculate_variation(self, current: float, previous: float) -> Optional[float]:
        """
        Calcula la variación porcentual entre dos valores

        Args:
            current: Valor actual
            previous: Valor anterior

        Returns:
            Variación porcentual o None si no se puede calcular
        """
        if previous == 0 or current is None or previous is None:
            return None
        return (current - previous) / previous
