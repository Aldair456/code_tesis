"""
Paquete de prompts organizados por categoría.
"""

# Importar todos los módulos de prompts
from . import business_analysis
from . import financial_analysis
from . import solvency_liquidity
from . import foda_risks

__all__ = ['business_analysis', 'financial_analysis', 'solvency_liquidity', 'foda_risks']
