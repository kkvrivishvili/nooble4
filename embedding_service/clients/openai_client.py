"""
Cliente para la API de OpenAI Embeddings.

Proporciona una interfaz limpia para generar embeddings
usando la API de OpenAI con manejo de errores y reintentos.
"""

import logging
import time
from typing import List, Optional, Dict, Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import ServiceUnavailableError


class OpenAIClient(BaseHTTPClient):
    """
    Cliente asíncrono para la API de OpenAI Embeddings.
    
    Extiende BaseHTTPClient para proporcionar funcionalidad
    específica para la generación de embeddings.
    """
    
    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Inicializa el cliente con la API key.
        
        Args:
            api_key: API key de OpenAI
            base_url: URL base de la API
            timeout: Timeout en segundos
            max_retries: Número máximo de reintentos
        """
        if not api_key:
            raise ValueError("API key de OpenAI es requerida")
        
        # Headers con autenticación
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Inicializar cliente base
        super().__init__(
            base_url=base_url,
            headers=headers
        )
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ServiceUnavailableError)
    )
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        encoding_format: str = "float",
        user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos.
        
        Args:
            texts: Lista de textos para generar embeddings
            model: Modelo de embedding a usar
            dimensions: Dimensiones del embedding (opcional)
            encoding_format: Formato de codificación
            user: Identificador único del usuario
            
        Returns:
            Dict con embeddings y metadatos
            
        Raises:
            ServiceUnavailableError: Si el servicio no está disponible
            Exception: Para otros errores
        """
        start_time = time.time()
        
        # Filtrar textos vacíos y recordar sus posiciones
        non_empty_texts = []
        non_empty_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)
        
        if not non_empty_texts:
            # Si todos los textos están vacíos, devolver embeddings de ceros
            dimensions = dimensions or 1536  # Default para text-embedding-3-small
            return {
                "embeddings": [[0.0] * dimensions for _ in texts],
                "model": model,
                "dimensions": dimensions,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0,
                "processing_time_ms": 0
            }
        
        # Preparar payload
        payload = {
            "input": non_empty_texts,
            "model": model,
            "encoding_format": encoding_format
        }
        
        # Agregar parámetros opcionales
        if dimensions and model.startswith("text-embedding-3"):
            payload["dimensions"] = dimensions
        
        if user:
            payload["user"] = user
        
        self.logger.debug(
            f"Generando embeddings para {len(non_empty_texts)} textos con {model}"
        )
        
        try:
            # Hacer petición
            response = await self.post(
                "/embeddings",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Validar estructura
            if "data" not in data:
                raise ValueError("Respuesta inválida de OpenAI API: sin data")
            
            # Extraer embeddings
            embeddings_data = data["data"]
            embeddings_dict = {item["index"]: item["embedding"] for item in embeddings_data}
            
            # Reconstruir lista completa con embeddings vacíos donde corresponda
            dimensions_actual = len(embeddings_dict[0]) if embeddings_dict else (dimensions or 1536)
            full_embeddings = []
            
            for i in range(len(texts)):
                if i in non_empty_indices:
                    # Obtener el índice en la respuesta de OpenAI
                    response_idx = non_empty_indices.index(i)
                    full_embeddings.append(embeddings_dict[response_idx])
                else:
                    # Texto vacío, agregar embedding de ceros
                    full_embeddings.append([0.0] * dimensions_actual)
            
            # Extraer métricas
            usage = data.get("usage", {})
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log métricas
            self.logger.info(
                f"Embeddings generados en {processing_time_ms}ms. "
                f"Tokens: {usage.get('total_tokens', 0)}"
            )
            
            return {
                "embeddings": full_embeddings,
                "model": data.get("model", model),
                "dimensions": dimensions_actual,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "processing_time_ms": processing_time_ms
            }
            
        except httpx.TimeoutException:
            self.logger.error(f"Timeout en llamada a OpenAI API después de {self.timeout}s")
            raise ServiceUnavailableError(
                f"OpenAI API timeout después de {self.timeout} segundos"
            )
        
        except Exception as e:
            self.logger.error(f"Error en llamada a OpenAI API: {str(e)}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista los modelos de embedding disponibles.
        
        Returns:
            Lista de modelos disponibles
        """
        try:
            response = await self.get("/models")
            data = response.json()
            
            # Filtrar solo modelos de embedding
            embedding_models = [
                model for model in data.get("data", [])
                if "embedding" in model.get("id", "")
            ]
            
            return embedding_models
            
        except Exception as e:
            self.logger.error(f"Error listando modelos: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Verifica si la API de OpenAI está disponible.
        
        Returns:
            True si está disponible
        """
        try:
            # Intentar generar un embedding simple como health check
            result = await self.generate_embeddings(
                texts=["health check"],
                model="text-embedding-3-small"
            )
            return len(result["embeddings"]) > 0
            
        except Exception:
            return False