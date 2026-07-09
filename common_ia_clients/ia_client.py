from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import anthropic
import logging
import time
# Configuración del logger
logger = logging.getLogger(__name__)


class IAProviderError(Exception):
    """Excepción personalizada para errores de proveedores de IA"""
    pass


class IAStrategy(ABC):
    """Interfaz abstracta para diferentes proveedores de IA"""

    @abstractmethod
    def invoke(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> str:
        """
        Invoca el modelo de IA con el prompt dado.

        :param prompt: El texto de entrada para el modelo.
        :param max_tokens: Número máximo de tokens a generar.
        :return: El texto generado por el modelo.
        :raises IAProviderError: Si hay error en la invocación.
        """
        pass

    @abstractmethod
    def get_model(self) -> str:
        """Retorna el identificador del modelo actual"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor de IA"""
        pass


class AnthropicStrategy(IAStrategy):
    """Implementación específica para Anthropic Claude"""

    def __init__(self,
                 api_key: str,
                 model: str = "claude-3-5-sonnet-20241022",
                 timeout_seconds: int = 120,
                 max_tokens: int = 10000,
                 temperature: float = 0,
                 top_k: int = 250,
                 top_p: float = 1,
                 max_retries: int = 4):
        """
        Inicializa la estrategia de Anthropic.

        :param api_key: Clave de API de Anthropic para autenticación.
        :param model: Identificador del modelo de Anthropic.
        :param timeout_seconds: Tiempo máximo de espera para la solicitud (en segundos).
        :param max_tokens: Número máximo de tokens a generar por defecto.
        :param temperature: Temperatura del modelo (0-1).
        :param top_k: Número de candidatos de tokens a considerar.
        :param top_p: Probabilidad acumulada para la selección de tokens.
        :param max_retries: Reintentos HTTP del SDK (5xx, 429, etc.; default del SDK es 2).
        """
        if not api_key:
            raise ValueError("La clave de API de Anthropic no puede estar vacía.")

        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.max_retries = max_retries

        try:
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=self.max_retries,
            )
        except Exception as e:
            raise IAProviderError(f"Error al inicializar el cliente de Anthropic: {e}")

    def invoke(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> str:
        """
        Invoca el modelo Claude de Anthropic.

        :param prompt: El texto de entrada para el modelo.
        :param max_tokens: Número máximo de tokens a generar.
        :param kwargs: Parámetros adicionales específicos de Anthropic.
        :return: El texto generado por el modelo.
        :raises IAProviderError: Si hay error en la invocación.
        """
        if not prompt or not prompt.strip():
            raise ValueError("El prompt no puede estar vacío.")

        try:
            logger.info(f"Invocando modelo {self.model} de Anthropic...")

            # Usar parámetros pasados o valores por defecto
            effective_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
            effective_temperature = kwargs.get('temperature', self.temperature)
            effective_top_k = kwargs.get('top_k', self.top_k)
            effective_top_p = kwargs.get('top_p', self.top_p)

            # Llamada a la API de Anthropic , CAMBIE POR QUE EL MODELO YA NO SE USA 
            response = self.client.messages.create(
                model=self.model,
                max_tokens=effective_max_tokens,
                temperature=effective_temperature,
                #top_k=effective_top_k,
                #top_p=effective_top_p,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extracción del texto generado
            if not response.content or len(response.content) == 0:
                raise IAProviderError("La respuesta del modelo está vacía.")

            generated_text = response.content[0].text.strip()

            if not generated_text:
                raise IAProviderError("El texto generado está vacío.")

            logger.info("Respuesta recibida exitosamente del modelo Anthropic.")
            return generated_text

        except anthropic.APIError as e:
            logger.error(f"Error de API de Anthropic: {e}")
            raise IAProviderError(f"Error de API de Anthropic: {e}")
        except anthropic.RateLimitError as e:
            logger.error(f"Límite de velocidad excedido en Anthropic: {e}")
            raise IAProviderError(f"Límite de velocidad excedido: {e}")
        except anthropic.AuthenticationError as e:
            logger.error(f"Error de autenticación en Anthropic: {e}")
            raise IAProviderError(f"Error de autenticación: Verifica tu API key")
        except Exception as e:
            logger.error(f"Error inesperado durante la invocación de Anthropic: {e}")
            raise IAProviderError(f"Error inesperado: {e}")

    def get_model(self) -> str:
        """Retorna el modelo actual de Anthropic"""
        return self.model

    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor"""
        return "Anthropic"




##-- aca solo mostrar si es que se legara a usar mas ia una strategia mas
class OpenAIStrategy(IAStrategy):
    """Implementación específica para OpenAI GPT"""

    def __init__(self,
                 api_key: str,
                 model: str = "gpt-4",
                 max_tokens: int = 4000,
                 temperature: float = 0):
        """
        Inicializa la estrategia de OpenAI.

        :param api_key: Clave de API de OpenAI.
        :param model: Modelo de OpenAI a usar.
        :param max_tokens: Número máximo de tokens.
        :param temperature: Temperatura del modelo.
        """
        if not api_key:
            raise ValueError("La clave de API de OpenAI no puede estar vacía.")

        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Aquí inicializarías el cliente de OpenAI
        # self.client = openai.OpenAI(api_key=api_key)

    def invoke(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> str:
        """
        Invoca el modelo de OpenAI.

        :param prompt: El texto de entrada para el modelo.
        :param max_tokens: Número máximo de tokens a generar.
        :return: El texto generado por el modelo.
        :raises IAProviderError: Si hay error en la invocación.
        """
        # Implementación para OpenAI
        raise NotImplementedError("Implementación de OpenAI pendiente")

    def get_model(self) -> str:
        """Retorna el modelo actual de OpenAI"""
        return self.model

    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor"""
        return "OpenAI"


class IAInvoker:
    """Contexto que usa diferentes estrategias de IA"""

    def __init__(self, strategy: IAStrategy):
        """
        Inicializa el invocador con una estrategia específica.

        :param strategy: La estrategia de IA a usar.
        """
        self._strategy = strategy

    def set_strategy(self, strategy: IAStrategy) -> None:
        """
        Cambia la estrategia de IA en tiempo de ejecución.

        :param strategy: Nueva estrategia a usar.
        """
        self._strategy = strategy
        logger.info(f"Estrategia cambiada a: {strategy.get_provider_name()}")

    def invoke(self, prompt: str, max_tokens: Optional[int] = None, **kwargs) -> str:
        """
        Invoca el modelo usando la estrategia actual.

        :param prompt: El texto de entrada para el modelo.
        :param max_tokens: Número máximo de tokens a generar.
        :return: El texto generado por el modelo.
        """
        return self._strategy.invoke(prompt, max_tokens, **kwargs)

    def get_current_model(self) -> str:
        """Retorna información sobre el modelo y proveedor actual"""
        return f"{self._strategy.get_provider_name()}: {self._strategy.get_model()}"

    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor actual"""
        return self._strategy.get_provider_name()


def prompt_ai(prompt: str, instance_ia: 'IAInvoker', source: str, max_tokens: Optional[int] = None, **kwargs) -> str:
    """
    Función centralizada para invocar IA con logging completo.

    :param prompt: El texto de entrada para el modelo.
    :param instance_ia: Instancia del invocador de IA.
    :param source: Identificador de la fuente que realiza la llamada.
    :param max_tokens: Número máximo de tokens a generar (opcional).
    :param kwargs: Parámetros adicionales para el modelo.
    :return: La respuesta generada por el modelo.
    :raises: Re-lanza cualquier excepción después de loggear.
    """
    if not prompt or not prompt.strip():
        logger.error(f"Prompt vacío recibido desde source: {source}")
        raise ValueError("El prompt no puede estar vacío.")

    if not source or not source.strip():
        logger.warning("Source no proporcionado o vacío")
        source = "unknown"

    start_time = time.time()

    try:
        logger.info(f"Iniciando invocación de IA desde source: {source}")

        # Invocar el modelo
        result_ia = instance_ia.invoke(prompt, max_tokens=max_tokens, **kwargs)

        # Calcular tiempo de procesamiento
        processing_time = round(time.time() - start_time, 2)

        # Log estructurado del éxito
        logger.info({
            "event": "ia_invocation_success",
            "source": source,
            "model": instance_ia.get_current_model(),
            "provider": instance_ia.get_provider_name(),
            "prompt_length": len(prompt),
            "response_length": len(result_ia),
            "processing_time_seconds": processing_time,
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,  # Truncar prompt largo
            "response_preview": result_ia[:200] + "..." if len(result_ia) > 200 else result_ia
        })

        return result_ia

    except Exception as e:
        # Calcular tiempo hasta el error
        error_time = round(time.time() - start_time, 2)

        # Log estructurado del error
        logger.error({
            "event": "ia_invocation_error",
            "source": source,
            "model": instance_ia.get_current_model(),
            "provider": instance_ia.get_provider_name(),
            "prompt_length": len(prompt),
            "processing_time_seconds": error_time,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt
        })

        # Re-lanzar la excepción para que el código llamador pueda manejarla
        raise



# # Ejemplo de uso:
#
# # Crear estrategia de Anthropic
# anthropic_strategy = AnthropicStrategy(
#     api_key="your-anthropic-api-key",
#     model="claude-3-5-sonnet-20241022",
#     max_tokens=8000
# )
#
# # Crear el invocador con la estrategia de Anthropic
# ia_invoker = IAInvoker(anthropic_strategy)
#
# # Usar el invocador
# try:
#     response = ia_invoker.invoke("Explícame qué es la inteligencia artificial")
#     print(f"Respuesta de {ia_invoker.get_current_model()}: {response}")
#
#     # Cambiar estrategia en tiempo de ejecución (si tuvieras OpenAI configurado)
#     # openai_strategy = OpenAIStrategy(api_key="your-openai-key")
#     # ia_invoker.set_strategy(openai_strategy)
#
# except IAProviderError as e:
#     print(f"Error del proveedor de IA: {e}")
# except ValueError as e:
#     print(f"Error de validación: {e}")
