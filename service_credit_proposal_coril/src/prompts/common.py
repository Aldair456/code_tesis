"""Utilidades compartidas para construcción de prompts IA."""


def business_log_prompt_section(business_log_context: str = "") -> str:
    """Bloque opcional de contexto interno del analista."""
    ctx = (business_log_context or "").strip()
    if not ctx:
        return ""
    return (
        "\nContexto interno del analista sobre la empresa "
        "(úsalo para personalizar el análisis cuando sea relevante; "
        "no inventes datos que no estén aquí):\n"
        f"{ctx}\n"
    )


def guarantees_prompt_section(guarantees_context: str = "") -> str:
    """Bloque opcional de garantías registradas (vía deals del business)."""
    ctx = (guarantees_context or "").strip()
    if not ctx:
        return ""
    return (
        "\nGarantías registradas de la empresa (vía sus deals; "
        "úsalo para cobertura/colateral cuando sea relevante; "
        "no inventes garantías que no estén aquí):\n"
        f"{ctx}\n"
    )


def internal_context_sections(
    business_log_context: str = "",
    guarantees_context: str = "",
) -> str:
    """Combina bloques opcionales de contexto interno para prompts IA."""
    return "".join(
        part
        for part in (
            business_log_prompt_section(business_log_context),
            guarantees_prompt_section(guarantees_context),
        )
        if part
    )
