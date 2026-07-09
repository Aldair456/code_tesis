"""
Funciones de normalización y prompts para análisis de negocio.
Convierte datos del JSON a formato consistente y contiene prompts para IA.
"""
import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


COUNTRY_LABELS = {
    "PE": "Perú",
    "CL": "Chile",
}

TAX_ID_LABELS = {
    "PE": "RUC",
    "CL": "RUT",
}


def resolve_country_context(country_code: str = "PE") -> Dict[str, str]:
    """Resuelve nombre de país e identificador tributario según código ISO (PE, CL, ...)."""
    code = (country_code or "PE").upper()
    return {
        "country_code": code,
        "country_name": COUNTRY_LABELS.get(code, code),
        "tax_id_label": TAX_ID_LABELS.get(code, "identificador tributario"),
    }


def _get_str(obj: Dict[str, Any], key: str, default: str = "") -> str:
    """
    Obtiene un valor de un diccionario y lo convierte a string de forma segura.
    
    Args:
        obj: Diccionario del cual obtener el valor
        key: Clave a buscar
        default: Valor por defecto si no existe o es None
        
    Returns:
        str: Valor convertido a string
    """
    value = obj.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def normalize_title_lines(value: Any) -> List[str]:
    """
    Normaliza títulos que pueden venir en diferentes formatos.
    Convierte a lista de strings para el template.
    
    Args:
        value: Puede ser None, lista, string con \n, o cualquier otro tipo
        
    Returns:
        List[str]: Lista de líneas del título
        
    Ejemplos:
        ["Grupo", "Económico"] → ["Grupo", "Económico"]
        "Grupo\nEconómico" → ["Grupo", "Económico"]
        None → [""]
        123 → ["123"]
    """
    if value is None:
        return [""]
    if isinstance(value, list):
        lines = [str(v) for v in value]
        return lines if lines else [""]
    if isinstance(value, str):
        lines = [s.rstrip() for s in value.split("\n")]
        return lines if lines else [""]
    return [str(value)]


def normalize_summary_items(raw: Any, desired_len: int = 10) -> List[Dict[str, Any]]:
    """
    Normaliza los items del resumen de la portada.
    Asegura que siempre haya exactamente 'desired_len' items.
    
    Args:
        raw: Lista de items del JSON (puede ser None, lista, etc.)
        desired_len: Cantidad deseada de items (default: 10)
        
    Returns:
        List[Dict]: Lista de items normalizados con estructura:
            [{"title_lines": [...], "value": "..."}, ...]
            
    Ejemplo:
        Si vienen 8 items → agrega 2 vacíos para tener 10
        Si vienen 12 items → corta a 10
        Si viene None → crea 10 items vacíos
    """
    items = []
    if isinstance(raw, list):
        for it in raw:
            if not isinstance(it, dict):
                continue
            items.append({
                "title_lines": normalize_title_lines(it.get("titleLines")),
                "value": _get_str(it, "value", ""),
            })
    while len(items) < desired_len:
        items.append({"title_lines": [""], "value": ""})
    return items[:desired_len]


def normalize_contacts(raw: Any, desired_len: int = 4) -> List[Dict[str, Any]]:
    """
    Normaliza los contactos de la portada.
    Asegura que siempre haya exactamente 'desired_len' contactos.
    
    Args:
        raw: Lista de contactos del JSON (puede ser None, lista, etc.)
        desired_len: Cantidad deseada de contactos (default: 4)
        
    Returns:
        List[Dict]: Lista de contactos normalizados con estructura:
            [{"label": "...", "value": "..."}, ...]
            
    Ejemplo:
        Si vienen 2 contactos → agrega 2 vacíos para tener 4
        Si vienen 5 contactos → corta a 4
        Si viene None → crea 4 contactos vacíos
    """
    contacts = []
    if isinstance(raw, list):
        for it in raw:
            if not isinstance(it, dict):
                continue
            contacts.append({
                "label": _get_str(it, "label", ""),
                "value": _get_str(it, "value", "")
            })
    while len(contacts) < desired_len:
        contacts.append({"label": "", "value": ""})
    return contacts[:desired_len]


# ====================================================================
# IMPORTS DE PROMPTS ORGANIZADOS POR CATEGORÍA
# ====================================================================

# Prompts de análisis de negocio
from services.service_credit_proposal_coril.src.prompts.business_analysis import (
    get_sector_analysis_prompt,
    get_product_analysis_prompt
)

# Prompts de análisis financiero
from services.service_credit_proposal_coril.src.prompts.financial_analysis import (
    get_profitability_analysis_prompt,
    get_cash_generation_analysis_prompt
)

# Prompts de solvencia y liquidez
from services.service_credit_proposal_coril.src.prompts.solvency_liquidity import (
    get_solvency_analysis_prompt,
    get_liquidity_analysis_prompt
)

# Prompts de FODA y riesgos
from services.service_credit_proposal_coril.src.prompts.foda_risks import (
    get_foda_analysis_prompt,
    get_risks_analysis_prompt
)


def extract_sources_from_text(text: str) -> Tuple[str, List[str]]:
    """
    Extrae fuentes del texto y devuelve texto limpio y lista de fuentes.
    
    Args:
        text: Texto completo con fuentes al final
        
    Returns:
        Tuple con (texto_limpio, lista_fuentes)
    """
    lines = text.split('\n')
    sources = []
    clean_lines = []
    
    in_sources_section = False
    for line in lines:
        line = line.strip()
        if line.lower().startswith(('fuentes:', 'fuente:', 'sources:', 'source:', '## fuentes:', '## fuente:', '## sources:', '## source:')):
            in_sources_section = True
            sources.append(line.replace(':', '').strip())
            continue
        
        if in_sources_section:
            if line and not line.startswith('-') and not line.startswith('•'):
                # Si ya no es una fuente, terminamos
                in_sources_section = False
                clean_lines.append(line)
            elif line:
                # Es una fuente
                sources.append(line.lstrip('-• ').strip())
        else:
            clean_lines.append(line)
    
    clean_text = '\n'.join(clean_lines).strip()
    return clean_text, sources


def _extract_log_data_text(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        stripped = data.strip()
        if not stripped:
            return ""
        try:
            parsed = json.loads(stripped)
            return _extract_log_data_text(parsed)
        except json.JSONDecodeError:
            return stripped
    if isinstance(data, list):
        parts = []
        for item in data:
            if isinstance(item, dict):
                for key in ("content", "details", "description", "text", "message", "action"):
                    if item.get(key):
                        parts.append(str(item[key]).strip())
                        break
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            elif item:
                parts.append(str(item).strip())
        return "; ".join(p for p in parts if p)
    if isinstance(data, dict):
        for key in ("content", "details", "description", "text", "message", "action"):
            if data.get(key):
                return str(data[key]).strip()
        return json.dumps(data, ensure_ascii=False)
    return str(data).strip()


def format_business_logs_for_prompt(logs: List[Dict[str, Any]], max_items: int = 20) -> str:
    """Convierte filas de business_log_events a texto para inyectar en prompts IA."""
    if not logs:
        return ""
    lines = []
    for log in logs[:max_items]:
        raw_date = log.get("date") or log.get("created_at") or ""
        if hasattr(raw_date, "strftime"):
            date_str = raw_date.strftime("%Y-%m-%d")
        else:
            date_str = str(raw_date)[:10] if raw_date else "sin fecha"
        title = (log.get("title") or "Nota").strip()
        extra = _extract_log_data_text(log.get("data"))
        line = f"- [{date_str}] {title}"
        if extra:
            line += f": {extra}"
        lines.append(line)
    return "\n".join(lines)


def load_business_log_context(business_id: str, business_log_repository) -> str:
    """Carga y formatea logs del business para prompts IA."""
    try:
        logs = business_log_repository.find_by_business_id(business_id)
        return format_business_logs_for_prompt(logs)
    except Exception as e:
        logger.warning("No se pudieron cargar business logs para %s: %s", business_id, e)
        return ""


def format_guarantees_for_prompt(guarantees: List[Dict[str, Any]], max_items: int = 30) -> str:
    """Convierte garantías del business (vía deals) a texto para prompts IA."""
    if not guarantees:
        return ""
    lines = []
    for item in guarantees[:max_items]:
        deal_title = (item.get("deal_title") or "Deal").strip()
        guarantee_type = (item.get("guarantee_type") or "OTRA").strip()
        description = (item.get("description") or "").strip()
        currency = (item.get("currency") or "PEN").strip()
        status = (item.get("status") or "ACTIVE").strip()
        appraisal = item.get("appraisal_value", 0)
        adjusted = item.get("adjusted_value", 0)
        line = f"- [Deal: {deal_title}] {guarantee_type}"
        if description:
            line += f" - {description}"
        line += f": tasación {appraisal}, ajustado {adjusted} {currency} ({status})"
        notes = (item.get("notes") or "").strip()
        if notes:
            line += f". Notas: {notes}"
        lines.append(line)
    return "\n".join(lines)


def load_guarantees_context(business_id: str, guarantee_repository) -> str:
    """Carga y formatea garantías del business para prompts IA."""
    try:
        guarantees = guarantee_repository.find_by_business_id(business_id)
        return format_guarantees_for_prompt(guarantees)
    except Exception as e:
        logger.warning("No se pudieron cargar garantías para %s: %s", business_id, e)
        return ""


def load_analysis_context(
    business_id: str,
    business_log_repository,
    guarantee_repository,
) -> Dict[str, str]:
    """Carga contexto interno (logs + garantías) para análisis IA del business."""
    return {
        "business_log_context": load_business_log_context(business_id, business_log_repository),
        "guarantees_context": load_guarantees_context(business_id, guarantee_repository),
    }


def prepare_business_data_for_analysis(business_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Prepara los datos del business para el análisis.
    
    Args:
        business_data: Datos crudos del business
        
    Returns:
        Dict con datos limpios para análisis
    """
    country_ctx = resolve_country_context(business_data.get("country", "PE"))
    logger.info("País para prompts: %s", country_ctx["country_name"])
    return {
        'company_name': business_data.get('name', 'Empresa'),
        'ruc': business_data.get('ruc', 'XXXXXXX'),
        'sector': business_data.get('sector', 'No especificado'),
        'subsector': business_data.get('subsector', 'No especificado'),
        'evaluator_id': business_data.get('evaluator_id'),
        'evaluator_name': business_data.get('evaluator_name', ''),
        **country_ctx,
    }


def validate_business_data(business_data: Dict[str, Any]) -> bool:
    """
    Valida que los datos del business sean suficientes para análisis.
    
    Args:
        business_data: Datos del business a validar
        
    Returns:
        True si es válido, False si no
    """
    required_fields = ['name', 'ruc']
    
    for field in required_fields:
        if not business_data.get(field):
            return False
    
    return True


def prepare_financial_data_for_analysis(financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara los datos financieros para el análisis.
    
    Args:
        financial_data: Datos financieros crudos
        
    Returns:
        Dict con datos financieros limpios para análisis
    """
    country_ctx = resolve_country_context(financial_data.get("country", "PE"))
    return {
        'company_name': financial_data.get('name', 'Empresa'),
        'ruc': financial_data.get('ruc', 'XXXXXXX'),
        'sector': financial_data.get('sector', 'No especificado'),
        'subsector': financial_data.get('subsector', 'No especificado'),
        'financial_indicators': financial_data.get('financial_indicators', []),
        'currency': financial_data.get('financial_statement', {}).get('currency', 'PEN'),
        'scale_type': financial_data.get('financial_statement', {}).get('scale_type', 'THOUSANDS'),
        'evaluator_id': financial_data.get('evaluator_id'),
        'evaluator_name': financial_data.get('evaluator_name', ''),
        **country_ctx,
    }


def validate_financial_data(financial_data: Dict[str, Any]) -> bool:
    """
    Valida que los datos financieros sean suficientes para análisis.
    
    Args:
        financial_data: Datos financieros a validar
        
    Returns:
        True si es válido, False si no
    """
    required_fields = ['name', 'ruc', 'financial_indicators']
    
    # Validar campos básicos
    if not all(financial_data.get(field) for field in required_fields):
        return False
    
    # Validar que haya indicadores financieros
    indicators = financial_data.get('financial_indicators', [])
    if not indicators or len(indicators) == 0:
        return False
    
    return True
