"""
Cliente para OpenAI embeddings API.
MODIFICADO: Integración con sistema de colas por tier.
"""

import logging
import aiohttp
from typing import List, Dict, Any, Optional

from embedding_service.config.settings import get_settings, OPENAI_MODELS

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenAIClient:
    """
    Cliente para comunicación con API de OpenAI.
    MODIFICADO: Optimizado para sistema de colas.
    """
    
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
        MODIFICADO: Tracking mejorado y validaciones por tier.
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
        
        # Preparar payload
        payload = {
            "input": non_empty_texts,
            "model": model,
            "encoding_format": settings.encoding_format
        }
        
        # Añadir dimensiones específicas si se configuraron
        if settings.preferred_dimensions > 0:
            if model.startswith("text-embedding-3"):
                payload["dimensions"] = settings.preferred_dimensions
        
        # Hacer request a OpenAI
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        raise Exception(
                            f"OpenAI API error: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        )
                    
                    result = await response.json()
                    
                    # Extraer embeddings
                    embeddings_data = result.get("data", [])
                    embeddings = [item["embedding"] for item in embeddings_data]
                    dimensions = len(embeddings[0]) if embeddings else self._get_dimensions(model)
                    
                    # Reconstruir lista completa
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
                    
                    return {
                        "embeddings": full_embeddings,
                        "dimensions": dimensions,
                        "model": model,
                        "usage": usage
                    }
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling OpenAI: {str(e)}")
            raise Exception(f"Error de red con OpenAI: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise Exception(f"Error generando embeddings: {str(e)}")
    
    def _get_dimensions(self, model: str) -> int:
        """Obtiene las dimensiones del modelo especificado."""
        model_info = OPENAI_MODELS.get(model, OPENAI_MODELS["text-embedding-3-small"])
        return model_info["dimensions"]