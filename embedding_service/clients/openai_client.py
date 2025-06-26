"""
Cliente para la API de OpenAI Embeddings.

Proporciona una interfaz limpia para generar embeddings
usando la API de OpenAI con manejo de errores y reintentos.
"""

import logging
import time
from typing import List, Optional, Dict, Any

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError, APIConnectionError
from common.errors.exceptions import ExternalServiceError

class OpenAIClient:
    """
    Cliente asíncrono para la API de OpenAI Embeddings usando el SDK oficial.
    """
    
    def __init__(
        self, 
        api_key: str,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ):
        """
        Inicializa el cliente con la API key y otras configuraciones.
        
        Args:
            api_key: API key de OpenAI
            base_url: URL base de la API (opcional)
            timeout: Timeout en segundos para las peticiones (desde EmbeddingServiceSettings)
            max_retries: Número máximo de reintentos automáticos por el SDK (desde EmbeddingServiceSettings)
        """
        if not api_key:
            raise ValueError("API key de OpenAI es requerida")
        
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url, 
            timeout=timeout,
            max_retries=max_retries
        )
        self.logger = logging.getLogger(__name__)

    def with_options(self, timeout: Optional[float] = None, max_retries: Optional[int] = None) -> 'OpenAIClient':
        """
        Crea una nueva instancia del cliente con opciones personalizadas.
        
        Permite configurar dinámicamente el timeout y reintentos sin modificar la instancia original.
        
        Args:
            timeout: Timeout personalizado en segundos para las peticiones (None para usar el valor por defecto).
            max_retries: Número máximo de reintentos (None para usar el valor por defecto).
            
        Returns:
            Una nueva instancia de OpenAIClient con las opciones actualizadas.
        """
        # Crear una nueva instancia con los mismos parámetros base
        new_client = OpenAIClient(
            api_key=self.api_key,
            timeout=timeout if timeout is not None else self.timeout,
            max_retries=max_retries if max_retries is not None else self.max_retries,
            base_url=self.base_url
        )
        
        self.logger.debug(
            f"Cliente OpenAI clonado con opciones: timeout={new_client.timeout}s, "
            f"max_retries={new_client.max_retries}"
        )
        
        return new_client

    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        encoding_format: str = "float", 
        user: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos usando el SDK de OpenAI.
        
        Args:
            texts: Lista de textos para generar embeddings.
            model: Modelo de embedding a usar.
            dimensions: Dimensiones del embedding (opcional, soportado por modelos v3).
            encoding_format: Formato de codificación ('float' o 'base64').
            user: Identificador único del usuario final (opcional).
            timeout: Timeout personalizado en segundos para la petición (None para usar el valor por defecto).
            max_retries: Número máximo de reintentos (None para usar el valor por defecto).
            
        Returns:
            Un diccionario conteniendo la lista de embeddings, el modelo usado,
            las dimensiones, información de uso de tokens y tiempo de procesamiento.
            
        Raises:
            ExternalServiceError: Si ocurre un error con la API de OpenAI.
            ValueError: Si los textos de entrada son inválidos.
        """
        start_time = time.time()
        
        non_empty_texts_with_original_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts_with_original_indices.append({"text": text, "original_index": i})
        
        if not non_empty_texts_with_original_indices:
            actual_dimensions = dimensions or 1536 
            self.logger.info("No hay textos válidos para embeber, devolviendo vectores de ceros.")
            return {
                "embeddings": [[0.0] * actual_dimensions for _ in texts],
                "model": model,
                "dimensions": actual_dimensions,
                "prompt_tokens": 0,
                "total_tokens": 0,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        input_texts_for_api = [item["text"] for item in non_empty_texts_with_original_indices]
        
        api_params = {
            "input": input_texts_for_api,
            "model": model,
            "encoding_format": encoding_format
        }
        
        if dimensions and "text-embedding-3" in model:
            api_params["dimensions"] = dimensions
        
        if user:
            api_params["user"] = user
            
        self.logger.debug(
            f"Generando embeddings para {len(input_texts_for_api)} textos con el modelo {model}."
        )

        try:
            # Preparamos los overrides para la llamada a la API
            request_options = {}
            if timeout is not None:
                request_options["timeout"] = timeout
            if max_retries is not None:
                request_options["max_retries"] = max_retries

            response = await self.client.embeddings.create(**api_params, **request_options)
            
            sdk_embeddings_map = {item.index: item.embedding for item in response.data}
            
            actual_dimensions = len(response.data[0].embedding) if response.data else (dimensions or 1536)
            
            full_embeddings: List[List[float]] = []
            current_sdk_idx = 0
            for i in range(len(texts)):
                is_processed = False
                for item in non_empty_texts_with_original_indices:
                    if item["original_index"] == i:
                        if current_sdk_idx in sdk_embeddings_map:
                             full_embeddings.append(sdk_embeddings_map[current_sdk_idx])
                             current_sdk_idx +=1
                        else:
                            self.logger.error(f"Falta embedding para el índice SDK {current_sdk_idx} (índice original {i})")
                            full_embeddings.append([0.0] * actual_dimensions)
                        is_processed = True
                        break
                if not is_processed:
                    full_embeddings.append([0.0] * actual_dimensions)

            processing_time_ms = int((time.time() - start_time) * 1000)
            
            self.logger.info(
                f"Embeddings generados en {processing_time_ms}ms. "
                f"Modelo: {response.model}. Tokens: {response.usage.total_tokens if response.usage else 'N/A'}."
            )
            
            return {
                "embeddings": full_embeddings,
                "model": response.model,
                "dimensions": actual_dimensions, 
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
                "processing_time_ms": processing_time_ms
            }

        except APITimeoutError as e:
            self.logger.error(f"Timeout en llamada a OpenAI API: {e}")
            raise ExternalServiceError(f"OpenAI API timeout: {e}", original_exception=e)
        except RateLimitError as e:
            self.logger.error(f"Rate limit excedido en OpenAI API: {e}")
            raise ExternalServiceError(f"OpenAI API rate limit excedido: {e}", original_exception=e)
        except APIConnectionError as e:
            self.logger.error(f"Error de conexión con OpenAI API: {e}")
            raise ExternalServiceError(f"OpenAI API error de conexión: {e}", original_exception=e)
        except APIError as e: 
            self.logger.error(f"Error en OpenAI API: {e}")
            raise ExternalServiceError(f"OpenAI API error: {e}", original_exception=e)
        except Exception as e: 
            self.logger.error(f"Error inesperado generando embeddings: {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado en el cliente OpenAI: {str(e)}", original_exception=e)

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista los modelos disponibles. (Refactorización pendiente si se necesita)
        Actualmente, esta función es un placeholder.
        """
        self.logger.info("La funcionalidad 'list_models' con el SDK de OpenAI aún no está completamente implementada.")
        # Ejemplo de cómo podría ser con el SDK:
        # try:
        #     models = await self.client.models.list()
        #     # Procesar y retornar 'models.data' según sea necesario, por ejemplo:
        #     # return [model.to_dict() for model in models.data if "embedding" in model.id]
        # except APIError as e:
        #     self.logger.error(f"Error listando modelos de OpenAI: {e}")
        #     raise ExternalServiceError(f"OpenAI API error listando modelos: {e}", original_exception=e)
        return [] # Placeholder
    
    async def health_check(self) -> bool:
        """
        Verifica si la API de OpenAI está disponible intentando generar un embedding simple.
        
        Returns:
            True si la generación de embedding es exitosa, False en caso contrario.
        """
        try:
            # Intentar generar un embedding simple como health check
            # Esto usará el nuevo método generate_embeddings basado en SDK
            result = await self.generate_embeddings(
                texts=["health check"],
                model="text-embedding-3-small" # Usar un modelo pequeño y eficiente
            )
            # Verificar que se obtuvieron embeddings y que no están vacíos
            return bool(result and result.get("embeddings") and result["embeddings"][0])
            
        except ExternalServiceError as e: # Capturar errores específicos del servicio externo
            self.logger.warning(f"Health check fallido para OpenAI: {e}")
            return False
        except Exception as e: # Capturar cualquier otro error inesperado
            self.logger.error(f"Error inesperado durante el health check de OpenAI: {e}", exc_info=True)
            return False