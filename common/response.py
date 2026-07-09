import json

class Response:
    """
    Clase para manejar respuestas estándar de la API.

    Permite crear respuestas con códigos de estado, mensajes personalizados,
    cuerpo flexible y la capacidad de fusionar headers y datos adicionales.
    """
    
    def __init__(self, status_code: int = 200, body: dict = None, message: str = None, headers: dict = None):
        self.status_code = status_code
        self.body = body if body else {}
        self.message = message
        self.headers = headers or {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True
        }
        
    def set_status(self, status_code: int):
        """
        Establece el código de estado HTTP de la respuesta.
        
        Args:
            status_code (int): El código de estado HTTP de la respuesta.
        """
        self.status_code = status_code

    def set_message(self, message: str):
        """
        Establece un mensaje de la respuesta.

        Args:
            message (str): El mensaje que acompañará la respuesta.
        """
        self.message = message

    def set_body(self, body: dict):
        """
        Establece el cuerpo de la respuesta.

        Args:
            body (dict): El cuerpo de la respuesta.
        """
        self.body = body

    def set_headers(self, headers: dict):
        """
        Establece los encabezados de la respuesta.

        Args:
            headers (dict): Los encabezados que deben ser establecidos en la respuesta.
        """
        self.headers = headers

    @staticmethod
    def merge_dict(dict1: dict, dict2: dict, keys_to_merge: list = None) -> dict:
        """
        Realiza un merge entre dos diccionarios, fusionando solo las claves especificadas.

        Args:
            dict1 (dict): El primer diccionario (será modificado).
            dict2 (dict): El segundo diccionario (sus claves se fusionarán con dict1).
            keys_to_merge (list, opcional): Lista de claves que deben ser fusionadas. Si no se pasa, se fusionan todas las claves.

        Returns:
            dict: El diccionario resultante de la fusión.
        """
        if keys_to_merge is None:
            keys_to_merge = dict2.keys()

        for key in keys_to_merge:
            if key in dict2:
                dict1[key] = dict2[key]
        
        return dict1

    def merge(self, new_attributes: dict):
        """
        Permite fusionar nuevos atributos (por ejemplo, headers) con los existentes.

        Args:
            new_attributes (dict): Nuevos atributos para añadir o reemplazar.
        """
        self.headers.update(new_attributes)

    def to_dict(self) -> dict:
        """
        Convierte la respuesta en un formato adecuado para ser devuelto por la API.

        Returns:
            dict: La respuesta en formato JSON con atributos 'statusCode', 'headers' y 'body'.
        """
        response_body = self.body
        if self.message: 
            response_body['message'] = self.message

        return {
            'statusCode': self.status_code,
            'headers': self.headers,
            'body': json.dumps(response_body)
        }
