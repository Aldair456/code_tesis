"""
Servicio para validar páginas detectadas por Reducto usando IA.

Filtra páginas que son Notas Financieras y deja solo las páginas reales de BS/PL/CF.
"""
import logging
import json
import urllib.request
from typing import Dict, List, Any, Optional
from common_ia_clients.ia_client import AnthropicStrategy
from models.model_1V2.src.utils.promts import promt_detect_financial_notes

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PageValidatorService:
    def __init__(self, anthropic_strategy: AnthropicStrategy):
        self.anthropic_strategy = anthropic_strategy
        self._parse_json_cache = None

    def _get_document_structure(self, reducto_json: Dict[str, Any]) -> str:
        """
        Extrae la estructura completa del documento con números de página.
        
        Returns:
            String con el contenido organizado por página
        """
        try:
            parse_url = reducto_json.get("result", {}).get("result", {}).get("parse", {}).get("result", {}).get("url")
            
            if not isinstance(parse_url, str) or not parse_url.startswith("http"):
                logger.warning("No se encontró parse.result.url, usando fallback")
                return self._get_document_structure_fallback(reducto_json)
            
            # Descargar el JSON parseado
            with urllib.request.urlopen(parse_url, timeout=30) as response:
                data = response.read()
                parse_json = json.loads(data.decode('utf-8'))
            
            chunks = parse_json.get("chunks") if isinstance(parse_json, dict) else None
            if not isinstance(chunks, list):
                return self._get_document_structure_fallback(reducto_json)
            
            # Organizar contenido por página
            pages_content = {}
            
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                
                blocks = chunk.get("blocks") if "blocks" in chunk else [chunk]
                
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    
                    bbox = block.get("bbox") or {}
                    page = bbox.get("page")
                    if not isinstance(page, int):
                        continue
                    
                    block_type = block.get("type", "")
                    content = block.get("content", "")
                    
                    if not isinstance(content, str) or not content.strip():
                        continue
                    
                    if page not in pages_content:
                        pages_content[page] = []
                    
                    # Formatear según el tipo
                    if block_type == "Table" and content.startswith("<"):
                        # Extraer texto de HTML
                        import re
                        text = re.sub(r'<[^>]+>', ' ', content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        pages_content[page].append(f"[TABLA]: {text[:300]}...")
                    else:
                        pages_content[page].append(f"[{block_type}]: {content[:200]}")
            
            # Construir string con estructura por página
            result = []
            for page_num in sorted(pages_content.keys()):
                result.append(f"\n{'='*60}")
                result.append(f"PÁGINA {page_num}")
                result.append(f"{'='*60}")
                result.append("\n".join(pages_content[page_num][:20]))  # Max 20 bloques por página
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Error obteniendo estructura del documento: {e}")
            return self._get_document_structure_fallback(reducto_json)
    
    def _get_document_structure_fallback(self, reducto_json: Dict[str, Any]) -> str:
        """
        Fallback: extrae estructura del JSON directo cuando la URL falla.
        """
        extract = reducto_json.get("result", {}).get("result", {}).get("extract", [])
        if not isinstance(extract, list):
            return ""
        
        pages_content = {}
        
        for item in extract:
            if not isinstance(item, dict):
                continue
            
            page_range = item.get("page_range", [])
            if not page_range:
                continue
            
            # Extraer estados
            estados = item.get("result", {}).get("result", {}).get("estados", [])
            if isinstance(estados, list):
                for estado in estados:
                    if not isinstance(estado, dict):
                        continue
                    
                    tipo = estado.get("tipo_estado", {}).get("value", "")
                    
                    for page_num in page_range:
                        if page_num not in pages_content:
                            pages_content[page_num] = []
                        pages_content[page_num].append(f"[Estado]: {tipo}")
        
        result = []
        for page_num in sorted(pages_content.keys()):
            result.append(f"\nPÁGINA {page_num}: {', '.join(pages_content[page_num])}")
        
        return "\n".join(result)

    def validate_pages(
        self,
        reducto_json: Dict[str, Any],
        pages_by_label: Dict[str, List[int]]
    ) -> Dict[str, List[int]]:
        """
        Detecta dónde empiezan las notas financieras y filtra páginas.
        
        Args:
            reducto_json: JSON completo de Reducto
            pages_by_label: Diccionario con páginas detectadas por Reducto
                           {"BS": [1, 5, 108-146], "PL": [2, 8], "CF": [3]}
            
        Returns:
            Diccionario con páginas filtradas (sin notas financieras)
        """
        logger.info("="*60)
        logger.info("INICIANDO DETECCIÓN DE NOTAS FINANCIERAS CON IA")
        logger.info("="*60)
        logger.info(f"Páginas detectadas por Reducto: {pages_by_label}")
        
        try:
            # Obtener estructura completa del documento
            logger.info("Extrayendo estructura del documento...")
            document_structure = self._get_document_structure(reducto_json)
            
            if not document_structure.strip():
                logger.warning("No se pudo extraer estructura del documento, manteniendo todas las páginas")
                return pages_by_label
            
            logger.info(f"Estructura extraída ({len(document_structure)} caracteres)")
            logger.info("Primeros 500 caracteres de la estructura:")
            logger.info("-"*60)
            logger.info(document_structure[:500])
            logger.info("-"*60)
            
            # Construir prompt usando la función de utils
            prompt = promt_detect_financial_notes(document_structure)
            
            # Llamar a la IA
            logger.info("Preguntando a la IA en qué página empiezan las notas financieras...")
            response = self.anthropic_strategy.invoke(prompt)
            
            logger.info(f"Respuesta de la IA: '{response}'")
            
            # Analizar respuesta
            response_clean = response.strip().upper()
            
            if "SIN_NOTAS" in response_clean or "SIN NOTAS" in response_clean:
                logger.info("✓ La IA indica que NO hay notas financieras en el documento")
                return pages_by_label
            
            # Intentar extraer el número de página
            import re
            match = re.search(r'\b(\d+)\b', response_clean)
            
            if not match:
                logger.warning(f"No se pudo extraer número de página de la respuesta: '{response}'")
                logger.warning("Manteniendo todas las páginas por seguridad")
                return pages_by_label
            
            notes_start_page = int(match.group(1))
            logger.info(f"✓ Las notas financieras empiezan en la página: {notes_start_page}")
            
            # Filtrar páginas
            validated_pages = {"BS": [], "PL": [], "CF": []}
            
            for label, pages in pages_by_label.items():
                for page_num in pages:
                    if page_num < notes_start_page:
                        validated_pages[label].append(page_num)
                        logger.info(f"  ✓ Página {page_num} ({label}): VÁLIDA (antes de las notas)")
                    else:
                        logger.info(f"  ✗ Página {page_num} ({label}): FILTRADA (es nota financiera)")
            
            logger.info("="*60)
            logger.info("RESULTADO DE LA VALIDACIÓN")
            logger.info("="*60)
            logger.info(f"Páginas ANTES: {pages_by_label}")
            logger.info(f"Páginas DESPUÉS: {validated_pages}")
            logger.info("="*60)
            
            return validated_pages
            
        except Exception as e:
            logger.error(f"Error en validación de páginas: {e}")
            logger.warning("Manteniendo todas las páginas por seguridad")
            return pages_by_label
