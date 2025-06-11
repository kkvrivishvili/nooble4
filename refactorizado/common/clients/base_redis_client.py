import json
import logging
import uuid
from typing import Optional

import redis
from pydantic import ValidationError

from refactorizado.common.db.redis_pool import RedisPool
from refactorizado.common.models.actions import DomainAction, DomainActionResponse
from refactorizado.common.utils.queue_manager import QueueManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseRedisClient:
    """
    Cliente base para la comunicación entre servicios a través de Redis.
    Implementa los patrones de comunicación estándar (asíncrono, pseudo-síncrono)
    y utiliza el QueueManager y los modelos de acción estandarizados.
    """

    def __init__(self, service_name: str, redis_pool: RedisPool):
        """
        Inicializa el cliente.

        Args:
            service_name (str): El nombre del servicio que utiliza este cliente (ej: "orchestrator").
            redis_pool (RedisPool): El pool de conexiones de Redis a utilizar.
        """
        self.service_name = service_name
        self.redis_pool = redis_pool
        self.queue_manager = QueueManager(service_name=self.service_name)

    def _get_connection(self) -> redis.Redis:
        """Obtiene una conexión del pool."""
        return self.redis_pool.get_connection()

    def send_action_async(self, action: DomainAction) -> None:
        """
        Envía una acción de forma asíncrona (fire-and-forget).

        Args:
            action (DomainAction): La acción a enviar.
        """
        try:
            # El servicio de destino se infiere del action_type. Ej: "management.agent.get" -> "management"
            target_service = action.action_type.split('.')[0]
            queue_name = QueueManager.get_service_action_queue(service_name=target_service)
            
            action.origin_service = self.service_name
            
            message = action.model_dump_json()

            with self._get_connection() as conn:
                conn.lpush(queue_name, message)
            
            logger.info(f"Acción asíncrona {action.action_id} ({action.action_type}) enviada a la cola {queue_name}.")

        except (redis.RedisError, ValidationError) as e:
            logger.error(f"Error al enviar acción asíncrona {action.action_id}: {e}")
            raise

    def send_action_pseudo_sync(
        self,
        action: DomainAction,
        timeout: int = 30
    ) -> DomainActionResponse:
        """
        Envía una acción y espera una respuesta de forma pseudo-síncrona.

        Args:
            action (DomainAction): La acción a enviar.
            timeout (int): Tiempo máximo de espera en segundos para la respuesta.

        Returns:
            DomainActionResponse: La respuesta recibida del servicio de destino.
        """
        # Generar un correlation_id si no existe. Es crucial para el patrón síncrono.
        if not action.correlation_id:
            action.correlation_id = uuid.uuid4()
        
        # La cola de respuesta es única para esta solicitud específica.
        # Se construye usando el nombre del servicio que llama (self.service_name) y el correlation_id.
        response_queue = self.queue_manager.get_response_queue(str(action.correlation_id))

        action.callback_queue_name = response_queue
        action.origin_service = self.service_name

        try:
            target_service = action.action_type.split('.')[0]
            action_queue = QueueManager.get_service_action_queue(service_name=target_service)
            
            message = action.model_dump_json()

            with self._get_connection() as conn:
                logger.info(f"Enviando acción pseudo-síncrona {action.action_id} a {action_queue}. Esperando respuesta en {response_queue}.")
                conn.lpush(action_queue, message)
                
                # Bloquear y esperar la respuesta
                response_data = conn.brpop(response_queue, timeout=timeout)

            if response_data is None:
                raise TimeoutError(f"No se recibió respuesta para la acción {action.action_id} en {timeout}s.")

            _, response_message = response_data
            
            response = DomainActionResponse.model_validate_json(response_message)

            logger.info(f"Respuesta recibida para la acción {action.action_id}.")
            
            if response.correlation_id != action.correlation_id:
                logger.warning(f"Mismatch de Correlation ID! Esperado: {action.correlation_id}, Recibido: {response.correlation_id}")

            return response

        except (redis.RedisError, ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Error en el flujo pseudo-síncrono para la acción {action.action_id}: {e}")
            # Aquí se podría construir y devolver un DomainActionResponse de error estandarizado
            raise
        except TimeoutError as e:
            logger.error(str(e))
            raise
