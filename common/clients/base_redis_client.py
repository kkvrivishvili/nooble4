import json
import logging
import uuid
from typing import Optional

import redis.asyncio as redis # Use asyncio version of redis
from pydantic import ValidationError

# Removed direct import of RedisPool class, will expect an initialized client
from common.models.actions import DomainAction, DomainActionResponse
from common.clients.queue_manager import QueueManager
from common.config.base_settings import CommonAppSettings

# logging.basicConfig(level=logging.INFO) #basicConfig is usually called once at app start
logger = logging.getLogger(__name__) # Logger setup is fine

class BaseRedisClient:
    """
    Cliente base para la comunicación entre servicios a través de Redis.
    Implementa los patrones de comunicación estándar (asíncrono, pseudo-síncrono)
    y utiliza el QueueManager y los modelos de acción estandarizados.
    """

    def __init__(self, service_name: str, redis_client: redis.Redis, settings: CommonAppSettings):
        """
        Inicializa el cliente.

        Args:
            service_name (str): El nombre del servicio que utiliza este cliente (ej: "orchestrator").
            redis_client (redis.Redis): Cliente Redis asíncrono ya inicializado.
            settings (CommonAppSettings): Configuración común de la aplicación.
        """
        self.service_name = service_name
        self.redis_client = redis_client # Store the async client
        # Initialize QueueManager with environment from settings. Assuming default prefix "nooble4" is okay.
        self.queue_manager = QueueManager(environment=settings.environment)
        self.settings = settings # Store settings if needed for other parts, e.g. logging

    # _get_connection is no longer needed as we have a direct client

    async def send_action_async(self, action: DomainAction) -> None:
        """
        Envía una acción de forma asíncrona (fire-and-forget).

        Args:
            action (DomainAction): La acción a enviar.
        """
        try:
            # El servicio de destino se infiere del action_type. Ej: "management.agent.get" -> "management"
            target_service = action.action_type.split('.')[0]
            # Use instance method of QueueManager
            queue_name = self.queue_manager.get_action_queue(service_name=target_service)
            
            action.origin_service = self.service_name
            
            message = action.model_dump_json()

            # Use the async client
            await self.redis_client.lpush(queue_name, message)
            
            logger.info(f"Acción asíncrona {action.action_id} ({action.action_type}) enviada a la cola {queue_name}.")

        except (redis.RedisError, ValidationError) as e:
            logger.error(f"Error al enviar acción asíncrona {action.action_id}: {e}")
            raise

    async def send_action_pseudo_sync(
        self,
        action: DomainAction,
        timeout: int = 30  # Default timeout from CommonAppSettings could be used here
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
        response_queue = self.queue_manager.get_response_queue(
            origin_service=self.service_name, 
            action_name=action.action_type, # Use full action_type for better specificity
            correlation_id=str(action.correlation_id)
        )

        action.callback_queue_name = response_queue
        action.origin_service = self.service_name

        try:
            target_service = action.action_type.split('.')[0]
            action_queue = self.queue_manager.get_action_queue(service_name=target_service)
            
            message = action.model_dump_json()

            logger.info(f"Enviando acción pseudo-síncrona {action.action_id} a {action_queue}. Esperando respuesta en {response_queue}.")
            await self.redis_client.lpush(action_queue, message)
            
            # Bloquear y esperar la respuesta con el cliente asíncrono
            response_data = await self.redis_client.brpop(response_queue, timeout=timeout)

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
            # Example: return DomainActionResponse(success=False, error_message=str(e), correlation_id=action.correlation_id, trace_id=action.trace_id)
            raise
        except TimeoutError as e:
            logger.error(str(e))
            # Example: return DomainActionResponse(success=False, error_message=str(e), error_type="TimeoutError", correlation_id=action.correlation_id, trace_id=action.trace_id)
            raise

    async def send_action_async_with_callback(
        self,
        action: DomainAction,
        callback_event_name: str,
        callback_context: Optional[str] = None,
        # callback_action_type: Optional[str] = None, # If DomainAction model supports this
    ) -> None:
        """
        Envía una acción de forma asíncrona y especifica una cola de callback
        para que el servicio de destino envíe una respuesta/notificación.

        Args:
            action (DomainAction): La acción a enviar.
            callback_event_name (str): El nombre del evento para la cola de callback.
            callback_context (Optional[str], optional): Contexto adicional para la cola de callback.
            # callback_action_type (Optional[str], optional): Tipo de acción esperada en el callback.
        """
        try:
            action.callback_queue_name = self.queue_manager.get_callback_queue(
                origin_service=self.service_name, 
                event_name=callback_event_name,
                context=callback_context
            )
            # if callback_action_type and hasattr(action, 'callback_action_type'):
            #     action.callback_action_type = callback_action_type
            
            # El resto es similar a send_action_async
            target_service = action.action_type.split('.')[0]
            queue_name = self.queue_manager.get_action_queue(service_name=target_service)
            
            action.origin_service = self.service_name
            message = action.model_dump_json()

            await self.redis_client.lpush(queue_name, message)
            
            logger.info(f"Acción asíncrona con callback {action.action_id} ({action.action_type}) enviada a {queue_name}. Callback en {action.callback_queue_name}.")

        except (redis.RedisError, ValidationError) as e:
            logger.error(f"Error al enviar acción asíncrona con callback {action.action_id}: {e}")
            raise
