import logging
from itertools import combinations
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Reglas para deducir trimestres faltantes a partir de acumulados (QnA) y trimestres sueltos.
PERIOD_DEDUCTION_RULES = [
    (["Q2A", "Q1"], "Q2"),
    (["Q2A", "Q2"], "Q1"),
    (["Q3A", "Q2A"], "Q3"),
    (["Q3A", "Q1", "Q2"], "Q3"),
    (["Q3A", "Q1", "Q3"], "Q2"),
    (["Q3A", "Q3", "Q2"], "Q1"),
    (["Q3A", "Q3", "Q1"], "Q2"),
    (["", "Q3A"], "Q4"),
    (["", "Q2A", "Q4"], "Q3"),
    (["", "Q2A", "Q3"], "Q4"),
    (["", "Q4", "Q3", "Q2"], "Q1"),
    (["", "Q4", "Q3", "Q1"], "Q2"),
    (["", "Q1", "Q2", "Q3"], "Q4"),
]


def deduce_all(available_suffixes: List[str]) -> List[Tuple]:
    """Deduce períodos posibles basado en sufijos disponibles y PERIOD_DEDUCTION_RULES."""
    try:
        available = set(available_suffixes)
        deductions = []
        changed = True
        while changed:
            changed = False
            for inputs, result in PERIOD_DEDUCTION_RULES:
                if all(inp in available for inp in inputs) and result not in available:
                    deductions.append((inputs, result))
                    available.add(result)
                    changed = True
        return deductions
    except Exception as e:
        logger.error(f"Error en deducción de períodos: {e}")
        return []


def get_suffixes_of_periods(periods: List[str], year: str) -> List[str]:
    """Obtiene sufijos de períodos (ej. Q1, Q2A) para un año específico."""
    try:
        suffixes = []
        for period in periods:
            if (
                isinstance(period, str)
                and len(period) >= 4
                and period[:4].isdigit()
                and period[:4] == year
            ):
                suffixes.append(period[4:])
        return suffixes
    except Exception as e:
        logger.error(f"Error obteniendo sufijos para año {year}: {e}")
        return []


def is_consecutive_4(seq):
    return len(seq) == 4 and all(seq[i] + 1 == seq[i + 1] for i in range(3))


def find_best_consecutive_4_dict(lists_dict):
    keys = list(lists_dict.keys())
    sets = [set(lists_dict[k]) for k in keys]
    n = len(keys)
    best_result = []
    best_sequence = []

    for add_count in range(1, n + 1):
        for add_indices in combinations(range(n), add_count):
            add_union = set()
            for i in add_indices:
                add_union |= sets[i]

            remaining = [i for i in range(n) if i not in add_indices]
            for sub_count in range(len(remaining) + 1):
                for sub_indices in combinations(remaining, sub_count):
                    if all(sets[j].issubset(add_union) for j in sub_indices):
                        sub_union = set()
                        for j in sub_indices:
                            sub_union |= sets[j]

                        result = sorted(add_union - sub_union)

                        if is_consecutive_4(result):
                            if not best_sequence or result > best_sequence:
                                best_sequence = result
                                # Build result list with dicts showing added/subtracted
                                res = []
                                for i in add_indices:
                                    res.append({"period": keys[i], "positive": True})
                                for j in sub_indices:
                                    res.append({"period": keys[j], "positive": False})
                                best_result = res
                                title_number = max(result)

    if not best_result:
        return None, None

    title = str((title_number - 1) // 4) + "Q" + str((title_number - 1) % 4 + 1)
    return title, best_result


def decompose_period(period: str) -> List[str]:
    if period.isdigit():  # Year
        year = int(period)
        return [f"{year}Q{i}" for i in range(1, 5)]
    elif period.endswith("A"):  # Accumulated quarter
        year = int(period[:4])
        q = int(period[5])
        return [f"{year}Q{i}" for i in range(1, q + 1)]
    else:  # Specific quarter
        return [period]


def build_period_composition_map(periods: List[str]) -> Dict[str, List[str]]:
    return {period: decompose_period(period) for period in periods}


def convert_quarters_to_ints(period_map: Dict[str, List[str]]) -> Dict[str, List[int]]:
    def quarter_to_int(q: str) -> int:
        year = int(q[:4])
        quarter = int(q[5])
        return year * 4 + quarter

    result = {}
    for period, quarters in period_map.items():
        result[period] = [quarter_to_int(q) for q in quarters]
    return result


def get_ltm_composition(
    periods: List[str],
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """Calcula composición LTM. Retorna (title, composition) o (None, None)."""
    try:
        if not periods:
            return None, None
        period_comp = build_period_composition_map(periods)
        period_ints = convert_quarters_to_ints(period_comp)
        return find_best_consecutive_4_dict(period_ints)
    except Exception as e:
        logger.error(f"Error calculando LTM: {e}")
        return None, None


# ── Monthly annualization ─────────────────────────────────────────────────────

def decompose_monthly_period(period: str) -> List[str]:
    """
    Descompone cualquier período en meses individuales 'YYYYMm'.
    Soporta: anual ("2025"), trimestral individual ("2025Q3"),
    trimestral acumulado ("2025Q3A"), mensual individual ("2025M9"),
    mensual acumulado ("2025M9A").
    """
    year = int(period[:4])
    rest = period[4:]

    if not rest:
        # Anual: todos los meses del año
        return [f"{year}M{m}" for m in range(1, 13)]

    accumulated = rest.endswith("A")

    if "Q" in rest:
        q = int(rest[1])  # "Q3" → 3, "Q3A" → 3
        if accumulated:
            # Q3A = Q1+Q2+Q3 = meses 1..9
            end_month = q * 3
            return [f"{year}M{m}" for m in range(1, end_month + 1)]
        else:
            # Q3 = meses 7,8,9
            start_month = (q - 1) * 3 + 1
            end_month = q * 3
            return [f"{year}M{m}" for m in range(start_month, end_month + 1)]

    if "M" in rest:
        m = int(rest[1:].rstrip("A"))  # "M9"→9, "M9A"→9, "M10A"→10
        if accumulated:
            return [f"{year}M{i}" for i in range(1, m + 1)]
        else:
            return [f"{year}M{m}"]

    return []


def build_monthly_composition_map(periods: List[str]) -> Dict[str, List[str]]:
    return {period: decompose_monthly_period(period) for period in periods}


def convert_months_to_ints(period_map: Dict[str, List[str]]) -> Dict[str, List[int]]:
    """Encoding: year * 12 + (month - 1), análogo al trimestral year * 4 + (quarter - 1)."""
    def month_to_int(m: str) -> int:
        year = int(m[:4])
        month = int(m[5:])  # "2025M9" → 9, "2025M12" → 12
        return year * 12 + (month - 1)

    result = {}
    for period, months in period_map.items():
        result[period] = [month_to_int(mo) for mo in months]
    return result


def find_best_consecutive_months(lists_dict: Dict[str, List[int]]) -> tuple:
    """
    Busca la mejor combinación de períodos (solo positivos, sin resta) que forme
    la secuencia consecutiva más larga de hasta 12 meses.
    Los períodos seleccionados no pueden solaparse entre sí.
    Gana: la secuencia más larga; si empatan, la más reciente.
    Retorna (title, composition) donde title = "YYYYMm" (sin sufijo A).
    """
    keys = list(lists_dict.keys())
    sets = [set(lists_dict[k]) for k in keys]
    n = len(keys)
    best_result = []
    best_sequence = []

    for count in range(1, n + 1):
        for indices in combinations(range(n), count):
            # Verificar que los períodos no se solapen
            union = set()
            has_overlap = False
            for i in indices:
                if sets[i] & union:
                    has_overlap = True
                    break
                union |= sets[i]

            if has_overlap:
                continue

            result = sorted(union)

            if not result:
                continue
            if len(result) > 12:
                continue
            # Debe ser completamente consecutivo (sin huecos)
            if not all(result[i] + 1 == result[i + 1] for i in range(len(result) - 1)):
                continue

            is_better = (
                not best_sequence
                or max(result) > max(best_sequence)
                or (max(result) == max(best_sequence) and len(result) > len(best_sequence))
            )
            if is_better:
                best_sequence = result
                best_result = [{"period": keys[i], "positive": True} for i in indices]

    if not best_result:
        return None, None

    max_int = max(best_sequence)
    year = max_int // 12
    month = max_int % 12 + 1
    title = f"{year}M{month}"
    return title, best_result


def period_month_span(period: str) -> Tuple[Optional[int], Optional[int], int]:
    """Retorna (mes_inicio, mes_fin, n_meses) usando encoding year*12+(month-1)."""
    months = decompose_monthly_period(period)
    if not months:
        return None, None, 0
    ints = convert_months_to_ints({period: months})[period]
    return min(ints), max(ints), len(set(ints))


def is_full_calendar_year_period(period: str) -> bool:
    """True si el período cubre exactamente enero–diciembre de un mismo año."""
    start, end, n_months = period_month_span(period)
    if n_months != 12 or start is None or end is None:
        return False
    year = end // 12
    return start == year * 12 and end == year * 12 + 11


def _periods_for_year(periods: List[str], year: int) -> List[str]:
    year_str = str(year)
    return [
        p for p in periods
        if isinstance(p, str) and len(p) >= 4 and p[:4] == year_str
    ]


def _infer_sole_trailing_annual_ytd(
    periods: List[str],
    trail_year: int,
) -> Optional[Tuple[str, List[Dict]]]:
    """
    YTD guardado como período anual 'YYYY' sin trimestres/meses en ese año.
    Si el historial usa trimestres o meses, se asume Q1 (3 meses) para anualizar.
    La composición usa 'YYYYQ1' y el lookup de datapoints resuelve a 'YYYY'.
    """
    year_str = str(trail_year)
    year_periods = _periods_for_year(periods, trail_year)
    if len(year_periods) != 1 or year_periods[0] != year_str:
        return None
    if not any(("Q" in p or "M" in p) for p in periods if p != year_str):
        return None
    return f"{trail_year}M3", [{"period": f"{trail_year}Q1", "positive": True}]


def _explicit_partial_trailing_periods(
    periods: List[str],
    trail_year: int,
) -> Optional[List[str]]:
    """
    Períodos parciales explícitos (Q/M, <12 meses) en el año trail cuando también
    existe el bucket anual 'YYYY'. Ej: ['2026', '2026Q1'] → ['2026Q1'].
    """
    year_str = str(trail_year)
    in_year = _periods_for_year(periods, trail_year)
    if year_str not in in_year:
        return None
    partials = sorted(
        p for p in in_year
        if p != year_str and period_month_span(p)[2] < 12
    )
    return partials or None


def get_trailing_annualized_composition(
    periods: List[str],
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """
    Anualiza solo el último tramo parcial en orden cronológico (no de subida).

    - Años completos (ej. "2024", "2025") no se anualizan.
    - Si el borde cronológico es un año cerrado, no hay anualizado.
    - Si hay un parcial al final (trimestral/mensual/YTD), retorna su composición.
    - Solo considera períodos del año del tramo final (no mezcla 2024 si el último dato es 2026).

    Retorna (title, composition) con title = "YYYYMm" (mes fin sin sufijo A).
    """
    if not periods:
        return None, None

    spans = []
    for period in periods:
        start, end, n_months = period_month_span(period)
        if n_months == 0 or start is None or end is None:
            continue
        spans.append({"period": period, "start": start, "end": end, "n_months": n_months})

    if not spans:
        return None, None

    max_end = max(s["end"] for s in spans)
    trail_year = max_end // 12
    year_start_int = trail_year * 12
    year_end_int = trail_year * 12 + 11

    if any(
        is_full_calendar_year_period(s["period"]) and s["end"] == max_end
        for s in spans
    ):
        ytd = _infer_sole_trailing_annual_ytd(periods, trail_year)
        if ytd:
            return ytd
        explicit_partials = _explicit_partial_trailing_periods(periods, trail_year)
        if explicit_partials:
            trimmed = [p for p in periods if p != str(trail_year)]
            return get_trailing_annualized_composition(trimmed)
        return None, None

    in_trail_year = [
        s for s in spans
        if s["start"] >= year_start_int and s["end"] <= year_end_int
    ]
    if not in_trail_year:
        return None, None

    lists_dict = {
        s["period"]: list(range(s["start"], s["end"] + 1))
        for s in in_trail_year
    }

    keys = list(lists_dict.keys())
    sets = [set(lists_dict[k]) for k in keys]
    n = len(keys)
    best_result: Optional[List[Dict]] = None
    best_sequence: Optional[List[int]] = None

    for count in range(1, n + 1):
        for indices in combinations(range(n), count):
            union: set = set()
            has_overlap = False
            for i in indices:
                if sets[i] & union:
                    has_overlap = True
                    break
                union |= sets[i]
            if has_overlap:
                continue

            result = sorted(union)
            if not result or max(result) != max_end:
                continue
            if not all(result[i] + 1 == result[i + 1] for i in range(len(result) - 1)):
                continue
            if len(result) > 12:
                continue
            if (
                len(result) == 12
                and result[0] == year_start_int
                and result[-1] == year_end_int
            ):
                return None, None

            if not best_sequence or len(result) > len(best_sequence):
                best_sequence = result
                best_result = [{"period": keys[i], "positive": True} for i in indices]

    if not best_result or not best_sequence:
        return None, None

    month = max_end % 12 + 1
    title = f"{trail_year}M{month}"
    return title, best_result


def get_monthly_annualized_composition(periods: List[str]) -> tuple:
    """
    Composición para anualizar el último tramo parcial cronológico.
    Retorna (title, composition) con title = "YYYYMm" (sin sufijo A), e.g. "2026M5".
    """
    return get_trailing_annualized_composition(periods)


def count_months_in_composition(composition: List[Dict]) -> int:
    """Cuenta meses distintos cubiertos por la composición."""
    all_months = set()
    for item in composition:
        period = item.get("period", "")
        all_months.update(decompose_monthly_period(period))
    return len(all_months)


def find_latest_composition_period(composition: List[Dict]) -> Optional[str]:
    """Período de la composición con el mes más reciente."""
    latest_period = None
    latest_month = -1
    for item in composition:
        period = item.get("period", "")
        months = decompose_monthly_period(period)
        if not months:
            continue
        ints = convert_months_to_ints({period: months})[period]
        max_month = max(ints)
        if max_month > latest_month:
            latest_month = max_month
            latest_period = period
    return latest_period

