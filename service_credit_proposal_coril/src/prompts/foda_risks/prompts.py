"""
Prompts para análisis FODA y Riesgos.
"""

from typing import List, Dict, Any

from services.service_credit_proposal_coril.src.prompts.common import internal_context_sections
from services.service_credit_proposal_coril.src.utils.system_prompt import credit_memo_system_prompt


def get_foda_analysis_prompt(
    company_name: str,
    ruc: str,
    sector: str,
    subsector: str,
    country_name: str = "Perú",
    tax_id_label: str = "RUC",
    business_log_context: str = "",
    guarantees_context: str = "",
) -> str:
    log_section = internal_context_sections(business_log_context, guarantees_context)
    prompt = f"""{credit_memo_system_prompt(country_name)}Genera el análisis FODA de {company_name} ({tax_id_label}: {ruc}) del sector {sector} / subsector {subsector} en {country_name}.

Empresa: {company_name}
Sector: {sector}
Subsector: {subsector}
Geografía: {country_name}
{log_section}
DEFINICIONES:
- Fortalezas y Debilidades: factores INTERNOS de la empresa únicamente
- Oportunidades y Amenazas: factores EXTERNOS del entorno únicamente

CRITERIOS DE CALIDAD POR ÍTEM:
- Cada ítem debe ser específico y cuantificable cuando sea posible
- Máximo 200 caracteres por ítem (prioriza especificidad sobre brevedad)
- Sin prefijos: NO uses "Fortaleza 1:", "F1:", "Oportunidad:" ni similares
- Fortalezas y Debilidades no deben contradecirse entre sí
- Solo años 2024–2025 si citas datos temporales
- Mínimo 4 ítems por categoría, máximo 6 ítems
- Incluir cifras y datos específicos cuando sea relevante, contextualizados a {country_name}
- Enfocarse en aspectos cuantificables y verificables
- Si no hay datos verificables, indica "información no disponible"

Adapta oportunidades, amenazas y referencias macro/sectoriales al contexto de {country_name}. No asumas Perú salvo que la geografía indicada lo sea.

IMPORTANTE — Información por año: Si mencionas datos externos, sector o macro con año, usa ÚNICAMENTE 2024 y 2025 como vigentes. Cualquier cifra anterior a 2024 está desactualizada (no cites 2022, 2023 ni años anteriores).

IMPORTANTE: Responde ÚNICAMENTE en el siguiente formato JSON exacto:

{{
  "foda": {{
    "fortalezas": [
      "descripción breve y concisa de la fortaleza",
      "otra fortaleza sin prefijo ni numeración"
    ],
    "oportunidades": [
      "descripción breve y concisa de la oportunidad",
      "otra oportunidad sin prefijo ni numeración"
    ],
    "debilidades": [
      "descripción breve y concisa de la debilidad",
      "otra debilidad sin prefijo ni numeración"
    ],
    "amenazas": [
      "descripción breve y concisa de la amenaza",
      "otra amenaza sin prefijo ni numeración"
    ]
  }}
}}

Requisitos de salida:
- Cada ítem debe ser SOLO la descripción: escribe directamente el contenido, sin prefijos ni numeración
- NO incluir texto fuera del formato JSON
- NO incluir explicaciones adicionales
- NO incluir fuentes, referencias ni citas dentro del JSON ni fuera

Responde en español, de forma profesional y concisa.
"""
    return prompt


def get_risks_analysis_prompt(
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
    risk_indicators = [
        ind for ind in financial_indicators
        if any(keyword in ind['indicator_name'].lower() for keyword in ['deuda', 'risk', 'volatility', 'beta', 'ratio', 'coverage', 'liquidez', 'solvencia'])
    ]

    indicators_text = "\n".join([
        f"- {ind['indicator_name']}: {ind['value']} ({ind['year']}, {ind['period_type']})"
        for ind in risk_indicators
    ])
    log_section = internal_context_sections(business_log_context, guarantees_context)

    prompt = f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Análisis de Riesgos" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} / {subsector} | País: {country_name}
{log_section}
Indicadores financieros disponibles:
{indicators_text}

INSTRUCCIÓN PRINCIPAL:
Identifica y jerarquiza los riesgos de mayor a menor materialidad para la empresa. Distingue entre riesgos ACTUALES (ya evidenciados en los indicadores) y riesgos POTENCIALES (que podrían materializarse).

Cubre las siguientes categorías en ese orden de presentación:

1. RIESGOS FINANCIEROS
   - Nivel de endeudamiento y apalancamiento
   - Presión sobre liquidez o cobertura de deuda
   - Vulnerabilidades en la estructura de capital

2. RIESGOS OPERATIVOS
   - Eficiencia operativa y dependencias críticas
   - Concentración de clientes, proveedores o geografías

3. RIESGOS DE MERCADO
   - Presión competitiva y riesgo de pérdida de cuota
   - Sensibilidad de la demanda a variables externas

4. RIESGOS REGULATORIOS
   - Exposición a cambios normativos en {country_name}
   - Requisitos de cumplimiento específicos del subsector {subsector}

5. FACTORES EXTERNOS
   - Riesgos macroeconómicos relevantes para {country_name}
   - Variables de tipo de cambio, tasas o commodities si aplica

FORMATO DE SALIDA:
- Texto corrido o viñetas por categoría; sin tablas ni separadores ---
- Máximo 1,800 caracteres en total
- Si los indicadores no permiten evaluar una categoría, indícalo brevemente en lugar de omitirla

Considera riesgos regulatorios, macroeconómicos y de mercado propios de {country_name}. No asumas que la empresa opera en Perú salvo que la geografía indicada lo sea.

Presenta la información en texto continuo o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas [1][2] ni sección "Fuentes" al final. Solo el análisis en texto corrido.

Responde en español, de forma profesional y concisa.
"""
    return prompt
