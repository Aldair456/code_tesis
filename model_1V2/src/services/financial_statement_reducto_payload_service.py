from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import json
import urllib.request
import logging

from models.model_1V2.src.config import config
from models.model_1V2.src.repositories.financial_statement_s3_repository import (
    FinancialStatementS3Repository,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FinancialStatementReductoPayloadService:
    def __init__(self, repository: FinancialStatementS3Repository) -> None:
        self._repo = repository

    @staticmethod
    def _get_nested(d: Dict[str, Any], path: List[str]) -> Any:
        cur: Any = d
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    @staticmethod
    def _extract_pages_by_label(reducto_json: Dict[str, Any]) -> Dict[str, List[int]]:
        splits = (
            FinancialStatementReductoPayloadService._get_nested(
                reducto_json, ["result", "result", "split", "result", "splits"]
            )
            or []
        )
        pages_by_label: Dict[str, List[int]] = {}
        if not isinstance(splits, list):
            return pages_by_label

        mapping = {
            "balance_general": "BS",
            "estado_resultados": "PL",
            "flujo_caja": "CF",
        }
        for s in splits:
            if not isinstance(s, dict):
                continue
            name = (s.get("name") or "").strip()
            label = mapping.get(name)
            if not label:
                continue
            pages = s.get("pages") or []
            if isinstance(pages, list):
                cleaned = [int(p) for p in pages if isinstance(p, (int, float, str)) and str(p).isdigit()]
                if cleaned:
                    pages_by_label[label] = cleaned
        return pages_by_label

    @staticmethod
    def _infer_type(pages_by_label: Dict[str, List[int]]) -> str:
        has_bs = bool(pages_by_label.get("BS"))
        has_pl = bool(pages_by_label.get("PL"))
        if has_bs and has_pl:
            return "PB"
        if has_bs:
            return "BS"
        if has_pl:
            return "PL"
        return "UNKNOWN"

    @staticmethod
    def _infer_statement_type(payload_type: str) -> str:
        """
        Compatibilidad con IA antigua (service_accounts_ia.py):
        valid_types = ["all", "bs", "pl"] y normaliza PB -> all.
        """
        t = (payload_type or "").strip().lower()
        if t in ("pb", "all", ""):
            return "all"
        if t == "bs":
            return "bs"
        if t == "pl":
            return "pl"
        return "all"

    @staticmethod
    def _extract_periodicity(reducto_json: Dict[str, Any]) -> str:
        extract = FinancialStatementReductoPayloadService._get_nested(reducto_json, ["result", "result", "extract"]) or []
        if not isinstance(extract, list):
            return ""
        for item in extract:
            if not isinstance(item, dict):
                continue
            estados = FinancialStatementReductoPayloadService._get_nested(
                item, ["result", "result", "estados"]
            )
            if not isinstance(estados, list):
                continue
            for e in estados:
                if not isinstance(e, dict):
                    continue
                tipo = FinancialStatementReductoPayloadService._get_nested(e, ["tipo_periodo", "value"])
                if isinstance(tipo, str) and tipo.strip():
                    return tipo.strip()
        return ""

    @staticmethod
    def _extract_links(reducto_json: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        # Reducto suele guardar metadata en result.result.metadata (pero lo hacemos defensivo)
        metadata = (
            FinancialStatementReductoPayloadService._get_nested(reducto_json, ["result", "result", "metadata"])
            or FinancialStatementReductoPayloadService._get_nested(reducto_json, ["result", "metadata"])
            or FinancialStatementReductoPayloadService._get_nested(reducto_json, ["metadata"])
            or {}
        )
        if not isinstance(metadata, dict):
            return None, None
        pdf_url = metadata.get("pdf_url")
        studio_link = metadata.get("studio_link")
        return (
            pdf_url if isinstance(pdf_url, str) and pdf_url else None,
            studio_link if isinstance(studio_link, str) and studio_link else None,
        )

    @staticmethod
    def _parse_result_node(reducto_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for path in (
            ["result", "result", "parse", "result"],
            ["result", "parse", "result"],
        ):
            node = FinancialStatementReductoPayloadService._get_nested(reducto_json, path)
            if isinstance(node, dict):
                return node
        return None

    @staticmethod
    def _fetch_parse_json(reducto_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        JSON de parse listo para _tables_html_from_parse:
        - Si parse.result.url es HTTP: GET y json.loads del cuerpo.
        - Si no hay URL (p. ej. parse embebido en Reducto): el mismo dict bajo
          parse.result con lista chunks no vacía.
        """
        parse_result = FinancialStatementReductoPayloadService._parse_result_node(reducto_json)
        if not isinstance(parse_result, dict):
            print("[parse] FUENTE: ninguna (no hay parse.result en el JSON) → _tables_html_from_extract")
            return None

        parse_url = parse_result.get("url")
        if isinstance(parse_url, str) and parse_url.startswith("http"):
            try:
                with urllib.request.urlopen(parse_url, timeout=30) as response:
                    data = response.read()
                fetched = json.loads(data.decode("utf-8"))
                if isinstance(fetched, dict):
                    logger.info("Parse JSON obtenido por URL (Reducto)")
                    print("[parse] FUENTE: URL (fetch remoto OK)")
                    return fetched
            except Exception:
                logger.warning(
                    "Fallo al obtener parse por URL; se intentará parse embebido si hay chunks",
                    exc_info=True,
                )
                print("[parse] URL presente pero el fetch falló; se revisa parse embebido…")

        chunks = parse_result.get("chunks")
        if isinstance(chunks, list) and len(chunks) > 0:
            logger.info("Parse JSON embebido en Reducto (sin URL o tras fallo de fetch)")
            print(f"[parse] FUENTE: EMBEBIDO (chunks={len(chunks)} en parse.result, sin depender de URL)")
            return parse_result

        print("[parse] FUENTE: ninguna (sin URL usable ni chunks en parse.result) → _tables_html_from_extract")
        return None

    @staticmethod
    def _tables_html_from_parse(
        parse_json: Dict[str, Any],
        pages_by_label: Dict[str, List[int]],
    ) -> Dict[str, str]:
        """
        Extrae tablas HTML del JSON parseado (URL remota o parse.result embebido),
        filtrando por páginas del split.
        """
        # El JSON parseado tiene estructura: {"type": "full", "chunks": [...]}
        chunks = parse_json.get("chunks") if isinstance(parse_json, dict) else None
        if not isinstance(chunks, list):
            return {"bs": "", "pl": "", "CF": ""}

        desired_pages = {
            "BS": set(pages_by_label.get("BS") or []),
            "PL": set(pages_by_label.get("PL") or []),
            "CF": set(pages_by_label.get("CF") or []),
        }

        tables_by_label: Dict[str, List[str]] = {"BS": [], "PL": [], "CF": []}
        
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            
            blocks = chunk.get("blocks") if "blocks" in chunk else [chunk]
            
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                
                if block.get("type") != "Table":
                    continue
                
                bbox = block.get("bbox") or {}
                page = bbox.get("page")
                if not isinstance(page, int):
                    continue
                
                content = block.get("content")
                if not isinstance(content, str) or "<table" not in content:
                    continue
                
                for label, pages in desired_pages.items():
                    if page in pages:
                        tables_by_label[label].append(content)

        bs_html = "\n\n".join(tables_by_label["BS"])
        pl_html = "\n\n".join(tables_by_label["PL"])
        cf_html = "\n\n".join(tables_by_label["CF"])

        return {"bs": bs_html, "pl": pl_html, "CF": cf_html}

    @staticmethod
    def _tables_html_from_extract(
        reducto_json: Dict[str, Any],
        pages_by_label: Dict[str, List[int]],
    ) -> Dict[str, str]:
        """
        Construye "tables" como en el payload viejo, pero usando HTML de Reducto.
        Retorna keys: bs, pl, CF (para compatibilidad con el ejemplo anterior).
        """
        extract = FinancialStatementReductoPayloadService._get_nested(reducto_json, ["result", "result", "extract"]) or []
        if not isinstance(extract, list):
            return {"bs": "", "pl": "", "CF": ""}

        desired_pages = {
            "BS": set(pages_by_label.get("BS") or []),
            "PL": set(pages_by_label.get("PL") or []),
            "CF": set(pages_by_label.get("CF") or []),
        }

        # Usamos sets para deduplicar tablas repetidas por múltiples líneas/citations
        tables_by_label: Dict[str, List[str]] = {"BS": [], "PL": [], "CF": []}
        seen_by_label: Dict[str, set] = {"BS": set(), "PL": set(), "CF": set()}
        # Fallback: texto tabular simple por label (si no hay HTML)
        fallback_lines: Dict[str, List[str]] = {"BS": [], "PL": [], "CF": []}

        for item in extract:
            if not isinstance(item, dict):
                continue
            page_range = item.get("page_range") or []
            pages: List[int] = []
            if isinstance(page_range, list):
                for p in page_range:
                    if isinstance(p, int):
                        pages.append(p)
                    elif isinstance(p, str) and p.isdigit():
                        pages.append(int(p))

            estados = FinancialStatementReductoPayloadService._get_nested(item, ["result", "result", "estados"]) or []
            if not isinstance(estados, list):
                continue

            for estado in estados:
                if not isinstance(estado, dict):
                    continue

                # solo recolectamos tablas que caen en páginas del split
                page_hit_labels = [
                    label for label, wanted in desired_pages.items() if pages and any(p in wanted for p in pages)
                ]
                if not page_hit_labels:
                    continue

                lineas = estado.get("lineas") or []
                if not isinstance(lineas, list):
                    continue

                for linea in lineas:
                    if not isinstance(linea, dict):
                        continue
                    # Guardar fallback simple (cuenta | monto) por si no hay HTML en CF
                    try:
                        nc = linea.get("nombre_cuenta") or {}
                        mt = linea.get("monto") or {}
                        cuenta = nc.get("value") if isinstance(nc, dict) else None
                        monto_val = mt.get("value") if isinstance(mt, dict) else None
                        if isinstance(cuenta, str) and cuenta.strip():
                            # El monto puede venir como 0 y el real estar en citations; guardamos ambos
                            monto_str = str(monto_val) if monto_val is not None else ""
                            # si hay citations con content numérico, usamos el primero como "raw"
                            raw = ""
                            if isinstance(mt, dict):
                                cits = mt.get("citations") or []
                                if isinstance(cits, list):
                                    for c in cits:
                                        if isinstance(c, dict) and isinstance(c.get("content"), str) and c.get("content"):
                                            raw = c["content"]
                                            break
                            line_txt = f"{cuenta.strip()} | {raw or monto_str}"
                            for lbl in page_hit_labels:
                                fallback_lines[lbl].append(line_txt)
                    except Exception:
                        pass

                    for field_name in ("nombre_cuenta", "monto"):
                        field = linea.get(field_name) or {}
                        if not isinstance(field, dict):
                            continue
                        citations = field.get("citations") or []
                        if not isinstance(citations, list):
                            continue
                        for cit in citations:
                            if not isinstance(cit, dict):
                                continue
                            parent = cit.get("parentBlock") or {}
                            if not isinstance(parent, dict):
                                continue
                            if (parent.get("type") or "").lower() != "table":
                                continue
                            html = parent.get("content")
                            if not isinstance(html, str) or "<table" not in html:
                                continue

                            for lbl in page_hit_labels:
                                if html in seen_by_label[lbl]:
                                    continue
                                seen_by_label[lbl].add(html)
                                tables_by_label[lbl].append(html)

        bs_html = "\n\n".join(tables_by_label["BS"])
        pl_html = "\n\n".join(tables_by_label["PL"])
        cf_html = "\n\n".join(tables_by_label["CF"])

        # Si algún estado no viene como tabla HTML, devolvemos fallback de texto
        if not bs_html.strip():
            bs_html = "\n".join(fallback_lines["BS"])
        if not pl_html.strip():
            pl_html = "\n".join(fallback_lines["PL"])
        if not cf_html.strip():
            cf_html = "\n".join(fallback_lines["CF"])

        return {"bs": bs_html, "pl": pl_html, "CF": cf_html}

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    def _quarter_from_month(month: int) -> Optional[str]:
        if month in (1, 2, 3):
            return "Q1"
        if month in (4, 5, 6):
            return "Q2"
        if month in (7, 8, 9):
            return "Q3"
        if month in (10, 11, 12):
            return "Q4"
        return None

    @staticmethod
    def _build_years_from_extract(
        reducto_json: Dict[str, Any],
        pages_by_label: Dict[str, List[int]],
        periodicity_type: str,
    ) -> Dict[str, List[Any]]:
        extract = FinancialStatementReductoPayloadService._get_nested(reducto_json, ["result", "result", "extract"]) or []
        if not isinstance(extract, list):
            return {"bs": [], "pl": [], "CF": []}

        desired_pages = {
            "BS": set(pages_by_label.get("BS") or []),
            "PL": set(pages_by_label.get("PL") or []),
            "CF": set(pages_by_label.get("CF") or []),
        }
        mapping = {
            "balance_general": "BS",
            "estado_resultados": "PL",
            "flujo_caja": "CF",
        }

        annual_years = {"BS": set(), "PL": set(), "CF": set()}
        quarterly_periods = {"BS": set(), "PL": set(), "CF": set()}
        monthly_periods = {"BS": set(), "PL": set(), "CF": set()}

        for item in extract:
            if not isinstance(item, dict):
                continue
            page_range = item.get("page_range") or []
            pages: List[int] = []
            if isinstance(page_range, list):
                for p in page_range:
                    if isinstance(p, int):
                        pages.append(p)
                    elif isinstance(p, str) and p.isdigit():
                        pages.append(int(p))

            estados = FinancialStatementReductoPayloadService._get_nested(item, ["result", "result", "estados"]) or []
            if not isinstance(estados, list):
                continue

            for estado in estados:
                if not isinstance(estado, dict):
                    continue
                tipo_estado = FinancialStatementReductoPayloadService._get_nested(estado, ["tipo_estado", "value"])
                if not isinstance(tipo_estado, str):
                    continue
                label = mapping.get(tipo_estado.strip().lower())
                if not label:
                    continue
                if pages and not any(p in desired_pages[label] for p in pages):
                    continue

                inicio_raw = FinancialStatementReductoPayloadService._get_nested(estado, ["periodo_inicio", "value"])
                fin_raw = FinancialStatementReductoPayloadService._get_nested(estado, ["periodo_fin", "value"])
                print(f"DEBUG RAW - label={label}, pages={pages}, inicio_raw={inicio_raw}, fin_raw={fin_raw}")
                
                inicio = FinancialStatementReductoPayloadService._parse_date(inicio_raw)
                fin = FinancialStatementReductoPayloadService._parse_date(fin_raw)
                if not fin:
                    continue

                if periodicity_type == "trimestral":
                    quarter = FinancialStatementReductoPayloadService._quarter_from_month(fin.month)
                    if not quarter:
                        continue
                    is_accumulated = bool(inicio and inicio.month == 1 and quarter in ("Q2", "Q3", "Q4"))
                    quarter_value = f"{quarter}A" if is_accumulated else quarter
                    quarterly_periods[label].add((fin.year, quarter_value))
                elif periodicity_type == "mensual":
                    month = fin.month
                    is_accumulated = bool(inicio and inicio.month == 1 and month > 1)
                    print(f"DEBUG mensual - label={label}, inicio={inicio}, fin={fin}, month={month}, is_accumulated={is_accumulated}")
                    month_value = f"M{month:02d}A" if is_accumulated else f"M{month:02d}"
                    monthly_periods[label].add((fin.year, month_value))
                else:
                    annual_years[label].add(fin.year)

        if periodicity_type == "trimestral":
            def _sort_key(v: Tuple[int, str]) -> Tuple[int, int, int]:
                year, q = v
                q_clean = q.replace("A", "")
                order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get(q_clean, 9)
                acc = 1 if q.endswith("A") else 0
                return (year, order, acc)

            return {
                "bs": [{"year": y, "quarter": q} for (y, q) in sorted(quarterly_periods["BS"], key=_sort_key)],
                "pl": [{"year": y, "quarter": q} for (y, q) in sorted(quarterly_periods["PL"], key=_sort_key)],
                "CF": [{"year": y, "quarter": q} for (y, q) in sorted(quarterly_periods["CF"], key=_sort_key)],
            }
        
        if periodicity_type == "mensual":
            def _sort_key_monthly(v: Tuple[int, str]) -> Tuple[int, int, int]:
                year, m = v
                m_clean = m.replace("M", "").replace("A", "")
                month_num = int(m_clean) if m_clean.isdigit() else 99
                acc = 1 if m.endswith("A") else 0
                return (year, month_num, acc)

            return {
                "bs": [{"year": y, "month": m} for (y, m) in sorted(monthly_periods["BS"], key=_sort_key_monthly)],
                "pl": [{"year": y, "month": m} for (y, m) in sorted(monthly_periods["PL"], key=_sort_key_monthly)],
                "CF": [{"year": y, "month": m} for (y, m) in sorted(monthly_periods["CF"], key=_sort_key_monthly)],
            }

        return {
            "bs": sorted(list(annual_years["BS"]), reverse=True),
            "pl": sorted(list(annual_years["PL"]), reverse=True),
            "CF": sorted(list(annual_years["CF"]), reverse=True),
        }

    def build_payload(self, *, bucket: str, financial_statement_id: str) -> Dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)
        
        reducto_key = f"{config.FINANCIAL_STATEMENT_JSON_PREFIX}{financial_statement_id}.json"
        pdf_key = f"{config.FINANCIAL_STATEMENTS_PREFIX}{financial_statement_id}.pdf"

        reducto_json = self._repo.get_json(reducto_key, bucket=bucket)
        
        # DEBUG: Ver estructura del JSON
        logger.info("DEBUG: Keys nivel raíz JSON: %s", list(reducto_json.keys()) if isinstance(reducto_json, dict) else "NO ES DICT")
        result_level_1 = reducto_json.get("result") if isinstance(reducto_json, dict) else None
        logger.info("DEBUG: result (nivel 1) keys: %s", list(result_level_1.keys()) if isinstance(result_level_1, dict) else "NO EXISTE")
        result_level_2 = result_level_1.get("result") if isinstance(result_level_1, dict) else None
        logger.info("DEBUG: result.result (nivel 2) keys: %s", list(result_level_2.keys()) if isinstance(result_level_2, dict) else "NO EXISTE")
        
        pages_by_label = self._extract_pages_by_label(reducto_json)
        logger.info("DEBUG: pages_by_label extraídos: %s", pages_by_label)
        
        periodicity_type = self._extract_periodicity(reducto_json)
        logger.info("DEBUG: periodicity_type extraído: %s", periodicity_type)
        
        _type = self._infer_type(pages_by_label)
        statement_type = self._infer_statement_type(_type)
        pdf_url, studio_link = self._extract_links(reducto_json)
        
        # Intentar usar el JSON parseado (más limpio) desde parse.result.url
        parse_json = self._fetch_parse_json(reducto_json)
        if parse_json:
            tables = self._tables_html_from_parse(parse_json, pages_by_label)
        else:
            tables = self._tables_html_from_extract(reducto_json, pages_by_label)
        
        logger.info("DEBUG: tables extraídas - bs: %d chars, pl: %d chars, CF: %d chars", 
                    len(tables.get("bs", "")), len(tables.get("pl", "")), len(tables.get("CF", "")))
        
        years = self._build_years_from_extract(reducto_json, pages_by_label, periodicity_type)
        logger.info("DEBUG: years extraídos: %s", years)

        job_id = (
            self._get_nested(reducto_json, ["result", "job_id"])
            or reducto_json.get("job_id")
        )
        
        return {
            "type": _type,
            "periodicity_type": periodicity_type,
            "statement_type": statement_type,
            "object_key": pdf_key,
            "object_key_reducto_json": reducto_key,
            "pages_by_label": pages_by_label,
            "tables": tables,
            "years": years,
            "job_id": job_id,
            "metadata": {
                "pdf_url": pdf_url,
                "studio_link": studio_link,
            },
            "financial_statement_id": financial_statement_id,
        }

