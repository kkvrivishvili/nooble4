"""
Servicio de gestión de colas con Redis para Domain Actions.

Este módulo implementa un sistema de colas basado en Redis para el procesamiento
asíncrono de tareas mediante Domain Actions.
"""

import json
import uuid
import logging
import asyncio
from typing import Dict, List, Any, Optional, Type, TypeVar, Generic, Union
import time
from datetime import datetime

import redis
from pydantic import BaseModel

from common.models.actions import DomainAction
from common.context import Context, with_context
from ingestion_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=DomainAction)


class QueueService:
    """Servicio para gestionar colas Redis de Domain Actions."""
    
    def __init__(self):
        """Inicializa la conexión con Redis."""
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.prefix = settings.REDIS_QUEUE_PREFIX
        self._test_connection()
        
    def _test_connection(self) -> bool:
        """Verifica la conexión con Redis."""
        try:
            self.redis_client.ping()
            logger.info("Conexión a Redis establecida correctamente")
            return True
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Error al conectar con Redis: {e}")
            return False
    
    def _get_queue_name(self, queue: str) -> str:
        """Retorna el nombre completo de la cola con prefijo."""
        return f"{self.prefix}:{queue}"
    
    @with_context
    async def enqueue(self, action: DomainAction, queue: str, ctx: Optional[Context] = None) -> str:
        """Encola una Domain Action en la cola especificada.
        
        Args:
            action: La Domain Action a encolar
            queue: Nombre de la cola destino
            ctx: Contexto de la operación
            
        Returns:
            str: ID de la tarea encolada
        """
        task_id = action.task_id if hasattr(action, 'task_id') else str(uuid.uuid4())
        
        # Si la acción no tiene task_id, añadirlo
        if not hasattr(action, 'task_id') or action.task_id is None:
            action.task_id = task_id
        
        # Serializar la acción
        serialized = action.json()
        
        # Información para seguimiento
        queue_name = self._get_queue_name(queue)
        timestamp = datetime.utcnow().isoformat()
        
        # Registrar en log
        logger.info(
            f"Encolando acción: domain={action.domain}, action={action.action}, "
            f"queue={queue_name}, task_id={task_id}"
        )
        
        # Encolar en Redis
        try:
            self.redis_client.rpush(queue_name, serialized)
            
            # Almacenar metadatos para seguimiento
            meta_key = f"{self.prefix}:meta:{task_id}"
            self.redis_client.hset(meta_key, mapping={
                "queue": queue_name,
                "enqueued_at": timestamp,
                "status": "pending",
                "domain": action.domain,
                "action": action.action
            })
            self.redis_client.expire(meta_key, settings.JOB_TIMEOUT)
            
            return task_id
        except Exception as e:
            logger.error(f"Error al encolar acción: {e}")
            raise
    
    @with_context
    async def dequeue(self, queue: str, timeout: int = 5, ctx: Optional[Context] = None) -> Optional[Dict[str, Any]]:
        """Extrae una acción de la cola especificada (blocking).
        
        Args:
            queue: Nombre de la cola origen
            timeout: Tiempo máximo de espera en segundos
            ctx: Contexto de la operación
            
        Returns:
            Optional[Dict[str, Any]]: Contenido de la acción o None si timeout
        """
        queue_name = self._get_queue_name(queue)
        
        try:
            # BLPOP es una operación bloqueante
            result = self.redis_client.blpop([queue_name], timeout)
            if result is None:
                return None
            
            _, serialized = result
            action_dict = json.loads(serialized)
            
            # Actualizar metadatos
            if 'task_id' in action_dict:
                task_id = action_dict['task_id']
                meta_key = f"{self.prefix}:meta:{task_id}"
                self.redis_client.hset(meta_key, "status", "processing")
                self.redis_client.hset(meta_key, "dequeued_at", datetime.utcnow().isoformat())
            
            return action_dict
        except Exception as e:
            logger.error(f"Error al desencolar de {queue_name}: {e}")
            return None
    
    @with_context
    async def dequeue_as_type(self, queue: str, action_type: Type[T], timeout: int = 5, ctx: Optional[Context] = None) -> Optional[T]:
        """Extrae una acción de la cola y la convierte al tipo especificado.
        
        Args:
            queue: Nombre de la cola origen
            action_type: Tipo de DomainAction para convertir el resultado
            timeout: Tiempo máximo de espera en segundos
            ctx: Contexto de la operación
            
        Returns:
            Optional[T]: Instancia de la acción tipada o None
        """
        action_dict = await self.dequeue(queue, timeout, ctx)
        if action_dict is None:
            return None
        
        try:
            return action_type.parse_obj(action_dict)
        except Exception as e:
            logger.error(f"Error al convertir acción a {action_type.__name__}: {e}")
            return None
    
    @with_context
    async def get_queue_length(self, queue: str, ctx: Optional[Context] = None) -> int:
        """Obtiene la longitud actual de una cola.
        
        Args:
            queue: Nombre de la cola
            ctx: Contexto de la operación
            
        Returns:
            int: Número de elementos en la cola
        """
        queue_name = self._get_queue_name(queue)
        try:
            return self.redis_client.llen(queue_name)
        except Exception as e:
            logger.error(f"Error al obtener longitud de cola {queue_name}: {e}")
            return 0
    
    @with_context
    async def get_task_status(self, task_id: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Obtiene el estado actual de una tarea por su ID.
        
        Args:
            task_id: ID de la tarea
            ctx: Contexto de la operación
            
        Returns:
            Dict[str, Any]: Metadatos de la tarea o diccionario vacío
        """
        meta_key = f"{self.prefix}:meta:{task_id}"
        try:
            result = self.redis_client.hgetall(meta_key)
            return result if result else {}
        except Exception as e:
            logger.error(f"Error al obtener estado de tarea {task_id}: {e}")
            return {}
    
    @with_context
    async def set_task_completed(self, task_id: str, result: Optional[Dict[str, Any]] = None, ctx: Optional[Context] = None) -> bool:
        """Marca una tarea como completada.
        
        Args:
            task_id: ID de la tarea
            result: Resultado opcional de la tarea
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se actualizó correctamente
        """
        meta_key = f"{self.prefix}:meta:{task_id}"
        try:
            meta_update = {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat()
            }
            if result:
                meta_update["result"] = json.dumps(result)
            
            self.redis_client.hset(meta_key, mapping=meta_update)
            # Extendemos el TTL para dar tiempo a consultar el resultado
            self.redis_client.expire(meta_key, 3600)  # 1 hora
            return True
        except Exception as e:
            logger.error(f"Error al marcar tarea {task_id} como completada: {e}")
            return False
    
    @with_context
    async def set_task_failed(self, task_id: str, error: str, ctx: Optional[Context] = None) -> bool:
        """Marca una tarea como fallida.
        
        Args:
            task_id: ID de la tarea
            error: Mensaje de error
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se actualizó correctamente
        """
        meta_key = f"{self.prefix}:meta:{task_id}"
        try:
            self.redis_client.hset(meta_key, mapping={
                "status": "failed",
                "error": error,
                "failed_at": datetime.utcnow().isoformat()
            })
            # Extendemos el TTL para dar tiempo a consultar el error
            self.redis_client.expire(meta_key, 3600)  # 1 hora
            return True
        except Exception as e:
            logger.error(f"Error al marcar tarea {task_id} como fallida: {e}")
            return False
    
    @with_context
    async def acquire_lock(self, lock_name: str, timeout: int = 30, ctx: Optional[Context] = None) -> str:
        """Adquiere un lock distribuido con Redis.
        
        Args:
            lock_name: Nombre del lock a adquirir
            timeout: Tiempo de expiración del lock en segundos
            ctx: Contexto de la operación
            
        Returns:
            str: Token del lock o cadena vacía si no se pudo adquirir
        """
        lock_key = f"{self.prefix}:lock:{lock_name}"
        lock_token = str(uuid.uuid4())
        
        # NX garantiza que solo se crea si no existe
        acquired = self.redis_client.set(lock_key, lock_token, ex=timeout, nx=True)
        
        if acquired:
            logger.debug(f"Lock adquirido: {lock_name}, token: {lock_token}")
            return lock_token
        else:
            logger.debug(f"No se pudo adquirir lock: {lock_name}")
            return ""
    
    @with_context
    async def release_lock(self, lock_name: str, lock_token: str, ctx: Optional[Context] = None) -> bool:
        """Libera un lock distribuido.
        
        Args:
            lock_name: Nombre del lock a liberar
            lock_token: Token obtenido al adquirir el lock
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se liberó correctamente
        """
        lock_key = f"{self.prefix}:lock:{lock_name}"
        
        # Verificamos que el token coincida antes de liberar
        pipe = self.redis_client.pipeline()
        try:
            pipe.watch(lock_key)
            current_token = pipe.get(lock_key)
            
            if current_token != lock_token:
                logger.warning(f"Intento de liberar lock con token inválido: {lock_name}")
                pipe.reset()
                return False
            
            pipe.multi()
            pipe.delete(lock_key)
            pipe.execute()
            logger.debug(f"Lock liberado: {lock_name}")
            return True
        except Exception as e:
            logger.error(f"Error al liberar lock {lock_name}: {e}")
            pipe.reset()
            return False


# Instancia global del servicio de colas
queue_service = QueueService()
