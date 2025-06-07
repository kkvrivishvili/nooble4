"""
Domain Queue Manager - Gestor unificado de colas por dominio y tier.

Este módulo implementa el sistema de colas estandarizado con:
- Formato: {domain}:{context_id}:{tier}
- Encolado automático con enriquecimiento
- Métricas y tracking por tier
- Rate limiting por tier
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import redis.asyncio as redis

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext

logger = logging.getLogger(__name__)


class DomainQueueManager:
    """
    Gestor centralizado de colas por dominio y tier.
    
    Maneja:
    - Encolado con formato estandarizado
    - Tracking de métricas por tier
    - Rate limiting por tier
    - Callbacks estructurados
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Inicializa queue manager.
        
        Args:
            redis_client: Cliente Redis configurado
        """
        self.redis = redis_client
        
        # Configuración de tiers
        self.tier_config = {
            "free": {
                "rate_limit_per_minute": 10,
                "rate_limit_per_day": 100,
                "priority": 4,
                "timeout": 30
            },
            "advance": {
                "rate_limit_per_minute": 50,
                "rate_limit_per_day": 1000,
                "priority": 3,
                "timeout": 60
            },
            "professional": {
                "rate_limit_per_minute": 200,
                "rate_limit_per_day": 10000,
                "priority": 2,
                "timeout": 120
            },
            "enterprise": {
                "rate_limit_per_minute": None,  # Sin límites
                "rate_limit_per_day": None,
                "priority": 1,
                "timeout": 300
            }
        }
    
    async def enqueue_execution(
        self,
        action: DomainAction,
        target_domain: str,
        context: ExecutionContext
    ) -> str:
        """
        Encola acción para ejecución en dominio específico.
        
        Args:
            action: Acción a encolar
            target_domain: Dominio destino (execution, embedding, query, etc.)
            context: Contexto de ejecución
            
        Returns:
            Nombre de cola donde se encoló
            
        Raises:
            ValueError: Si el tier no es válido o rate limit excedido
        """
        # Validar tier
        if context.tenant_tier not in self.tier_config:
            raise ValueError(f"Tier inválido: {context.tenant_tier}")
        
        # Verificar rate limits
        await self._check_rate_limits(context)
        
        # Generar nombre de cola
        queue_name = context.get_queue_name(target_domain)
        
        # Enriquecer acción con contexto
        enriched_action = self._enrich_action(action, context, target_domain)
        
        # Encolar
        await self.redis.lpush(queue_name, enriched_action.json())
        
        # Tracking y métricas
        await self._track_usage(context, action, queue_name)
        
        logger.info(f"Acción encolada: {queue_name}, task_id: {action.task_id}")
        return queue_name
    
    async def enqueue_callback(
        self,
        callback_action: DomainAction,
        callback_queue: str
    ) -> bool:
        """
        Encola callback en cola específica.
        
        Args:
            callback_action: Acción de callback
            callback_queue: Cola destino del callback
            
        Returns:
            True si se encoló correctamente
        """
        try:
            await self.redis.lpush(callback_queue, callback_action.json())
            logger.debug(f"Callback encolado: {callback_queue}, task_id: {callback_action.task_id}")
            return True
        except Exception as e:
            logger.error(f"Error encolando callback: {str(e)}")
            return False
    
    async def dequeue_with_priority(
        self,
        domain: str,
        timeout: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Desencola acción respetando prioridad de tiers.
        
        Args:
            domain: Dominio a procesar
            timeout: Timeout en segundos
            
        Returns:
            Acción desencolada o None si timeout
        """
        # Construir lista de colas por prioridad
        queue_names = self._get_queues_by_priority(domain)
        
        # Intentar desencolar con prioridad
        result = await self.redis.brpop(queue_names, timeout)
        
        if result:
            queue_name, action_data = result
            action_dict = json.loads(action_data)
            
            # Tracking de procesamiento
            await self._track_dequeue(queue_name, action_dict)
            
            return action_dict
        
        return None
    
    async def get_queue_stats(self, domain: str) -> Dict[str, Any]:
        """
        Obtiene estadísticas de colas para un dominio.
        
        Args:
            domain: Dominio a consultar
            
        Returns:
            Estadísticas por tier
        """
        stats = {}
        
        for tier in self.tier_config.keys():
            queue_pattern = f"{domain}:*:{tier}"
            
            # Contar elementos en todas las colas del tier
            queue_keys = await self.redis.keys(queue_pattern)
            total_items = 0
            
            for queue_key in queue_keys:
                queue_size = await self.redis.llen(queue_key)
                total_items += queue_size
            
            stats[tier] = {
                "queue_count": len(queue_keys),
                "total_items": total_items,
                "rate_limit": self.tier_config[tier]["rate_limit_per_minute"]
            }
        
        return stats
    
    async def _check_rate_limits(self, context: ExecutionContext):
        """Verifica rate limits para el contexto."""
        tier_config = self.tier_config[context.tenant_tier]
        
        # Enterprise sin límites
        if tier_config["rate_limit_per_minute"] is None:
            return
        
        # Verificar límite por minuto
        current_minute = int(time.time() / 60)
        minute_key = f"rate_limit:{context.tenant_id}:minute:{current_minute}"
        
        current_count = await self.redis.incr(minute_key)
        await self.redis.expire(minute_key, 60)  # TTL de 1 minuto
        
        if current_count > tier_config["rate_limit_per_minute"]:
            raise ValueError(f"Rate limit excedido para tier {context.tenant_tier}: {current_count}/min")
        
        # Verificar límite diario
        if tier_config["rate_limit_per_day"]:
            today = date.today().isoformat()
            day_key = f"rate_limit:{context.tenant_id}:day:{today}"
            
            daily_count = await self.redis.incr(day_key)
            await self.redis.expire(day_key, 86400)  # TTL de 24 horas
            
            if daily_count > tier_config["rate_limit_per_day"]:
                raise ValueError(f"Rate limit diario excedido para tier {context.tenant_tier}: {daily_count}/day")
    
    def _enrich_action(
        self,
        action: DomainAction,
        context: ExecutionContext,
        target_domain: str
    ) -> DomainAction:
        """Enriquece acción con contexto y metadatos."""
        # Crear copia de la acción
        action_data = action.dict()
        
        # Agregar contexto
        action_data["execution_context"] = context.to_dict()
        action_data["tenant_id"] = context.tenant_id
        action_data["tenant_tier"] = context.tenant_tier
        
        # Agregar metadatos de encolado
        action_data["queue_metadata"] = {
            "enqueued_at": datetime.utcnow().isoformat(),
            "target_domain": target_domain,
            "queue_name": context.get_queue_name(target_domain),
            "tier_priority": self.tier_config[context.tenant_tier]["priority"]
        }
        
        # Retornar nueva instancia
        return DomainAction.parse_obj(action_data)
    
    async def _track_usage(
        self,
        context: ExecutionContext,
        action: DomainAction,
        queue_name: str
    ):
        """Registra métricas de uso."""
        # Métricas por tenant
        tenant_key = f"usage:{context.tenant_id}:{date.today().isoformat()}"
        await self.redis.hincrby(tenant_key, "total_requests", 1)
        await self.redis.hincrby(tenant_key, f"{context.context_type}_requests", 1)
        await self.redis.expire(tenant_key, 86400 * 7)  # 7 días
        
        # Métricas por tier
        tier_key = f"usage:tier:{context.tenant_tier}:{date.today().isoformat()}"
        await self.redis.hincrby(tier_key, "total_requests", 1)
        await self.redis.expire(tier_key, 86400 * 30)  # 30 días
        
        # Métricas de cola
        queue_stats_key = f"queue_stats:{queue_name}"
        await self.redis.hincrby(queue_stats_key, "enqueued", 1)
        await self.redis.hset(queue_stats_key, "last_enqueued", datetime.utcnow().isoformat())
        await self.redis.expire(queue_stats_key, 3600)  # 1 hora
    
    async def _track_dequeue(self, queue_name: str, action_dict: Dict[str, Any]):
        """Registra métricas de desencolado."""
        queue_stats_key = f"queue_stats:{queue_name}"
        await self.redis.hincrby(queue_stats_key, "dequeued", 1)
        await self.redis.hset(queue_stats_key, "last_dequeued", datetime.utcnow().isoformat())
    
    def _get_queues_by_priority(self, domain: str) -> List[str]:
        """
        Genera lista de colas ordenadas por prioridad.
        
        Args:
            domain: Dominio para generar colas
            
        Returns:
            Lista de patrones de cola ordenada por prioridad
        """
        # Ordenar tiers por prioridad (1 = más alta)
        sorted_tiers = sorted(
            self.tier_config.keys(),
            key=lambda tier: self.tier_config[tier]["priority"]
        )
        
        # Generar patrones de cola
        return [f"{domain}:*:{tier}" for tier in sorted_tiers]


class QueueMonitor:
    """
    Monitor de colas para observabilidad.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """Obtiene vista general del sistema de colas."""
        domains = ["execution", "embedding", "query", "orchestrator"]
        overview = {}
        
        for domain in domains:
            overview[domain] = await self._get_domain_stats(domain)
        
        return overview
    
    async def _get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """Obtiene estadísticas de un dominio específico."""
        stats = {"tiers": {}, "total_items": 0}
        
        tiers = ["enterprise", "professional", "advance", "free"]
        
        for tier in tiers:
            queue_pattern = f"{domain}:*:{tier}"
            queue_keys = await self.redis.keys(queue_pattern)
            
            tier_items = 0
            for queue_key in queue_keys:
                queue_size = await self.redis.llen(queue_key)
                tier_items += queue_size
            
            stats["tiers"][tier] = {
                "queue_count": len(queue_keys),
                "items": tier_items
            }
            stats["total_items"] += tier_items
        
        return stats