"""
Prompts para análisis financiero (rentabilidad y generación de caja).
"""

from typing import List, Dict, Any

from services.service_credit_proposal_coril.src.prompts.common import internal_context_sections
from services.service_credit_proposal_coril.src.utils.system_prompt import credit_memo_system_prompt


def get_profitability_analysis_prompt(
    company_name: str,
    ruc: str,
    sector: str,
    subsector: str,
    financial_indicators: List[Dict[str, Any]],
    country_name: str = "Perú",
    tax_id_label: str = "RUC",
    business_log_context: str = "",
    guarantees_context: str = "",
) -> str:
    profitability_indicators = [
        ind for ind in financial_indicators
        if any(keyword in ind['indicator_name'].lower() for keyword in ['roe', 'roa', 'roic', 'margen', 'rentabilidad', 'utilidad', 'ebitda'])
    ]

    indicators_text = "\n".join([
        f"- {ind['indicator_name']}: {ind['value']} ({ind['year']}, {ind['period_type']})"
        for ind in profitability_indicators
    ])
    log_section = internal_context_sections(business_log_context, guarantees_context)

    prompt = f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Análisis de Rentabilidad" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} / {subsector} | País: {country_name}
{log_section}
Indicadores financieros disponibles:
{indicators_text}

INSTRUCCIÓN PRINCIPAL:
Inicia con una línea de diagnóstico en este formato exacto:
RENTABILIDAD: [ALTA / MEDIA / BAJA / NEGATIVA]

Luego desarrolla el análisis cubriendo:

1. Evolución de márgenes
   - Margen bruto, EBITDA y neto: valores, tendencia y calidad
   - Factores que explican mejoras o deterioros en el período

2. Retornos sobre capital
   - ROE y ROA: nivel actual vs. expectativa sectorial en {country_name}
   - Eficiencia en el uso de activos y patrimonio

3. Drivers de rentabilidad
   - Principales palancas que sostienen o comprimen los márgenes
   - Estructura de costos y sensibilidad a variables clave (tipo de cambio, commodities, mano de obra)

4. Comparación sectorial
   - Posición relativa de {company_name} frente al sector {sector} en {country_name}
   - Si el benchmark no está disponible, indícalo explícitamente

5. Riesgos sobre rentabilidad futura
   - Factores que podrían presionar márgenes en 2025
   - Sostenibilidad de la rentabilidad actual

FORMATO DE SALIDA:
- Texto corrido o viñetas por sección; sin tablas ni separadores ---
- Máximo 2,000 caracteres (excluyendo la línea de diagnóstico)
- Si un indicador no está en los indicadores financieros listados, no lo estimes; indícalo como no disponible

Adapta el análisis al marco económico, regulatorio y sectorial de {country_name}. No asumas que la empresa opera en Perú salvo que la geografía indicada lo sea.

Presenta la información en texto continuo, párrafos o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas [1][2] ni sección "Fuentes" al final. Solo el análisis en texto corrido.

Responde en español, de forma profesional y concisa.
"""
    return prompt


def get_cash_generation_analysis_prompt(
    company_name: str,
    ruc: str,
    sector: str,
    subsector: str,
    financial_indicators: List[Dict[str, Any]],
    country_name: str = "Perú",
    tax_id_label: str = "RUC",
    business_log_context: str = "",
    guarantees_context: str = "",
) -> str:
    cash_flow_indicators = [
        ind for ind in financial_indicators
        if any(keyword in ind['indicator_name'].lower() for keyword in ['fco', 'fci', 'fcf', 'flujo', 'caja', 'cash', 'capital', 'working'])
    ]

    indicators_text = "\n".join([
        f"- {ind['indicator_name']}: {ind['value']} ({ind['year']}, {ind['period_type']})"
        for ind in cash_flow_indicators
    ])
    log_section = internal_context_sections(business_log_context, guarantees_context)

    prompt = f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Análisis de Flujo de Caja" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} / {subsector} | País: {country_name}
{log_section}
Indicadores financieros disponibles:
{indicators_text}

INSTRUCCIÓN PRINCIPAL:
Inicia con una línea de diagnóstico en este formato exacto:
GENERACIÓN DE CAJA: [FUERTE / ESTABLE / DÉBIL / NEGATIVA]

Distingue explícitamente entre los tres flujos en tu análisis:
- FCO: Flujo de Caja Operativo
- FCI: Flujo de Caja de Inversión
- FCL: Flujo de Caja Libre (FCO – Capex)

Si los datos no permiten calcular alguno de los tres, indícalo explícitamente en lugar de estimarlo.

Desarrolla el análisis cubriendo:

1. Calidad del FCO
   - Nivel, estabilidad y recurrencia del flujo operativo
   - Conversión de utilidades en caja (calidad del resultado)
   - Impacto del capital de trabajo sobre el FCO

2. Patrón de inversión (FCI)
   - Intensidad de capex y naturaleza (mantenimiento vs. expansión)
   - Ciclo de inversión y su coherencia con la etapa del negocio

3. Flujo de Caja Libre
   - Capacidad de generar caja después de inversiones
   - Uso del FCL: servicio de deuda, dividendos, acumulación de caja

4. Ciclo de caja
   - Eficiencia en la gestión de cobros, pagos e inventarios
   - Presiones estacionales o estructurales sobre el ciclo

5. Solvencia y flexibilidad financiera
   - Capacidad para cubrir servicio de deuda con FCO
   - Acceso a liquidez externa en escenarios de estrés

6. Tendencias y proyección
   - Dirección del FCL en 2024–2025
   - Señales de alerta o de mejora en la generación de caja

FORMATO DE SALIDA:
- Texto corrido o viñetas por sección; sin tablas ni separadores ---
- Máximo 2,000 caracteres (excluyendo la línea de diagnóstico)

Adapta el análisis al marco económico, regulatorio y sectorial de {country_name}. No asumas que la empresa opera en Perú salvo que la geografía indicada lo sea.

Presenta la información en texto continuo, párrafos o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas [1][2] ni sección "Fuentes" al final. Solo el análisis en texto corrido.

Responde en español, de forma profesional y concisa.
"""
    return prompt
