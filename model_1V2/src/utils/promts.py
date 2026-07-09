import json
def promt_anuales_bs_and_pl(text):
    prompt = (
        """
        Eres un experto en identificar los estados financieros denominados "bs" (correspondiente a "Estado de Situación Financiera", "Balance General" o términos similares) y "pl" (correspondiente a "Estado de Resultados", "Pérdidas y Ganancias", "Profit & Loss", "P&L" o términos similares). Tu tarea es analizar el texto proporcionado y detectar las páginas en las que se encuentran estos estados financieros. Debes devolver la siguiente estructura en formato JSON:

        {
            "bs": [página donde inicia, página donde termina],
            "pl": [página donde inicia, página donde termina]
        }

        Dado que estos estados financieros son anuales, aparecerán en una sola página cada uno. Por lo tanto, la página de inicio y la página de fin serán la misma. Si no encuentras alguno de los estados financieros, devuelve null en su lugar. Si no encuentras alguno de los estados financieros, devuelve `null` en su lugar.
        """
        f"El texto que debes procesar tiene las páginas enumeradas al inicio de cada página de la siguiente manera: ###PAGE_ID:numero###. Asegúrate de extraer correctamente las páginas correspondientes para cada estado financiero.\n\n {text}"
    )
    return prompt


def promt_anuales_years(text):
    prompt = (
        "Analiza el siguiente texto y extrae exclusivamente los años que aparezcan en el contexto de información financiera. "
        "Los años pueden estar en cualquier formato, pero deben estar claramente relacionados con estados financieros, "
        "informes de resultados o información contable. "
        "Devuelve únicamente un array JSON con los años detectados, sin comentarios, sin explicaciones y sin otros datos adicionales. "
        "Asegúrate de que los años en el array sean únicos y no se repitan."
        "Si no se encuentran años relevantes, devuelve un array vacío [].\n\n"
        f"Texto a analizar:\n{text}"
    )
    return prompt


def promt_trimestral_bs_and_pl(text):  ##posible mejora
    prompt = (
        """
        Eres un experto en identificar los estados financieros denominados "bs" (correspondiente a "Estado de Situación Financiera", "Balance General" o términos similares) y "pl" (correspondiente a "Estado de Resultados", "Pérdidas y Ganancias", "Profit & Loss", "P&L" o términos similares). Tu tarea es analizar el texto proporcionado y detectar las páginas en las que se encuentran estos estados financieros. Debes devolver la siguiente estructura en formato JSON:

        {
            "bs": [página donde inicia, página donde termina],
            "pl": [página donde inicia, página donde termina]
        }

        Si alguno de estos estados financieros ocupa solo una página, asegúrate de que la página de inicio y la página de fin sean la misma. Si no encuentras alguno de los estados financieros, devuelve `null` en su lugar.
        """
        f"El texto que debes procesar tiene las páginas enumeradas al inicio de cada página de la siguiente manera: ###PAGE_ID:numero###. Asegúrate de extraer correctamente las páginas correspondientes para cada estado financiero.\n\n {text}"
    )
    return prompt


def promt_trimestral_year_bs(text):
    promt = (
        """
        Eres un experto en identificar los cuartiles de un año. Tu tarea es determinar a qué cuartil pertenece la fecha mencionada en el texto proporcionado, teniendo en cuenta que si no se menciona un cuartil específico, debes asignarlo según la fecha. Los cuartiles del año son los siguientes:

        {
            'Q1': ["del 1 de enero al 31 de marzo", "al 31 de marzo"],
            'Q2': ["del 1 de abril al 30 de junio", "al 30 de junio"],
            'Q3': ["del 1 de julio al 30 de septiembre", "al 30 de septiembre"],
            'Q4': ["del 1 de octubre al 31 de diciembre", "al 31 de diciembre"]
        }

        Tu tarea es analizar el texto proporcionado y devolver los cuartiles presentes en el mismo en el siguiente formato JSON:

        [
            {"year": <año>, "quarter": <cuartil>}
        ]

        Donde:
        - "year" debe ser un número entero que representa el año mencionado en el texto.
        - "quarter" debe ser uno de los cuartiles [Q1, Q2, Q3, Q4], dependiendo de la fecha encontrada en el texto.

        """

        f"A continuación, se muestra el texto proporcionado, que puede incluir una o varias tablas: \n\n {text}"
    )
    return promt


def promt_trimestral_year_pl(text):
    promt = (
        """
        Eres un experto en identificar los cuartiles de un año. Tu tarea es determinar a qué cuartil pertenece la fecha mencionada en el texto proporcionado. Si no se menciona un cuartil específico, debes asignarlo según la fecha que encuentres. Los cuartiles del año son los siguientes:

        {
            'Q1': [
                "del 1 de enero al 31 de marzo",
                "al 31 de marzo",
                "del 1 de enero al 31 de marzo (específico o relacionados)",
                "al 31 de marzo (específico o relacionados)"
            ],
            'Q2': [
                "del 1 de abril al 30 de junio",
                "al 30 de junio",
                "del 1 de abril al 30 de junio (específico o relacionados)",
                "al 30 de junio (específico o relacionados)"
            ],
            'Q3': [
                "del 1 de julio al 30 de septiembre",
                "al 30 de septiembre",
                "del 1 de julio al 30 de septiembre (específico o relacionados con específico)",
                "al 30 de septiembre (específico o relacionados)"
            ],
            'Q4': [
                "del 1 de octubre al 31 de diciembre",
                "al 31 de diciembre",
                "del 1 de octubre al 31 de diciembre (específico o relacionados)",
                "al 31 de diciembre (específico o relacionados)"
            ],
            'Q1A': [
                "del 1 de enero al 31 de marzo (acumulado o relacionados con acumulado)",
                "al 31 de marzo (acumulado o relacionados con acumulado)"
            ],
            'Q2A': [
                "del 1 de enero al 30 de junio",
                "al 30 de junio (acumulado o relacionados con acumulado)"
            ],
            'Q3A': [
                "del 1 de enero al 30 de septiembre",
                "al 30 de septiembre (acumulado o relacionados con acumulado)"
            ],
            'Q4A': [
                "del 1 de enero al 31 de diciembre",
                "al 31 de diciembre (acumulado o relacionados con acumulado)"
            ]
        }

        Tu tarea es analizar el texto proporcionado y devolver los cuartiles presentes en el mismo en el siguiente formato JSON:
    subtítulos
        [
            {"year": <año>, "quarter": <cuartil>}
        ]

        Donde:
        - "year" debe ser un número entero que representa el año mencionado en el texto.
        - "quarter" debe ser uno de los cuartiles [Q1, Q2, Q3, Q4, AQ1, AQ2, AQ3, AQ4], dependiendo de la fecha encontrada en el texto.
        """

        f"A continuación, se muestra el texto proporcionado, que puede incluir una o varias tablas: \n\n {text}"
    )

    return promt


def promt_extract_bs(table_text: str, years: list, list_account: list):
    prompt = (
        "### Objetivo: Extraer y estructurar la información financiera del estado financiero completo en formato JSON.\n\n"

        "El estado financiero corresponde a un Balance General (BS), por lo que debes mapear los conceptos correspondientes "
        "a ingresos, costos y gastos usando las cuentas del diccionario contable.\n\n"

        "### Diccionario Contable:\n"
        f"{json.dumps(list_account)}\n\n"

        "### Reglas clave:\n"
        "- Usa **solo las cuentas del diccionario contable**, **NO crees nuevas cuentas**.\n"
        "- **No dejes elementos sin asignar**. Si no encuentras una cuenta exacta, elige la más adecuada según el contexto.\n"
        "- Usa las categorías como referencia principal, pero considera el contexto y el nombre del concepto.\n"
        "- Si un concepto es ambiguo, asigna la categoría más relevante para **ingresos**, **costos** o **gastos**.\n"
        "- Las cuentas están en **español**, pero el diccionario está en **inglés**. Realiza la correspondencia correctamente.\n"
        "- Si varias partidas tienen la misma naturaleza, **súmalas en una única cuenta** y usa `details` para los ítems individuales.\n"
        "- El valor total de una cuenta (`value`) debe ser la suma de los valores de `details`.\n"
        "- **NO** generes objetos duplicados con el mismo `name`, `year`, `period` y `value`.\n"
        "- **NO** incluyas elementos con `value: 0` o `details: []`.\n"
        "- **Asegúrate de mapear correctamente los periodos**. Si los años están representados como `Q<number>` (trimestres), mapea cada periodo al formato `<year>Q<number>`. Si no hay trimestres, solo usa el año.\n\n"

        "### Años y periodos (prioridad):\n"
        "- La **fuente principal** de años y periodos es el **texto/HTML de la tabla** (encabezados de columnas: p. ej. `Dic-2025`, `Dic-2024`, fechas o años asociados a cada columna de cifras).\n"
        "- La **Lista de Años** de más abajo es **auxiliar** (metadata del sistema). Si la tabla muestra **más** años que esa lista, o la lista está incompleta o vacía, **debes inferir todos los años/periodos desde la tabla** y emitir la salida **para cada columna temporal** que tenga valores.\n"
        "- Cada `value` y cada ítem en `details` debe corresponder al **año y periodo** de la columna de la que proviene el número.\n\n"

        "### Lista de Años (referencia; la tabla prevalece si difiere):\n"
        f"{json.dumps(years)}\n\n"

        "### Estado Financiero COMPLETO:\n"
        f"{table_text}\n\n"

        "### Salida esperada:\n"
        "Un JSON con la siguiente estructura:\n"
        "\"output\": [\n"
        "{\n"
        "  \"name\": \"<cuenta>\",\n"
        "  \"value\": <SUMA_DE_DETAILS>,\n"
        "  \"year\": <año>,\n"
        "  \"period\": \"<year><Q<number> si aplica>\",\n"
        "  \"details\": [\n"
        "    {\"name\": \"<detalle>\", \"value\": <valor>}\n"
        "  ]\n"
        "}\n"
        "]\n\n"
        "### FORMATO DE RESPUESTA (CRÍTICO):\n"
        "- Devuelve ÚNICAMENTE el array JSON, sin markdown, sin backticks, sin explicaciones.\n"
        "- NO uses ```json ni ``` en tu respuesta.\n"
        "- NO agregues texto antes o después del JSON.\n"
    )
    return prompt


def promt_extract_pl(table_text: str, years: list, list_account: list):
    prompt = (
        f"### Objetivo: Extraer y estructurar la información financiera del **Estado de Resultados (PL)** en formato JSON.\n\n"

        "Este reporte corresponde a un **Estado de Resultados (PL)**, por lo que los conceptos deben mapearse a **ingresos**, **costos** y **gastos**, "
        "utilizando las cuentas del diccionario contable proporcionado.\n\n"

        "### Diccionario Contable:\n"
        f"{json.dumps(list_account)}\n\n"

        "### Reglas clave:\n"
        "- Usa **solo las cuentas del diccionario contable**, **NO crees nuevas cuentas**.\n"
        "- **No dejes elementos sin asignar**. Si no encuentras una cuenta exacta, elige la más adecuada dentro del diccionario, priorizando la categoría más cercana en función del contexto y la naturaleza del concepto.\n"
        "- Usa los tags como referencia principal, pero considera el contexto y el nombre del concepto.\n"
        "- Si un concepto es ambiguo, asigna la categoría más relevante para **ingresos**, **costos** o **gastos**.\n"
        "- Las cuentas están en **español**, pero el diccionario está en **inglés**. Realiza la correspondencia correctamente.\n"
        "- Si hay varias partidas similares, **súmalas en una única cuenta**, detallando cada ítem en `details`.\n"
        "- El valor total (`value`) de cada cuenta debe ser la suma de los valores en `details`.\n"
        "- **NO** generes objetos duplicados con el mismo `name`, `year`, `period` y `value`.\n"
        "- **NO** incluyas elementos con `value: 0` o `details: []`.\n"
        "- **Asegúrate de mapear correctamente los periodos**. Si los años están representados como `Q<number>` (trimestres), mapea cada periodo al formato `<year>Q<number>`. Si es un periodo acumulado, agrega un sufijo `A` después del número del trimestre, es decir: `<year>Q<number>A`. Si no hay trimestres, solo usa el año.\n\n"

        "### Años y periodos (prioridad):\n"
        "- La **fuente principal** de años y periodos es el **texto/HTML de la tabla** (encabezados: p. ej. `Dic-2025`, `Dic-2024`, o el año que encabeza cada columna de cifras).\n"
        "- La **Lista de Años** de más abajo es **auxiliar**. Si la tabla muestra **más** años que esa lista, o la lista está incompleta o vacía, **debes inferir todos los años/periodos desde la tabla** y generar la salida **para cada columna temporal** con datos.\n"
        "- Cada `value` y cada ítem en `details` debe alinearse al **año y periodo** de la columna correspondiente.\n\n"

        "### Lista de Años (referencia; la tabla prevalece si difiere):\n"
        f"{json.dumps(years)}\n\n"

        f"### Estado Financiero COMPLETO (Tipo: Estado de Resultados):\n"
        f"{table_text}\n\n"

        "### Salida esperada:\n"
        "Un JSON con la siguiente estructura:\n"
        "\"output\": [\n"
        "{\n"
        "  \"name\": \"<cuenta>\",\n"
        "  \"value\": <SUMA_DE_DETAILS>,\n"
        "  \"year\": <año>,\n"
        "  \"period\": \"<year><Q<number>A opcional si aplica>\",\n"
        "  \"details\": [\n"
        "    {\"name\": \"<detalle>\", \"value\": <valor>}\n"
        "  ]\n"
        "}\n"
        "]\n\n"
        "### FORMATO DE RESPUESTA (CRÍTICO):\n"
        "- Devuelve ÚNICAMENTE el array JSON, sin markdown, sin backticks, sin explicaciones.\n"
        "- NO uses ```json ni ``` en tu respuesta.\n"
        "- NO agregues texto antes o después del JSON.\n"
    )
    return prompt


# def promt_extract_cf_main(table_text: str, years: list, list_account: list):
#     """
#     Prompt para extraer SOLO los 3 flujos principales de caja (operación, inversión, financiación).
#     """
#     prompt = (
#         "### Objetivo: Extraer y estructurar SOLO los 3 flujos principales del **Estado de Flujo de Efectivo (CF)** en formato JSON.\n\n"
#
#         "Este reporte corresponde a un **Estado de Flujo de Efectivo (CF)**, por lo que debes extraer ÚNICAMENTE los siguientes 3 valores para todos los años:\n\n"
#
#         "1. **Flujo de caja de operación** (puede aparecer como: Flujo de Caja Operativo, Flujo de Efectivo Operativo, Resultado de efectivo del periodo por operación, Resultado de efectivo de operación, Flujo de efectivo de la operación, Efectivo neto proveniente de las actividades de operación, Flujo de caja neto de actividades de operación, Flujo de caja de actividades de operación)\n"
#         "   **CRÍTICO**: Para el flujo de operación, incluye en `details` TODAS las partidas que componen las actividades de operación, tales como:\n"
#         "   - Ganancia (Pérdida) Neta del Ejercicio\n"
#         "   - Depreciación, Amortización y Agotamiento\n"
#         "   - Ganancias (Pérdidas) no Distribuidas de Subsidiarias\n"
#         "   - Pérdida (Ganancia) en Venta de Propiedades, Planta y Equipo\n"
#         "   - Gasto por Intereses / Ingreso por Intereses\n"
#         "   - Pérdida (Ganancia) por Diferencias de Cambio\n"
#         "   - Gasto por Impuestos a las Ganancias\n"
#         "   - Otros Ajustes por Partidas Distintas al Efectivo\n"
#         "   - Cambios en activos y pasivos operativos (Cuentas por Cobrar, Inventarios, Otros Activos, Cuentas por Pagar)\n"
#         "   - Intereses Recibidos / Intereses Pagados\n"
#         "   - Impuestos a las Ganancias Pagados\n"
#         "   - Y cualquier otra partida que aparezca en las actividades de operación\n\n"
#
#         "2. **Flujo de caja de inversión** (puede aparecer como: Flujo de efectivo de inversión, Actividades de inversión, Flujo de caja de actividades de inversión, Efectivo neto utilizado en actividades de inversión)\n"
#         "   **CRÍTICO**: Para el flujo de inversión, incluye en `details` TODAS las partidas que componen las actividades de inversión, tales como:\n"
#         "   - Reembolso de Préstamos Concedidos a Terceros\n"
#         "   - Reembolsos Recibidos de Préstamos a Entidades Relacionadas\n"
#         "   - Venta de Propiedades, Planta y Equipo\n"
#         "   - Dividendos Recibidos\n"
#         "   - Préstamos Concedidos a Terceros\n"
#         "   - Préstamos Concedidos a Entidades Relacionadas\n"
#         "   - Compra de Propiedades, Planta y Equipo\n"
#         "   - Compra de Activos Intangibles\n"
#         "   - Otros Cobros (Pagos) de Efectivo Relativos a las Actividades de Inversión\n"
#         "   - Y cualquier otra partida que aparezca en las actividades de inversión\n\n"
#
#         "3. **Flujo de caja de financiación** (puede aparecer como: Flujo de efectivo de financiación, Actividades de financiación, Flujo de caja de actividades de financiación, Efectivo neto proveniente de actividades de financiación)\n"
#         "   **CRÍTICO**: Para el flujo de financiación, incluye en `details` TODAS las partidas que componen las actividades de financiación, tales como:\n"
#         "   - Obtención de Préstamos\n"
#         "   - Préstamos de Entidades Relacionadas\n"
#         "   - Amortización o Pago de Préstamos\n"
#         "   - Pasivos por Arrendamiento Financiero\n"
#         "   - Dividendos Pagados\n"
#         "   - Y cualquier otra partida que aparezca en las actividades de financiación\n\n"
#
#         "4. **Otras partidas del estado de flujo de efectivo**: Si hay otras partidas que no pertenecen a los 3 flujos principales (como \"Efecto de variación en tipo de cambio\", \"Efectos de las Variaciones en las Tasas de Cambio sobre el Efectivo\", etc.), inclúyelas también como elementos separados en el JSON.\n\n"
#
#         "### Diccionario Contable:\n"
#         f"{json.dumps(list_account)}\n\n"
#
#         "### Reglas clave:\n"
#         "- Usa **solo las cuentas del diccionario contable**, **NO crees nuevas cuentas**.\n"
#         "- **No dejes elementos sin asignar**. Si no encuentras una cuenta exacta, elige la más adecuada dentro del diccionario.\n"
#         "- Los valores deben ser **numéricos** (sin comas, sin símbolos de moneda).\n"
#         "- Si el valor es **negativo**, incluye el signo menos.\n"
#         "- Si no encuentras un valor, usa `null`.\n"
#         "- **CRÍTICO**: Para cada flujo (operación, inversión, financiación), DEBES incluir en `details` TODAS las partidas individuales que componen ese flujo, no solo el total. Cada partida debe aparecer como un objeto separado dentro de `details`.\n"
#         "- Si hay varias partidas similares, **súmalas en una única cuenta**, detallando cada ítem en `details`.\n"
#         "- El valor total (`value`) de cada cuenta debe ser la suma de los valores en `details`.\n"
#         "- **NO** generes objetos duplicados con el mismo `name`, `year`, `period` y `value`.\n"
#         "- **NO** incluyas elementos con `value: 0` o `details: []`.\n"
#         "- **Asegúrate de mapear correctamente los periodos**. Si los años están representados como `Q<number>` (trimestres), mapea cada periodo al formato `<year>Q<number>`. Si es un periodo acumulado, agrega un sufijo `A` después del número del trimestre, es decir: `<year>Q<number>A`. Si no hay trimestres, solo usa el año.\n\n"
#
#         "### Lista de Años:\n"
#         f"{json.dumps(years)}\n\n"
#
#         "### Estado Financiero COMPLETO (Tipo: Estado de Flujo de Efectivo):\n"
#         f"{table_text}\n\n"
#
#         "### Salida esperada:\n"
#         "Un JSON con SOLO los 3 flujos principales para todos los años:\n"
#         "\"output\": [\n"
#         "  {\n"
#         "    \"name\": \"Flujo de caja de operación\",\n"
#         "    \"value\": <valor_total>,\n"
#         "    \"year\": <año>,\n"
#         "    \"period\": \"<year><Q<number>A opcional si aplica>\",\n"
#         "    \"details\": [\n"
#         "      {\"name\": \"<detalle>\", \"value\": <valor>}\n"
#         "    ]\n"
#         "  },\n"
#         "  {\n"
#         "    \"name\": \"Flujo de caja de inversión\",\n"
#         "    \"value\": <valor_total>,\n"
#         "    \"year\": <año>,\n"
#         "    \"period\": \"<year><Q<number>A opcional si aplica>\",\n"
#         "    \"details\": [\n"
#         "      {\"name\": \"<detalle>\", \"value\": <valor>}\n"
#         "    ]\n"
#         "  },\n"
#         "  {\n"
#         "    \"name\": \"Flujo de caja de financiación\",\n"
#         "    \"value\": <valor_total>,\n"
#         "    \"year\": <año>,\n"
#         "    \"period\": \"<year><Q<number>A opcional si aplica>\",\n"
#         "    \"details\": [\n"
#         "      {\"name\": \"<detalle>\", \"value\": <valor>}\n"
#         "    ]\n"
#         "  }\n"
#         "]\n"
#     )
#     return prompt

def promt_extract_cf_main(table_text: str, years: list, list_account: list):
    """
    Prompt para extraer SOLO los 3 flujos principales de caja (operación, inversión, financiación).
    """
    # Filtrar cuentas con type="FC" y ordenarlas por priority
    fc_accounts = [acc for acc in list_account if acc.get("type") == "FC"]
    print(fc_accounts)
    fc_accounts_sorted = sorted(fc_accounts, key=lambda x: x.get("priority", 999))
    
    # Extraer los nombres de las cuentas FC
    fc_account_names = [acc.get("name") for acc in fc_accounts_sorted if acc.get("name")]
    
    # Construir la lista de nombres para las reglas
    names_list = "\n".join([f"  - `{name}`" for name in fc_account_names]) if fc_account_names else "  - (No se encontraron cuentas FC en el diccionario)"
    
    # Construir el ejemplo de salida dinámicamente
    output_examples = ""
    for i, name in enumerate(fc_account_names, 1):
        output_examples += (
            f"  {{\n"
            f"    \"name\": \"{name}\",\n"
            f"    \"value\": <valor_total>,\n"
            f"    \"year\": <año>,\n"
            f"    \"period\": \"<year><Q<number>A opcional si aplica>\",\n"
            f"    \"details\": [\n"
            f"      {{\"name\": \"<detalle>\", \"value\": <valor>}}\n"
            f"    ]\n"
            f"  }}{',' if i < len(fc_account_names) else ''}\n"
        )
    
    prompt = (
        "### Objetivo: Extraer y estructurar SOLO los 3 flujos principales del **Estado de Flujo de Efectivo (CF)** en formato JSON.\n\n"

        "Este reporte corresponde a un **Estado de Flujo de Efectivo (CF)**, por lo que debes extraer ÚNICAMENTE los siguientes 3 valores para todos los años:\n\n"

        "1. **Flujo de caja de operación** (puede aparecer como: Flujo de Caja Operativo, Flujo de Efectivo Operativo, Resultado de efectivo del periodo por operación, Resultado de efectivo de operación, Flujo de efectivo de la operación, Efectivo neto proveniente de las actividades de operación, Flujo de caja neto de actividades de operación, Flujo de caja de actividades de operación)\n"
        "   **CRÍTICO**: Para el flujo de operación, incluye en `details` TODAS las partidas que componen las actividades de operación, tales como:\n"
        "   - Ganancia (Pérdida) Neta del Ejercicio\n"
        "   - Depreciación, Amortización y Agotamiento\n"
        "   - Ganancias (Pérdidas) no Distribuidas de Subsidiarias\n"
        "   - Pérdida (Ganancia) en Venta de Propiedades, Planta y Equipo\n"
        "   - Gasto por Intereses / Ingreso por Intereses\n"
        "   - Pérdida (Ganancia) por Diferencias de Cambio\n"
        "   - Gasto por Impuestos a las Ganancias\n"
        "   - Otros Ajustes por Partidas Distintas al Efectivo\n"
        "   - Cambios en activos y pasivos operativos (Cuentas por Cobrar, Inventarios, Otros Activos, Cuentas por Pagar)\n"
        "   - Intereses Recibidos / Intereses Pagados\n"
        "   - Impuestos a las Ganancias Pagados\n"
        "   - Y cualquier otra partida que aparezca en las actividades de operación\n\n"

        "2. **Flujo de caja de inversión** (puede aparecer como: Flujo de efectivo de inversión, Actividades de inversión, Flujo de caja de actividades de inversión, Efectivo neto utilizado en actividades de inversión)\n"
        "   **CRÍTICO**: Para el flujo de inversión, incluye en `details` TODAS las partidas que componen las actividades de inversión, tales como:\n"
        "   - Reembolso de Préstamos Concedidos a Terceros\n"
        "   - Reembolsos Recibidos de Préstamos a Entidades Relacionadas\n"
        "   - Venta de Propiedades, Planta y Equipo\n"
        "   - Dividendos Recibidos\n"
        "   - Préstamos Concedidos a Terceros\n"
        "   - Préstamos Concedidos a Entidades Relacionadas\n"
        "   - Compra de Propiedades, Planta y Equipo\n"
        "   - Compra de Activos Intangibles\n"
        "   - Otros Cobros (Pagos) de Efectivo Relativos a las Actividades de Inversión\n"
        "   - Y cualquier otra partida que aparezca en las actividades de inversión\n\n"

        "3. **Flujo de caja de financiación** (puede aparecer como: Flujo de efectivo de financiación, Actividades de financiación, Flujo de caja de actividades de financiación, Efectivo neto proveniente de actividades de financiación)\n"
        "   **CRÍTICO**: Para el flujo de financiación, incluye en `details` TODAS las partidas que componen las actividades de financiación, tales como:\n"
        "   - Obtención de Préstamos\n"
        "   - Préstamos de Entidades Relacionadas\n"
        "   - Amortización o Pago de Préstamos\n"
        "   - Pasivos por Arrendamiento Financiero\n"
        "   - Dividendos Pagados\n"
        "   - Y cualquier otra partida que aparezca en las actividades de financiación\n\n"

        "4. **Otras partidas del estado de flujo de efectivo**: Si hay otras partidas que no pertenecen a los 3 flujos principales (como \"Efecto de variación en tipo de cambio\", \"Efectos de las Variaciones en las Tasas de Cambio sobre el Efectivo\", etc.), inclúyelas también como elementos separados en el JSON.\n\n"

        "### Diccionario Contable:\n"
        f"{json.dumps(list_account)}\n\n"

        "### Reglas clave:\n"
        "- **CRÍTICO**: El campo `name` DEBE ser el nombre exacto de una de las cuentas con `type: \"FC\"` que aparecen en el diccionario contable. Las cuentas FC disponibles son:\n"
        f"{names_list}\n"
        "- **NO hardcodees nombres**, usa SOLO los nombres que aparecen en el diccionario contable para las cuentas con `type: \"FC\"`.\n"
        "- Usa **solo las cuentas del diccionario contable**, **NO crees nuevas cuentas**.\n"
        "- **No dejes elementos sin asignar**. Si no encuentras una cuenta exacta, elige la más adecuada dentro del diccionario.\n"
        "- **CRÍTICO**: El campo `name` dentro de `details` DEBE ser el nombre de la cuenta del diccionario contable que corresponda a cada partida, NO uses el nombre que aparece en el texto del estado financiero.\n"
        "- Los valores deben ser **numéricos** (sin comas, sin símbolos de moneda).\n"
        "- Si el valor es **negativo**, incluye el signo menos.\n"
        "- Si no encuentras un valor, usa `null`.\n"
        "- **Si no encuentras NINGÚN dato en el estado financiero, devuelve un array vacío: []**\n"
        "- **CRÍTICO**: Para cada flujo (operación, inversión, financiación), DEBES incluir en `details` TODAS las partidas individuales que componen ese flujo, no solo el total. Cada partida debe aparecer como un objeto separado dentro de `details`.\n"
        "- Si hay varias partidas similares, **súmalas en una única cuenta**, detallando cada ítem en `details`.\n"
        "- El valor total (`value`) de cada cuenta debe ser la suma de los valores en `details`.\n"
        "- **NO** generes objetos duplicados con el mismo `name`, `year`, `period` y `value`.\n"
        "- **NO** incluyas elementos con `value: 0` o `details: []`.\n"
        "- **Asegúrate de mapear correctamente los periodos**. Si los años están representados como `Q<number>` (trimestres), mapea cada periodo al formato `<year>Q<number>`. Si es un periodo acumulado, agrega un sufijo `A` después del número del trimestre, es decir: `<year>Q<number>A`. Si no hay trimestres, solo usa el año.\n\n"

        "### Lista de Años:\n"
        f"{json.dumps(years)}\n\n"

        "### Estado Financiero COMPLETO (Tipo: Estado de Flujo de Efectivo):\n"
        f"{table_text}\n\n"

        "### Salida esperada:\n"
        "Un JSON con SOLO los flujos principales para todos los años. **CRÍTICO**: El campo `name` DEBE ser el nombre exacto de una de las cuentas con `type: \"FC\"` del diccionario contable.\n\n"
        "\"output\": [\n"
        f"{output_examples}"
        "]\n\n"
        "**Si no encuentras datos, devuelve: []**\n\n"
        "### FORMATO DE RESPUESTA (CRÍTICO):\n"
        "- Devuelve ÚNICAMENTE el array JSON, sin markdown, sin backticks, sin explicaciones.\n"
        "- NO uses ```json ni ``` en tu respuesta.\n"
        "- NO agregues texto antes o después del JSON.\n"
        "- La respuesta debe empezar directamente con [ y terminar con ].\n"
    )
    return prompt


def promt_extract_cf_details(table_text: str, years: list, list_account: list):
    """
    Prompt para extraer SOLO las partidas adicionales (details) del Estado de Flujo de Efectivo (CF).
    """
    prompt = (
        "### Objetivo: Extraer y estructurar SOLO las partidas adicionales del **Estado de Flujo de Efectivo (CF)** que NO están clasificadas en los 3 flujos principales (operación, inversión, financiación).\n\n"
        
        "Este reporte corresponde a un **Estado de Flujo de Efectivo (CF)**, por lo que debes extraer TODAS las demás partidas que aparecen en el estado de flujo de efectivo y que NO son los 3 flujos principales. Estas partidas adicionales deben incluirse en una cuenta especial llamada **\"details\"** con las siguientes características:\n\n"
        
        "**Partidas adicionales a extraer** (ejemplos, pero incluye TODAS las que encuentres):\n"
        "- Depreciación y amortización\n"
        "- Costos financieros\n"
        "- Deterioro por baja de propiedad, planta y equipo\n"
        "- Provisiones\n"
        "- Diferencia en cambio\n"
        "- Participación en resultados de subsidiarias\n"
        "- Ingresos financieros\n"
        "- Cambios en activos y pasivos operativos (cuentas por cobrar, inventarios, gastos pagados por adelantado, cuentas por pagar)\n"
        "- Cobro de intereses\n"
        "- Pago de intereses\n"
        "- Pago de impuesto a la renta\n"
        "- Compra de propiedad, planta y equipo\n"
        "- Compra de intangibles\n"
        "- Préstamos otorgados/recibidos\n"
        "- Dividendos pagados/recibidos\n"
        "- Cualquier otra partida que aparezca en el estado de flujo de efectivo y que NO sea uno de los 3 flujos principales\n\n"
        
        "### Diccionario Contable:\n"
        f"{json.dumps(list_account)}\n\n"
        
        "### Reglas clave:\n"
        "- Usa **solo las cuentas del diccionario contable**, **NO crees nuevas cuentas**.\n"
        "- **No dejes elementos sin asignar**. Si no encuentras una cuenta exacta, elige la más adecuada dentro del diccionario.\n"
        "- Los valores deben ser **numéricos** (sin comas, sin símbolos de moneda).\n"
        "- Si el valor es **negativo**, incluye el signo menos.\n"
        "- Si no encuentras un valor, usa `null`.\n"
        "- **CRÍTICO**: Crea una cuenta con `name: \"details\"` para cada año/periodo, y dentro de `details` incluye TODAS las partidas adicionales encontradas.\n"
        "- El valor total (`value`) de cada cuenta \"details\" debe ser la suma de los valores en `details`.\n"
        "- **NO** generes objetos duplicados con el mismo `name`, `year`, `period` y `value`.\n"
        "- **NO** incluyas elementos con `value: 0` o `details: []`.\n"
        "- **NO** incluyas los 3 flujos principales (operación, inversión, financiación), solo las partidas adicionales.\n"
        "- **Asegúrate de mapear correctamente los periodos**. Si los años están representados como `Q<number>` (trimestres), mapea cada periodo al formato `<year>Q<number>`. Si es un periodo acumulado, agrega un sufijo `A` después del número del trimestre, es decir: `<year>Q<number>A`. Si no hay trimestres, solo usa el año.\n\n"
        
        "### Lista de Años:\n"
        f"{json.dumps(years)}\n\n"
        
        "### Estado Financiero COMPLETO (Tipo: Estado de Flujo de Efectivo):\n"
        f"{table_text}\n\n"
        
        "### Salida esperada:\n"
        "Un JSON con SOLO las partidas adicionales en una cuenta \"details\" para cada año/periodo:\n"
        "\"output\": [\n"
        "  {\n"
        "    \"name\": \"details\",\n"
        "    \"value\": <SUMA_TOTAL_DE_TODAS_LAS_PARTIDAS_ADICIONALES>,\n"
        "    \"year\": <año>,\n"
        "    \"period\": \"<year><Q<number>A opcional si aplica>\",\n"
        "    \"details\": [\n"
        "      {\"name\": \"Depreciación y amortización\", \"value\": <valor>},\n"
        "      {\"name\": \"Costos financieros\", \"value\": <valor>},\n"
        "      {\"name\": \"Disminución en cuentas por cobrar\", \"value\": <valor>},\n"
        "      ... (todas las demás partidas adicionales del estado de flujo de efectivo)\n"
        "    ]\n"
        "  }\n"
        "]\n\n"
        "### FORMATO DE RESPUESTA (CRÍTICO):\n"
        "- Devuelve ÚNICAMENTE el array JSON, sin markdown, sin backticks, sin explicaciones.\n"
        "- NO uses ```json ni ``` en tu respuesta.\n"
        "- NO agregues texto antes o después del JSON.\n"
    )
    return prompt


def promt_extract_cf(table_text: str, years: list, list_account: list):
    """
    Prompt para extraer flujos de caja del Estado de Flujo de Efectivo (CF).
    DEPRECATED: Usar promt_extract_cf_main y promt_extract_cf_details en su lugar.
    """
    prompt = promt_extract_cf_main(table_text, years, list_account)
    return prompt