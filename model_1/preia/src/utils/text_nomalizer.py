import re
from typing import Dict, Optional, List


class TextNormalizer:
    """
    Clase genérica y simple para normalización de texto.
    Limpia caracteres mal codificados, espacios, y otros elementos de texto.
    """

    def __init__(self,
                 fix_encoding: bool = True,
                 fix_spaces: bool = True,
                 remove_special_chars: bool = False,
                 custom_replacements: Dict[str, str] = None):
        """
        Args:
            fix_encoding: Si corregir caracteres mal codificados (Ã³→ó, etc.)
            fix_spaces: Si normalizar espacios múltiples
            remove_special_chars: Si remover caracteres especiales no deseados
            custom_replacements: Diccionario con reemplazos personalizados
        """
        self.fix_encoding = fix_encoding
        self.fix_spaces = fix_spaces
        self.remove_special_chars = remove_special_chars
        self.custom_replacements = custom_replacements or {}

        # Mapeo de caracteres mal codificados
        self._encoding_fixes = {
            'Ã³': 'ó', 'Ã±': 'ñ', 'Ã­': 'í', 'Ã¡': 'á', 'Ã©': 'é', 'Ãº': 'ú',
            'Ã¬': 'ì', 'Ã²': 'ò', 'Ã¹': 'ù', 'Ã ': 'à', 'Ã¨': 'è', 'Ã§': 'ç',
            'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã¼': 'ü', 'ÃŸ': 'ß', 'Â°': '°', 'Â±': '±',
            'Â': '', 'Ã': ''
        }

        # Caracteres especiales comunes a remover
        self._special_chars = ['', '', '', '', '']

    def normalize(self, text: str) -> str:
        """
        Normaliza el texto aplicando todas las configuraciones.

        Args:
            text: Texto a normalizar

        Returns:
            Texto normalizado
        """
        if not text:
            return text

        result = text

        # 1. Corregir encoding
        if self.fix_encoding:
            result = self._fix_encoding(result)

        # 2. Reemplazos personalizados
        if self.custom_replacements:
            result = self._apply_custom_replacements(result)

        # 3. Normalizar espacios
        if self.fix_spaces:
            result = self._fix_spaces(result)

        # 4. Remover caracteres especiales
        if self.remove_special_chars:
            result = self._remove_special_chars(result)

        return result

    def normalize_file(self, input_path: str, output_path: str = None) -> str:
        """
        Normaliza un archivo completo.

        Args:
            input_path: Ruta del archivo a normalizar
            output_path: Ruta de salida (opcional, sino sobrescribe)

        Returns:
            Texto normalizado
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()

            normalized_text = self.normalize(text)

            output_file = output_path if output_path else input_path
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(normalized_text)

            return normalized_text

        except Exception as e:
            raise Exception(f"Error processing file: {e}")

    def normalize_lines(self, lines: List[str]) -> List[str]:
        """
        Normaliza una lista de líneas.

        Args:
            lines: Lista de líneas a normalizar

        Returns:
            Lista de líneas normalizadas
        """
        return [self.normalize(line) for line in lines]

    def _fix_encoding(self, text: str) -> str:
        """Corrige caracteres mal codificados"""
        result = text
        for bad_char, good_char in self._encoding_fixes.items():
            result = result.replace(bad_char, good_char)
        return result

    def _fix_spaces(self, text: str) -> str:
        """Normaliza espacios múltiples"""
        # Convertir múltiples espacios en uno solo
        result = re.sub(r' +', ' ', text)
        # Limpiar espacios al inicio y final de líneas
        result = re.sub(r'^ +| +$', '', result, flags=re.MULTILINE)
        return result

    def _remove_special_chars(self, text: str) -> str:
        """Remueve caracteres especiales no deseados"""
        result = text
        for char in self._special_chars:
            result = result.replace(char, '')
        return result

    def _apply_custom_replacements(self, text: str) -> str:
        """Aplica reemplazos personalizados"""
        result = text
        for old_text, new_text in self.custom_replacements.items():
            result = result.replace(old_text, new_text)
        return result

    def add_replacement(self, old_text: str, new_text: str):
        """Agrega un reemplazo personalizado"""
        self.custom_replacements[old_text] = new_text

    def remove_replacement(self, old_text: str):
        """Remueve un reemplazo personalizado"""
        if old_text in self.custom_replacements:
            del self.custom_replacements[old_text]


# Función de conveniencia para uso rápido
def normalize_text(text: str,
                   fix_encoding: bool = True,
                   fix_spaces: bool = True,
                   remove_special_chars: bool = False) -> str:
    """Función rápida para normalizar texto"""
    normalizer = TextNormalizer(
        fix_encoding=fix_encoding,
        fix_spaces=fix_spaces,
        remove_special_chars=remove_special_chars
    )
    return normalizer.normalize(text)


def normalize_file(file_path: str, output_path: str = None) -> str:
    """Función rápida para normalizar archivos"""
    normalizer = TextNormalizer()
    return normalizer.normalize_file(file_path, output_path)


