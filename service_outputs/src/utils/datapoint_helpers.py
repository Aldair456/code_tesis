"""
Shared helper functions for datapoint classification, transformation, and
structure building. Used by OutputService and DerivedCashflowService.

All functions are pure (no class methods) and receive dependencies as parameters.
"""
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Classification
# ──────────────────────────────────────────────────────────────────────────────

def is_pl_datapoint(datapoint) -> bool:
    """Determines if a datapoint belongs to P&L (Income Statement)."""
    try:
        account_type = getattr(datapoint, 'account_type', None)
        if account_type and account_type.upper() in ['PL', 'IS', 'INCOME_STATEMENT']:
            return True

        account_tags = getattr(datapoint, 'account_tags', [])
        if account_tags:
            pl_tags = ['income', 'revenue', 'expense', 'cost', 'ebitda', 'operating']
            if any(tag.lower() in pl_tags for tag in account_tags):
                return True

        account_name = getattr(datapoint, 'account_name', '').lower()
        pl_keywords = ['sales', 'revenue', 'income', 'cost', 'expense', 'ebitda',
                       'depreciation', 'amortization', 'interest', 'tax']
        return any(kw in account_name for kw in pl_keywords)
    except Exception:
        return False


def is_bs_datapoint(datapoint) -> bool:
    """Determines if a datapoint belongs to BS (Balance Sheet)."""
    try:
        account_type = getattr(datapoint, 'account_type', None)
        if account_type and account_type.upper() in ['BS', 'BALANCE_SHEET']:
            return True

        account_tags = getattr(datapoint, 'account_tags', [])
        if account_tags:
            bs_tags = ['asset', 'liability', 'equity', 'cash', 'inventory', 'receivable', 'payable']
            if any(tag.lower() in bs_tags for tag in account_tags):
                return True

        account_name = getattr(datapoint, 'account_name', '').lower()
        bs_keywords = ['cash', 'inventory', 'receivable', 'payable', 'asset',
                       'liability', 'equity', 'debt', 'investment']
        return any(kw in account_name for kw in bs_keywords)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Datapoint transformation
# ──────────────────────────────────────────────────────────────────────────────

def copy_datapoint_with_value(dp, value):
    """Creates a copy of a datapoint with a new value."""
    if hasattr(dp, 'model_copy'):
        copy = dp.model_copy()
        copy.value = value
    elif hasattr(dp, 'copy'):
        copy = dp.copy()
        copy['value'] = value
    else:
        copy = {
            'value': value,
            'account_name': getattr(dp, 'account_name', ''),
            'account_tags': getattr(dp, 'account_tags', []),
            'account_type': getattr(dp, 'account_type', ''),
            'account_value_type': getattr(dp, 'account_value_type', ''),
            'year': getattr(dp, 'year', None),
            'period': getattr(dp, 'period', None),
        }
    return copy


def create_negative_datapoints(datapoints: List) -> List:
    """Creates copies of datapoints with negated values (for subtraction in LTM)."""
    result = []
    for dp in datapoints:
        if hasattr(dp, 'model_copy'):
            neg = dp.model_copy()
            neg.value = -dp.value if dp.value is not None else None
        elif hasattr(dp, 'copy'):
            neg = dp.copy()
            neg['value'] = -dp['value'] if dp.get('value') is not None else None
        else:
            raw_val = getattr(dp, 'value', None)
            neg = {
                'value': -raw_val if raw_val is not None else None,
                'account_name': getattr(dp, 'account_name', ''),
                'account_tags': getattr(dp, 'account_tags', []),
                'account_type': getattr(dp, 'account_type', ''),
                'account_value_type': getattr(dp, 'account_value_type', ''),
                'year': getattr(dp, 'year', None),
                'period': getattr(dp, 'period', None),
            }
        result.append(neg)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Fetching & grouping
# ──────────────────────────────────────────────────────────────────────────────

def fetch_all_datapoints(repo,
                         statement_id: str,
                         account_names: Optional[List[str]] = None,
                         account_types: Optional[List[str]] = None,
                         years: Optional[List[int]] = None,
                         periods: Optional[List[str]] = None
                         ) -> List:
    """
    Fetches all datapoints with internal batch pagination and safety limit.
    repo must implement find_with_account_info_arrays(...).
    """
    batch_size = 1000
    offset = 0
    all_datapoints = []

    while True:
        batch = repo.find_with_account_info_arrays(
            statement_id=statement_id,
            account_names=account_names,
            account_types=account_types,
            years=years,
            periods=periods,
            limit=batch_size,
            offset=offset
        )
        if not batch:
            break
        all_datapoints.extend(batch)
        if len(batch) < batch_size:
            break
        if len(all_datapoints) >= 50000:
            logger.warning(f"Safety limit reached: {len(all_datapoints)} datapoints")
            break
        offset += batch_size

    logger.info(f"Fetched {len(all_datapoints)} datapoints for statement {statement_id}")
    return all_datapoints


def is_annual_datapoint_period(period) -> bool:
    """True si el datapoint pertenece a un periodo anual (2024, 2024A), no trimestral/mensual."""
    if period is None:
        return True
    if isinstance(period, int):
        return True
    if isinstance(period, str):
        p = period.strip()
        if not p:
            return True
        if p.isdigit():
            return True
        if len(p) == 5 and p[:4].isdigit() and p[4].upper() == "A":
            return True
    return False


def group_datapoints_by_year(datapoints: List) -> Tuple[Dict[int, List], List[int]]:
    """
    Groups datapoints by year, filtering out non-annual periods.
    Returns (dict year->datapoints, sorted years list).
    """
    if not datapoints:
        return {}, []

    datapoints_by_year = defaultdict(list)
    for dp in datapoints:
        year = getattr(dp, 'year', None)
        if year is None or not isinstance(year, int):
            continue
        period = getattr(dp, 'period', None)
        if not is_annual_datapoint_period(period):
            continue
        datapoints_by_year[year].append(dp)

    result = dict(datapoints_by_year)
    years = sorted(result.keys())
    return result, years


def group_datapoints_by_period(datapoints: List) -> Dict[str, List]:
    """
    Groups datapoints by period (year string or sub-annual period key).
    Returns dict period->datapoints.
    """
    if not datapoints:
        return {}

    datapoints_by_period = defaultdict(list)
    for dp in datapoints:
        year = getattr(dp, 'year', None)
        if year is None or not isinstance(year, int):
            continue
        period = getattr(dp, 'period', None)
        if period and isinstance(period, str) and period.strip():
            datapoints_by_period[period].append(dp)
        else:
            datapoints_by_period[str(year)].append(dp)

    return dict(datapoints_by_period)


def distinct_periods_from_datapoints(datapoints: List) -> List[str]:
    """Extrae períodos únicos ordenados desde datapoints."""
    periods = {
        str(getattr(dp, "period", "")).strip()
        for dp in datapoints
        if getattr(dp, "period", None) and str(getattr(dp, "period", "")).strip()
    }
    return sorted(periods)


def resolve_trailing_compositions_from_datapoints(
    datapoints: List,
    statement_periodicity: Optional[str] = None,
) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str], Optional[List[Dict]]]:
    """
    Recalcula LTM y anualizado desde períodos reales en datapoints.
    Retorna (ltm_title, ltm_composition, ma_title, ma_composition).
    """
    from services.service_outputs.src.utils.calculate_ltm import (
        get_ltm_composition as compute_ltm,
        get_monthly_annualized_composition,
    )

    distinct_periods = distinct_periods_from_datapoints(datapoints)
    if not distinct_periods:
        return None, None, None, None

    is_monthly = (statement_periodicity or "").lower() == "mensual"
    ltm_title = None
    ltm_composition = None
    if not is_monthly:
        ltm_result = compute_ltm(distinct_periods)
        if ltm_result and ltm_result[0] and ltm_result[1]:
            ltm_title, ltm_composition = ltm_result

    ma_title, ma_composition = get_monthly_annualized_composition(distinct_periods)
    if not ma_composition:
        ma_title = None

    return ltm_title, ltm_composition, ma_title, ma_composition


# ──────────────────────────────────────────────────────────────────────────────
# Financial statement composition readers
# ──────────────────────────────────────────────────────────────────────────────

def get_ltm_composition(fs_repo, statement_id: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Reads ltm_composition and ltm_title from the financial statement.
    Returns (composition_list, title) or (None, title).
    """
    from common.exceptions.exceptions import NotFoundError

    fs = fs_repo.find_by_id(statement_id)
    if not fs:
        raise NotFoundError(f"Financial statement {statement_id} not found")

    ltm_composition = getattr(fs, 'ltm_composition', None)
    ltm_title = getattr(fs, 'ltm_title', None)

    if isinstance(ltm_composition, str) and ltm_composition.strip():
        try:
            ltm_composition = json.loads(ltm_composition)
        except json.JSONDecodeError:
            ltm_composition = None

    if not isinstance(ltm_composition, list) or len(ltm_composition) == 0:
        ltm_composition = None

    return ltm_composition, ltm_title


def get_monthly_annualized_composition(fs_repo, statement_id: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Reads monthly_annualized_composition and monthly_annualized_title from the financial statement.
    Returns (composition_list, title) or (None, title).
    """
    from common.exceptions.exceptions import NotFoundError

    fs = fs_repo.find_by_id(statement_id)
    if not fs:
        raise NotFoundError(f"Financial statement {statement_id} not found")

    ma_composition = getattr(fs, 'monthly_annualized_composition', None)
    ma_title = getattr(fs, 'monthly_annualized_title', None)

    if isinstance(ma_composition, str) and ma_composition.strip():
        try:
            ma_composition = json.loads(ma_composition)
        except Exception:
            ma_composition = None

    if not isinstance(ma_composition, list) or len(ma_composition) == 0:
        ma_composition = None

    return ma_composition, ma_title


def count_months_in_composition(composition: List[Dict]) -> int:
    """Counts distinct months covered by the composition periods."""
    try:
        from services.service_outputs.src.utils.calculate_ltm import decompose_monthly_period
        all_months = set()
        for item in composition:
            period = item.get("period", "")
            months = decompose_monthly_period(period)
            all_months.update(months)
        return len(all_months)
    except Exception as e:
        logger.warning(f"Could not count months in composition: {e}. Assuming 12.")
        return 12


def find_latest_composition_period(composition: List[Dict]) -> Optional[str]:
    """Returns the period in the composition that has the most recent month."""
    try:
        from services.service_outputs.src.utils.calculate_ltm import (
            decompose_monthly_period, convert_months_to_ints
        )
        latest_period = None
        latest_month = -1
        for item in composition:
            period = item.get("period", "")
            months = decompose_monthly_period(period)
            if not months:
                continue
            max_month = max(convert_months_to_ints({period: months})[period])
            if max_month > latest_month:
                latest_month = max_month
                latest_period = period
        return latest_period
    except Exception as e:
        logger.warning(f"Error finding latest composition period: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Period resolution (composition label vs datapoint key in BD)
# ──────────────────────────────────────────────────────────────────────────────

def resolve_datapoint_period(
    period: str,
    datapoints_by_period: Dict[str, List],
) -> Optional[str]:
    """
    Resuelve la clave de período usada en financial_datapoints.
    Ej.: composición '2026Q1' cuando los datos están bajo '2026' (YTD anual).
    """
    if not period:
        return None

    keys = set(datapoints_by_period.keys())
    if period in keys and datapoints_by_period[period]:
        return period

    year = period[:4] if len(period) >= 4 and period[:4].isdigit() else None
    if year and year in keys and datapoints_by_period[year]:
        return year

    bare = period.rstrip("A")
    if bare in keys and datapoints_by_period[bare]:
        return bare
    accumulated = f"{bare}A"
    if accumulated in keys and datapoints_by_period[accumulated]:
        return accumulated

    return None


# ──────────────────────────────────────────────────────────────────────────────
# LTM structure builders
# ──────────────────────────────────────────────────────────────────────────────

def build_ltm_pl_datapoints(ltm_composition: List[Dict],
                            datapoints_by_period: Dict[str, List]) -> List:
    """Builds P&L datapoints applying the LTM formula (sum/subtract by period)."""
    ltm_pl = []
    for item in ltm_composition:
        period = item["period"]
        is_positive = item["positive"]

        resolved = resolve_datapoint_period(period, datapoints_by_period)
        period_dps = datapoints_by_period.get(resolved) if resolved else None
        if not period_dps:
            logger.warning(f"LTM period {period} not found in datapoints")
            continue

        pl_dps = [dp for dp in period_dps if is_pl_datapoint(dp)]
        if not pl_dps:
            continue

        if is_positive:
            ltm_pl.extend(pl_dps)
        else:
            ltm_pl.extend(create_negative_datapoints(pl_dps))

    return ltm_pl


def build_ltm_structure(ltm_composition: List[Dict],
                        datapoints_by_period: Dict[str, List],
                        ltm_title: str) -> Dict[str, List]:
    """
    Builds the complete LTM datapoints structure for the calculator.
    P&L: formula-based (sum/subtract). BS: from ltm_title period. Plus annual periods.
    """
    ltm_period_key = f"LTM_{ltm_title}"

    ltm_pl = build_ltm_pl_datapoints(ltm_composition, datapoints_by_period)
    bs_key = resolve_datapoint_period(ltm_title, datapoints_by_period) or ltm_title
    bs_dps = [dp for dp in datapoints_by_period.get(bs_key, [])
              if is_bs_datapoint(dp)]

    combined = ltm_pl + bs_dps
    structure = {}
    if combined:
        structure[ltm_period_key] = combined

    # Include annual periods for formulas that reference them
    annual = {p: dps for p, dps in datapoints_by_period.items()
              if p and isinstance(p, str) and p.isdigit()}
    structure.update(annual)

    logger.info(f"LTM structure: {len(structure)} periods, key={ltm_period_key}")
    return structure


# ──────────────────────────────────────────────────────────────────────────────
# Monthly Annualized structure builders
# ──────────────────────────────────────────────────────────────────────────────

def build_monthly_pl_datapoints(ma_composition: List[Dict],
                                datapoints_by_period: Dict[str, List],
                                factor: float) -> List:
    """
    Builds P&L datapoints for monthly annualized period.
    Applies composition formula (sum/subtract) and annualization factor.
    """
    ma_pl = []
    for item in ma_composition:
        period = item["period"]
        is_positive = item["positive"]

        resolved = resolve_datapoint_period(period, datapoints_by_period)
        period_dps = datapoints_by_period.get(resolved) if resolved else None
        if not period_dps:
            logger.warning(f"MA period {period} not found in datapoints")
            continue

        pl_dps = [dp for dp in period_dps if is_pl_datapoint(dp)]
        if not pl_dps:
            continue

        # Scale each datapoint by annualization factor
        scaled = []
        for dp in pl_dps:
            value = getattr(dp, 'value', None) if hasattr(dp, 'value') else dp.get('value')
            scaled_value = (value * factor) if value is not None else None
            scaled.append(copy_datapoint_with_value(dp, scaled_value))

        if is_positive:
            ma_pl.extend(scaled)
        else:
            ma_pl.extend(create_negative_datapoints(scaled))

    return ma_pl


def build_monthly_annualized_structure(ma_composition: List[Dict],
                                       datapoints_by_period: Dict[str, List],
                                       ma_title: str,
                                       factor: float) -> Dict[str, List]:
    """
    Builds the complete monthly annualized datapoints structure.
    P&L: composition + factor. BS: snapshot from latest period. Plus annual periods.
    """
    ma_period_key = f"MA_{ma_title}"

    ma_pl = build_monthly_pl_datapoints(ma_composition, datapoints_by_period, factor)

    # BS: snapshot from latest period (strip trailing 'A')
    latest_period = find_latest_composition_period(ma_composition)
    bs_period = latest_period.rstrip("A") if latest_period else None
    bs_dps = []
    if bs_period:
        bs_key = resolve_datapoint_period(bs_period, datapoints_by_period) or bs_period
        bs_dps = [dp for dp in datapoints_by_period.get(bs_key, [])
                  if is_bs_datapoint(dp)]
        if not bs_dps and latest_period:
            alt_key = resolve_datapoint_period(latest_period, datapoints_by_period) or latest_period
            if alt_key != bs_key:
                bs_dps = [dp for dp in datapoints_by_period.get(alt_key, [])
                          if is_bs_datapoint(dp)]

    combined = ma_pl + bs_dps
    structure = {}
    if combined:
        structure[ma_period_key] = combined

    # Include annual periods
    annual = {p: dps for p, dps in datapoints_by_period.items()
              if p and isinstance(p, str) and p.isdigit()}
    structure.update(annual)

    logger.info(f"MA structure: {len(structure)} periods, key={ma_period_key}")
    return structure
