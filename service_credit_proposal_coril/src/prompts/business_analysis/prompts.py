"""
Prompts para análisis de negocio (sector y producto).
"""

from services.service_credit_proposal_coril.src.prompts.common import internal_context_sections
from services.service_credit_proposal_coril.src.utils.system_prompt import credit_memo_system_prompt


def get_sector_analysis_prompt(
    company_name: str,
    ruc: str,
    sector: str,
    subsector: str,
    country_name: str = "Perú",
    tax_id_label: str = "RUC",
    business_log_context: str = "",
    guarantees_context: str = "",
) -> str:
    context_section = internal_context_sections(business_log_context, guarantees_context)
    return f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Análisis Sectorial" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} | Subsector: {subsector} | País: {country_name}
{context_section}
Desarrolla el análisis en máximo 2,500 caracteres cubriendo obligatoriamente:

1. Tamaño y dinámica del sector
   - Cifras de producción, ventas o participación en PBI (2024–2025)
   - Tasa de crecimiento reciente y perspectiva de corto plazo

2. Drivers y estructura del mercado
   - Principales factores que impulsan o frenan el sector
   - Nivel de concentración y barreras de entrada relevantes

3. Marco regulatorio en {country_name}
   - Normas, licencias o restricciones que afecten al subsector {subsector}
   - Cambios regulatorios recientes o previstos en 2025

4. Perspectiva sectorial
   - Tendencia esperada y factores de riesgo macro-sectorial

FORMATO DE SALIDA:
- Texto corrido con subtítulos breves o viñetas; sin tablas ni separadores
- Si una cifra no está disponible para {country_name}, indícalo explícitamente
- Máximo 2,500 caracteres incluyendo además instrucciones de este apartado

Utiliza solo información oficial de la empresa o del país. Adapta el análisis sectorial al contexto económico, regulatorio y de mercado de {country_name}. No asumas Perú salvo que la geografía indicada lo sea.

IMPORTANTE — Información por año: Considera ÚNICAMENTE datos de 2024 y 2025 como vigentes. Cualquier información o cifra anterior a 2024 está desactualizada (no uses por ejemplo "en 2022 el sector creció X, en 2023 creció Y"). Solo menciona años 2024 y 2025 si citas datos temporales.

Presenta la información en texto continuo o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas ni sección "Fuentes" al final. Solo el análisis.

Responde en español, de forma profesional y concisa."""


def get_product_analysis_prompt(
    company_name: str,
    ruc: str,
    sector: str,
    subsector: str,
    country_name: str = "Perú",
    tax_id_label: str = "RUC",
    business_log_context: str = "",
    guarantees_context: str = "",
) -> str:
    context_section = internal_context_sections(business_log_context, guarantees_context)
    return f"""{credit_memo_system_prompt(country_name)}Redacta la sección "Producto, Demanda y Mercado" del Credit Memo para comité de crédito.

Empresa: {company_name} | {tax_id_label}: {ruc}
Sector: {sector} | Subsector: {subsector} | País: {country_name}
{context_section}
Desarrolla el análisis en máximo 2,500 caracteres cubriendo:

1. Descripción del negocio
   - Producto o servicio principal y propuesta de valor
   - Modelo de negocio (B2B, B2C, mixto) y canales de distribución

2. Mercado objetivo
   - Perfil del cliente y segmentos atendidos en {country_name}
   - Estimación del mercado direccionable (TAM/SAM si hay datos)

3. Posición competitiva
   - Principales competidores y diferenciadores de la empresa
   - Indicios de concentración de clientes o proveedores (riesgo de dependencia)

4. Dinámica de demanda
   - Estacionalidad, ciclicidad o factores externos que afecten los ingresos
   - Tendencia de la demanda en 2024–2025

5. Riesgos específicos del producto/mercado
   - Factores que puedan erosionar ingresos o márgenes

FORMATO DE SALIDA:
- Texto corrido o viñetas; sin tablas ni separadores
- Enfócate exclusivamente en la empresa, no en el sector general
- Si no hay datos verificables sobre {company_name}, indica "información no disponible"
- Máximo 2,500 caracteres

Utiliza solamente información interna de la empresa; nada que tenga que ver con el sector económico general. Adapta referencias de mercado y demanda al contexto de {country_name}. No asumas Perú salvo que la geografía indicada lo sea.

IMPORTANTE — Información por año: Considera ÚNICAMENTE datos de 2024 y 2025 como vigentes. Cualquier información o cifra anterior a 2024 está desactualizada (no uses por ejemplo "en 2022... en 2023..."). Solo menciona años 2024 y 2025 si citas datos temporales.

Presenta la información en texto continuo o listas con viñetas. No uses tablas en formato markdown (evita el formato con | para columnas y filas). No uses líneas separadoras con guiones (---) entre párrafos.

NO incluir fuentes, referencias bibliográficas, citas ni sección "Fuentes" al final. Solo el análisis.

Responde en español, de forma profesional y concisa."""
