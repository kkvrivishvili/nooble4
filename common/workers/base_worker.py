import asyncio
import logging
import traceback
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from pydantic import ValidationError
import redis.asyncio as redis_async

from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from common.clients.queue_manager import QueueManager
from common.config import CommonAppSettings
from common.clients import BaseRedisClient

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """
    Worker base abstracto (Arquitectura v4.0).

    Este worker actúa como un componente de infraestructura. Su responsabilidad es
    escuchar en una cola de Redis, recibir y deserializar acciones (`DomainAction`),
    y delegar el procesamiento a una capa de servicio a través del método abstracto
    `_handle_action`.

    También gestiona el ciclo de vida de la respuesta, enviando `DomainActionResponse`
    para comunicaciones pseudo-síncronas o nuevos `DomainAction` para callbacks asíncronos.

    VERSIÓN: 4.x - Alineado con el estándar de arquitectura v4.0.
    """

    def __init__(self, app_settings: CommonAppSettings, async_redis_conn: redis_async.Redis, consumer_id_suffix: Optional[str] = None):
        if not app_settings:
            raise ValueError("La configuración de la aplicación (app_settings) es obligatoria.")
        if not app_settings.service_name:
            raise ValueError("El nombre del servicio (app_settings.service_name) es obligatorio.")
        if async_redis_conn is None:
            raise ValueError("La conexión Redis asíncrona (async_redis_conn) es obligatoria.")

        self.app_settings = app_settings
        self.service_name = app_settings.service_name
        self.async_redis_conn = async_redis_conn
        
        # Corregir inicialización de QueueManager y usar settings para environment
        self.queue_manager = QueueManager(environment=self.app_settings.environment)
        self.action_stream_name = self.queue_manager.get_service_action_stream(self.service_name) # MODIFIED: stream name

        # Nombres para el grupo de consumidores y el consumidor
        self.consumer_group_name = f"{self.service_name}-group"
        worker_unique_id = consumer_id_suffix or str(uuid.uuid4()).split('-')[-1] # Corto UUID si no hay sufijo
        self.consumer_name = f"{self.service_name}-worker-{worker_unique_id}"

        # self.redis_client es una instancia de BaseRedisClient, disponible para que las subclases
        # puedan enviar acciones a otros servicios si es necesario.
        self.redis_client = BaseRedisClient(
            service_name=self.service_name, # Pasar el nombre del servicio actual
            redis_client=self.async_redis_conn,
            settings=self.app_settings
        )

        self._running = False
        self.initialized = False
        self._worker_task: Optional[asyncio.Task] = None

    @abstractmethod
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction delegando a la capa de servicio.

        Este es el método abstracto que cada worker hijo DEBE implementar. Actúa como
        un enrutador que llama a la lógica de negocio apropiada basada en `action.action_type`.

        Args:
            action: La `DomainAction` recibida.

        Returns:
            - Un `dict` con los datos de resultado si la acción requiere una respuesta o un callback.
            - `None` para acciones "fire-and-forget" que no generan respuesta.

        Raises:
            Exception: Si ocurre un error durante el procesamiento. La excepción será
                       capturada por el bucle principal del worker, que se encargará de
                       registrar el error y enviar una respuesta de error si corresponde.
        """
        pass

    async def _ensure_consumer_group_exists(self):
        """Asegura que el grupo de consumidores exista en el stream, creándolo si es necesario."""
        try:
            # MKSTREAM crea el stream si no existe
            await self.async_redis_conn.xgroup_create(
                name=self.action_stream_name,
                groupname=self.consumer_group_name,
                id='0',  # Empezar desde el principio del stream si se crea nuevo
                mkstream=True
            )
            logger.info(f"[{self.service_name}] Grupo de consumidores '{self.consumer_group_name}' creado/verificado para el stream '{self.action_stream_name}'.")
        except redis_async.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"[{self.service_name}] Grupo de consumidores '{self.consumer_group_name}' ya existe para el stream '{self.action_stream_name}'.")
            else:
                logger.error(f"[{self.service_name}] Error al crear/verificar grupo de consumidores '{self.consumer_group_name}': {e}")
                raise # Re-lanzar si es un error inesperado

    async def initialize(self):
        """
        Método de inicialización base. Los workers hijos deben sobreescribirlo para
        inicializar sus componentes (como la capa de servicio) y luego llamar a
        `await super().initialize()`.
        """
        await self._ensure_consumer_group_exists() # MODIFIED: Asegurar grupo antes de inicializar
        self.initialized = True
        logger.info(f"[{self.service_name}] BaseWorker ({self.consumer_name}) inicializado. Escuchando en stream '{self.action_stream_name}', grupo '{self.consumer_group_name}'.")

    async def _process_action_loop(self):
        """Bucle principal que escucha y procesa acciones del stream Redis usando un grupo de consumidores."""
        # El logger de inicialización ya está en el método initialize.
        # logger.info(f"[{self.service_name}] Worker ({self.consumer_name}) iniciando. Escuchando en stream: {self.action_stream_name}, grupo: {self.consumer_group_name}")
        
        if not self.initialized:
            await self.initialize() # Esto ahora también llama a _ensure_consumer_group_exists

        self._running = True
        message_id_to_ack = None # Para asegurar el ACK incluso si hay error post-procesamiento

        while self._running:
            action = None # Asegurar que action está definida para el logging en caso de error temprano
            try:
                # Leer hasta 1 mensaje, bloquear por 1000ms (1 segundo)
                # '>' significa solo nuevos mensajes no aún entregados a ningún consumidor en este grupo
                stream_messages = await self.async_redis_conn.xreadgroup(
                    groupname=self.consumer_group_name,
                    consumername=self.consumer_name,
                    streams={self.action_stream_name: '>'},
                    count=1,
                    block=1000  # Milliseconds
                )

                if not stream_messages: # Timeout, no message received
                    await asyncio.sleep(0.01) # Opcional, para no hacer busy-loop tan agresivo
                    continue

                # stream_messages = [ (b'stream_name', [ (b'message_id_1', {b'field_1': b'value_1'}), ... ]) ]
                _stream_key_name, message_list = stream_messages[0]
                if not message_list:
                    continue
                
                message_id_bytes, message_payload_dict = message_list[0]
                message_id_to_ack = message_id_bytes.decode('utf-8')

                message_json_bytes = message_payload_dict.get(b'data')
                if message_json_bytes is None:
                    logger.error(f"[{self.service_name}][{self.consumer_name}] Mensaje {message_id_to_ack} del stream {self.action_stream_name} no tiene campo 'data'. Descartando y ACK.")
                    await self.async_redis_conn.xack(self.action_stream_name, self.consumer_group_name, message_id_to_ack)
                    message_id_to_ack = None
                    continue
                
                message_json = message_json_bytes.decode('utf-8')
                action = DomainAction.model_validate_json(message_json)
                logger.info(f"[{self.service_name}][{self.consumer_name}] Acción {action.action_id} ({action.action_type}) recibida del stream (MsgID: {message_id_to_ack})", extra=action.get_log_extra())

                try:
                    handler_result = await self._handle_action(action)

                    # Procesamiento de respuesta/callback se mantiene igual
                    if handler_result is None and not action.callback_queue_name:
                        logger.debug(f"[{self.service_name}][{self.consumer_name}] Acción fire-and-forget {action.action_id} completada.")
                        # No hay más que hacer para fire-and-forget, se hará ACK abajo
                    else:
                        is_pseudo_sync = action.callback_queue_name and not action.callback_action_type
                        is_async_callback = action.callback_queue_name and action.callback_action_type

                        if is_pseudo_sync:
                            if action.correlation_id is None:
                                logger.error(f"[{self.service_name}][{self.consumer_name}] Error crítico: Acción {action.action_id} ({action.action_type}) requiere respuesta pseudo-síncrona pero no tiene correlation_id. No se enviará respuesta.")
                                raise ValueError(f"Acción {action.action_id} ({action.action_type}) requiere respuesta pseudo-síncrona pero no tiene correlation_id.")
                            response = self._create_success_response(action, handler_result or {})
                            await self._send_response(response, action.callback_queue_name)
                        elif is_async_callback:
                            await self._send_callback(action, handler_result or {})
                        # Si handler_result no es None pero no es ni pseudo-sync ni async_callback, es un fire-and-forget que devolvió algo. Se hace ACK.

                    # Si todo fue bien, ACK el mensaje
                    await self.async_redis_conn.xack(self.action_stream_name, self.consumer_group_name, message_id_to_ack)
                    logger.debug(f"[{self.service_name}][{self.consumer_name}] Mensaje {message_id_to_ack} ACKed.")
                    message_id_to_ack = None # Reseteado después de ACK exitoso

                except Exception as e:
                    # Error durante _handle_action o envío de respuesta/callback
                    # NO HACER ACK. El mensaje permanecerá en PEL para ser reprocesado o reclamado.
                    logger.error(f"[{self.service_name}][{self.consumer_name}] Error en handler para '{action.action_type}' (MsgID: {message_id_to_ack}): {e}", extra=action.get_log_extra() if action else None)
                    traceback.print_exc()
                    if action and action.callback_queue_name: # Solo intentar enviar error si es posible
                        error_code = "HANDLER_EXECUTION_ERROR"
                        error_response = self._create_error_response(action, str(e), error_code)
                        # Solo enviar respuesta de error si hay una cola de callback definida para respuestas pseudo-síncronas
                        if action.callback_queue_name and not action.callback_action_type: # Es pseudo-síncrono
                            if action.correlation_id is None:
                                logger.error(f"[{self.service_name}][{self.consumer_name}] Error crítico al intentar enviar respuesta de error: Acción {action.action_id} ({action.action_type}) requiere respuesta pseudo-síncrona pero no tiene correlation_id. No se enviará respuesta de error.")
                                # La excepción original 'e' ya está en curso y causará que el mensaje no sea ACKed.
                                # No es necesario levantar otra excepción aquí, solo evitar el intento de _send_response.
                            else:
                                await self._send_response(error_response, action.callback_queue_name)
                        else:
                            logger.warning(f"[{self.service_name}][{self.consumer_name}] No se envió respuesta de error para {action.action_id} ({action.action_type}) porque no es pseudo-síncrona o no tiene callback_queue_name.")
                    # No ACK aquí. message_id_to_ack no se resetea.
            
            except ValidationError as e:
                logger.error(f"[{self.service_name}][{self.consumer_name}] Error de validación de DomainAction (MsgID: {message_id_to_ack}): {e}. Mensaje original: {message_json_bytes.decode('utf-8') if message_json_bytes else 'N/A'}")
                if message_id_to_ack: # Si tenemos un ID, ACK para no reprocesar mensaje malformado
                    await self.async_redis_conn.xack(self.action_stream_name, self.consumer_group_name, message_id_to_ack)
                    logger.warning(f"[{self.service_name}][{self.consumer_name}] Mensaje malformado {message_id_to_ack} ACKed para evitar bucle.")
                    message_id_to_ack = None
            
            except redis_async.RedisError as e:
                # Errores de Redis como conexión perdida durante XREADGROUP o XACK
                logger.error(f"[{self.service_name}][{self.consumer_name}] Error de conexión con Redis (MsgID: {message_id_to_ack}): {e}. Reintentando en 5s...")
                await asyncio.sleep(5) # El mensaje (si se leyó) no será ACKed y debería ser reprocesado
            
            except Exception as e:
                logger.critical(f"[{self.service_name}][{self.consumer_name}] Error crítico en el bucle del worker (MsgID: {message_id_to_ack}): {e}")
                traceback.print_exc()
                self._running = False # Detener el worker en caso de error muy grave

        logger.info(f"[{self.service_name}][{self.consumer_name}] Worker detenido.")

    def _create_success_response(self, action: DomainAction, data: Optional[Dict[str, Any]]) -> DomainActionResponse:
        """Crea una DomainActionResponse de éxito."""
        return DomainActionResponse(
            action_id=uuid.uuid4(),
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            task_id=action.task_id,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            success=True,
            data=data,
            error=None
        )

    def _create_error_response(self, action: DomainAction, error_message: str, error_code: str) -> DomainActionResponse:
        """Crea una DomainActionResponse de error.
        Nota: error_type se establece en "ProcessingError" como un valor genérico.
        Los workers específicos pueden necesitar crear objetos ErrorDetail más detallados si es necesario.
        """
        """Crea una DomainActionResponse de error."""
        return DomainActionResponse(
            action_id=uuid.uuid4(),
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            task_id=action.task_id,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            success=False,
            data=None,
            error=ErrorDetail(error_type="ProcessingError", error_code=error_code, message=error_message)
        )

    async def _send_response(self, response: DomainActionResponse, target_queue_name: str):
        """Envía una DomainActionResponse a su cola de callback."""
        if not target_queue_name:
            logger.warning(f"[{self.service_name}] Se intentó enviar respuesta para {response.correlation_id} (Acción: {response.action_id}) sin target_queue_name.")
            return

        log_extra = {
            "action_id": str(response.action_id),
            "correlation_id": str(response.correlation_id),
            "task_id": str(response.task_id),
            "tenant_id": response.tenant_id,
            "session_id": response.session_id,
            "target_queue": target_queue_name
        }

        try:
            await self.async_redis_conn.lpush(target_queue_name, response.model_dump_json())
            logger.info(f"[{self.service_name}] Respuesta {response.action_id} para {response.correlation_id} enviada a {target_queue_name}.", extra=log_extra)
        except redis_async.RedisError as e:
            logger.error(f"[{self.service_name}] Error de Redis al enviar respuesta a {target_queue_name}: {e}", extra=log_extra)

    async def _send_callback(self, original_action: DomainAction, callback_data: Dict[str, Any]):
        """Crea y envía un nuevo DomainAction como callback."""
        callback_action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=original_action.callback_action_type,
            tenant_id=original_action.tenant_id, # Campo requerido
            task_id=original_action.task_id,
            correlation_id=original_action.correlation_id,
            trace_id=original_action.trace_id,
            session_id=original_action.session_id,
            origin_service=self.service_name,
            data=callback_data,
            # Los callbacks no suelen tener callbacks a su vez.
            callback_queue_name=None,
            callback_action_type=None
        )
        try:
            await self.async_redis_conn.lpush(original_action.callback_queue_name, callback_action.model_dump_json())
            logger.info(f"[{self.service_name}] Callback {callback_action.action_id} ({callback_action.action_type}) enviado a {original_action.callback_queue_name}.", extra=callback_action.get_log_extra())
        except redis_async.RedisError as e:
            logger.error(f"[{self.service_name}] Error de Redis al enviar callback a {original_action.callback_queue_name}: {e}", extra=callback_action.get_log_extra())

    async def run(self):
        """Inicia el worker y su bucle de procesamiento."""
        self._worker_task = asyncio.create_task(self._process_action_loop())
        await self._worker_task

    async def start(self):
        """Método de conveniencia para iniciar el worker."""
        if not self._running:
            logger.info(f"[{self.service_name}] Iniciando worker...")
            self._worker_task = asyncio.create_task(self.run())

    async def stop(self):
        """Detiene el worker de forma segura."""
        if self._running:
            logger.info(f"[{self.service_name}] Deteniendo worker...")
            self._running = False
            if self._worker_task:
                try:
                    await asyncio.wait_for(self._worker_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"[{self.service_name}] El worker no se detuvo a tiempo, forzando cancelación.")
                    self._worker_task.cancel()
                except asyncio.CancelledError:
                    pass # La tarea fue cancelada, es normal.
            logger.info(f"[{self.service_name}] Worker detenido completamente.")
