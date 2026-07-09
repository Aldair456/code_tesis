from lark import Lark, Transformer, v_args, Token, Tree

DSL_GRAMMAR = """
    start: expr

    ?expr: expr "+" term  -> add
         | expr "-" term  -> sub
         | term

    ?term: term "*" factor  -> mul
         | term "/" factor  -> div
         | factor

    ?factor: function_call
           | NUMBER        -> number
           | STRING        -> string
           | "(" expr ")"

    function_call: FUNC_NAME "(" args? ")"
    args: arg ("," arg)*
    arg: VAR "=" expr
       | expr

    FUNC_NAME: "SUM" | "AVG" | "MAX" | "MIN" | "ABS"
    VAR: /(?!SUM|AVG|MAX|MIN|ABS)[a-zA-Z_][a-zA-Z0-9_]*/
    STRING: /"[^"]*"/
    NUMBER: /-?[0-9]+(\\.[0-9]+)?/

    %import common.WS
    %ignore WS
"""


def get_value_from_datapoint(dp, is_dict=None):
    """Extrae el valor de un datapoint, sea dict u objeto"""
    if is_dict is None:
        is_dict = isinstance(dp, dict)

    if is_dict:
        return dp.get("value", 0)
    else:
        return getattr(dp, "value", 0)


def get_account_name_from_datapoint(dp, is_dict=None):
    """Extrae el account_name de un datapoint, sea dict u objeto"""
    if is_dict is None:
        is_dict = isinstance(dp, dict)

    if is_dict:
        return dp.get("account_name", "")
    else:
        return getattr(dp, "account_name", "")


def get_account_tags_from_datapoint(dp, is_dict=None):
    """Extrae las account_tags de un datapoint, sea dict u objeto"""
    if is_dict is None:
        is_dict = isinstance(dp, dict)

    if is_dict:
        return dp.get("account_tags", [])
    else:
        return getattr(dp, "account_tags", [])


def get_account_value_type_from_datapoint(dp, is_dict=None):
    """Extrae el account_value_type de un datapoint, sea dict u objeto"""
    if is_dict is None:
        is_dict = isinstance(dp, dict)

    if is_dict:
        return dp.get("account_value_type", None)
    else:
        return getattr(dp, "account_value_type", None)


def get_data_points(current_period, datapoints_period, **kwargs):
    """Función mejorada para obtener data points con lógica inteligente de períodos"""
    dict_type = {
        "positive": 1,
        "negative": -1,
    }

    tag = kwargs.get("tag")
    name = kwargs.get("name")
    offset = kwargs.get("offset", 0)
    _type = kwargs.get("type", "false") == "true"

    if tag and name:
        return None  # Error: No se puede filtrar por ambos

    # NUEVA LÓGICA: Determinar el período objetivo basado en current_period y offset
    target_period = _calculate_target_period(current_period, offset, datapoints_period)

    if target_period is None:
        return None  # No se pudo determinar período objetivo

    # Buscar datos en el período objetivo
    target_data = datapoints_period.get(target_period)
    if not target_data:
        return []

    # Detectar si son diccionarios u objetos basándose en el primer elemento
    is_dict = isinstance(target_data[0], dict)

    result = []

    for dp in target_data:
        # Filtrar por tag o name
        if tag:
            tags = get_account_tags_from_datapoint(dp, is_dict)
            if tag not in tags:
                continue
        elif name:
            dp_name = get_account_name_from_datapoint(dp, is_dict)
            if dp_name != name:
                continue
        else:
            continue  # Si no hay filtro, no incluir

        # Obtener valor
        value = get_value_from_datapoint(dp, is_dict)

        # Aplicar transformación de tipo si es necesario
        if _type:
            value_type = get_account_value_type_from_datapoint(dp, is_dict)
            multiplier = dict_type.get(value_type, 0)
            value *= multiplier

        result.append(value)

    return result


def _calculate_target_period(current_period, offset, datapoints_period):
    """
    Calcula el período objetivo basado en el período actual y offset

    Lógica:
    - LTM_2024Q1 + offset=-1 → buscar año anterior más cercano (2023)
    - 2024Q1 + offset=-1 → buscar 2023 (año anterior)
    - 2024Q2 + offset=-1 → buscar 2024Q1 (trimestre anterior)
    - 2024 + offset=-1 → buscar 2023 (año anterior)
    """
    if offset == 0:
        # Sin offset, usar el período actual si existe
        if current_period in datapoints_period:
            return current_period
        return None

    # Con offset, aplicar lógica inteligente
    if isinstance(current_period, str):
        if current_period.startswith("LTM_"):
            # Período LTM: extraer año base y buscar año anterior
            base_period = current_period[4:]  # Quitar "LTM_"
            if "Q" in base_period:
                year = int(base_period[:4])
                return _find_closest_year(year, offset, datapoints_period)
            else:
                year = int(base_period)
                return _find_closest_year(year, offset, datapoints_period)
        elif "Q" in current_period:
            # Período trimestral: 2024Q1, 2024Q2, etc.
            year = int(current_period[:4])
            quarter = int(current_period[5:])

            if offset == -1:
                # Buscar período anterior inteligente
                if quarter == 1:
                    # Q1 → buscar año anterior completo
                    return _find_closest_year(year - 1, 0, datapoints_period)
                else:
                    # Q2, Q3, Q4 → buscar trimestre anterior
                    prev_quarter = f"{year}Q{quarter - 1}"
                    if prev_quarter in datapoints_period:
                        return prev_quarter
                    # Si no existe el trimestre, buscar año anterior
                    return _find_closest_year(year - 1, 0, datapoints_period)
            else:
                # Para otros offsets, calcular período objetivo
                target_year = year
                target_quarter = quarter + offset

                # Ajustar año si es necesario
                while target_quarter < 1:
                    target_quarter += 4
                    target_year -= 1
                while target_quarter > 4:
                    target_quarter -= 4
                    target_year += 1

                target_period = f"{target_year}Q{target_quarter}"
                if target_period in datapoints_period:
                    return target_period
                # Si no existe, buscar año completo
                return _find_closest_year(target_year, 0, datapoints_period)
        else:
            # Período anual: "2024"
            try:
                year = int(current_period)
                return _find_closest_year(year, offset, datapoints_period)
            except ValueError:
                return None
    elif isinstance(current_period, int):
        # Período anual: 2024
        return _find_closest_year(current_period, offset, datapoints_period)

    return None


def _find_closest_year(target_year, offset, datapoints_period):
    """
    Busca el año más cercano disponible en datapoints_period
    """
    # Calcular año objetivo
    target = target_year + offset

    # Verificar si el año objetivo existe directamente
    if target in datapoints_period:
        return target

    # Buscar años disponibles
    available_years = [k for k in datapoints_period.keys() if isinstance(k, int)]
    if not available_years:
        return None

    available_years.sort()

    # Buscar el año más cercano
    if offset <= 0:  # Buscar hacia atrás o actual
        candidates = [y for y in available_years if y <= target]
        return candidates[-1] if candidates else available_years[0]
    else:  # Buscar hacia adelante
        candidates = [y for y in available_years if y >= target]
        return candidates[0] if candidates else available_years[-1]


def execute_function(func_name, current_period, datapoints_period, **kwargs):
    """Función de ejecución mejorada"""
    if func_name == "ABS":
        value = kwargs.get("default")
        try:
            return abs(float(value))
        except Exception:
            return None

    data_points = get_data_points(current_period, datapoints_period, **kwargs)
    if data_points is None:
        return None

    aggregations = {
        "SUM": sum,
        "AVG": lambda values: sum(values) / len(values) if values else None,
        "MIN": lambda values: min(values) if values else None,
        "MAX": lambda values: max(values) if values else None
    }

    if func_name not in aggregations:
        return None  # Función no soportada, devuelve None

    return aggregations[func_name](data_points) if data_points is not None else None


class DSLTransformer(Transformer):
    def __init__(self, current_period=None, datapoints_period=None):
        super().__init__()
        self.current_period = current_period
        self.datapoints_period = datapoints_period

    def update_context(self, current_period, datapoints_period):
        """Permite cambiar el período y datos sin crear un nuevo transformer"""
        self.current_period = current_period
        self.datapoints_period = datapoints_period

    def extract_value(self, val):
        if isinstance(val, list):
            return self.extract_value(val[0]) if val else None
        if hasattr(val, 'children'):
            return self.extract_value(val.children)
        if isinstance(val, Tree):
            return self.extract_value(val.children[0]) if val.children else None
        if isinstance(val, Token):
            try:
                return float(val)
            except ValueError:
                return None  # Valor inválido, retorna None
        return float(val) if isinstance(val, str) and val.replace('.', '', 1).isdigit() else val

    def start(self, args):
        return args[0] if args and args[0] is not None else None

    def expr(self, args):
        return args[0] if args and args[0] is not None else None

    def number(self, n):
        return self.extract_value(n[0])

    def add(self, args):
        a, b = self.extract_value(args[0]), self.extract_value(args[1])
        return a + b if a is not None and b is not None else None

    def sub(self, args):
        a, b = self.extract_value(args[0]), self.extract_value(args[1])
        return a - b if a is not None and b is not None else None

    def mul(self, args):
        a, b = self.extract_value(args[0]), self.extract_value(args[1])
        return a * b if a is not None and b is not None else None

    def div(self, args):
        a, b = self.extract_value(args[0]), self.extract_value(args[1])
        if a is None or b is None or b == 0:
            return None  # Evita divisiones por cero o valores inválidos
        return a / b

    def function_call(self, args):
        func_name = str(args[0])
        arguments = args[1] if len(args) > 1 else []

        kwargs = {}
        for arg in arguments:
            if isinstance(arg, tuple):
                key, value = arg
                kwargs[key] = self.extract_value(value)
            else:
                kwargs['default'] = self.extract_value(arg)

        result = execute_function(func_name, self.current_period, self.datapoints_period, **kwargs)
        return result if result is not None else None  # Si hay error, devuelve None

    def args(self, args):
        return args

    def arg(self, args):
        if len(args) == 2:
            return (str(args[0]), self.extract_value(args[1]))
        return self.extract_value(args[0])

    def value(self, args):
        return self.extract_value(args[0])

    def FUNC_NAME(self, token):
        return str(token)

    def VAR(self, token):
        return str(token)

    def STRING(self, token):
        return token[1:-1]


class DSLCalculator:
    """Clase simple para manejar el parser y transformer reutilizable"""

    def __init__(self):
        self.transformer = DSLTransformer()
        self.parser = Lark(DSL_GRAMMAR, parser='lalr')

    def parse_script(self, expresion: str):
        """Convierte comillas simples a dobles para compatibilidad"""
        parsed_script = expresion.replace("'", "\"")
        return parsed_script

    def calculate(self, expression, current_period, datapoints_period):
        """Calcula una expresión cambiando el contexto del transformer"""
        try:
            # Actualizar el contexto sin crear nuevo transformer
            self.transformer.update_context(current_period, datapoints_period)

            # Convertir comillas simples a dobles automáticamente
            parsed_expression = self.parse_script(expression)

            # Parsear y transformar
            tree = self.parser.parse(parsed_expression)
            result = self.transformer.transform(tree)

            return result
        except Exception as e:
            print(f"Error calculating expression '{expression}': {e}")
            return None