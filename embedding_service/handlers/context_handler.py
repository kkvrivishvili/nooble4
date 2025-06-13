"""
Context Handler - Manejo y validación de contextos de embedding en Embedding Service.

Este módulo se encarga de:
- Resolver ExecutionContext desde DomainActions
- Validar permisos de embedding
- Gestionar configuraciones de modelos
- Cache de validaciones para performance
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from common.models.execution_context import ExecutionContext
from embedding_service.config.settings import get_settings, OPENAI_MODELS

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingContextHandler:
    """
    Manejador de contextos de embedding para Embedding Service.

    Responsable de resolver y validar contextos para generación
    de embeddings.
    """

    def __init__(self, redis_client=None):
        """
        Inicializa handler.

        Args:
            redis_client: Cliente Redis para cache (opcional)
        """
        self.redis = redis_client

        # Cache TTL para validaciones (5 minutos)
        self.validation_cache_ttl = 300

    async def resolve_embedding_context(
        self,
        context_dict: Dict[str, Any]
    ) -> ExecutionContext:
        """
        Resuelve ExecutionContext desde diccionario.

        Args:
            context_dict: Diccionario con datos del contexto

        Returns:
            ExecutionContext válido

        Raises:
            ValueError: Si el contexto no es válido
        """
        try:
            # Crear ExecutionContext desde diccionario
            context = ExecutionContext.from_dict(context_dict)

            logger.info(f"Contexto de embedding resuelto: {context.context_id}")
            return context

        except Exception as e:
            logger.error(f"Error resolviendo contexto de embedding: {str(e)}")
            raise ValueError(f"Contexto de embedding inválido: {str(e)}")

    async def validate_embedding_permissions(
        self,
        context: ExecutionContext,
        texts: List[str],
        model: str
    ) -> bool:
        """
        Valida permisos de embedding.

        Args:
            context: Contexto de ejecución
            texts: Textos para procesar
            model: Modelo a usar

        Returns:
            True si tiene permisos

        Raises:
            ValueError: Si no tiene permisos
        """
        # Validar número de textos por request
        if len(texts) > settings.max_texts_per_request:
            raise ValueError(
                f"Número de textos excede límite: {len(texts)}/{settings.max_texts_per_request}"
            )

        # Validar longitud de textos
        for i, text in enumerate(texts):
            if text and len(text) > settings.max_text_length:
                raise ValueError(
                    f"Texto {i} excede límite de longitud: {len(text)}/{settings.max_text_length}"
                )

        # Validar modelo permitido
        if model not in OPENAI_MODELS:
            raise ValueError(f"Modelo no soportado: {model}")

        # Validar rate limits
        await self._validate_rate_limits(context)

        logger.info(f"Permisos de embedding validados para {context.context_id}")
        return True

    async def _validate_rate_limits(self, context: ExecutionContext):
        """Valida rate limits."""
        max_requests = settings.max_requests_per_hour

        if not max_requests or max_requests <= 0:
            return

        if not self.redis:
            logger.warning("Redis no configurado, saltando validación de rate limit.")
            return

        # Verificar límite por hora
        current_hour = int(datetime.utcnow().timestamp() / 3600)
        hour_key = f"embedding_rate_limit:{context.tenant_id}:hour:{current_hour}"

        current_count = await self.redis.incr(hour_key)
        if current_count == 1:
            await self.redis.expire(hour_key, 3600)  # TTL de 1 hora

        if current_count > max_requests:
            raise ValueError(
                f"Rate limit de embeddings excedido: {current_count}/{max_requests} por hora"
            )

    async def get_model_configuration(self, model: str) -> Dict[str, Any]:
        """
        Obtiene configuración del modelo.

        Args:
            model: Nombre del modelo

        Returns:
            Dict con configuración del modelo
        """
        model_info = OPENAI_MODELS.get(model)
        if not model_info:
            raise ValueError(f"Modelo no soportado: {model}")

        return model_info

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        if not self.redis:
            return {"cache": "disabled"}

        # Contar keys de rate limiting
        rate_limit_keys = await self.redis.keys("embedding_rate_limit:*")

        return {
            "cache": "enabled",
            "rate_limit_entries": len(rate_limit_keys),
            "ttl_seconds": self.validation_cache_ttl
        }


# Factory function
async def get_embedding_context_handler(redis_client=None) -> EmbeddingContextHandler:
    """Factory para obtener EmbeddingContextHandler configurado."""
    return EmbeddingContextHandler(redis_client)