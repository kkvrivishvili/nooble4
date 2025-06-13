"""
Embedding Processor - Procesador principal de generación de embeddings.

Coordina la validación, generación y cache de embeddings.
"""

import logging
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional

from common.models.execution_context import ExecutionContext
from embedding_service.models.actions import EmbeddingGenerateAction
from embedding_service.clients.openai_client import OpenAIClient
from embedding_service.services.validation_service import ValidationService
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingProcessor:
    """
    Procesador principal de embeddings.
    
    Coordina validación, cache, generación y tracking
    de embeddings con optimizaciones por tier.
    """
    
    def __init__(self, validation_service: ValidationService, redis_client=None):
        """
        Inicializa processor.
        
        Args:
            validation_service: Servicio de validación
            redis_client: Cliente Redis para cache
        """
        self.validation_service = validation_service
        self.redis = redis_client
        
        # Inicializar cliente OpenAI
        self.openai_client = OpenAIClient()
    
    async def process_embedding_request(
        self,
        action: EmbeddingGenerateAction,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Procesa solicitud de embedding completa.
        
        Args:
            action: Acción de embedding
            context: Contexto de ejecución
            
        Returns:
            Dict con resultado del embedding
        """
        start_time = time.time()
        
        try:
            logger.info(f"Procesando embedding: {len(action.texts)} textos...")
            
            # 1. Validar textos
            validation_result = await self.validation_service.validate_texts(
                texts=action.texts,
                model=action.model or settings.default_embedding_model,
                context=context
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"Validación fallida: {validation_result['issues'][0]['message']}")
            
            # 2. Verificar cache (si está habilitado)
            embeddings_result = None
            if settings.embedding_cache_enabled:
                embeddings_result = await self._check_cache(action.texts, action.model, context.tenant_id)
            
            # 3. Generar embeddings si no están en cache
            if not embeddings_result:
                embeddings_result = await self.openai_client.generate_embeddings(
                    texts=action.texts,
                    model=action.model,
                    tenant_id=context.tenant_id,
                    collection_id=str(action.collection_id) if action.collection_id else None,
                    chunk_ids=action.chunk_ids,
                    metadata=action.metadata
                )
                
                # Cachear resultado si está habilitado
                if settings.embedding_cache_enabled:
                    await self._cache_embeddings(action.texts, action.model, embeddings_result, context.tenant_id)
            
            # 4. Tracking de métricas
            processing_time = time.time() - start_time
            await self._track_embedding_metrics(
                context, action, embeddings_result, processing_time
            )
            
            # 5. Preparar resultado final
            result = {
                "embeddings": embeddings_result["embeddings"],
                "model": embeddings_result["model"],
                "dimensions": embeddings_result["dimensions"],
                "total_tokens": embeddings_result["usage"].get("total_tokens", 0),
                "processing_time": processing_time,
                "from_cache": embeddings_result.get("from_cache", False)
            }
            
            logger.info(f"Embedding completado en {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error en proceso de embedding: {str(e)}")
            raise
    
    async def _check_cache(
        self, 
        texts: List[str], 
        model: str, 
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Verifica cache de embeddings."""
        if not self.redis:
            return None
        
        try:
            # Generar cache key
            cache_key = self._generate_cache_key(texts, model, tenant_id)
            
            # Verificar cache
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                import json
                result = json.loads(cached_result)
                result["from_cache"] = True
                logger.info(f"Embeddings obtenidos desde cache: {len(texts)} textos")
                return result
                
        except json.JSONDecodeError as e:
            # Error específico al decodificar JSON inválido en la caché
            logger.error(f"Error al decodificar JSON de cache: {str(e)}")
            # Remover clave de cache inválida
            try:
                await self.redis.delete(cache_key)
                logger.warning(f"Cache inválida eliminada: {cache_key}")
            except Exception:
                pass
        except ConnectionError as e:
            # Error específico de conexión a Redis
            logger.error(f"Error de conexión a Redis: {str(e)}")
        except Exception as e:
            # Fallback para otros errores inesperados
            logger.error(f"Error inesperado verificando cache: {str(e)}")
        
        return None
    
    async def _cache_embeddings(
        self, 
        texts: List[str], 
        model: str, 
        embeddings_result: Dict[str, Any], 
        tenant_id: str
    ):
        """Cachea embeddings generados."""
        if not self.redis:
            return
        
        try:
            # Generar cache key
            cache_key = self._generate_cache_key(texts, model, tenant_id)
            
            # Preparar datos para cache (sin from_cache flag)
            cache_data = {
                "embeddings": embeddings_result["embeddings"],
                "model": embeddings_result["model"],
                "dimensions": embeddings_result["dimensions"],
                "usage": embeddings_result["usage"]
            }
            
            # Cachear con TTL
            import json
            await self.redis.setex(
                cache_key,
                settings.embedding_cache_ttl,
                json.dumps(cache_data)
            )
            
            logger.debug(f"Embeddings cacheados: {cache_key}")
            
        except KeyError as e:
            # Error específico cuando falta un campo en embeddings_result
            logger.error(f"Error de estructura en embeddings_result: falta campo {str(e)}")
        except json.JSONEncodeError as e:
            # Error específico al codificar los datos como JSON
            logger.error(f"Error al codificar embeddings como JSON: {str(e)}")
        except ConnectionError as e:
            # Error específico de conexión a Redis
            logger.error(f"Error de conexión a Redis al cachear: {str(e)}")
        except Exception as e:
            # Fallback para otros errores inesperados
            logger.error(f"Error inesperado cacheando embeddings: {str(e)}")
    
    def _generate_cache_key(self, texts: List[str], model: str, tenant_id: str) -> str:
        """Genera clave de cache para embeddings con mayor resistencia a colisiones."""
        # Crear un salt combinando modelo, tenant y el contenido del primer texto (parcial)
        first_text = texts[0][:50] if texts else ""
        salt = f"{model}:{tenant_id}:{first_text}"
        
        # Crear hash de los textos con el salt
        texts_content = "|".join(texts)
        combined_content = f"{salt}:{texts_content}"
        texts_hash = hashlib.md5(combined_content.encode()).hexdigest()
        
        # Usar un hash más largo (16 caracteres) para reducir posibilidad de colisiones
        return f"embeddings_cache:{tenant_id}:{model}:{texts_hash[:16]}:{len(texts)}"
    
    async def _track_embedding_metrics(
        self,
        context: ExecutionContext,
        action: EmbeddingGenerateAction,
        result: Dict[str, Any],
        processing_time: float
    ):
        """Registra métricas de embedding."""
        if not self.redis or not settings.enable_embedding_tracking:
            return

        try:
            today = datetime.now().date().isoformat()

            # Métricas por tenant
            tenant_key = f"embedding_metrics:{context.tenant_id}:{today}"
            await self.redis.hincrby(tenant_key, "total_requests", 1)
            await self.redis.hincrby(tenant_key, "total_texts", len(action.texts))
            await self.redis.hincrby(tenant_key, "total_tokens", result["usage"].get("total_tokens", 0))

            if result.get("from_cache", False):
                await self.redis.hincrby(tenant_key, "cache_hits", 1)
            else:
                await self.redis.hincrby(tenant_key, "cache_misses", 1)

            # TTL
            await self.redis.expire(tenant_key, 86400 * 7)  # 7 días

        except Exception as e:
            logger.error(f"Error tracking embedding metrics: {str(e)}")
    
    async def get_embedding_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de embeddings para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"embedding_metrics:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            # Calcular cache hit rate
            cache_hits = int(metrics.get("cache_hits", 0))
            cache_misses = int(metrics.get("cache_misses", 0))
            total_cache_requests = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0.0
            
            return {
                "date": today,
                "total_requests": int(metrics.get("total_requests", 0)),
                "total_texts": int(metrics.get("total_texts", 0)),
                "total_tokens": int(metrics.get("total_tokens", 0)),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "avg_texts_per_request": self._calculate_avg_texts(metrics)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo embedding stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_avg_texts(self, metrics: Dict[str, str]) -> float:
        """Calcula promedio de textos por request."""
        total_requests = int(metrics.get("total_requests", 0))
        total_texts = int(metrics.get("total_texts", 0))
        
        if total_requests == 0:
            return 0.0
        
        return round(total_texts / total_requests, 2)