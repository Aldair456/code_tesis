import asyncio
import re

def extract_delimited_text(text: str, char_start: str, char_end: str) -> str | None:
    """
    Extrae de forma eficiente un bloque de texto delimitado dentro de 'text',
    usando los caracteres de inicio y fin proporcionados.
    """
    if not text or not char_start or not char_end:
        return None  # Validación de entrada

    start = text.find(char_start)
    end = text.rfind(char_end)

    if start == -1 or end == -1 or end <= start:
        return None

    return text[start:end + 1]



def textract_tables_to_text(content_tables) -> str:
    """
    Convierte las tablas extraídas de Amazon Textract en un formato de texto legible.

    :param content_tables: Lista de tablas extraídas por Textract. Cada tabla es una lista de filas,
                            y cada fila es una lista de celdas.
    :return: Una cadena de texto que representa las tablas extraídas, formateadas adecuadamente.
    """
    resultado_str = "=== Resultados de Análisis de Textract ===\n\n"

    for idx, table in enumerate(content_tables, start=1):
        resultado_str += f"\n--- Tabla #{idx} ---\n"

        for row in table:
            # Formatear cada fila como una cadena de texto separada por " | "
            formatted_row = " | ".join([str(cell) if cell else "N/A" for cell in row])
            resultado_str += f"{formatted_row}\n"

        resultado_str += "\n" + "-" * 40 + "\n"
    return resultado_str


async def find_page_content(texto, page_id: int):
    """
    Extrae el contenido completo de la página dada por su ID en el texto recibido de forma asíncrona.

    :param texto: Cadena de texto a analizar.
    :param page_id: ID de la página que se quiere extraer.
    :return: El contenido completo de la página o None si no se encuentra.
    """
    # Crear el patrón para buscar la página específica
    page_id_pattern = f'###PAGE_ID:{page_id:03d}###'

    # Busca la página en el texto
    match = await asyncio.to_thread(re.search, page_id_pattern, texto)

    if match:
        # Encontramos el inicio de la página, ahora vamos a obtener el contenido hasta el siguiente `PAGE_ID` o fin del texto
        start_index = match.end()  # Después de la coincidencia del PAGE_ID
        next_page_match = await asyncio.to_thread(re.search, r'###PAGE_ID:\d{3}###', texto[start_index:])

        if next_page_match:
            # Si encontramos el siguiente PAGE_ID, la página termina antes de este
            end_index = start_index + next_page_match.start()
            return texto[start_index:end_index].strip()  # Devolvemos el contenido de la página
        else:
            # Si no hay más PAGE_ID, significa que esta es la última página
            return texto[start_index:].strip()  # Devolvemos el resto del texto como la última página

    return None  # Si no se encuentra el `PAGE_ID`, devolvemos None