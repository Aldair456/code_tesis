"""
Prompts para análisis de solvencia y liquidez.
"""

from typing import List, Dict, Any

from services.service_credit_proposal_coril.src.prompts.common import internal_context_sections
from services.service_credit_proposal_coril.src.utils.system_prompt import credit_memo_system_prompt


def get_solvency_analysis_prompt(
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
    solvency_indicators = [
        ind for ind in financial_indicators
        if any(keyword in ind['indicator_name'].lower() for keyword in ['deuda', 'debt', 'apalancamiento', 'leverage', 'solvencia', 'ratio', 'coverage', 'endeudamiento'])
    ]

    indicators_text = "\n".join([
        f"- {ind['indicator_name']}: {ind['value']} ({ind['year']}, {ind['period_type']})"
        for ind in solvency_indicators
    ])
    log_section = internal_context_sections(business_log_context, guarantees_context)

    prompt = f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Análisis de Solvencia" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} / {subsector} | País: {country_name}
{log_section}
Indicadores financieros disponibles:
{indicators_text}

INSTRUCCIÓN PRINCIPAL:
Inicia con una línea de diagnóstico en este formato exacto:
SOLVENCIA: [SÓLIDA / ADECUADA / AJUSTADA / CRÍTICA]

Luego desarrolla el análisis cubriendo:

1. Nivel de endeudamiento
   - Ratio deuda/patrimonio y comparación con benchmark sectorial en {country_name}
   - Evolución del apalancamiento en el período disponible

2. Capacidad de pago
   - Cobertura de intereses (EBITDA / Gastos financieros)
   - Cobertura de servicio de deuda (principal + intereses)

3. Evaluación crediticia general
   - Calidad de los activos como respaldo de la deuda
   - Factores que fortalecen o deterioran la solvencia estructural

4. Posición relativa sectorial
   - Cómo se ubica la empresa frente al sector {sector} en {country_name}
   - Si el benchmark no está disponible, indícalo explícitamente

FORMATO DE SALIDA:
- Texto corrido o viñetas; sin tablas ni separadores ---
- Máximo 1,200 caracteres (excluyendo la línea de diagnóstico)

Adapta el análisis al marco crediticio y sectorial de {country_name}. No asumas que la empresa opera en Perú salvo que la geografía indicada lo sea.

Presenta la información en texto continuo o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas [1][2] ni sección "Fuentes" al final. Solo el análisis en texto corrido.

Responde en español, de forma profesional y concisa.
"""
    return prompt


def get_liquidity_analysis_prompt(
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
    liquidity_indicators = [
        ind for ind in financial_indicators
        if any(keyword in ind['indicator_name'].lower() for keyword in ['liquidez', 'current', 'quick', 'cash', 'working', 'capital', 'rotacion'])
    ]

    indicators_text = "\n".join([
        f"- {ind['indicator_name']}: {ind['value']} ({ind['year']}, {ind['period_type']})"
        for ind in liquidity_indicators
    ])
    log_section = internal_context_sections(business_log_context, guarantees_context)

    prompt = f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Análisis de Liquidez" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} / {subsector} | País: {country_name}
{log_section}
Indicadores financieros disponibles:
{indicators_text}

INSTRUCCIÓN PRINCIPAL:
Inicia con una línea de diagnóstico en este formato exacto:
LIQUIDEZ: [HOLGADA / ADECUADA / AJUSTADA / CRÍTICA]

Luego desarrolla el análisis cubriendo estas tres dimensiones:

1. Posición de liquidez
   - Ratio corriente: valor, interpretación y comparación sectorial
   - Ratio ácido: posición sin inventarios y lo que revela sobre la calidad del activo circulante

2. Ciclo de caja y capital de trabajo
   - Días de cobro, días de pago y días de inventario (si disponibles)
   - Ciclo de conversión de efectivo y eficiencia en la gestión del capital de trabajo

3. Brechas y necesidades de financiamiento
   - Identificación de brechas temporales de liquidez
   - Dependencia de líneas de crédito revolventes u otras facilidades
   - Recomendación sobre estructura de financiamiento de corto plazo

FORMATO DE SALIDA:
- Texto corrido o viñetas por dimensión; sin tablas ni separadores ---
- Cuando sea posible, compara los ratios contra el promedio del sector {sector} en {country_name}
- Si un indicador no está disponible en los indicadores financieros listados, indícalo en lugar de estimar
- Máximo 2,000 caracteres (excluyendo la línea de diagnóstico)

Adapta el análisis al marco económico y sectorial de {country_name}. No asumas que la empresa opera en Perú salvo que la geografía indicada lo sea.

Presenta la información en texto continuo o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas [1][2] ni sección "Fuentes" al final. Solo el análisis en texto corrido.

Responde en español, de forma profesional y concisa.
"""
    return prompt
