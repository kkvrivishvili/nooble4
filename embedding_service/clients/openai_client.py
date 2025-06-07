"""
Cliente simple para OpenAI embeddings API.

# TODO: Oportunidades de mejora futura:
# 1. Implementar mecanismos de retry con backoff exponencial para llamadas a la API
# 2. Añadir caché de resultados para evitar duplicar peticiones frecuentes
# 3. Mejorar manejo de errores con excepciones específicas por tipo de error
# 4. Considerar extracción de un BaseAPIClient para compartir lógica con otros clientes
"""

import logging
import aiohttp
from typing import List, Dict, Any, Optional

from common.errors import ServiceError
from embedding_service.config.settings import get_settings, OPENAI_MODELS

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenAIClient:
    """Cliente para comunicación con API de OpenAI para generación de embeddings."""
    
    def __init__(self):
        """Inicializa cliente con configuración default."""
        self.api_key = settings.openai_api_key
        self.api_url = "https://api.openai.com/v1/embeddings"
        self.timeout = settings.openai_timeout_seconds
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = None,
        tenant_id: str = None,
        collection_id: Optional[str] = None,
        chunk_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos.
        
        Args:
            texts: Lista de textos para generar embeddings
            model: Modelo a utilizar
            tenant_id: ID del tenant (para tracking)
            collection_id: ID de colección (para tracking)
            chunk_ids: IDs de chunks (para tracking)
            metadata: Metadatos adicionales (para tracking)
            
        Returns:
            Dict con 'embeddings', 'dimensions', 'model' y 'usage'
        """
        # Configurar modelo
        model = model or settings.default_embedding_model
        
        # Filtrar textos vacíos
        non_empty_texts = [t for t in texts if t and t.strip()]
        if not non_empty_texts:
            # Si no hay textos válidos, devolver embeddings de ceros
            dimensions = self._get_dimensions(model)
            return {
                "embeddings": [[0.0] * dimensions for _ in texts],
                "dimensions": dimensions,
                "usage": {"total_tokens": 0},
                "model": model
            }
        
        # Preparar request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Preparar payload con parámetros completos según documentación oficial
        payload = {
            "input": non_empty_texts,
            "model": model,
            "encoding_format": settings.encoding_format
        }
        
        # Añadir dimensiones específicas si se configuraron (solo para modelos que lo soportan)
        if settings.preferred_dimensions > 0:
            # text-embedding-3-small y text-embedding-3-large soportan dimensiones reducidas
            if model.startswith("text-embedding-3"):
                payload["dimensions"] = settings.preferred_dimensions
                logger.info(f"Solicitando dimensiones reducidas: {settings.preferred_dimensions}")
            else:
                logger.warning(f"El modelo {model} no soporta dimensiones personalizadas. Se usarán las dimensiones default.")
        
        # Hacer request a OpenAI
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        raise ServiceError(
                            f"OpenAI API error: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        )
                    
                    result = await response.json()
                    
                    # Extraer embeddings
                    embeddings_data = result.get("data", [])
                    embeddings = [item["embedding"] for item in embeddings_data]
                    dimensions = len(embeddings[0]) if embeddings else self._get_dimensions(model)
                    
                    # Reconstruir lista completa (incluyendo vectores cero para textos vacíos)
                    full_embeddings = []
                    non_empty_idx = 0
                    
                    for text in texts:
                        if text and text.strip():
                            full_embeddings.append(embeddings[non_empty_idx])
                            non_empty_idx += 1
                        else:
                            full_embeddings.append([0.0] * dimensions)
                    
                    # Preparar resultado
                    usage = result.get("usage", {})
                    
                    # Tracking de tokens - en la implementación refactorizada,
                    # el tracking se manejará en otro nivel de abstracción
                    
                    return {
                        "embeddings": full_embeddings,
                        "dimensions": dimensions,
                        "model": model,
                        "usage": usage
                    }
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling OpenAI: {str(e)}")
            raise ServiceError(f"Error de red con OpenAI: {str(e)}")
        except Exception as e:
            if isinstance(e, ServiceError):
                raise
            logger.error(f"Unexpected error: {str(e)}")
            raise ServiceError(f"Error generando embeddings: {str(e)}")
    
    def _get_dimensions(self, model: str) -> int:
        """
        Obtiene las dimensiones del modelo especificado.
        
        Args:
            model: Nombre del modelo
            
        Returns:
            Dimensiones del modelo
        """
        model_info = OPENAI_MODELS.get(model, OPENAI_MODELS["text-embedding-3-small"])
        return model_info["dimensions"]
