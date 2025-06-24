"""
Handler para la generación de embeddings usando OpenAI API.

Maneja la comunicación con la API de OpenAI y la generación
de embeddings vectoriales.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..clients.openai_client import OpenAIClient


class OpenAIHandler(BaseHandler):
    """
    Handler para generar embeddings usando OpenAI.
    
    Coordina la generación de embeddings con reintentos,
    manejo de errores y tracking de métricas.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Inicializar cliente OpenAI
        self.openai_client = OpenAIClient(
            api_key=self.app_settings.openai_api_key,
            base_url=self.app_settings.openai_base_url,
            timeout=self.app_settings.openai_timeout_seconds,
            max_retries=self.app_settings.openai_max_retries
        )
        
        # Configuración por defecto
        self.default_model = self.app_settings.openai_default_model
        self.default_dimensions = self.app_settings.default_dimensions_by_model.get(
            self.default_model, 
            1536  # Default para text-embedding-3-small
        )
        
        self._logger.info("OpenAIHandler inicializado")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        trace_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos.
        
        Args:
            texts: Lista de textos
            model: Modelo específico a usar (string, no enum)
            dimensions: Dimensiones del embedding
            encoding_format: Formato de codificación
            tenant_id: ID del tenant
            trace_id: ID de traza
            
        Returns:
            Dict con embeddings y metadatos
        """
        # Configurar parámetros
        model = model or self.default_model
        encoding_format = encoding_format or "float"
        
        # Las dimensiones siempre deben venir del EmbeddingRequest (RAGConfig centralizado)
        # No usar fallbacks locales para mantener la centralización
        
        self._logger.info(
            f"Generando embeddings para {len(texts)} textos con modelo {model}",
            extra={
                "tenant_id": tenant_id,
                "trace_id": str(trace_id) if trace_id else None,
                "model": model,
                "dimensions": dimensions
            }
        )
        
        try:
            # Llamar al cliente OpenAI
            result = await self.openai_client.generate_embeddings(
                texts=texts,
                model=model,
                dimensions=dimensions,
                encoding_format=encoding_format,
                user=tenant_id  # Usar tenant_id como user para tracking en OpenAI
            )
            
            self._logger.info(
                f"Embeddings generados exitosamente en {result.get('processing_time_ms')}ms",
                extra={
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "model": model,
                    "text_count": len(texts),
                    "total_tokens": result.get("total_tokens", 0),
                    "dimensions": result.get("dimensions", 0)
                }
            )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error generando embeddings: {e}",
                exc_info=True,
                extra={"tenant_id": tenant_id, "model": model}
            )
            raise ExternalServiceError(
                f"Error al generar embeddings con OpenAI: {str(e)}",
                original_exception=e
            )
    
    async def validate_model(self, model: str) -> bool:
        """
        Valida si un modelo está disponible.
        
        Args:
            model: Nombre del modelo
            
        Returns:
            True si el modelo está disponible
        """
        try:
            # Por ahora, validamos contra una lista conocida
            valid_models = [
                "text-embedding-3-small",
                "text-embedding-3-large",
                "text-embedding-ada-002"
            ]
            return model in valid_models
            
        except Exception as e:
            self._logger.error(f"Error validando modelo {model}: {e}")
            return False
    
    def estimate_tokens(self, texts: List[str]) -> int:
        """
        Estima el número de tokens para una lista de textos.
        
        Esta es una estimación aproximada. Para una estimación
        precisa se debería usar tiktoken.
        
        Args:
            texts: Lista de textos
            
        Returns:
            Número estimado de tokens
        """
        # Estimación simple: ~4 caracteres por token
        total_chars = sum(len(text) for text in texts)
        return max(1, total_chars // 4)