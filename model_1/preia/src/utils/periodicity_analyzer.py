# import os
# import logging
# import re
# from typing import List, Dict, Tuple, Optional
# from functools import lru_cache
#
# # Configuración del logger
# logger = logging.getLogger(__name__)
#
#
# class PeriodicityAnalyzer:
#     """
#     Clase para analizar la periodicidad de documentos basándose en fechas encontradas.
#     Determina si un documento es anual o trimestral.
#     """
#
#     def __init__(self):
#         """Inicializa el analizador de periodicidad."""
#
#         # Constantes de meses
#         self.months = [
#             "enero", "febrero", "marzo", "abril", "mayo", "junio",
#             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
#         ]
#
#         self.month_variants = [
#             "ene", "enero", "feb", "febrero", "mar", "marzo", "abr", "abril",
#             "may", "mayo", "jun", "junio", "jul", "julio", "ago", "agosto",
#             "sep", "set", "sept", "setiembre", "septiembre", "oct", "octubre",
#             "nov", "noviembre", "dic", "diciembre"
#         ]
#
#         self.months_pattern = "|".join(self.month_variants)
#
#         self.month_numbers = {
#             "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
#             "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
#         }
#
#         self.normalize_month = {
#             "ene": "enero", "feb": "febrero", "mar": "marzo", "abr": "abril",
#             "may": "mayo", "jun": "junio", "jul": "julio", "ago": "agosto",
#             "sep": "septiembre", "set": "septiembre", "sept": "septiembre",
#             "setiembre": "septiembre", "septiembre": "septiembre",
#             "oct": "octubre", "nov": "noviembre", "dic": "diciembre"
#         }
#
#     def normalize_text(self, text: str) -> str:
#         """
#         Normaliza las variantes de meses en el texto.
#
#         Args:
#             text (str): Texto a normalizar
#
#         Returns:
#             str: Texto normalizado
#         """
#         for variant, official in self.normalize_month.items():
#             text = re.sub(rf"\b{variant}\b", official, text, flags=re.IGNORECASE)
#         return text
#
#     def extract_first_lines_per_page(self, text: str, lines_per_page: int = 10) -> Dict[str, List[str]]:
#         """
#         Extrae las primeras líneas de cada página del documento.
#
#         Args:
#             text (str): Texto completo del documento
#             lines_per_page (int): Número de líneas a extraer por página
#
#         Returns:
#             Dict[str, List[str]]: Diccionario con líneas por página
#         """
#         pages = re.split(r"###PAGE_ID:\d+###", text)
#         pages = [page.strip() for page in pages if page.strip()]
#
#         result = {}
#         for i, page_content in enumerate(pages, start=1):
#             lines = page_content.splitlines()
#             first_lines = lines[:lines_per_page]
#             result[f"PAGE_{i}"] = first_lines
#
#         return result
#
#     def search_dates_in_lines(self, lines: List[str]) -> List[str]:
#         """
#         Busca todas las fechas en las líneas proporcionadas.
#
#         Args:
#             lines (List[str]): Líneas de texto donde buscar fechas
#
#         Returns:
#             List[str]: Lista de fechas encontradas
#         """
#         found_dates = []
#
#         # Patrones de búsqueda
#         numeric_pattern = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b")
#         year_pattern = re.compile(r"\b(de|del|año[s]?)(?:\s+)?(\d{4})\b", re.IGNORECASE)
#         textual_pattern = re.compile(rf"\b(\d{{1,2}})?\s*(de)?\s*({self.months_pattern})\s*(de)?\s*(\d{{4}})?\b",
#                                      re.IGNORECASE)
#         range_pattern = re.compile(
#             rf"del\s+(\d{{1,2}})\s+de\s+({self.months_pattern})\s+al\s+(\d{{1,2}})\s+de\s+({self.months_pattern})(?:\s+de\s+(\d{{4}}))?",
#             re.IGNORECASE)
#         al_date_pattern = re.compile(rf"\bAl\s+(\d{{1,2}})?\s*(de)?\s*({self.months_pattern})\s*(de)?\s*(\d{{4}})?\b",
#                                      re.IGNORECASE)
#
#         for line in lines:
#             # Fechas numéricas
#             numeric_matches = numeric_pattern.findall(line)
#             found_dates.extend(numeric_matches)
#
#             # Años
#             year_matches = year_pattern.findall(line)
#             for match in year_matches:
#                 found_dates.append(match[1])
#
#             # Fechas textuales
#             textual_matches = textual_pattern.findall(line)
#             for match in textual_matches:
#                 date = " ".join([part for part in match if part]).strip()
#                 if date:
#                     found_dates.append(date)
#
#             # Rangos de fechas
#             range_matches = range_pattern.findall(line)
#             for match in range_matches:
#                 date_range = f"del {match[0]} de {match[1]} al {match[2]} de {match[3]}"
#                 if match[4]:
#                     date_range += f" de {match[4]}"
#                 found_dates.append(date_range)
#
#             # Fechas con "Al"
#             al_matches = al_date_pattern.findall(line)
#             for match in al_matches:
#                 al_date = "Al " + " ".join([part for part in match if part]).strip()
#                 found_dates.append(al_date)
#
#         # Limpiar y eliminar duplicados
#         found_dates = [date.strip() for date in found_dates if date.strip()]
#         unique_dates = list(dict.fromkeys(found_dates))
#
#         return unique_dates
#
#     def extract_month_from_numeric_date(self, date: str) -> str:
#         """
#         Extrae mes de fechas numéricas (solo si el día es 30 o 31).
#
#         Args:
#             date (str): Fecha en formato numérico
#
#         Returns:
#             str: Nombre del mes o cadena vacía
#         """
#         patterns = [
#             r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",  # DD/MM/YYYY
#             r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"  # YYYY/MM/DD
#         ]
#
#         for pattern in patterns:
#             match = re.match(pattern, date)
#             if match:
#                 if pattern == patterns[0]:  # DD/MM/YYYY
#                     day = int(match.group(1))
#                     month_num = int(match.group(2))
#                 else:  # YYYY/MM/DD
#                     day = int(match.group(3))
#                     month_num = int(match.group(2))
#
#                 # Solo procesar si el día es 30 o 31
#                 if day not in [30, 31]:
#                     return ""
#
#                 # Convertir número de mes a nombre
#                 for month, num in self.month_numbers.items():
#                     if num == month_num:
#                         return month
#         return ""
#
#     def extract_month_from_textual_date(self, date: str) -> str:
#         """
#         Extrae mes de fechas textuales (solo si el día es 30 o 31).
#
#         Args:
#             date (str): Fecha en formato textual
#
#         Returns:
#             str: Nombre del mes o cadena vacía
#         """
#         pattern = re.compile(r"(\d{1,2})\s*de\s*(" + self.months_pattern + r")\b", re.IGNORECASE)
#         match = pattern.search(date)
#
#         if match:
#             day = int(match.group(1))
#             month_raw = match.group(2).lower()
#             month = self.normalize_month.get(month_raw, month_raw)
#
#             # Solo contar si el día es 30 o 31
#             if day in [30, 31]:
#                 return month
#         return ""
#
#     def has_day_30_or_31_textual(self, date: str) -> bool:
#         """
#         Verifica si una fecha textual tiene día 30 o 31.
#
#         Args:
#             date (str): Fecha a verificar
#
#         Returns:
#             bool: True si tiene día 30 o 31
#         """
#         pattern = re.compile(r"(\d{1,2})\s*de\s*(" + self.months_pattern + r")\b", re.IGNORECASE)
#         match = pattern.search(date)
#
#         if match:
#             day = int(match.group(1))
#             return day in [30, 31]
#         return False
#
#     def is_only_month(self, date: str) -> bool:
#         """
#         Verifica si la fecha es solo un mes (sin día específico).
#
#         Args:
#             date (str): Fecha a verificar
#
#         Returns:
#             bool: True si es solo un mes
#         """
#         date_lower = date.lower().strip()
#         return date_lower in self.month_variants
#
#     def extract_first_month_from_dates(self, dates: List[str]) -> str:
#         """
#         Extrae solo el PRIMER mes encontrado en la lista de fechas.
#
#         Args:
#             dates (List[str]): Lista de fechas
#
#         Returns:
#             str: Primer mes encontrado o cadena vacía
#         """
#         for date in dates:
#             date_lower = date.lower()
#
#             # Caso 1: Si es solo un mes (sin día), siempre lo detectamos
#             if self.is_only_month(date):
#                 for month in self.months:
#                     if month in date_lower:
#                         return month
#                 continue
#
#             # Caso 2: Si es fecha con día, aplicamos restricción de días 30 o 31
#             textual_month = self.extract_month_from_textual_date(date)
#             if textual_month:
#                 return textual_month
#
#             # Si no hay mes textual válido, verificar si tiene día 30 o 31
#             if self.has_day_30_or_31_textual(date):
#                 for month in self.months:
#                     if month in date_lower:
#                         return month
#             else:
#                 # Intentar con fecha numérica
#                 extracted_month = self.extract_month_from_numeric_date(date)
#                 if extracted_month:
#                     return extracted_month
#
#         return ""
#
#     def search_annual_rent_form(self, pages: Dict[str, List[str]]) -> bool:
#         """
#         Busca si aparece formulario de renta anual en las primeras páginas.
#
#         Args:
#             pages (Dict[str, List[str]]): Páginas con líneas de texto
#
#         Returns:
#             bool: True si se encuentra formulario de renta anual
#         """
#         pattern = re.compile(r"formulario\s*\d+\s*renta\s*anual", re.IGNORECASE)
#         pages_to_check = list(pages.keys())[:3]
#
#         for page in pages_to_check:
#             page_text = " ".join(pages[page]).lower()
#             if pattern.search(page_text):
#                 return True
#         return False
#
#     def determine_periodicity_with_first_months(self, first_months: List[str], has_rent_form: bool) -> str:
#         """
#         Determina periodicidad basándose en los primeros meses de cada página.
#
#         Args:
#             first_months (List[str]): Lista de primeros meses detectados
#             has_rent_form (bool): Si aparece formulario de renta anual
#
#         Returns:
#             str: "anual" o "trimestral"
#         """
#         if has_rent_form:
#             return "anual"
#
#         # Eliminar duplicados manteniendo el orden
#         unique_months = list(dict.fromkeys(first_months))
#
#         # Lógica principal:
#         # Si hay más de un mes diferente -> trimestral
#         if len(unique_months) > 1:
#             return "trimestral"
#
#         # Si todos los meses son diciembre -> anual
#         if len(unique_months) == 1 and unique_months[0] == "diciembre":
#             return "anual"
#
#         # Si hay un solo mes y NO es diciembre -> trimestral
#         if len(unique_months) == 1 and unique_months[0] != "diciembre":
#             return "trimestral"
#
#         # Casos adicionales
#         if len(unique_months) >= 4:
#             return "anual"
#
#         return "anual"
#
#     def analyze_periodicity(self, text: str, lines_per_page: int = 10) -> str:
#         """
#         Función principal que determina periodicidad desde texto.
#
#         Args:
#             text (str): Texto completo del documento
#             lines_per_page (int): Número de líneas a analizar por página
#
#         Returns:
#             str: "anual" o "trimestral"
#         """
#         # Normalizar texto
#         normalized_text = self.normalize_text(text)
#
#         # Extraer primeras líneas por página
#         page_lines = self.extract_first_lines_per_page(normalized_text, lines_per_page)
#
#         # Buscar formulario de renta anual
#         has_rent_form = self.search_annual_rent_form(page_lines)
#
#         # Procesar solo las primeras 3 páginas
#         first_months_per_page = []
#
#         for page, lines in list(page_lines.items())[:3]:
#             dates = self.search_dates_in_lines(lines)
#             first_month = self.extract_first_month_from_dates(dates)
#             if first_month:
#                 first_months_per_page.append(first_month)
#
#         # Determinar periodicidad
#         periodicity = self.determine_periodicity_with_first_months(
#             first_months_per_page,
#             has_rent_form
#         )
#
#         logger.info(f"Primeros meses detectados: {first_months_per_page}")
#         logger.info(f"Formulario renta: {has_rent_form}")
#         logger.info(f"Periodicidad determinada: {periodicity}")
#
#         return periodicity
#
#     def analyze_periodicity_with_debug(self, text: str, lines_per_page: int = 10) -> Dict:
#         """
#         Versión con información de debug para análisis detallado.
#
#         Args:
#             text (str): Texto completo del documento
#             lines_per_page (int): Número de líneas a analizar por página
#
#         Returns:
#             Dict: Información detallada del proceso de análisis
#         """
#         normalized_text = self.normalize_text(text)
#         page_lines = self.extract_first_lines_per_page(normalized_text, lines_per_page)
#         has_rent_form = self.search_annual_rent_form(page_lines)
#
#         debug_info = {
#             "formulario_renta_detectado": has_rent_form,
#             "paginas_procesadas": [],
#             "primeros_meses_por_pagina": [],
#             "periodicidad": ""
#         }
#
#         first_months_per_page = []
#
#         for page, lines in list(page_lines.items())[:3]:
#             dates = self.search_dates_in_lines(lines)
#             first_month = self.extract_first_month_from_dates(dates)
#
#             page_info = {
#                 "pagina": page,
#                 "fechas_encontradas": dates,
#                 "primer_mes_detectado": first_month
#             }
#
#             debug_info["paginas_procesadas"].append(page_info)
#
#             if first_month:
#                 first_months_per_page.append(first_month)
#
#         debug_info["primeros_meses_por_pagina"] = first_months_per_page
#
#         periodicity = self.determine_periodicity_with_first_months(
#             first_months_per_page,
#             has_rent_form
#         )
#
#         debug_info["periodicidad"] = periodicity
#
#         return debug_info
#
#


import os
import logging
import re
from typing import List, Dict, Tuple, Optional, Set
from functools import lru_cache
from collections import Counter

# Configuración del logger
logger = logging.getLogger(__name__)


class PeriodicityAnalyzer:
    """
    Clase para analizar la periodicidad de documentos basándose en fechas encontradas.
    Determina si un documento es anual o trimestral.
    """

    def __init__(self):
        """Inicializa el analizador de periodicidad."""

        # Constantes de meses - usando tuplas para inmutabilidad
        self.months = (
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        )

        # Diccionario más eficiente para normalización
        self.normalize_month = {
            "ene": "enero", "feb": "febrero", "mar": "marzo", "abr": "abril",
            "may": "mayo", "jun": "junio", "jul": "julio", "ago": "agosto",
            "sep": "septiembre", "set": "septiembre", "sept": "septiembre",
            "setiembre": "septiembre", "oct": "octubre", "nov": "noviembre",
            "dic": "diciembre",
            # Agregamos las formas completas para evitar búsquedas innecesarias
            "enero": "enero", "febrero": "febrero", "marzo": "marzo",
            "abril": "abril", "mayo": "mayo", "junio": "junio",
            "julio": "julio", "agosto": "agosto", "septiembre": "septiembre",
            "octubre": "octubre", "noviembre": "noviembre", "diciembre": "diciembre"
        }

        # Pre-compilar el patrón de meses para mejor rendimiento
        self.months_pattern = "|".join(self.normalize_month.keys())
        self._months_regex = re.compile(
            rf"\b({self.months_pattern})\b",
            re.IGNORECASE
        )

        # Diccionario inverso para búsquedas más rápidas
        self.month_to_number = {month: i + 1 for i, month in enumerate(self.months)}

        # Pre-compilar patrones frecuentes
        self._compile_patterns()

        # Meses que típicamente indican fin de trimestre
        self.quarter_end_months = {"marzo", "junio", "septiembre", "diciembre"}

    def _compile_patterns(self):
        """Pre-compila los patrones regex para mejor rendimiento."""
        self._patterns = {
            'numeric': re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"),
            'year': re.compile(r"\b(?:de|del|año[s]?)(?:\s+)?(\d{4})\b", re.IGNORECASE),
            'textual': re.compile(
                rf"\b(\d{{1,2}})?\s*(?:de|del)?\s*({self.months_pattern})\s*(?:de|del)?\s*(\d{{4}})?\b",
                re.IGNORECASE
            ),
            'range': re.compile(
                rf"del\s+(\d{{1,2}})\s+de\s+({self.months_pattern})\s+al\s+(\d{{1,2}})\s+de\s+({self.months_pattern})(?:\s+de\s+(\d{{4}}))?",
                re.IGNORECASE
            ),
            'al_date': re.compile(
                rf"\b[Aa][Ll]\s+(\d{{1,2}})?\s*(?:de|del)?\s*({self.months_pattern})\s*(?:de|del)?\s*(\d{{4}})?\b",
                re.IGNORECASE
            ),
            'rent_form': re.compile(r"formulario\s*\d+\s*renta\s*anual", re.IGNORECASE),
            'day_month': re.compile(rf"(\d{{1,2}})\s*(?:de|del)\s*({self.months_pattern})\b", re.IGNORECASE),
            # Nuevos patrones para mejor detección
            'quarterly_indicators': re.compile(
                r"\b(?:trimestre|trimestral|quarterly|Q[1-4]|[1-4]T|TRIMESTRE\s+[IVX]+)\b",
                re.IGNORECASE
            ),
            'annual_indicators': re.compile(
                r"\b(?:anual|yearly|ejercicio\s+completo|año\s+completo)\b",
                re.IGNORECASE
            ),
            # Patrón para detectar encabezados de estados financieros
            'financial_header': re.compile(
                r"estados?\s+financieros?\s*\|?\s*(?:individual|consolidado)?\s*(?:trimestre|anual)",
                re.IGNORECASE
            )
        }

    @lru_cache(maxsize=128)
    def normalize_text(self, text: str) -> str:
        """
        Normaliza las variantes de meses en el texto.
        Usa cache para textos repetidos.

        Args:
            text (str): Texto a normalizar

        Returns:
            str: Texto normalizado
        """

        # Método optimizado usando regex compilado
        def replacer(match):
            month = match.group(1).lower()
            return self.normalize_month.get(month, month)

        return self._months_regex.sub(replacer, text)

    def extract_first_lines_per_page(self, text: str, lines_per_page: int = 10) -> Dict[str, List[str]]:
        """
        Extrae las primeras líneas de cada página del documento.

        Args:
            text (str): Texto completo del documento
            lines_per_page (int): Número de líneas a extraer por página

        Returns:
            Dict[str, List[str]]: Diccionario con líneas por página
        """
        # Usar split más eficiente
        page_separator = "###PAGE_ID:"
        if page_separator not in text:
            # Si no hay separadores de página, tratar todo como una página
            lines = text.strip().splitlines()
            return {"PAGE_1": lines[:lines_per_page]}

        pages = text.split(page_separator)
        result = {}

        for i, page_content in enumerate(pages[1:], start=1):  # Ignorar primera división vacía
            # Encontrar donde termina el ID y empieza el contenido
            content_start = page_content.find("###")
            if content_start != -1:
                page_content = page_content[content_start + 3:]

            lines = page_content.strip().splitlines()
            if lines:  # Solo agregar páginas con contenido
                result[f"PAGE_{i}"] = lines[:lines_per_page]

        return result

    def search_dates_in_lines(self, lines: List[str]) -> List[str]:
        """
        Busca todas las fechas en las líneas proporcionadas.
        Versión optimizada con menos redundancia.

        Args:
            lines (List[str]): Líneas de texto donde buscar fechas

        Returns:
            List[str]: Lista de fechas encontradas únicas
        """
        found_dates = []

        # Procesar todas las líneas de una vez para mejor rendimiento
        full_text = "\n".join(lines)

        logger.info(f"Buscando fechas en {len(lines)} líneas de texto")

        # Aplicar cada patrón una sola vez
        # Fechas numéricas
        numeric_matches = self._patterns['numeric'].findall(full_text)
        if numeric_matches:
            logger.info(f"Fechas numéricas encontradas: {numeric_matches[:3]}...")  # Solo primeras 3
            found_dates.extend(numeric_matches)

        # Años
        year_matches = self._patterns['year'].findall(full_text)
        if year_matches:
            logger.info(f"Años encontrados: {set(year_matches)}")  # Set para evitar repetidos en log
        found_dates.extend(year_matches)

        # Fechas textuales - mejorado para manejar "del"
        textual_matches = self._patterns['textual'].findall(full_text)
        logger.info(f"Fechas textuales encontradas: {len(textual_matches)}")

        for match in textual_matches:
            # match es una tupla: (día, mes, año)
            parts = []
            if match[0]:  # día
                parts.append(match[0])
            if match[1]:  # mes
                parts.append(match[1])
            if match[2]:  # año
                parts.append(match[2])

            if parts and match[1]:  # Asegurarse de que hay al menos un mes
                date = " de ".join(parts)
                found_dates.append(date)

        # Rangos de fechas
        range_matches = self._patterns['range'].findall(full_text)
        if range_matches:
            logger.info(f"Rangos de fechas encontrados: {len(range_matches)}")

        for match in range_matches:
            date_range = f"del {match[0]} de {match[1]} al {match[2]} de {match[3]}"
            if match[4]:
                date_range += f" de {match[4]}"
            found_dates.append(date_range)

        # Fechas con "Al" - común en estados financieros
        al_matches = self._patterns['al_date'].findall(full_text)
        if al_matches:
            logger.info(f"Fechas con 'Al' encontradas: {len(al_matches)}")

        for match in al_matches:
            parts = []
            if match[0]:  # día
                parts.append(match[0])
            if match[1]:  # mes
                parts.append(match[1])
            if match[2]:  # año
                parts.append(match[2])

            if parts and match[1]:  # Asegurarse de que hay al menos un mes
                found_dates.append("Al " + " de ".join(parts))

        # Eliminar duplicados manteniendo orden
        seen = set()
        unique_dates = []
        for date in found_dates:
            date_clean = date.strip()
            if date_clean and date_clean not in seen:
                seen.add(date_clean)
                unique_dates.append(date_clean)

        logger.info(f"Total fechas únicas encontradas: {len(unique_dates)}")

        return unique_dates

    def extract_month_from_numeric_date(self, date: str) -> str:
        """
        Extrae mes de fechas numéricas (solo si el día es 30 o 31).
        Versión optimizada con validación mejorada.

        Args:
            date (str): Fecha en formato numérico

        Returns:
            str: Nombre del mes o cadena vacía
        """
        # Intentar ambos formatos
        for pattern, day_idx, month_idx in [
            (r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", 0, 1),  # DD/MM/YYYY
            (r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", 2, 1)  # YYYY/MM/DD
        ]:
            match = re.match(pattern, date.strip())
            if match:
                try:
                    day = int(match.group(day_idx + 1))
                    month_num = int(match.group(month_idx + 1))

                    # Validar día y mes
                    if day in [30, 31] and 1 <= month_num <= 12:
                        return self.months[month_num - 1]
                except (ValueError, IndexError):
                    continue

        return ""

    def extract_month_from_textual_date(self, date: str) -> str:
        """
        Extrae mes de fechas textuales (solo si el día es 30 o 31).
        Versión optimizada.

        Args:
            date (str): Fecha en formato textual

        Returns:
            str: Nombre del mes o cadena vacía
        """
        match = self._patterns['day_month'].search(date)

        if match:
            try:
                day = int(match.group(1))
                if day in [30, 31]:
                    month_raw = match.group(2).lower()
                    return self.normalize_month.get(month_raw, month_raw)
            except ValueError:
                pass

        return ""

    def has_day_30_or_31_textual(self, date: str) -> bool:
        """
        Verifica si una fecha textual tiene día 30 o 31.

        Args:
            date (str): Fecha a verificar

        Returns:
            bool: True si tiene día 30 o 31
        """
        match = self._patterns['day_month'].search(date)

        if match:
            try:
                day = int(match.group(1))
                return day in [30, 31]
            except ValueError:
                pass

        return False

    def is_only_month(self, date: str) -> bool:
        """
        Verifica si la fecha es solo un mes (sin día específico).

        Args:
            date (str): Fecha a verificar

        Returns:
            bool: True si es solo un mes
        """
        date_clean = date.lower().strip()
        return date_clean in self.normalize_month

    def extract_first_month_from_dates(self, dates: List[str]) -> str:
        """
        Extrae solo el PRIMER mes encontrado en la lista de fechas.
        Versión optimizada con menos iteraciones.

        Args:
            dates (List[str]): Lista de fechas

        Returns:
            str: Primer mes encontrado o cadena vacía
        """
        logger.info(f"Extrayendo primer mes de {len(dates)} fechas")

        for i, date in enumerate(dates):
            if not date:
                continue

            date_lower = date.lower()

            # Caso 1: Si es solo un mes (sin día)
            if self.is_only_month(date):
                normalized = self.normalize_month.get(date_lower.strip())
                if normalized:
                    logger.info(f"Mes encontrado (solo mes): '{normalized}' en fecha #{i + 1}")
                    return normalized
                continue

            # Caso 2: Fechas con día 30 o 31
            # Primero intentar extracción textual (más común)
            month = self.extract_month_from_textual_date(date)
            if month:
                logger.info(f"Mes encontrado (fecha textual día 30/31): '{month}' en fecha #{i + 1}: {date}")
                return month

            # Si no, intentar numérica
            month = self.extract_month_from_numeric_date(date)
            if month:
                logger.info(f"Mes encontrado (fecha numérica día 30/31): '{month}' en fecha #{i + 1}: {date}")
                return month

        logger.info("No se encontró ningún mes válido con día 30/31")
        return ""

    def search_annual_rent_form(self, pages: Dict[str, List[str]]) -> bool:
        """
        Busca si aparece formulario de renta anual en las primeras páginas.
        Versión optimizada.

        Args:
            pages (Dict[str, List[str]]): Páginas con líneas de texto

        Returns:
            bool: True si se encuentra formulario de renta anual
        """
        # Obtener solo las primeras 3 páginas
        pages_to_check = list(pages.items())[:3]

        logger.info(f"Buscando formulario de renta anual en primeras {len(pages_to_check)} páginas")

        for page_name, lines in pages_to_check:
            # Unir líneas y buscar una sola vez por página
            page_text = " ".join(lines)
            if self._patterns['rent_form'].search(page_text):
                logger.info(f"Formulario de renta anual encontrado en {page_name}")
                return True

        logger.info("No se encontró formulario de renta anual")
        return False

    def _check_additional_indicators(self, pages: Dict[str, List[str]]) -> Dict[str, bool]:
        """
        Busca indicadores adicionales de periodicidad en el documento.

        Args:
            pages (Dict[str, List[str]]): Páginas del documento

        Returns:
            Dict con indicadores encontrados
        """
        indicators = {
            'has_quarterly_terms': False,
            'has_annual_terms': False
        }

        # Revisar primeras 3 páginas
        pages_to_check = list(pages.items())[:3]
        logger.info(f"Buscando indicadores adicionales en {len(pages_to_check)} páginas")

        for page_name, lines in pages_to_check:
            text = " ".join(lines)

            if self._patterns['quarterly_indicators'].search(text):
                indicators['has_quarterly_terms'] = True
                logger.info(f"Términos trimestrales encontrados en {page_name}")

            if self._patterns['annual_indicators'].search(text):
                indicators['has_annual_terms'] = True
                logger.info(f"Términos anuales encontrados en {page_name}")

        return indicators

    def determine_periodicity_with_first_months(self, first_months: List[str], has_rent_form: bool) -> str:
        """
        Determina periodicidad basándose en los primeros meses de cada página.
        Versión mejorada con lógica más robusta.

        Args:
            first_months (List[str]): Lista de primeros meses detectados
            has_rent_form (bool): Si aparece formulario de renta anual

        Returns:
            str: "anual" o "trimestral"
        """
        # Si hay formulario de renta anual, es definitivamente anual
        if has_rent_form:
            logger.info("Periodicidad: ANUAL (formulario de renta anual detectado)")
            return "anual"

        # Si no hay meses detectados, por defecto anual
        if not first_months:
            logger.info("Periodicidad: ANUAL (no se detectaron meses)")
            return "anual"

        # Eliminar duplicados manteniendo el orden
        unique_months = list(dict.fromkeys(first_months))

        logger.info(f"Meses únicos detectados: {unique_months}")

        # Contar cuántos son meses de fin de trimestre
        quarter_months_count = sum(1 for month in unique_months
                                   if month in self.quarter_end_months)

        logger.info(f"Meses de fin de trimestre: {quarter_months_count} de {len(unique_months)}")

        # Lógica mejorada:
        # 1. Si todos los meses son diciembre -> anual
        if len(unique_months) == 1 and unique_months[0] == "diciembre":
            logger.info("Periodicidad: ANUAL (solo diciembre detectado)")
            return "anual"

        # 2. Si hay un solo mes NO diciembre -> trimestral
        if len(unique_months) == 1 and unique_months[0] != "diciembre":
            logger.info(f"Periodicidad: TRIMESTRAL (solo {unique_months[0]} detectado)")
            return "trimestral"

        # 3. Si hay múltiples meses
        if len(unique_months) > 1:
            # Si la mayoría son meses de fin de trimestre -> trimestral
            if quarter_months_count >= len(unique_months) * 0.6:
                logger.info("Periodicidad: TRIMESTRAL (mayoría son meses de fin de trimestre)")
                return "trimestral"

            # Si hay 4 o más meses diferentes -> probablemente anual
            if len(unique_months) >= 4:
                logger.info("Periodicidad: ANUAL (4 o más meses diferentes)")
                return "anual"

            # Por defecto con múltiples meses -> trimestral
            logger.info("Periodicidad: TRIMESTRAL (múltiples meses detectados)")
            return "trimestral"

        # Caso por defecto
        logger.info("Periodicidad: ANUAL (caso por defecto)")
        return "anual"

    def analyze_periodicity(self, text: str, lines_per_page: int = 10) -> str:
        """
        Función principal que determina periodicidad desde texto.
        Versión mejorada con análisis adicional.

        Args:
            text (str): Texto completo del documento
            lines_per_page (int): Número de líneas a analizar por página

        Returns:
            str: "anual" o "trimestral"
        """
        logger.info("=" * 50)
        logger.info("Iniciando análisis de periodicidad")

        # Validar entrada
        if not text or not text.strip():
            logger.warning("Texto vacío recibido para análisis")
            return "anual"

        # Normalizar texto
        normalized_text = self.normalize_text(text)

        # Extraer primeras líneas por página
        page_lines = self.extract_first_lines_per_page(normalized_text, lines_per_page)

        if not page_lines:
            logger.warning("No se pudieron extraer páginas del documento")
            return "anual"

        logger.info(f"Total de páginas extraídas: {len(page_lines)}")

        # Buscar formulario de renta anual
        has_rent_form = self.search_annual_rent_form(page_lines)

        # Buscar indicadores adicionales
        indicators = self._check_additional_indicators(page_lines)

        # Procesar solo las primeras 3 páginas
        first_months_per_page = []

        for page_name in list(page_lines.keys())[:3]:
            logger.info(f"\nProcesando {page_name}...")
            lines = page_lines[page_name]
            dates = self.search_dates_in_lines(lines)

            if dates:
                logger.info(f"Fechas encontradas en {page_name}: {dates[:5]}{'...' if len(dates) > 5 else ''}")

            first_month = self.extract_first_month_from_dates(dates)
            if first_month:
                first_months_per_page.append(first_month)
                logger.info(f"✓ Primer mes de {page_name}: {first_month}")
            else:
                logger.info(f"✗ No se encontró mes válido en {page_name}")

        logger.info(f"\n--- RESUMEN ---")
        logger.info(f"Formulario renta anual: {'SÍ' if has_rent_form else 'NO'}")
        logger.info(f"Términos trimestrales: {'SÍ' if indicators['has_quarterly_terms'] else 'NO'}")
        logger.info(f"Términos anuales: {'SÍ' if indicators['has_annual_terms'] else 'NO'}")
        logger.info(f"Primeros meses detectados: {first_months_per_page}")

        # Determinar periodicidad con toda la información
        periodicity = self.determine_periodicity_with_first_months(
            first_months_per_page,
            has_rent_form
        )

        # Ajustar basado en indicadores adicionales si hay ambigüedad
        if not has_rent_form and len(first_months_per_page) <= 1:
            if indicators['has_quarterly_terms'] and not indicators['has_annual_terms']:
                logger.info("Ajuste: Detectados términos trimestrales sin términos anuales")
                periodicity = "trimestral"
            elif indicators['has_annual_terms'] and not indicators['has_quarterly_terms']:
                logger.info("Ajuste: Detectados términos anuales sin términos trimestrales")
                periodicity = "anual"

        logger.info(f"\n>>> PERIODICIDAD FINAL: {periodicity.upper()} <<<")
        logger.info("=" * 50 + "\n")

        return periodicity

    def analyze_periodicity_with_debug(self, text: str, lines_per_page: int = 10) -> Dict:
        """
        Versión con información de debug para análisis detallado.
        Mejorada con más información diagnóstica.

        Args:
            text (str): Texto completo del documento
            lines_per_page (int): Número de líneas a analizar por página

        Returns:
            Dict: Información detallada del proceso de análisis
        """
        # Validar entrada
        if not text or not text.strip():
            return {
                "error": "Texto vacío recibido",
                "periodicidad": "anual"
            }

        normalized_text = self.normalize_text(text)
        page_lines = self.extract_first_lines_per_page(normalized_text, lines_per_page)
        has_rent_form = self.search_annual_rent_form(page_lines)
        indicators = self._check_additional_indicators(page_lines)

        debug_info = {
            "formulario_renta_detectado": has_rent_form,
            "indicadores_adicionales": indicators,
            "paginas_totales": len(page_lines),
            "paginas_procesadas": [],
            "primeros_meses_por_pagina": [],
            "meses_unicos": [],
            "meses_fin_trimestre": [],
            "periodicidad": "",
            "razon_decision": ""
        }

        first_months_per_page = []

        for page_name in list(page_lines.keys())[:3]:
            lines = page_lines[page_name]
            dates = self.search_dates_in_lines(lines)
            first_month = self.extract_first_month_from_dates(dates)

            page_info = {
                "pagina": page_name,
                "lineas_analizadas": len(lines),
                "fechas_encontradas": dates[:5],  # Limitar para no sobrecargar
                "total_fechas": len(dates),
                "primer_mes_detectado": first_month
            }

            debug_info["paginas_procesadas"].append(page_info)

            if first_month:
                first_months_per_page.append(first_month)

        debug_info["primeros_meses_por_pagina"] = first_months_per_page
        debug_info["meses_unicos"] = list(dict.fromkeys(first_months_per_page))
        debug_info["meses_fin_trimestre"] = [
            m for m in debug_info["meses_unicos"]
            if m in self.quarter_end_months
        ]

        # Determinar periodicidad
        periodicity = self.determine_periodicity_with_first_months(
            first_months_per_page,
            has_rent_form
        )

        # Ajustar con indicadores adicionales
        if not has_rent_form and len(first_months_per_page) <= 1:
            if indicators['has_quarterly_terms'] and not indicators['has_annual_terms']:
                periodicity = "trimestral"
                debug_info["razon_decision"] = "Indicadores trimestrales encontrados"
            elif indicators['has_annual_terms'] and not indicators['has_quarterly_terms']:
                periodicity = "anual"
                debug_info["razon_decision"] = "Indicadores anuales encontrados"

        if not debug_info["razon_decision"]:
            if has_rent_form:
                debug_info["razon_decision"] = "Formulario de renta anual detectado"
            elif len(debug_info["meses_unicos"]) > 1:
                debug_info["razon_decision"] = "Múltiples meses diferentes detectados"
            elif len(debug_info["meses_unicos"]) == 1:
                if debug_info["meses_unicos"][0] == "diciembre":
                    debug_info["razon_decision"] = "Solo diciembre detectado"
                else:
                    debug_info["razon_decision"] = f"Solo {debug_info['meses_unicos'][0]} detectado (no diciembre)"

        debug_info["periodicidad"] = periodicity

        return debug_info