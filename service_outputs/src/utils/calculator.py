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


def get_data_points(current_year, datapoints_year, **kwargs):
    """Función mejorada para obtener data points que funciona con dict y objetos"""
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

    year = int(current_year + offset)

    if year not in datapoints_year:
        return None  # Año inexistente, retorna None

    year_data = datapoints_year[year]
    if not year_data:
        return []

    # Detectar si son diccionarios u objetos basándose en el primer elemento
    is_dict = isinstance(year_data[0], dict)

    result = []

    for dp in year_data:
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


def execute_function(func_name, current_year, datapoints_year, **kwargs):
    """Función de ejecución mejorada"""
    if func_name == "ABS":
        value = kwargs.get("default")
        try:
            return abs(float(value))
        except Exception:
            return None

    data_points = get_data_points(current_year, datapoints_year, **kwargs)
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
    def __init__(self, current_year=None, datapoints_year=None):
        super().__init__()
        self.current_year = current_year
        self.datapoints_year = datapoints_year

    def update_context(self, current_year, datapoints_year):
        """Permite cambiar el año y datos sin crear un nuevo transformer"""
        self.current_year = current_year
        self.datapoints_year = datapoints_year

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

        result = execute_function(func_name, self.current_year, self.datapoints_year, **kwargs)
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

    def calculate(self, expression, current_year, datapoints_year):
        """Calcula una expresión cambiando el contexto del transformer"""
        try:
            # Actualizar el contexto sin crear nuevo transformer
            self.transformer.update_context(current_year, datapoints_year)

            # Convertir comillas simples a dobles automáticamente
            parsed_expression = self.parse_script(expression)

            # Parsear y transformar
            tree = self.parser.parse(parsed_expression)
            result = self.transformer.transform(tree)

            return result
        except Exception as e:
            print(f"Error calculating expression '{expression}': {e}")
            return None








