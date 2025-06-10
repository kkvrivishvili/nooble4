# Propuesta de Estandarización: El `BaseWorker`

## 1. Objetivo

Este documento define el estándar para los **Workers** en el ecosistema Nooble4. El `BaseWorker` es un componente fundamental y reutilizable dentro de cada microservicio. Su única responsabilidad es actuar como el motor de procesamiento de mensajes: escuchar las colas de acciones de Redis, gestionar el ciclo de vida de los mensajes y delegar la lógica de negocio a los `Handlers` específicos.

La estandarización del worker simplifica drásticamente el desarrollo de nuevos servicios, garantiza un manejo de errores consistente y se integra de forma nativa con la librería `common.communication`.

## 2. Principios de Diseño

*   **Responsabilidad Única**: El worker solo se ocupa de la infraestructura de mensajería (recibir, deserializar, despachar, responder), no de la lógica de negocio.
*   **Basado en Handlers**: El worker utiliza un sistema de registro (`handler_registry`) para mapear un [action_type](cci:1://file:///d:/VSCODE/nooble4/common/communication/payloads.py:41:4-46:16) a su [BaseActionHandler](cci:2://file:///d:/VSCODE/nooble4/common/communication/handler.py:16:0-166:47) correspondiente.
*   **Integración Nativa**: Utiliza [DomainAction](cci:2://file:///d:/VSCODE/nooble4/common/communication/payloads.py:18:0-46:16), [DomainActionResponse](cci:2://file:///d:/VSCODE/nooble4/common/communication/payloads.py:48:0-74:16), y [BaseActionHandler](cci:2://file:///d:/VSCODE/nooble4/common/communication/handler.py:16:0-166:47) de la librería `common.communication`.
*   **Manejo de Patrones de Comunicación**: El worker debe soportar de forma transparente los tres patrones de comunicación definidos:
    1.  Pseudo-Síncrono (RPC sobre Redis).
    2.  Asíncrono Fire-and-Forget.
    3.  Asíncrono con Callback.
*   **Robustez**: Incluye manejo de errores centralizado para fallos de deserialización, handlers no encontrados y excepciones durante el procesamiento.

## 3. Estructura y Lógica del `BaseWorker`

A continuación se presenta la estructura propuesta para una clase `BaseWorker` que se podría incluir en la librería `common.communication`.

```python
# En: common/communication/worker.py (Propuesta de nueva ubicación)

import logging
import json
import redis
from typing import Dict, Type, Optional

from .payloads import DomainAction, DomainActionResponse
from .handler import BaseActionHandler
from .client import BaseRedisClient # Para enviar respuestas/callbacks

logger = logging.getLogger(__name__)

class BaseWorker:
    def __init__(self, redis_connection: redis.Redis, service_name: str):
        self.redis_connection = redis_connection
        self.service_name = service_name
        self.listen_queues = [] # Las colas a escuchar, ej: ['nooble4:dev:management:actions']
        self.handler_registry: Dict[str, BaseActionHandler] = {}
        # El worker necesita un cliente para enviar respuestas y callbacks
        self.redis_client = BaseRedisClient(redis_connection, origin_service_name=service_name)
        self._running = False

    def register_handler(self, action_type: str, handler_class: Type[BaseActionHandler]):
        """
        Registra una clase de handler para un action_type específico.
        El worker inyectará el redis_client al handler al instanciarlo.
        """
        if action_type in self.handler_registry:
            logger.warning(f"Handler for action_type '{action_type}' is being overridden.")
        # Instanciamos el handler, proveyendo el cliente Redis para que pueda enviar callbacks
        self.handler_registry[action_type] = handler_class(redis_client=self.redis_client)
        logger.info(f"Handler {handler_class.__name__} registered for action_type '{action_type}'.")

    def set_listen_queues(self, queues: list):
        """Establece las colas que el worker debe escuchar."""
        self.listen_queues = queues
        logger.info(f"Worker will listen on queues: {self.listen_queues}")

    def run(self):
        """Inicia el bucle principal del worker para escuchar y procesar mensajes."""
        if not self.listen_queues:
            logger.error("Cannot run worker: no listen queues have been set.")
            return
        if not self.handler_registry:
            logger.warning("Worker is running with no registered handlers.")

        self._running = True
        logger.info(f"Worker '{self.service_name}' started. Listening on {self.listen_queues}...")
        while self._running:
            try:
                # blpop es una operación de bloqueo que espera por mensajes en las colas
                queue_name_bytes, message_bytes = self.redis_connection.blpop(self.listen_queues)
                queue_name = queue_name_bytes.decode('utf-8')
                logger.debug(f"Received message from queue: {queue_name}")
                self._process_message(message_bytes)
            except redis.exceptions.RedisError as e:
                logger.exception("Redis error in worker loop. Reconnecting might be needed.")
                # Aquí se podría añadir lógica de reconexión
            except Exception as e:
                logger.exception(f"Unexpected error in worker loop: {e}")

    def stop(self):
        """Detiene el bucle del worker de forma segura."""
        self._running = False

    def _process_message(self, message_bytes: bytes):
        try:
            message_dict = json.loads(message_bytes.decode('utf-8'))
            action = DomainAction.model_validate(message_dict)
        except (json.JSONDecodeError, Exception) as e:
            logger.exception(f"Failed to parse message into DomainAction. Message content: {message_bytes[:500]}")
            # Aquí se podría mover el mensaje a una Dead Letter Queue (DLQ)
            return

        handler = self.handler_registry.get(action.action_type)
        if not handler:
            logger.error(f"No handler registered for action_type '{action.action_type}'. Discarding action {action.action_id}.")
            # También podría enviarse una respuesta de error si es un llamado síncrono
            return

        logger.info(f"Processing action {action.action_id} ({action.action_type}) with handler {type(handler).__name__}.")
        
        try:
            # El handler procesa la acción y devuelve una respuesta estándar
            # NOTA: Asumiendo que process_action es síncrono para este ejemplo. En un entorno real, sería async.
            parsed_data = handler._parse_action_data(action, handler.__orig_bases__[0].__args__[0])
            response = handler.process_action(action, parsed_data) 

            # Si la acción original tenía un `callback_queue_name`, es un llamado pseudo-síncrono
            # y debemos enviar la respuesta de vuelta.
            if action.callback_queue_name and isinstance(response, DomainActionResponse):
                self._send_response(action.callback_queue_name, response)

        except Exception as e:
            logger.exception(f"Handler {type(handler).__name__} failed to process action {action.action_id}.")
            # Si falla, y es síncrono, enviar una respuesta de error
            if action.callback_queue_name:
                error_response = handler.create_error_response(
                    original_action=action,
                    error_code="HANDLER_EXECUTION_FAILED",
                    message=str(e)
                )
                self._send_response(action.callback_queue_name, error_response)

    def _send_response(self, response_queue: str, response: DomainActionResponse):
        """Envía la respuesta a la cola de respuesta especificada."""
        try:
            logger.debug(f"Sending response for correlation_id {response.correlation_id} to queue {response_queue}")
            self.redis_client.redis.rpush(response_queue, response.model_dump_json())
        except Exception as e:
            logger.exception(f"Failed to send response to queue {response_queue}")
