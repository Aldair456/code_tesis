"""
Servicio para armar el body_for_create a partir de parallel_results o evento combinado.
Usa BusinessAnalysisService para datos del negocio (header, client_name, etc.).
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from common.exceptions.exceptions import BadRequestError

logger = logging.getLogger(__name__)


# Título por defecto cuando proposal_type es TS (informe general, sin CORIL).
DEFAULT_TITLE_TS = "INFORME  DE RIESGOS"
# Título por defecto cuando es CORIL u otro tipo.
DEFAULT_TITLE_CORIL = "ALFIN BANCO | INFORME DE RIESGOS"


class CreditMemoBuilderService:
    """
    Arma el body listo para create_credit_proposal_coril a partir del output
    del estado Parallel (parallel_results) o del output de CombineResults.
    Si se inyecta evaluator_routes_repository, consulta evaluator_routes por evaluator_id
    y usa título "General" (sin CORIL) cuando proposal_type es TS.
    """

    def __init__(
        self,
        business_analysis_service,
        financial_analysis_repository=None,
        evaluator_routes_repository=None,
    ):
        self.business_analysis_service = business_analysis_service
        self.financial_analysis_repository = financial_analysis_repository
        self.evaluator_routes_repository = evaluator_routes_repository

    def build_body_for_create(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construye body_for_create para pasarlo al lambda create_credit_proposal_coril.

        Input (uno de los dos):
        - parallel_results (array) + business_id: output del estado Parallel.
        - business_id + producto_demanda_mercado, sector_economico, ... en la raíz: output de CombineResults.

        Campos opcionales: total_amount, currency, credit_type, term, guarantee, report_title,
        credit_memo_id, user_id, deal_id, proposal_number.
        """
        clean_event = self._remove_metadata(event)
        business_id = clean_event.get("business_id")
        if not business_id:
            raise BadRequestError("business_id es requerido.")

        business = self.business_analysis_service.get_business_by_id(business_id)
        if not business:
            logger.warning("Business no encontrado: %s, usando valores por defecto", business_id)
            client_name = "Cliente"
            client_ruc = "-"
            header = {
                "economicGroup": "-",
                "constitutionDate": "-",
                "clientSince": "-",
                "companySize": "-",
                "sbsClassification": "",
                "approvalLevel": "-",
            }
            evaluator_id = None
        else:
            client_name = business.get("legal_name") or business.get("name") or "Cliente"
            client_ruc = business.get("ruc") or "-"
            header = self._build_header_from_business(business)
            evaluator_id = business.get("evaluator_id")

        total_amount = clean_event.get("total_amount")
        currency = clean_event.get("currency", "USD")
        credit_type = clean_event.get("credit_type")
        term = clean_event.get("term")
        guarantee = clean_event.get("guarantee")

        # Título por defecto: si el evento trae report_title se respeta; si no, se usa según evaluator_routes.
        # Si proposal_type es TS → título "General" (sin CORIL); si no → título estándar.
        default_title = DEFAULT_TITLE_CORIL
        if evaluator_id and self.evaluator_routes_repository:
            proposal_type = self.evaluator_routes_repository.get_proposal_type(evaluator_id)
            if proposal_type and str(proposal_type).upper() == "TS":
                default_title = DEFAULT_TITLE_TS
        report_title = clean_event.get("report_title", default_title)

        parallel_results = clean_event.get("parallel_results")
        if parallel_results:
            credit_memo_content = self._build_credit_memo_content(parallel_results)
        else:
            credit_memo_content = self._credit_memo_from_combined_output(clean_event)

        sections = self._build_proposal_data_sections(credit_memo_content)
        risk_proposal = self._build_risk_proposal(
            total_amount=total_amount,
            currency=currency,
            credit_type=credit_type,
            term=term,
            guarantee=guarantee,
        )

        # Buscar información financiera si tenemos el repositorio
        financial_info = {}
        
        if self.financial_analysis_repository:
            try:
                financial_data = self.financial_analysis_repository.get_financial_data_by_business_id(business_id)

                # Obtener datapoints directos (cuentas) tambien
                fin_result = self.financial_analysis_repository.get_financial_stament_Datapoints(business_id)
                datapoints = fin_result.get("datapoints") if isinstance(fin_result, dict) else fin_result
                ltm_composition = fin_result.get("ltm_composition", []) if isinstance(fin_result, dict) else []
                ltm_title_db = fin_result.get("ltm_title", "") if isinstance(fin_result, dict) else ""
                
                if financial_data:
                    financial_info = self._process_financial_data(datapoints, ltm_composition=ltm_composition, ltm_title_db=ltm_title_db)
            
            except Exception as e:
                logger.error(f"Error obteniendo datos financieros: {str(e)}", exc_info=True)

        proposal_data = {
            "use_template_design": 1,
            "header": header,
            "reportTitle": report_title,
            "clientName": client_name,
            "clientRuc": client_ruc,
            "riskProposal": risk_proposal,
            "sections": sections,
        }
        
        # Merge financial info into proposal_data
        if financial_info:
            proposal_data.update(financial_info)
        
        # Override with event financial_results like before if needed (though now we fetch it)
        if clean_event.get("financial_results"):
             proposal_data["financial_results"] = clean_event.get("financial_results")

        return {
            "credit_memo_id": clean_event.get("credit_memo_id"),
            "business_id": business_id,
            "proposal_data": proposal_data,
            "user_id": clean_event.get("user_id"),
            "deal_id": clean_event.get("deal_id"),
            "total_amount": total_amount,
            "currency": currency,
            "proposal_number": clean_event.get("proposal_number"),
        }

    @staticmethod
    def _format_number(value: float) -> str:
        return "{:,.0f}".format(value)

    @staticmethod
    def _format_percentage(value: float, total: float) -> str:
        if total == 0 or value == 0:
            return "0,00%"
        
        percentage = (value / total) * 100
        
        # Manejo de casos extremos (replicando frontend)
        if abs(percentage) < 0.01 and percentage != 0:
            return "0,01%"
        if abs(percentage) > 9999:
            return "∞%"
            
        return "{:.2f}%".format(percentage).replace(".", ",")

    def _calculate_ltm(self, indicator_name: str, datapoints: List[Dict[str, Any]], last_period: str, ltm_composition: List[Dict[str, Any]] = None) -> float:
        """
        Calculates LTM. If ltm_composition is provided (from FS official), use it.
        Otherwise falls back to YTD logic: LTM = Current_YTD + (Prev_Annual - Prev_YTD)
        """
        if ltm_composition:
            ltm_value = 0.0
            for comp in ltm_composition:
                p = comp.get("period")
                pos = comp.get("positive", True)
                dp = next((d for d in datapoints if d.get('indicator_name') == indicator_name and d.get('period') == p), None)
                if dp:
                    ltm_value += dp.get('value', 0) if pos else -dp.get('value', 0)
            return ltm_value

        if not last_period or 'Q' not in last_period:
            return 0.0
            
        try:
            year = int(last_period[:4])
            q_str = "".join(filter(str.isdigit, last_period[last_period.find('Q')+1:]))
            quarter = int(q_str)
        except (ValueError, IndexError):
            return 0.0

        current_ytd = next((d.get('value',0) for d in datapoints if d.get('indicator_name') == indicator_name and d.get('period') == last_period), 0.0)
        
        prev_year = year - 1
        dp_prev_annual = next((d for d in datapoints if d.get('indicator_name') == indicator_name and d.get('period') in [str(prev_year), f"{prev_year}A"]), None)
        
        prev_ytd_candidates = [f"{prev_year}Q{quarter}", f"{prev_year}Q{quarter}A"]
        dp_prev_ytd = next((d for d in datapoints if d.get('indicator_name') == indicator_name and d.get('period') in prev_ytd_candidates), None)

        if dp_prev_annual and dp_prev_ytd:
            return current_ytd + (dp_prev_annual.get('value', 0) - dp_prev_ytd.get('value', 0))
        
        return current_ytd

    def _get_ltm_value_by_tag(self, datapoints: List[Dict[str, Any]], last_period: str, tag: str, ltm_composition: List[Dict[str, Any]] = None) -> float:
        def get_tag_val(period):
            return sum(dp.get("value", 0) for dp in datapoints if dp.get("period") == period and tag in (dp.get("tags") or []))

        if ltm_composition:
            ltm_value = 0.0
            for comp in ltm_composition:
                p = comp.get("period")
                pos = comp.get("positive", True)
                val = get_tag_val(p)
                ltm_value += val if pos else -val
            return ltm_value

        if not last_period or 'Q' not in last_period: return 0.0
        try:
            year = int(last_period[:4])
            q_str = "".join(filter(str.isdigit, last_period[last_period.find('Q')+1:]))
            quarter = int(q_str)
        except: return 0.0

        current_ytd = get_tag_val(last_period)
        prev_year = year - 1
        prev_annual_val = get_tag_val(str(prev_year)) or get_tag_val(f"{prev_year}A")
        prev_ytd_val = 0
        for p in [f"{prev_year}Q{quarter}", f"{prev_year}Q{quarter}A"]:
            v = get_tag_val(p)
            if v != 0:
                prev_ytd_val = v
                break

        if prev_annual_val != 0 and prev_ytd_val != 0:
            return current_ytd + (prev_annual_val - prev_ytd_val)
        
        return current_ytd

    @staticmethod
    def _period_to_closing_date(period: str) -> Optional[datetime]:
        """Mapea period a fecha de cierre (como front: 2024→31dic, 2025Q1→31mar, 2025Q3→30sep)."""
        if not period:
            return None
        p = str(period).strip()
        if "Q" in p.upper():
            try:
                year = int(p[:4])
                q = p.upper().split("Q")[-1]
                q = "".join(c for c in q if c.isdigit()) or "1"
                qnum = int(q)
                if qnum == 1:
                    return datetime(year, 3, 31)
                if qnum == 2:
                    return datetime(year, 6, 30)
                if qnum == 3:
                    return datetime(year, 9, 30)
                if qnum == 4:
                    return datetime(year, 12, 31)
                return datetime(year, 12, 31)
            except (ValueError, IndexError):
                return None
        try:
            year = int(p[:4]) if len(p) >= 4 else int(p)
            return datetime(year, 12, 31)
        except ValueError:
            return None

    def _get_last_available_period(self, datapoints: List[Dict[str, Any]]) -> str:
        """Último periodo disponible = el más reciente por fecha de cierre (como front getLastAvailablePeriod).
        Año completo '2024' → 31 dic; trimestral '2025Q3' → 30 sep. Orden descendente, primer periodo."""
        if not datapoints:
            return ""
        seen = set()
        periods_with_dates = []
        for d in datapoints:
            p = d.get("period")
            if p is None or p in seen:
                continue
            seen.add(p)
            date = self._period_to_closing_date(str(p))
            if date:
                periods_with_dates.append((p, date))
        if not periods_with_dates:
            return ""
        periods_with_dates.sort(key=lambda x: x[1], reverse=True)
        return str(periods_with_dates[0][0])

    def _process_financial_data(self, datapoints: List[Dict[str, Any]], ltm_composition: List[Dict[str, Any]] = None, ltm_title_db: str = "") -> Dict[str, Any]:
        """
        Procesa los datapoints financieros crudos para estructurarlos
        en las secciones requeridas por el template (financial_results, balance_general, cash_flow).
        """
        print("datapoints", datapoints)
        if not datapoints:
            return {}

        # 1. Agrupar por categoría
        grouped = {
            "financial_results": [], 
            "balance_general": [],   
            "cash_flow": []          
        }
        
        years = set()
        
        category_map = {
            "PL": "financial_results",
            "BS": "balance_general",
            "FC": "cash_flow",
            "ESTADO DE RESULTADOS": "financial_results",
            "BALANCE GENERAL": "balance_general",
            "FLUJO DE CAJA": "cash_flow"
        }

        # Values by year and account name for quick access
        values_by_year_name = {}

        for dp in datapoints:
            y = str(dp.get("year"))
            p = str(dp.get("period"))
            if y and (p == y or p == f"{y}A"):
                years.add(y)
                if y not in values_by_year_name:
                    values_by_year_name[y] = {}
                name = dp.get("indicator_name")
                val = dp.get("value", 0)
                values_by_year_name[y][name] = val
            
            cat_raw = dp.get("indicator_category", "").upper()
            target_key = category_map.get(cat_raw)
            if not target_key:
                if "RESULT" in cat_raw or "PL" in cat_raw: target_key = "financial_results"
                elif "BALANCE" in cat_raw or "BS" in cat_raw: target_key = "balance_general"
                elif "FLUJO" in cat_raw or "CASH" in cat_raw or "CF" in cat_raw: target_key = "cash_flow"
            
            if target_key:
                grouped[target_key].append(dp)

        years_list = sorted(list(years))
        # Keep only the last 2 available annual years
        if len(years_list) > 2:
            years_list = years_list[-2:]
        
        last_period = self._get_last_available_period(datapoints)
        ltm_label = ltm_title_db if ltm_title_db else (f"LTM {last_period}" if last_period else "LTM")

        result = {
            "years_list": sorted(list(years), reverse=True)[:2],
            "ltm_label": ltm_label
        }

        def get_value_by_tag(dp_list, target_year, tag):
            total = 0
            for dp in dp_list:
                y = str(dp.get("year"))
                p = str(dp.get("period"))
                if y == target_year and (p == y or p == f"{y}A"):
                    tags = dp.get("tags", [])
                    if tag in tags:
                        total += dp.get("value", 0)
            return total

        # Helper method for total calculation
        def get_total_for_year(year_str, keywords):
            total = 0
            year_data = values_by_year_name.get(year_str, {})
            for name, val in year_data.items():
                if any(k.lower() in name.lower() for k in keywords):
                    total += val
            return total

        def get_denominator_for_account(year, output_key, account_tags):
            if output_key == "financial_results":
                 # Total Sales: Sum of all accounts with tag 'gm' that are POSITIVE
                 total_sales = 0
                 for dp in datapoints:
                     y = dp.get("year")
                     p = dp.get("period")
                     # Convert year to str for comparison if needed
                     if str(y) == str(year) and (str(p) == str(year) or str(p) == f"{year}A") and "gm" in (dp.get("tags") or []):
                         val = dp.get("value", 0)
                         if val > 0:
                             total_sales += val
                 
                 if total_sales == 0:
                     total_sales = get_total_for_year(year, ["ventas", "ingresos", "sales", "revenue"])
                 return total_sales
            elif output_key == "balance_general":
                is_asset = any(t in ["currentAsset", "nonCurrentAsset"] for t in account_tags)
                if is_asset:
                    return get_value_by_tag(datapoints, year, "currentAsset") + get_value_by_tag(datapoints, year, "nonCurrentAsset")
                else: 
                    # Liability or Equity
                    return get_value_by_tag(datapoints, year, "currentLiability") + get_value_by_tag(datapoints, year, "nonCurrentLiability") + get_value_by_tag(datapoints, year, "equity")
            return 0

        def get_ltm_denominator(output_key, account_tags):
             if not last_period and not ltm_composition: return 0
             if output_key == "financial_results":
                 # Total Sales LTM: Sum LTM of all indicators that have tag 'gm' and are positive
                 gm_indicators = set()
                 for dp in datapoints:
                     if "gm" in (dp.get("tags") or []):
                         gm_indicators.add(dp.get("indicator_name"))
                 
                 total_sales_ltm = 0
                 for name in gm_indicators:
                     val = self._calculate_ltm(name, datapoints, last_period, ltm_composition=ltm_composition)
                     if val > 0:
                         total_sales_ltm += val
                 
                 if total_sales_ltm == 0:
                    total_sales_ltm = self._calculate_ltm("Ventas Totales", datapoints, last_period, ltm_composition=ltm_composition) or self._calculate_ltm("Total Sales", datapoints, last_period, ltm_composition=ltm_composition)
                 return total_sales_ltm
             elif output_key == "balance_general":
                 is_asset = any(t in ["currentAsset", "nonCurrentAsset", "asset"] for t in account_tags)
                 if is_asset:
                     return self._get_ltm_value_by_tag(datapoints, last_period, "asset", ltm_composition=ltm_composition) or (self._get_ltm_value_by_tag(datapoints, last_period, "currentAsset", ltm_composition=ltm_composition) + self._get_ltm_value_by_tag(datapoints, last_period, "nonCurrentAsset", ltm_composition=ltm_composition))
                 else:
                     return self._get_ltm_value_by_tag(datapoints, last_period, "liability", ltm_composition=ltm_composition) + self._get_ltm_value_by_tag(datapoints, last_period, "equity", ltm_composition=ltm_composition) or (self._get_ltm_value_by_tag(datapoints, last_period, "currentLiability", ltm_composition=ltm_composition) + self._get_ltm_value_by_tag(datapoints, last_period, "nonCurrentLiability", ltm_composition=ltm_composition) + self._get_ltm_value_by_tag(datapoints, last_period, "equity", ltm_composition=ltm_composition))
             return 0

        # Helper para construir tablas
        def build_table(output_key, items):
            if not items:
                return None

            # Mapa name -> display_name desde accounts (label = display_name en el payload)
            name_to_display = {}
            for it in items:
                n = it.get("indicator_name")
                d = it.get("indicator_display_name")
                if n and d:
                    name_to_display[n] = d
                elif n:
                    name_to_display.setdefault(n, n)

            def _norm_label(s):
                """Elimina espacios de más: trim + colapsar espacios internos a uno."""
                if s is None: return ""
                return " ".join(str(s).split())

            indicators = {} # { name: { year: { value: X, details: [...], tags: [...] } } }
            account_meta = {}  # name -> { tags: [], priority: int } para secciones (gm/om/ebt/nm) y orden
            indicator_order = []

            for item in items:
                name = item.get("indicator_name")
                if name not in indicators:
                    indicators[name] = {}
                    tags_raw = item.get("tags") or []
                    if isinstance(tags_raw, str):
                        try: tags_raw = json.loads(tags_raw) if tags_raw.strip() else []
                        except Exception: tags_raw = []
                    account_meta[name] = {
                        "tags": tags_raw if isinstance(tags_raw, list) else [],
                        "priority": item.get("indicator_priority") if item.get("indicator_priority") is not None else 0
                    }
                    indicator_order.append(name)
                
                y = str(item.get("year"))
                if y not in years_list:
                    continue

                val = item.get("value", 0)
                details_raw = item.get("details")
                tags = item.get("tags", [])
                
                # Parse details
                details = []
                if isinstance(details_raw, str):
                    try: details = json.loads(details_raw)
                    except: details = []
                elif isinstance(details_raw, list):
                    details = details_raw

                p = str(item.get("period"))
                if p == y or p == f"{y}A":
                    indicators[name][y] = {"value": val, "details": details, "tags": tags}

            rows = []
            pl_section_tags = ["gm", "om", "ebt", "nm"]
            balance_section_tags = ["currentAsset", "nonCurrentAsset", "currentLiability", "nonCurrentLiability", "equity"]
            section_tags = None  # gm/om/ebt/nm para P&L, o balance_section_tags para Balance
            total_rows_list = []
            accounts_by_section = None

            # --- AGREGACIONES (Tag-based): total por sección + cuentas por sección ---
            if output_key == "financial_results":
                section_tags = pl_section_tags
                totals_names = ["Margen Bruto", "Margen Operativo", "Margen antes de Impuestos", "Margen Neto"]
                for t_name in totals_names:
                    t_row_years = []
                    t_tags = ["gm"] if t_name == "Margen Bruto" else ["gm", "om"] if t_name == "Margen Operativo" else ["gm", "om", "ebt"] if t_name == "Margen antes de Impuestos" else ["gm", "om", "ebt", "nm"]
                    for y in years_list:
                        val = sum(get_value_by_tag(datapoints, y, tag) for tag in t_tags)
                        denominator = get_denominator_for_account(y, output_key, ["gm"])
                        t_row_years.append({"amount": self._format_number(val), "percentage": self._format_percentage(val, denominator)})
                    ltm_val = sum(self._get_ltm_value_by_tag(datapoints, last_period, tag, ltm_composition=ltm_composition) for tag in t_tags)
                    ltm_den = get_ltm_denominator(output_key, ["gm"])
                    total_rows_list.append({
                        "label": _norm_label(name_to_display.get(t_name) or name_to_display.get(t_name.upper()) or t_name.upper()),
                        "years": t_row_years,
                        "ltm_amount": self._format_number(ltm_val),
                        "ltm_percentage": self._format_percentage(ltm_val, ltm_den),
                        "last_period_amount": "-"
                    })
                accounts_by_section = {t: [] for t in pl_section_tags}
                for name in indicator_order:
                    placed = False
                    for tag in pl_section_tags:
                        if tag in account_meta.get(name, {}).get("tags", []):
                            accounts_by_section[tag].append(name)
                            placed = True
                            break
                    if not placed:
                        accounts_by_section["nm"].append(name)
                for tag in pl_section_tags:
                    accounts_by_section[tag].sort(key=lambda n: ((account_meta.get(n, {}).get("priority", 0)), n))

            elif output_key == "balance_general":
                section_tags = balance_section_tags
                totals_map = [
                    ("Activos Corrientes", "currentAsset"),
                    ("Activos No Corrientes", "nonCurrentAsset"),
                    ("Pasivos Corrientes", "currentLiability"),
                    ("Pasivos No Corrientes", "nonCurrentLiability"),
                    ("Patrimonio", "equity"),
                ]
                for t_label, t_tag in totals_map:
                    t_row_years = []
                    for y in years_list:
                        val = get_value_by_tag(datapoints, y, t_tag)
                        denominator = get_denominator_for_account(y, output_key, [t_tag])
                        t_row_years.append({"amount": self._format_number(val), "percentage": self._format_percentage(val, denominator)})
                    ltm_val = self._get_ltm_value_by_tag(datapoints, last_period, t_tag, ltm_composition=ltm_composition)
                    ltm_den = get_ltm_denominator(output_key, [t_tag])
                    # Último periodo (solo Balance): total sección = suma de values de cuentas de esa sección en ese period (solo items Balance)
                    lp_sum = sum(d.get("value", 0) for d in items if d.get("period") == last_period and t_tag in (d.get("tags") or [])) if last_period else 0
                    total_rows_list.append({
                        "label": _norm_label(name_to_display.get(t_label, t_label)),
                        "years": t_row_years,
                        "ltm_amount": self._format_number(ltm_val),
                        "ltm_percentage": self._format_percentage(ltm_val, ltm_den),
                        "last_period_amount": self._format_number(lp_sum) if last_period else "-"
                    })
                # Cuentas por sección por tag (como front: Activos Corrientes → currentAsset, etc.)
                accounts_by_section = {t: [] for t in balance_section_tags}
                for name in indicator_order:
                    placed = False
                    for tag in balance_section_tags:
                        if tag in account_meta.get(name, {}).get("tags", []):
                            accounts_by_section[tag].append(name)
                            placed = True
                            break
                    if not placed:
                        accounts_by_section["equity"].append(name)
                for tag in balance_section_tags:
                    accounts_by_section[tag].sort(key=lambda n: ((account_meta.get(n, {}).get("priority", 0)), n))

            elif output_key == "cash_flow":
                # Una sola sección "Flujo de Caja" con tag "flujo de caja" (como CF_SECTIONS en front)
                cf_section_tag = "flujo de caja"
                section_tags = [cf_section_tag]
                t_label = "Flujo de Caja"
                t_row_years = []
                for y in years_list:
                    val = get_value_by_tag(datapoints, y, cf_section_tag)
                    denominator = get_denominator_for_account(y, output_key, [cf_section_tag])
                    t_row_years.append({"amount": self._format_number(val), "percentage": self._format_percentage(val, denominator)})
                ltm_val = self._get_ltm_value_by_tag(datapoints, last_period, cf_section_tag, ltm_composition=ltm_composition)
                ltm_den = get_ltm_denominator(output_key, [cf_section_tag])
                total_rows_list.append({
                    "label": _norm_label(name_to_display.get(t_label, t_label)),
                    "years": t_row_years,
                    "ltm_amount": self._format_number(ltm_val),
                    "ltm_percentage": self._format_percentage(ltm_val, ltm_den),
                    "last_period_amount": "-"
                })
                accounts_by_section = {cf_section_tag: []}
                for name in indicator_order:
                    if cf_section_tag in account_meta.get(name, {}).get("tags", []):
                        accounts_by_section[cf_section_tag].append(name)
                accounts_by_section[cf_section_tag].sort(key=lambda n: ((account_meta.get(n, {}).get("priority", 0)), n))

            # --- CUENTAS INDIVIDUALES (por sección en financial_results: total luego sus cuentas por tag) ---
            def append_account_and_details(name):
                sample_item = next((dp for dp in items if dp.get("indicator_name") == name), {})
                a_tags = sample_item.get("tags", [])
                row_years = []
                for y in years_list:
                    data = indicators[name].get(y, {"value": 0, "details": []})
                    val = data["value"]
                    denominator = get_denominator_for_account(y, output_key, a_tags)
                    row_years.append({"amount": self._format_number(val), "percentage": self._format_percentage(val, denominator)})
                ltm_val = 0
                ltm_percentage = "0,00%"
                last_period_val = 0
                if output_key in ["financial_results", "cash_flow"]:
                    ltm_val = self._calculate_ltm(name, datapoints, last_period, ltm_composition=ltm_composition)
                    ltm_den = get_ltm_denominator(output_key, a_tags)
                    ltm_percentage = self._format_percentage(ltm_val, ltm_den)
                elif output_key == "balance_general":
                    # Valor Último periodo = value del datapoint para esta cuenta y period (solo items Balance). Si no hay dato o no es número válido → 0.
                    dp_lp = next((d for d in items if (d.get('indicator_name') == name or d.get('accountId') == name) and d.get('period') == last_period), None)
                    raw = dp_lp.get('value', 0) if dp_lp else 0
                    try:
                        v = float(raw) if raw is not None else 0
                        last_period_val = 0 if (v != v or v == float('inf') or v == float('-inf')) else v  # NaN / no finito → 0
                    except (TypeError, ValueError):
                        last_period_val = 0
                    ltm_val = self._calculate_ltm(name, datapoints, last_period, ltm_composition=ltm_composition) or last_period_val
                    ltm_den = get_ltm_denominator(output_key, a_tags)
                    ltm_percentage = self._format_percentage(ltm_val, ltm_den)
                rows.append({
                    "label": _norm_label(name_to_display.get(name, name)),
                    "years": row_years,
                    "ltm_amount": self._format_number(ltm_val),
                    "ltm_percentage": ltm_percentage,
                    "last_period_amount": self._format_number(last_period_val) if output_key == "balance_general" else "-"
                })
                unique_detail_names = []
                for y in years_list:
                    for d in indicators[name].get(y, {}).get("details", []):
                        dn = d.get("name")
                        if dn and dn not in unique_detail_names:
                            unique_detail_names.append(dn)
                if output_key == "balance_general" and last_period:
                    dp_lp = next((d for d in items if (d.get('indicator_name') == name or d.get('accountId') == name) and d.get('period') == last_period), None)
                    if dp_lp and dp_lp.get("details"):
                        try: det_lp = json.loads(dp_lp["details"]) if isinstance(dp_lp["details"], str) else (dp_lp["details"] or [])
                        except Exception: det_lp = []
                        for d in det_lp:
                            dn = d.get("name")
                            if dn and dn not in unique_detail_names:
                                unique_detail_names.append(dn)
                for d_name in unique_detail_names:
                    detail_years = []
                    for y in years_list:
                        data = indicators[name].get(y, {"value": 0, "details": []})
                        d_val = next((d.get("value", 0) for d in data["details"] if d.get("name") == d_name), 0)
                        denominator = get_denominator_for_account(y, output_key, a_tags)
                        detail_years.append({"amount": self._format_number(d_val), "percentage": self._format_percentage(d_val, denominator)})
                    d_lp_val = 0
                    if output_key == "balance_general" and last_period:
                        dp_lp = next((d for d in items if (d.get('indicator_name') == name or d.get('accountId') == name) and d.get('period') == last_period), None)
                        if dp_lp and dp_lp.get("details"):
                            try: det_lp = json.loads(dp_lp["details"]) if isinstance(dp_lp["details"], str) else (dp_lp["details"] or [])
                            except Exception: det_lp = []
                            d_lp_val = next((d.get("value", 0) for d in det_lp if d.get("name") == d_name), 0)
                    rows.append({
                        "label": _norm_label(name_to_display.get(d_name, d_name)),
                        "years": detail_years,
                        "ltm_amount": "-",
                        "ltm_percentage": "-",
                        "last_period_amount": self._format_number(d_lp_val) if output_key == "balance_general" else "-"
                    })

            # Igual que credit_proposal: por cada sección primero las cuentas (Caja, Mercaderías, etc.), luego el total de la sección (Activos Corrientes, Activos No Corrientes, …).
            if section_tags and total_rows_list and accounts_by_section:
                for i, tag in enumerate(section_tags):
                    for name in accounts_by_section[tag]:
                        append_account_and_details(name)
                    if i < len(total_rows_list) and total_rows_list[i]:
                        rows.append(total_rows_list[i])
            else:
                for name in indicator_order:
                    append_account_and_details(name)

            # Solo Estados de Resultados: última columna = "LTM". Balance = periodo real; Flujo de Caja = ltm_label
            if output_key == "balance_general":
                col_label = last_period if last_period else (ltm_label or "LTM")
            elif output_key == "financial_results":
                col_label = "LTM"
            else:
                col_label = ltm_label if ltm_label else "LTM"
            table_data = {
                "years_list": years_list,
                "ltm_label": col_label,
                f"{output_key}_list": rows
            }
            
            if output_key == "balance_general":
                table_data["balance_sheet_list"] = rows
                del table_data[f"{output_key}_list"]
                # Mostrar el periodo real (ej. 2025Q3) como en credit_proposal, no el texto "Ultimo Periodo"
                table_data["last_period_label"] = last_period if last_period else table_data.get("ltm_label", "")
            
            return table_data

        for key in grouped:
            table = build_table(key, grouped[key])
            if table:
                result[key] = table

        return result

    @staticmethod
    def _remove_metadata(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: CreditMemoBuilderService._remove_metadata(v) for k, v in obj.items() if k not in ("metadata", "request_id")}
        if isinstance(obj, list):
            return [CreditMemoBuilderService._remove_metadata(item) for item in obj]
        return obj

    @staticmethod
    def _format_currency(amount: Optional[float], currency: str = "USD") -> str:
        if amount is None:
            return "-"
        symbol = "S/" if currency == "PEN" else "US$"
        return f"{symbol} {amount:,.2f}"

    @staticmethod
    def _build_header_from_business(business: Dict[str, Any]) -> Dict[str, str]:
        return {
            "economicGroup": business.get("economic_group") or "-",
            "constitutionDate": business.get("constitution_date") or "-",
            "clientSince": business.get("client_since") or "-",
            "companySize": business.get("scale_type") or "-",
            "sbsClassification": business.get("sbs_classification") or "-",
            "approvalLevel": business.get("approval_level") or "-",
        }

    def _build_risk_proposal(
        self,
        total_amount: Optional[float],
        currency: str,
        credit_type: Optional[str] = None,
        term: Optional[str] = None,
        guarantee: Optional[str] = None,
    ) -> Dict[str, Any]:
        items = []
        items.append({"label": "Tipo de Crédito", "value": credit_type or "-"})
        items.append({"label": "Monto", "value": self._format_currency(total_amount, currency)})
        items.append({"label": "Plazo", "value": term or "-"})
        items.append({"label": "Garantía", "value": guarantee or "-"})
        return {"title": "1. Exposición Propuesta Por Riesgos", "items": items}

    @staticmethod
    def _parse_body(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = item.get("Payload") or item
        if "analysis" in payload:
            return payload
        body = payload.get("body")
        if not body:
            return None
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return None
        return body

    @staticmethod
    def _detect_result_type(parsed: Dict[str, Any]) -> Optional[str]:
        data = parsed.get("data") or parsed
        analysis = data.get("analysis") or {}
        message = (parsed.get("message") or "").lower()
        if "producto_demanda_mercado" in analysis and "sector_economico" in analysis:
            return "analyze_business"
        if "sector_economico" in analysis and "producto_demanda_mercado" not in analysis:
            return "analyze_sector_economico"
        if "rentabilidad" in analysis and "generacion_caja" in analysis:
            return "analyze_financial"
        if "solvencia" in analysis and "liquidez" in analysis:
            return "analyze_solvency_liquidity"
        if "foda" in analysis and "riesgos" in analysis:
            return "analyze_foda_risks"
        if "negocio completado" in message or "análisis de negocio" in message:
            return "analyze_business"
        if "sector económico" in message:
            return "analyze_sector_economico"
        if "financiero completado" in message or "análisis financiero" in message:
            return "analyze_financial"
        if "solvencia y liquidez" in message:
            return "analyze_solvency_liquidity"
        if "foda" in message and "riesgos" in message:
            return "analyze_foda_risks"
        return None

    def _get_result_by_key(self, parallel_results: List[Dict], result_key: str) -> Optional[Dict[str, Any]]:
        if not parallel_results:
            return None
        first = parallel_results[0]
        if "results" in first:
            for item in parallel_results:
                results = item.get("results") or {}
                if result_key in results:
                    return results[result_key]
            return None
        for item in parallel_results:
            parsed = self._parse_body(item)
            if not parsed:
                continue
            if self._detect_result_type(parsed) == result_key:
                return item
        return None

    def _extract_contenido(self, lambda_result: Optional[Dict[str, Any]], key: str) -> Optional[str]:
        if not lambda_result:
            return None
        parsed = self._parse_body(lambda_result)
        if not parsed:
            return None
        data = parsed.get("data") or parsed
        analysis = data.get("analysis") or {}
        block = analysis.get(key) or {}
        return block.get("contenido") if isinstance(block, dict) else None

    def _build_credit_memo_content(self, parallel_results: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        return {
            "producto_demanda_mercado": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_business"), "producto_demanda_mercado"),
            "sector_economico": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_sector_economico"), "sector_economico"),
            "rentabilidad": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_financial"), "rentabilidad"),
            "generacion_caja": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_financial"), "generacion_caja"),
            "solvencia": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_solvency_liquidity"), "solvencia"),
            "liquidez": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_solvency_liquidity"), "liquidez"),
            "foda": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_foda_risks"), "foda"),
            "riesgos": self._extract_contenido(self._get_result_by_key(parallel_results, "analyze_foda_risks"), "riesgos"),
        }

    @staticmethod
    def _fix_json_newlines_inside_strings(s: str) -> str:
        result = []
        i = 0
        in_string = False
        escape = False
        n = len(s)
        while i < n:
            c = s[i]
            if escape:
                result.append(c)
                escape = False
            elif c == "\\" and in_string:
                escape = True
                result.append(c)
            elif c == '"' and not escape:
                in_string = not in_string
                result.append(c)
            elif c in "\n\r" and in_string:
                result.append(" ")
            else:
                result.append(c)
            i += 1
        return "".join(result)

    @staticmethod
    def _parse_foda_for_section(foda_raw: Any) -> Optional[Dict[str, List[str]]]:
        if foda_raw is None:
            return None
        obj = None
        if isinstance(foda_raw, dict):
            obj = foda_raw
        elif isinstance(foda_raw, str) and foda_raw.strip():
            s = foda_raw.strip()
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                try:
                    obj = json.loads(CreditMemoBuilderService._fix_json_newlines_inside_strings(s))
                except json.JSONDecodeError:
                    return None
        if not obj or not isinstance(obj, dict):
            return None
        inner = obj.get("foda") if isinstance(obj.get("foda"), dict) else obj
        if not inner or not isinstance(inner, dict):
            return None
        result = {}
        for key in ("fortalezas", "oportunidades", "debilidades", "amenazas"):
            val = inner.get(key)
            result[key] = [str(item).replace("\n", " ").replace("\r", " ").strip() for item in val] if isinstance(val, list) else []
        return result if any(result.values()) else None

    def _build_proposal_data_sections(self, credit_memo_content: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
        def _text(*keys: str) -> str:
            parts = [credit_memo_content.get(k) or "" for k in keys]
            return "\n\n".join(p for p in parts if p).strip() or "(Sin contenido)"

        sections = [
            {"number": "2", "title": "Producto | Demanda | Mercado", "content": _text("producto_demanda_mercado")},
            {"number": "5", "title": "Sector Económico", "content": _text("sector_economico")},
            {"number": "6", "title": "Beneficio Rentabilidad", "content": _text("rentabilidad")},
            {"number": "7", "title": "Generación de Recursos", "content": _text("generacion_caja")},
            {"number": "8", "title": "Solvencia y Liquidez", "content": _text("solvencia", "liquidez")},
            {"number": "9", "title": "Análisis FODA", "content": _text("foda")},
            {"number": "10", "title": "Opinión de Riesgos", "content": _text("riesgos")},
        ]
        foda_parsed = self._parse_foda_for_section(credit_memo_content.get("foda"))
        for s in sections:
            if s.get("number") == "9" and foda_parsed:
                s["foda"] = foda_parsed
                s["content"] = ""
        return sections

    @staticmethod
    def _extract_contenido_from_value(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return val.get("contenido")
        return None

    def _credit_memo_from_combined_output(self, event: Dict[str, Any]) -> Dict[str, Optional[str]]:
        keys = [
            "producto_demanda_mercado", "sector_economico", "rentabilidad", "generacion_caja",
            "solvencia", "liquidez", "foda", "riesgos",
        ]
        return {k: CreditMemoBuilderService._extract_contenido_from_value(event.get(k)) for k in keys}

