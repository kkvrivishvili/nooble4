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
    
    def __init__(self, app_settings, openai_client: OpenAIClient, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: Configuración global de la aplicación
            direct_redis_conn: Conexión Redis directa (opcional)
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Validar que el cliente esté presente
        self.app_settings = app_settings
        self.openai_client = OpenAIClient(
            api_key=self.app_settings.openai_api_key,
            timeout=self.app_settings.openai_timeout_seconds,
            max_retries=self.app_settings.openai_max_retries,
            base_url=self.app_settings.openai_base_url,
        )
        

        
        self._logger.info("OpenAIHandler inicializado con inyección de cliente")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        trace_id: Optional[UUID] = None,
        rag_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos.
        
        Args:
            texts: Lista de textos
            model: Modelo específico a usar (string, no enum)
            dimensions: Dimensiones del embedding
            encoding_format: Formato de codificación
            tenant_id: ID del tenant
            agent_id: ID del agente
            trace_id: ID de traza
            rag_config: Configuración RAG opcional con parámetros dinámicos
            
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
            request_timeout = None
            request_max_retries = None

            if rag_config:
                request_timeout = rag_config.timeout
                request_max_retries = rag_config.max_retries
                self._logger.debug(
                    f"Usando configuración de RAG para la solicitud: timeout={request_timeout}, max_retries={request_max_retries}"
                )

            result = await self.openai_client.generate_embeddings(
                texts=texts,
                model=model,
                dimensions=dimensions,
                encoding_format=encoding_format,
                timeout=request_timeout,
                max_retries=request_max_retries,
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