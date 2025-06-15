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

    VERSIÓN: 8.0 - Alineado con el estándar de arquitectura v4.0.
    """

    def __init__(self, app_settings: CommonAppSettings, async_redis_conn: redis_async.Redis):
        if not app_settings:
            raise ValueError("La configuración de la aplicación (app_settings) es obligatoria.")
        if not app_settings.service_name:
            raise ValueError("El nombre del servicio (app_settings.service_name) es obligatorio.")
        if async_redis_conn is None:
            raise ValueError("La conexión Redis asíncrona (async_redis_conn) es obligatoria.")

        self.app_settings = app_settings
        self.service_name = app_settings.service_name
        self.async_redis_conn = async_redis_conn
        
        self.queue_manager = QueueManager(service_name=self.service_name)
        self.action_queue_name = self.queue_manager.get_service_action_queue()

        self.redis_client = BaseRedisClient(
            app_settings=self.app_settings,
            redis_conn=self.async_redis_conn,
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

    async def initialize(self):
        """
        Método de inicialización base. Los workers hijos deben sobreescribirlo para
        inicializar sus componentes (como la capa de servicio) y luego llamar a
        `await super().initialize()`.
        """
        self.initialized = True
        logger.info(f"[{self.service_name}] BaseWorker inicializado.")

    async def _process_action_loop(self):
        """Bucle principal que escucha y procesa acciones de la cola Redis."""
        logger.info(f"[{self.service_name}] Worker iniciando. Escuchando en cola: {self.action_queue_name}")
        
        if not self.initialized:
            await self.initialize()

        self._running = True
        while self._running:
            try:
                message_data = await self.async_redis_conn.brpop(self.action_queue_name, timeout=1)

                if message_data is None:
                    await asyncio.sleep(0.01)
                    continue

                _, message_json = message_data
                action = DomainAction.model_validate_json(message_json)
                logger.info(f"[{self.service_name}] Acción recibida: {action.action_id} ({action.action_type})", extra=action.get_log_extra())

                try:
                    handler_result = await self._handle_action(action)

                    if handler_result is None:
                        continue # Acción fire-and-forget completada

                    is_pseudo_sync = action.callback_queue_name and not action.callback_action_type
                    is_async_callback = action.callback_queue_name and action.callback_action_type

                    if is_pseudo_sync:
                        response = self._create_success_response(action, handler_result)
                        await self._send_response(response)
                    elif is_async_callback:
                        await self._send_callback(action, handler_result)

                except Exception as e:
                    logger.error(f"[{self.service_name}] Error en handler para '{action.action_type}': {e}", extra=action.get_log_extra())
                    traceback.print_exc()
                    if action.callback_queue_name:
                        error_code = "HANDLER_EXECUTION_ERROR"
                        error_response = self._create_error_response(action, str(e), error_code)
                        await self._send_response(error_response)
            
            except ValidationError as e:
                logger.error(f"[{self.service_name}] Error de validación de DomainAction: {e}. Mensaje: {message_json}")
                # No se puede enviar respuesta de error si la acción no es válida,
                # ya que podríamos no tener un callback_queue_name.
            
            except redis_async.RedisError as e:
                logger.error(f"[{self.service_name}] Error de conexión con Redis: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.critical(f"[{self.service_name}] Error crítico en el bucle del worker: {e}")
                self._running = False

        logger.info(f"[{self.service_name}] Worker detenido.")

    def _create_success_response(self, action: DomainAction, data: Optional[Dict[str, Any]]) -> DomainActionResponse:
        """Crea una DomainActionResponse de éxito."""
        return DomainActionResponse(
            action_id=str(uuid.uuid4()),
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            task_id=action.task_id,
            origin_service=self.service_name,
            success=True,
            data=data,
            error=None,
            callback_queue_name=action.callback_queue_name
        )

    def _create_error_response(self, action: DomainAction, error_message: str, error_code: str) -> DomainActionResponse:
        """Crea una DomainActionResponse de error."""
        return DomainActionResponse(
            action_id=str(uuid.uuid4()),
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            task_id=action.task_id,
            origin_service=self.service_name,
            success=False,
            data=None,
            error=ErrorDetail(code=error_code, message=error_message),
            callback_queue_name=action.callback_queue_name
        )

    async def _send_response(self, response: DomainActionResponse):
        """Envía una DomainActionResponse a su cola de callback."""
        if not response.callback_queue_name:
            logger.warning(f"[{self.service_name}] Se intentó enviar respuesta para {response.correlation_id} sin callback_queue_name.")
            return

        try:
            await self.async_redis_conn.lpush(response.callback_queue_name, response.model_dump_json())
            logger.info(f"[{self.service_name}] Respuesta {response.action_id} para {response.correlation_id} enviada a {response.callback_queue_name}.", extra=response.get_log_extra())
        except redis_async.RedisError as e:
            logger.error(f"[{self.service_name}] Error de Redis al enviar respuesta a {response.callback_queue_name}: {e}", extra=response.get_log_extra())

    async def _send_callback(self, original_action: DomainAction, callback_data: Dict[str, Any]):
        """Crea y envía un nuevo DomainAction como callback."""
        callback_action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type=original_action.callback_action_type,
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
