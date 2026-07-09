import base64
import json
import logging
import re
import tempfile
import markdown
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

import os
# AGREGADO PARA WINDOWS LOCAL: Añadir GTK3 al PATH/DLL search path antes de importar WeasyPrint
gtk3_path = r"D:\ALDAIR\Documents\GTK3-Runtime Win64\bin"
if os.path.exists(gtk3_path):
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(gtk3_path)
    if gtk3_path not in os.environ['PATH']:
        os.environ['PATH'] = gtk3_path + os.pathsep + os.environ['PATH']

from weasyprint import HTML

from services.service_credit_proposal_coril.src.utils.normalizers import _get_str

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PDFGeneratorCorilService:
    """Servicio para generar PDFs de propuestas de crédito coril desde JSON."""
    
    def __init__(self, templates_dir: Path = None):
        """
        Inicializa el servicio de generación de PDF coril.
        
        Args:
            templates_dir: Directorio donde están los templates HTML. 
                          Si es None, usa el directorio templates del servicio.
        """
        if templates_dir is None:
            # Obtener el directorio de templates relativo a este archivo
            current_file = Path(__file__).resolve()
            service_dir = current_file.parent.parent.parent  # services/service_credit_proposal_coril
            templates_dir = service_dir / "src" / "templates"
        
        self.templates_dir = Path(templates_dir)
        if not self.templates_dir.exists():
            raise ValueError(f"El directorio de templates no existe: {self.templates_dir}")
        
        # Inicializar environment de Jinja2
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        
        # Registrar filtro markdown (normaliza texto y convierte tablas)
        self.env.filters['markdown'] = lambda text: self._markdown_filter(text or "")
        
        logger.info(f"PDFGeneratorCorilService inicializado con templates en: {self.templates_dir}")

    def _markdown_filter(self, text: str) -> str:
        """
        Normaliza el contenido markdown antes de convertirlo a HTML:
        - ~- y ~ se reemplazan por ≈ para evitar caracteres raros en PDF (ej. ~-38 pp → ≈ -38 pp).
        - Dobles saltos de línea que parten frases (ej. "del\\n\\nEstado") se unen para que no queden
          líneas sueltas en medio del párrafo.
        """
        if not text or not text.strip():
            return ""
        # Caracteres: tilde como "aprox." se ve mal; usar símbolo ≈
        text = text.replace("~-", "≈ -").replace(" ~", " ≈ ")
        # Quitar líneas que son solo --- (regla horizontal en markdown) para que no salgan rayas en el doc
        text = re.sub(r"\n\s*---\s*\n", "\n\n", text)
        # Unir líneas partidas: doble salto cuando la siguiente es continuación (minúscula, coma, raya, etc.)
        text = re.sub(r"\n\n(?=[a-záéíóúñü—,\"])", "\n", text)
        return markdown.markdown(text, extensions=["tables"])

    def generate_pdf_from_json(self, proposal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera un PDF desde los datos JSON de la propuesta coril.
        
        Args:
            proposal_data: Diccionario con los datos de la propuesta (como sample_cover.json)
            
        Returns:
            Dict con:
                - pdfBase64: PDF codificado en base64
                - filename: Nombre sugerido del archivo
                - size_bytes: Tamaño del PDF en bytes
        """
        try:
            logger.info("Iniciando generación de PDF coril desde JSON")
            
            # 1. Construir view model
            vm = self._build_cover_view_model(proposal_data)
            
            # 2. Renderizar HTML
            html_content = self._render_html(vm)
            
            # 3. Convertir HTML a PDF
            pdf_bytes = self._html_to_pdf(html_content)
            
            # 4. Codificar en base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # 5. Generar nombre de archivo
            client_name = proposal_data.get("clientName", "propuesta")
            # Limpiar nombre para archivo
            safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')[:50]  # Limitar longitud
            filename = f"credit_proposal_coril_{safe_name}.pdf"
            
            result = {
                "pdfBase64": pdf_base64,
                "filename": filename,
                "size_bytes": len(pdf_bytes),
                "size_kb": round(len(pdf_bytes) / 1024, 2)
            }
            
            logger.info(f"PDF coril generado exitosamente: {filename} ({result['size_kb']} KB)")
            return result
            
        except Exception as e:
            logger.error(f"Error generando PDF coril: {str(e)}", exc_info=True)
            raise Exception(f"Error al generar PDF coril: {str(e)}") from e
    
    def _strip_markdown_json_fence(self, s: str) -> str:
        """Quita el envoltorio ```json ... ``` del contenido para poder parsear el JSON."""
        s = s.strip()
        if s.startswith("```"):
            idx = s.find("\n")
            if idx != -1:
                s = s[idx + 1:]
            if s.endswith("```"):
                s = s[:-3].strip()
        return s

    def _parse_foda_content(self, content: Any) -> Optional[Dict[str, List[str]]]:
        """Parsea JSON FODA desde content (string) para mostrar listas en el PDF."""
        if not content or not isinstance(content, str):
            return None
        
        s = self._strip_markdown_json_fence(content.strip())
        
        # 1. Intentar parsear como JSON
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            # Intentar reparar JSON con newlines
            s_fixed = self._fix_json_newlines_inside_strings(s)
            try:
                obj = json.loads(s_fixed)
            except json.JSONDecodeError:
                # Si falla JSON, intentar parsear como texto plano estructurado
                return self._parse_foda_text(s)

        if not isinstance(obj, dict):
            return self._parse_foda_text(s)
            
        inner = obj.get("foda") if isinstance(obj.get("foda"), dict) else obj
        if not isinstance(inner, dict):
            return self._parse_foda_text(s)
            
        result = {}
        for key in ("fortalezas", "oportunidades", "debilidades", "amenazas"):
            val = inner.get(key)
            result[key] = [str(x).replace("\n", " ").replace("\r", " ").strip() for x in val] if isinstance(val, list) else []
        
        if any(result.values()):
            return result
            
        # Si el objeto JSON no tenía las claves esperadas, intentar texto plano
        return self._parse_foda_text(s)

    def _parse_foda_text(self, text: str) -> Optional[Dict[str, List[str]]]:
        """Parsea texto plano estructurado (Fortalezas, Oportunidades, etc)."""
        import re
        
        # Patrón para encontrar los encabezados
        headers_pattern = r"(?i)(fortalezas|oportunidades|debilidades|amenazas)"
        matches = list(re.finditer(headers_pattern, text))
        
        if not matches:
            return None
            
        result = {
            "fortalezas": [],
            "oportunidades": [],
            "debilidades": [],
            "amenazas": []
        }
        
        for i, match in enumerate(matches):
            key = match.group(1).lower()
            start = match.end()
            end = matches[i+1].start() if i + 1 < len(matches) else len(text)
            
            section_text = text[start:end].strip()
            # Limpiar separadores iniciales comunes
            if section_text.startswith(":") or section_text.startswith("-"):
                 section_text = section_text[1:].strip()

            # Separar por líneas (o bullets • si están en la misma línea)
            # Primero separar por saltos de línea
            raw_lines = [line.strip() for line in section_text.split('\n') if line.strip()]
            
            # Luego procesar cada línea para limpiar bullets
            clean_lines = []
            for line in raw_lines:
                # Si la línea contiene múltiples bullets (•), separarlos
                if "•" in line:
                    sub_parts = [p.strip() for p in line.split("•") if p.strip()]
                    clean_lines.extend(sub_parts)
                else:
                    # Remover bullets comunes al inicio: -, *, 1.
                    clean_line = re.sub(r"^[\s\-\*0-9\.]+\s*", "", line)
                    if clean_line:
                        clean_lines.append(clean_line)
                    
            result[key] = clean_lines

        if any(result.values()):
            return result
        return None

    def _fix_json_newlines_inside_strings(self, s: str) -> str:
        """Reemplaza newlines literales solo dentro de strings del JSON."""
        result, i, in_string, escape = [], 0, False, False
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

    def _build_cover_view_model(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        """Construye el view model para el template Jinja2 de coril."""
        # 1. Header Information
        header = draft.get("header", {})
        
        # 2. General Report Info
        report_title = _get_str(draft, "reportTitle", "")
        client_name = _get_str(draft, "clientName", "")
        client_ruc = _get_str(draft, "clientRuc", "")
        
        # 3. Risk Proposal
        risk_proposal = draft.get("riskProposal", {})
        
        # 4. Sections List (normalizar sección 9 FODA: si content es JSON, parsear a section.foda)
        sections = list(draft.get("sections", []))
        for section in sections:
            if section.get("number") != "9":
                continue
            if section.get("foda"):
                continue
            content = section.get("content")
            foda = self._parse_foda_content(content)
            if foda:
                section["foda"] = foda
                section["content"] = ""

        # 5. Financial Results
        financial_results = draft.get("financial_results")

        # 6. Balance General
        balance_general = draft.get("balance_general")

        # 7. Flujo de Caja
        cash_flow = draft.get("cash_flow")

        vm: Dict[str, Any] = {
            "header": header,
            "reportTitle": report_title,
            "clientName": client_name,
            "clientRuc": client_ruc,
            "riskProposal": risk_proposal,
            "sections": sections,
            "financial_results": financial_results,
            "balance_general": balance_general,
            "cash_flow": cash_flow,
        }
        
        return vm
    
    def _render_html(self, view_model: Dict[str, Any]) -> str:
        """Renderiza el HTML usando Jinja2."""
        template = self.env.get_template("coril_cover.html")
        html = template.render(**view_model)
        return html
    
    def _html_to_pdf(self, html_content: str) -> bytes:
        """
        Convierte HTML a PDF usando WeasyPrint (más liviano y confiable que Playwright en Lambda).
        
        Args:
            html_content: Contenido HTML como string
            
        Returns:
            bytes: PDF en formato binario
        """
        try:
            # WeasyPrint convierte directamente desde string HTML a PDF
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        except Exception as e:
            logger.error(f"Error en WeasyPrint: {str(e)}", exc_info=True)
            raise
