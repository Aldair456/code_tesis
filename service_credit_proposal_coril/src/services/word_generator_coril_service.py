import logging
import os
import tempfile
import re



from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    from docxtpl import DocxTemplate, RichText
except ImportError:
    DocxTemplate = None
    RichText = None

logger = logging.getLogger(__name__)

# Zona horaria Perú (America/Lima = UTC-5, sin horario de verano)
PERU_UTC_OFFSET_HOURS = 5


def _utc_to_peru_datetime(utc_dt: Union[datetime, str, None]) -> str:
    """
    Convierte fecha/hora UTC (desde BD, ej. 2026-01-30 01:39:39.133195) a hora local Perú (UTC-5).
    Retorna string formateado para el documento: dd/mm/yyyy HH:MM:SS.
    """
    logger.info("[fecha_hora_creacion] _utc_to_peru_datetime entrada: utc_dt=%s (tipo=%s)", utc_dt, type(utc_dt).__name__)
    if utc_dt is None:
        logger.warning("[fecha_hora_creacion] created_at_utc es None → fecha_hora_creacion quedará vacío")
        return ""
    if isinstance(utc_dt, str):
        try:
            # Aceptar ISO (2026-01-30T01:39:39.133195 o 2026-01-30 01:39:39.133195); BD suele ser naive UTC
            utc_dt = datetime.fromisoformat(utc_dt.replace("Z", "+00:00").replace(" ", "T", 1))
        except (ValueError, TypeError) as e:
            logger.warning("[fecha_hora_creacion] fallo parseo ISO: %s", e)
            try:
                utc_dt = datetime.strptime(utc_dt.split(".")[0].replace("T", " "), "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError) as e2:
                logger.warning("[fecha_hora_creacion] fallo parseo strptime: %s → fecha_hora_creacion vacío", e2)
                return ""
    if not isinstance(utc_dt, datetime):
        logger.warning("[fecha_hora_creacion] valor no es datetime ni str válido → fecha_hora_creacion vacío")
        return ""
    # Asumir naive datetime en UTC; convertir a Perú restando 5 horas
    peru_dt = utc_dt - timedelta(hours=PERU_UTC_OFFSET_HOURS)
    result = peru_dt.strftime("%d/%m/%Y %H:%M:%S")
    logger.info("[fecha_hora_creacion] _utc_to_peru_datetime salida: %s", result)
    return result


class WordGeneratorCorilService:
    """Servicio para generar documentos Word a partir de datos de propuestas coril usando docxtpl."""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

        self.template_path = templates_dir / "credit-proposal-template.docx"
        
        if not self.template_path.exists():
            logger.warning(f"Template Word no encontrado en: {self.template_path}")
    
    def _get_str(self, obj: Dict[str, Any], key: str, default: str = "") -> str:
        """Obtiene valor string de diccionario de forma segura."""
        value = obj.get(key)
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)
    
    def _value_for_docxtpl(self, value: str) -> Any:
        """
        Convierte valor con Markdown a RichText para docxtpl.
        Soporta negritas (**texto**), encabezados (# ## ###) y saltos de línea.
        Si no hay Markdown, procesa como texto plano normal.
        """
        if not value or RichText is None:
            return value
        # Quitar líneas que son solo --- (regla horizontal) para que no salgan rayas en el doc
        value = re.sub(r"\n\s*---\s*\n", "\n\n", value)
        # Si no hay formato markdown, usar el método original
        if "**" not in value and "\n" not in value and "#" not in value:
            return value
        
        rt = RichText()
        
        # Procesar línea por línea
        lines = value.split('\n')
        for line_idx, line in enumerate(lines):
            if line_idx > 0:
                rt.add('\n')
            
            # Procesar markdown en la línea (encabezados, negritas, etc.)
            self._add_markdown_to_richtext(rt, line)
        
        return rt
    
    def _add_markdown_to_richtext(self, rt: RichText, text: str) -> None:
        """
        Agrega texto con formato Markdown a RichText.
        Soporta **negrita**, encabezados (# ## ###) y bullets (-).
        Los encabezados se convierten a texto en negrita con salto de línea.
        """
        # Detectar y procesar encabezados (# ## ###)
        header_match = re.match(r'^(#{1,6})\s+(.+)$', text)
        if header_match:
            # Es un encabezado - convertir a texto en negrita
            header_level = len(header_match.group(1))
            header_text = header_match.group(2)
            
            # Agregar salto de línea antes si no es la primera línea
            # (ya se maneja en _value_for_docxtpl)
            
            # Procesar el texto del encabezado (puede tener negritas)
            self._process_text_with_bold(rt, header_text, is_header=True)
            return
        
        # Detectar bullets (-)
        bullet_match = re.match(r'^-\s+(.+)$', text)
        if bullet_match:
            # Es un bullet - agregar bullet y procesar texto
            rt.add('• ', bold=False)
            self._process_text_with_bold(rt, bullet_match.group(1), is_header=False)
            return
        
        # Texto normal - procesar negritas
        self._process_text_with_bold(rt, text, is_header=False)
    
    def _process_text_with_bold(self, rt: RichText, text: str, is_header: bool = False) -> None:
        """
        Procesa texto con negritas (**texto**) y lo agrega a RichText.
        Si is_header=True, todo el texto se pone en negrita.
        """
        if is_header:
            # Para encabezados, todo en negrita
            parts = re.split(r'(\*\*.*?\*\*)', text)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    # Texto en negrita dentro del encabezado
                    bold_text = part[2:-2]
                    rt.add(bold_text, bold=True)
                else:
                    # Texto normal del encabezado (también en negrita)
                    if part:
                        rt.add(part, bold=True)
        else:
            # Para texto normal, solo procesar negritas
            parts = re.split(r'(\*\*.*?\*\*)', text)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    # Es texto en negrita
                    bold_text = part[2:-2]
                    rt.add(bold_text, bold=True)
                else:
                    # Es texto normal
                    if part:
                        rt.add(part, bold=False)
    
    def _build_template_context(
        self,
        proposal_data: Dict[str, Any],
        created_at_utc: Union[datetime, str, None] = None,
    ) -> Dict[str, Any]:
        """
        Construye el contexto para el template docxtpl.

        Placeholders en el Word (sintaxis Jinja2 de docxtpl):
        - Variables simples: {{ nombre_variable }} → ej: {{ client_name }}, {{ report_title }}
        - Listas/loops: {% for item in risk_proposal_items %}...{{ item.label }}: {{ item.value }}{% endfor %}
        - Condicionales: {% if section_product_content %}{{ section_product_content }}{% endif %}

        Variables disponibles en el contexto (usar estos nombres exactos en credit-proposal-template.docx):
          Fecha: fecha_hora_creacion (hora local Perú, desde created_at del credit memo en BD)
          Header: header_economic_group, header_constitution_date, header_client_since, header_company_size,
                  header_sbs_classification, header_approval_level
          General: report_title, client_name, client_ruc
          Riesgo: risk_proposal_title, risk_proposal_purpose, risk_proposal_items (lista con .label, .value),
                  risk_credit_type, risk_amount, risk_term, risk_guarantee,
                  risk_proposal_item_1_label/value ... risk_proposal_item_N_label/value
          Secciones 2-10: section_product_title/content, section_debt_title, debt_table_title, debt_source,
                  section_shareholders_title/content, section_sector_title/content, section_profitability_title/content,
                  section_generation_title/content, section_solvency_title/content, section_foda_title,
                  section_foda_fortalezas, section_foda_oportunidades, section_foda_debilidades, section_foda_amenazas
                  (cada una es lista; también section_foda_fortalezas_1, _2, etc.)
                  section_opinion_title/content
        """
        context: Dict[str, Any] = {}

        # 0. Fecha/hora de creación (desde BD, UTC → hora local Perú)
        context["fecha_hora_creacion"] = _utc_to_peru_datetime(created_at_utc)
        logger.info("[fecha_hora_creacion] contexto: fecha_hora_creacion=%r", context["fecha_hora_creacion"])

        # 1. Header Information
        header = proposal_data.get("header", {})
        context["header_economic_group"] = self._get_str(header, "economicGroup", "")
        context["header_constitution_date"] = self._get_str(header, "constitutionDate", "")
        context["header_client_since"] = self._get_str(header, "clientSince", "")
        context["header_company_size"] = self._get_str(header, "companySize", "")
        context["header_sbs_classification"] = self._get_str(header, "sbsClassification", "")
        context["header_approval_level"] = self._get_str(header, "approvalLevel", "")

        # 2. General Report Info
        context["report_title"] = self._get_str(proposal_data, "reportTitle", "")
        context["client_name"] = self._get_str(proposal_data, "clientName", "")
        context["client_ruc"] = self._get_str(proposal_data, "clientRuc", "")

        # 3. Risk Proposal (Section 1)
        risk_proposal = proposal_data.get("riskProposal", {})
        context["risk_proposal_title"] = self._get_str(risk_proposal, "title", "")
        context["risk_proposal_purpose"] = self._value_for_docxtpl(self._get_str(risk_proposal, "purpose", ""))
        
        risk_items = risk_proposal.get("items", [])
        context["risk_proposal_items"] = []
        for idx, item in enumerate(risk_items, 1):
            if isinstance(item, dict):
                context[f"risk_proposal_item_{idx}_label"] = self._get_str(item, "label", "")
                context[f"risk_proposal_item_{idx}_value"] = self._get_str(item, "value", "")
                context["risk_proposal_items"].append({
                    "label": self._get_str(item, "label", ""),
                    "value": self._get_str(item, "value", "")
                })

        # Friendly aliases for the known 4 items
        if len(risk_items) >= 4:
            context["risk_credit_type"] = self._get_str(risk_items[0], "value", "")
            context["risk_amount"] = self._get_str(risk_items[1], "value", "")
            context["risk_term"] = self._get_str(risk_items[2], "value", "")
            context["risk_guarantee"] = self._get_str(risk_items[3], "value", "")

        # 4. Sections List Processing
        sections = proposal_data.get("sections", [])
        
        # Helper to find section by number
        def find_section(num: str) -> Dict[str, Any]:
            for sec in sections:
                if isinstance(sec, dict) and sec.get("number") == num:
                    return sec
            return {}

        # Section 2: Producto | Demanda | Mercado
        sec2 = find_section("2")
        context["section_product_title"] = self._get_str(sec2, "title", "")
        context["section_product_content"] = self._value_for_docxtpl(self._get_str(sec2, "content", ""))

        # Section 3: Acceso al Crédito (Deuda)
        sec3 = find_section("3")
        context["section_debt_title"] = self._get_str(sec3, "title", "")
        debt_table = sec3.get("debtTable", {})
        context["debt_table_title"] = self._get_str(debt_table, "title", "")
        context["debt_source"] = self._get_str(debt_table, "source", "")

        # Section 4: Accionistas (Shareholders)
        sec4 = find_section("4")
        context["section_shareholders_title"] = self._get_str(sec4, "title", "")
        context["section_shareholders_content"] = self._value_for_docxtpl(self._get_str(sec4, "content", ""))

        # Section 5: Sector Económico
        sec5 = find_section("5")
        context["section_sector_title"] = self._get_str(sec5, "title", "")
        context["section_sector_content"] = self._value_for_docxtpl(self._get_str(sec5, "content", ""))

        # Section 6: Beneficio Rentabilidad
        sec6 = find_section("6")
        context["section_profitability_title"] = self._get_str(sec6, "title", "")
        context["section_profitability_content"] = self._value_for_docxtpl(self._get_str(sec6, "content", ""))

        # Section 7: Generación de Recursos
        sec7 = find_section("7")
        context["section_generation_title"] = self._get_str(sec7, "title", "")
        context["section_generation_content"] = self._value_for_docxtpl(self._get_str(sec7, "content", ""))

        # Section 8: Solvencia y Liquidez
        sec8 = find_section("8")
        context["section_solvency_title"] = self._get_str(sec8, "title", "")
        context["section_solvency_content"] = self._value_for_docxtpl(self._get_str(sec8, "content", ""))

        # Section 9: FODA
        sec9 = find_section("9")
        context["section_foda_title"] = self._get_str(sec9, "title", "")
        foda = sec9.get("foda", {})
        
        # Process FODA lists
        for key in ["fortalezas", "oportunidades", "debilidades", "amenazas"]:
            items = foda.get(key, [])
            if not isinstance(items, list): 
                items = []
            context[f"section_foda_{key}"] = [self._value_for_docxtpl(str(i)) for i in items]
            # Also numbered individual items for easy placement
            for idx, val in enumerate(items, 1):
                 context[f"section_foda_{key}_{idx}"] = self._value_for_docxtpl(str(val))

        # Section 10: Opinión de Riesgos
        sec10 = find_section("10")
        context["section_opinion_title"] = self._get_str(sec10, "title", "")
        context["section_opinion_content"] = self._value_for_docxtpl(self._get_str(sec10, "content", ""))

        # 11. Financial Results (Resultados Financieros)
        financial_results = proposal_data.get("financial_results", {})
        
        # Procesar encabezados de años
        years_list = financial_results.get("years_list", [])
        context["fin_header_y1"] = str(years_list[0]) if len(years_list) > 0 else "-"
        context["fin_header_y2"] = str(years_list[1]) if len(years_list) > 1 else "-"
        context["fin_header_ltm"] = self._get_str(financial_results, "ltm_label", "LTM")

        # Procesar filas de la tabla
        fin_list = financial_results.get("financial_results_list", [])
        
        # Lista completa por compatibilidad (FALTABA ESTA LÍNEA)
        financial_items = []

        # Listas separadas para Resultados Financieros
        items_margen_bruto = []
        items_margen_operativo = []
        items_margen_antes_impuestos = []
        items_margen_neto = []
        
        # Totales extraídos
        context["total_margen_bruto"] = {}
        context["total_margen_operativo"] = {}
        context["total_margen_antes_impuestos"] = {}
        context["total_margen_neto"] = {}

        # Flag de sección (iniciamos en el primer bloque: Ventas -> Margen Bruto)
        current_fin_section = "BRUTO" 

        for item in fin_list:
            label = self._get_str(item, "label", "")
            years_data = item.get("years", [])
            
            # Datos Año 1
            y1_amount = "-"
            y1_perc = "-"
            if len(years_data) > 0:
                y1_amount = self._get_str(years_data[0], "amount", "-")
                y1_perc = self._get_str(years_data[0], "percentage", "-")
            
            # Datos Año 2    
            y2_amount = "-"
            y2_perc = "-"
            if len(years_data) > 1:
                y2_amount = self._get_str(years_data[1], "amount", "-")
                y2_perc = self._get_str(years_data[1], "percentage", "-")
                
            # Datos LTM
            ltm_amount = self._get_str(item, "ltm_amount", "-")
            ltm_perc = self._get_str(item, "ltm_percentage", "-")
            
            row_data = {
                "label": label,
                "y1_amount": y1_amount, 
                "y1_perc": y1_perc,
                "y2_amount": y2_amount,
                "y2_perc": y2_perc,
                "ltm_amount": ltm_amount,
                "ltm_perc": ltm_perc
            }

            # Identificar Totales y cambiar de sección
            # Normalizamos el label para comparación insensible a mayúsculas/minúsculas si fuera necesario (aquí es exacto)
            if label == "MARGEN BRUTO":
                context["total_margen_bruto"] = row_data
                current_fin_section = "BRUTO" # CORRECTO: Mantenemos la sección BRUTO para los items que siguen
                continue 
            elif label == "MARGEN OPERATIVO":
                context["total_margen_operativo"] = row_data
                current_fin_section = "OPERATIVO"
                continue
            elif label == "MARGEN ANTES DE IMPUESTOS" or label == "Margen Antes de Impuestos":
                # Guardamos el primero que encontremos (el payload tiene duplicado a veces)
                if not context["total_margen_antes_impuestos"]: 
                    context["total_margen_antes_impuestos"] = row_data
                current_fin_section = "ANTES_IMPUESTOS"
                continue
            elif label == "MARGEN NETO":
                context["total_margen_neto"] = row_data
                current_fin_section = "NETO"
                continue

            # Agregar a la lista correspondiente
            if current_fin_section == "BRUTO":
                items_margen_bruto.append(row_data)
            elif current_fin_section == "OPERATIVO":
                items_margen_operativo.append(row_data)
            elif current_fin_section == "ANTES_IMPUESTOS":
                items_margen_antes_impuestos.append(row_data)
            elif current_fin_section == "NETO":
                items_margen_neto.append(row_data)
            
            # Lista completa por compatibilidad
            financial_items.append(row_data)
            
        context["financial_items"] = financial_items
        context["items_margen_bruto"] = items_margen_bruto
        context["items_margen_operativo"] = items_margen_operativo
        context["items_margen_antes_impuestos"] = items_margen_antes_impuestos
        context["items_margen_neto"] = items_margen_neto

        # 12. Balance General
        balance_general = proposal_data.get("balance_general", {})
        
        # Procesar encabezados de años para Balance
        bal_years_list = balance_general.get("years_list", [])
        context["bal_header_y1"] = str(bal_years_list[0]) if len(bal_years_list) > 0 else "-"
        context["bal_header_y2"] = str(bal_years_list[1]) if len(bal_years_list) > 1 else "-"
        context["bal_header_last_period"] = self._get_str(balance_general, "last_period_label", "Periodo")

        # Procesar filas de Balance
        bal_list = balance_general.get("balance_sheet_list", [])
        # Listas separadas para facilitar el diseño en Word
        balance_items = []  # <--- FALTABA ESTA LÍNEA
        items_activos_corrientes = []
        items_activos_no_corrientes = []
        items_pasivos_corrientes = []
        items_pasivos_no_corrientes = []
        items_patrimonio = []
        
        # Totales extraídos para usar fuera del loop
        context["total_activos_corrientes"] = {}
        context["total_activos_no_corrientes"] = {}
        context["total_pasivos_corrientes"] = {}
        context["total_pasivos_no_corrientes"] = {}
        context["total_patrimonio"] = {}

        # Flag para controlar en qué sección estamos
        current_section = None 

        for item in bal_list:
            label = self._get_str(item, "label", "")
            years_data = item.get("years", [])
            
            # Extraer valores
            y1_amount = "-"
            y1_perc = "-"
            if len(years_data) > 0:
                y1_amount = self._get_str(years_data[0], "amount", "-")
                y1_perc = self._get_str(years_data[0], "percentage", "-")
            
            y2_amount = "-"
            y2_perc = "-"
            if len(years_data) > 1:
                y2_amount = self._get_str(years_data[1], "amount", "-")
                y2_perc = self._get_str(years_data[1], "percentage", "-")
                
            last_amount = self._get_str(item, "last_period_amount", "-")
            last_perc = self._get_str(item, "last_period_percentage", "-")

            row_data = {
                "label": label,
                "y1_amount": y1_amount, 
                "y1_perc": y1_perc,
                "y2_amount": y2_amount,
                "y2_perc": y2_perc,
                "last_amount": last_amount,
                "last_perc": last_perc
            }

            # Identificar secciones y totales
            if label == "Activos Corrientes":
                context["total_activos_corrientes"] = row_data
                current_section = "AC"
                continue # No lo agregamos a la lista, va aparte
            elif label == "Activos No Corrientes":
                context["total_activos_no_corrientes"] = row_data
                current_section = "ANC"
                continue
            elif label == "Pasivos Corrientes":
                context["total_pasivos_corrientes"] = row_data
                current_section = "PC"
                continue
            elif label == "Pasivos No Corrientes":
                context["total_pasivos_no_corrientes"] = row_data
                current_section = "PNC"
                continue
            elif label == "Patrimonio":
                context["total_patrimonio"] = row_data
                current_section = "PAT"
                continue

            # Agregar a la lista correspondiente según la sección actual
            if current_section == "AC":
                items_activos_corrientes.append(row_data)
            elif current_section == "ANC":
                items_activos_no_corrientes.append(row_data)
            elif current_section == "PC":
                items_pasivos_corrientes.append(row_data)
            elif current_section == "PNC":
                items_pasivos_no_corrientes.append(row_data)
            elif current_section == "PAT":
                items_patrimonio.append(row_data)
            
            # También mantenemos la lista completa por compatibilidad
            balance_items.append(row_data)
            
        context["balance_items"] = balance_items
        context["items_activos_corrientes"] = items_activos_corrientes
        context["items_activos_no_corrientes"] = items_activos_no_corrientes
        context["items_pasivos_corrientes"] = items_pasivos_corrientes
        context["items_pasivos_no_corrientes"] = items_pasivos_no_corrientes
        context["items_patrimonio"] = items_patrimonio

        # 13. Flujo de Caja
        cash_flow = proposal_data.get("cash_flow", {})
        
        # Encabezados
        cf_years_list = cash_flow.get("years_list", [])
        context["cf_header_y1"] = str(cf_years_list[0]) if len(cf_years_list) > 0 else "-"
        context["cf_header_y2"] = str(cf_years_list[1]) if len(cf_years_list) > 1 else "-"
        context["cf_header_ltm"] = self._get_str(cash_flow, "ltm_label", "LTM")

        # Filas
        cf_list = cash_flow.get("cash_flow_list", [])
        
        # Lista completa por compatibilidad
        cash_flow_items = []
        
        # Listas separadas para Flujo de Caja
        items_flujo_operativo = []
        items_flujo_inversion = []
        items_flujo_financiamiento = []
        
        # Totales extraídos
        context["total_flujo_operativo"] = {}
        context["total_flujo_inversion"] = {}
        context["total_flujo_financiamiento"] = {}
        context["total_flujo_financiamiento"] = {}
        context["total_flujo_caja"] = {} # Neto global
        
        # Agregamos esta lista VACÍA para que no explote tu template si tienes un loop for
        items_flujo_caja_neto = [] 
        context["items_flujo_caja_neto"] = items_flujo_caja_neto

        # Flag de sección
        current_cf_section = None

        for item in cf_list:
            label = self._get_str(item, "label", "")
            years_data = item.get("years", [])
            
            y1_amount = "-"
            y1_perc = "-" # Flujo de caja a veces no tiene porcentaje, pero lo dejaremos por consistencia
            if len(years_data) > 0:
                y1_amount = self._get_str(years_data[0], "amount", "-")
                y1_perc = self._get_str(years_data[0], "percentage", "")
            
            y2_amount = "-"
            y2_perc = "-"
            if len(years_data) > 1:
                y2_amount = self._get_str(years_data[1], "amount", "-")
                y2_perc = self._get_str(years_data[1], "percentage", "")
                
            ltm_amount = self._get_str(item, "ltm_amount", "-")
            ltm_perc = self._get_str(item, "ltm_percentage", "-")
            
            row_data = {
                "label": label,
                "y1_amount": y1_amount,
                "y1_perc": y1_perc,
                "y2_amount": y2_amount,
                "y2_perc": y2_perc,
                "ltm_amount": ltm_amount,
                "ltm_perc": ltm_perc
            }
            
            # Identificar Totales y cambiar de sección
            # Nota: El payload trae "Flujo de Caja" (Neto) primero, luego FINANCIAMIENTO, LUEGO INVERSION, LUEGO OPERATIVO (al revés del orden usual contable)
            
            if label == "Flujo de Caja":
                context["total_flujo_caja"] = row_data
                # No cambia sección específica, es el global. Lo dejamos sin sección o mantenemos la anterior si hubiera.
                # En este payload suele ser el primero, así que current_cf_section sigue siendo None
                pass 
            elif label == "Flujo de Caja de Financiamiento":
                context["total_flujo_financiamiento"] = row_data
                current_cf_section = "FINANCIAMIENTO"
                continue
            elif label == "Flujo de Caja de Inversión":
                context["total_flujo_inversion"] = row_data
                current_cf_section = "INVERSION"
                continue
            elif label == "Flujo de Caja Operativo":
                context["total_flujo_operativo"] = row_data
                current_cf_section = "OPERATIVO"
                continue

            # Agregar a la lista correspondiente
            if current_cf_section == "OPERATIVO":
                items_flujo_operativo.append(row_data)
            elif current_cf_section == "INVERSION":
                items_flujo_inversion.append(row_data)
            elif current_cf_section == "FINANCIAMIENTO":
                items_flujo_financiamiento.append(row_data)
            
            # Lista general por compatibilidad
            cash_flow_items.append(row_data)
            
        context["cash_flow_items"] = cash_flow_items
        context["items_flujo_operativo"] = items_flujo_operativo
        context["items_flujo_inversion"] = items_flujo_inversion
        context["items_flujo_financiamiento"] = items_flujo_financiamiento

        return context
    
    def generate_word_document(
        self,
        proposal_data: Dict[str, Any],
        filename: str = None,
        created_at_utc: Union[datetime, str, None] = None,
    ) -> Dict[str, Any]:
        """
        Genera un documento Word a partir de los datos de la propuesta.
        
        Args:
            proposal_data: Datos completos de la propuesta
            filename: Nombre opcional para el archivo
            created_at_utc: Fecha/hora de creación del credit memo en BD (UTC); se muestra en hora Perú en {{ fecha_hora_creacion }}
            
        Returns:
            Dict con información del documento generado
            
        Raises:
            RuntimeError: Si docxtpl no está disponible o el template no existe
        """
        if DocxTemplate is None:
            raise RuntimeError("docxtpl is required to generate DOCX documents")
        
        if not self.template_path.exists():
            raise RuntimeError(f"Template Word no encontrado: {self.template_path}")
        
        try:
            # Generar nombre de archivo
            if not filename:
                client_name = proposal_data.get("clientName", "propuesta")
                safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = safe_name.replace(' ', '_')[:50]
                filename = f"credit_proposal_coril_{safe_name}.docx"
            
            # Construir contexto para template (incl. fecha_hora_creacion en hora Perú)
            logger.info("[fecha_hora_creacion] generate_word_document recibido: created_at_utc=%s", created_at_utc)
            context = self._build_template_context(proposal_data, created_at_utc=created_at_utc)
            logger.info("[fecha_hora_creacion] context tiene fecha_hora_creacion=%r", context.get("fecha_hora_creacion"))
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                temp_path = tmp_file.name
            
            # Generar documento usando template
            template = DocxTemplate(str(self.template_path))
            template.render(context)
            template.save(temp_path)
            
            # Leer archivo generado
            with open(temp_path, 'rb') as f:
                docx_content = f.read()
            
            # Limpiar archivo temporal
            os.unlink(temp_path)
            
            # Retornar información del documento
            return {
                "filename": filename,
                "content": docx_content,
                "size_bytes": len(docx_content),
                "size_kb": round(len(docx_content) / 1024, 2)
            }
            
        except Exception as e:
            logger.error(f"Error generando documento Word: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error generando documento Word: {str(e)}") from e
