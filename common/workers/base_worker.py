import asyncio
import importlib
import logging
import traceback
import uuid
from typing import Optional, Type, Dict, Any

from pydantic import BaseModel

import redis.asyncio as redis_async # Cambiado a redis.asyncio
from pydantic import ValidationError

# from refactorizado.common.redis_pool import RedisPool # Eliminado, se usará conexión async directa
from common.handlers.base_handler import BaseHandler # Ancestro común
from common.handlers.base_context_handler import BaseContextHandler # Para isinstance
from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from common.utils.queue_manager import QueueManager
from common.config import CommonAppSettings # Para el constructor
from common.clients import BaseRedisClient # Para el constructor y uso

logger = logging.getLogger(__name__)


class HandlerNotFoundError(Exception):
    """Excepción para cuando no se encuentra un handler para un action_type."""
    pass


class BaseWorker:
    """
    Worker genérico que procesa acciones de Redis de forma dinámica.

    Descubre, instancia y ejecuta el handler apropiado para cada `DomainAction`
    basándose en una convención de nombres y estructura de carpetas.

    VERSIÓN: 7.0 - Refactorizado para Redis asíncrono y nueva instanciación de handlers.
    """

    def __init__(self, app_settings: CommonAppSettings, async_redis_conn: redis_async.Redis, handler_base_package_path: str):
        if not app_settings:
            raise ValueError("La configuración de la aplicación (app_settings) es obligatoria.")
        if not app_settings.service_name:
            raise ValueError("El nombre del servicio (app_settings.service_name) es obligatorio.")
        if async_redis_conn is None:
            raise ValueError("La conexión Redis asíncrona (async_redis_conn) es obligatoria.")
        if not handler_base_package_path:
            raise ValueError("La ruta base del paquete de handlers (handler_base_package_path) es obligatoria.")

        self.app_settings = app_settings
        self.service_name = app_settings.service_name # Tomado de app_settings
        self.async_redis_conn = async_redis_conn # Conexión Redis asíncrona 'cruda'
        self.handler_base_package_path = handler_base_package_path
        
        # QueueManager ahora podría tomar app_settings si necesita más config, o solo service_name
        self.queue_manager = QueueManager(service_name=self.service_name)
        self.action_queue_name = self.queue_manager.get_service_action_queue()

        # Crear el BaseRedisClient para los handlers
        self.redis_client = BaseRedisClient(
            app_settings=self.app_settings,
            redis_conn=self.async_redis_conn, # BaseRedisClient usa la conexión 'cruda'
            # service_name es tomado de app_settings dentro de BaseRedisClient
        )

        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def _get_handler_class(self, action_type: str) -> Type[BaseHandler]:
        """Descubre y carga dinámicamente la clase del handler basada en el action_type."""
        try:
            parts = action_type.split('.')
            handler_name_snake = parts[-1] + "_handler"
            class_name_camel = "".join(part.capitalize() for part in parts[-1].split('_')) + "Handler"
            
            module_subpath_parts = parts[:-1] + [handler_name_snake]
            module_relative_path = ".".join(module_subpath_parts)
            
            full_module_to_import = f"{self.handler_base_package_path}.{module_relative_path}"

            logger.debug(f"[{self.service_name}] Intentando importar handler: {full_module_to_import}.{class_name_camel}")
            handler_module = importlib.import_module(full_module_to_import)
            handler_class = getattr(handler_module, class_name_camel)
            return handler_class
        except (ImportError, AttributeError) as e:
            logger.error(f"[{self.service_name}] No se pudo encontrar o cargar el handler para action_type='{action_type}'. Detalle: {e}")
            raise HandlerNotFoundError(
                f"No se pudo encontrar o cargar el handler para action_type='{action_type}'. "
                f"Detalle: {e}"
            )

    async def _get_handler_instance(self, action: DomainAction) -> BaseHandler:
        """Obtiene una instancia inicializada del handler para una acción."""
        handler_class = self._get_handler_class(action.action_type)
        
        handler_args = {
            "action": action,
            "app_settings": self.app_settings,
            "redis_client": self.redis_client
            # service_name es parte de app_settings y BaseActionHandler lo usa desde allí.
            # El logger también se configura en BaseActionHandler usando app_settings.
        }

        if issubclass(handler_class, BaseContextHandler):
            handler_args["context_redis_client"] = self.async_redis_conn
        
        # No se necesita un caso especial para BaseCallbackHandler ya que sus necesidades
        # son cubiertas por los argumentos de BaseActionHandler.

        # El kwarg 'service_name' ya no se pasa directamente a BaseActionHandler si usa app_settings.
        # Si BaseHandler (el ancestro más antiguo) lo necesitara explícitamente y no lo toma de app_settings,
        # se podría añadir aquí, pero BaseActionHandler ya maneja service_name y logger desde app_settings.
        handler_instance = handler_class(**handler_args)
        
        # El método initialize puede necesitar acceso a app_settings o redis_client si realiza
        # operaciones asíncronas o de configuración que ahora dependen de estos.
        # Por ahora, asumimos que initialize() no necesita cambios o los tomará de self.
        await handler_instance.initialize() 
        return handler_instance

    async def _handle_action(self, action: DomainAction) -> Optional[DomainActionResponse]:
        """Orquesta el ciclo de vida completo de la ejecución de una acción."""
        try:
            handler = await self._get_handler_instance(action)
            response_model = await handler.execute()  # Ahora devuelve Optional[BaseModel]
            return self._create_success_response(action, response_model)

        
        except HandlerNotFoundError as e:
            logger.error(f"[{self.service_name}] {e}", extra=action.get_log_extra())
            return self._create_error_response(action, str(e), "HANDLER_NOT_FOUND")
        
        except ValidationError as e:
            logger.error(f"[{self.service_name}] Error de validación de payload para '{action.action_type}': {e}", extra=action.get_log_extra())
            return self._create_error_response(action, f"Payload inválido: {e}", "INVALID_PAYLOAD")
        
        except Exception as e:
            logger.error(f"[{self.service_name}] Error inesperado en handler para '{action.action_type}': {e}", extra=action.get_log_extra())
            traceback.print_exc()
            return self._create_error_response(action, f"Error interno del handler: {e}", "HANDLER_EXECUTION_ERROR")

    async def _process_action_loop(self):
        """Bucle principal que escucha y procesa acciones de la cola Redis de forma asíncrona."""
        logger.info(f"[{self.service_name}] Worker iniciando. Escuchando en cola: {self.action_queue_name}")
        self._running = True

        while self._running:
            try:
                # Usar la conexión Redis asíncrona para brpop
                message_data = await self.async_redis_conn.brpop(self.action_queue_name, timeout=1)

                if message_data is None:
                    # No es necesario un sleep aquí si brpop tiene timeout, pero un pequeño sleep puede ser útil
                    # para ceder control en caso de que el bucle esté muy activo sin mensajes.
                    await asyncio.sleep(0.01) 
                    continue

                _, message_json = message_data
                action = None
                try:
                    action = DomainAction.model_validate_json(message_json)
                    logger.info(f"[{self.service_name}] Acción recibida: {action.action_id} ({action.action_type})", extra=action.get_log_extra())

                    response = await self._handle_action(action)

                    if response and action.callback_queue_name:
                        await self._send_response(response) # _send_response ahora es async
                    
                except ValidationError as e:
                    logger.error(f"[{self.service_name}] Error de validación de DomainAction: {e}. Mensaje: {message_json}")
                    if action and action.callback_queue_name:
                        error_response = self._create_error_response(action, f"Error de validación: {e}", "VALIDATION_ERROR")
                        await self._send_response(error_response) # _send_response ahora es async
                
                except Exception as e:
                    logger.error(f"[{self.service_name}] Error inesperado procesando acción {getattr(action, 'action_id', 'N/A')}: {e}", extra=getattr(action, 'get_log_extra', lambda: {})())
                    traceback.print_exc()
                    if action and action.callback_queue_name:
                        error_response = self._create_error_response(action, f"Error interno del worker: {e}", "WORKER_EXECUTION_ERROR")
                        await self._send_response(error_response) # _send_response ahora es async

            except redis_async.RedisError as e: # Capturar excepciones de Redis asíncrono
                logger.error(f"[{self.service_name}] Error de conexión con Redis: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.critical(f"[{self.service_name}] Error crítico en el bucle del worker: {e}")
                self._running = False # Considerar si detenerse o intentar recuperarse

        logger.info(f"[{self.service_name}] Worker detenido.")

    async def _send_response(self, response: DomainActionResponse):
        """Envía una DomainActionResponse a su cola de callback correspondiente de forma asíncrona."""
        if not response.callback_queue_name:
            logger.warning(f"[{self.service_name}] Se intentó enviar respuesta para {response.correlation_id} sin callback_queue_name.")
            return

        try:
            # Usar la conexión Redis asíncrona para lpush
            await self.async_redis_conn.lpush(response.callback_queue_name, response.model_dump_json())
            logger.info(f"[{self.service_name}] Respuesta {response.action_id} para {response.correlation_id} enviada a {response.callback_queue_name}.", extra=response.get_log_extra())
        except redis_async.RedisError as e: # Capturar excepciones de Redis asíncrono
            logger.error(f"[{self.service_name}] Error de Redis al enviar respuesta {response.action_id} a {response.callback_queue_name}: {e}", extra=response.get_log_extra())

    def _create_success_response(self, original_action: DomainAction, response_model: Optional[BaseModel]) -> DomainActionResponse:
        """Crea una DomainActionResponse estandarizada para éxito."""
        payload_dict: Optional[Dict[str, Any]] = None
        if response_model is not None:
            payload_dict = response_model.model_dump(mode='json')

        return DomainActionResponse(
            action_id=str(uuid.uuid4()),
            correlation_id=original_action.correlation_id,
            task_id=original_action.task_id,
            trace_id=original_action.trace_id,
            callback_queue_name=original_action.callback_queue_name,
            action_type_response_to=original_action.action_type,
            success=True,
            data=payload_dict
        )

    def _create_error_response(self, original_action: DomainAction, error_message: str, error_code: str) -> DomainActionResponse:
        """Crea una DomainActionResponse estandarizada para errores."""
        return DomainActionResponse(
            action_id=str(uuid.uuid4()),
            correlation_id=original_action.correlation_id,
            task_id=original_action.task_id,
            trace_id=original_action.trace_id,
            callback_queue_name=original_action.callback_queue_name,
            action_type_response_to=original_action.action_type,
            success=False,
            error=ErrorDetail(message=error_message, code=error_code)
        )

    async def start(self):
        """Inicia el worker en una tarea de fondo."""
        if self._running:
            logger.warning(f"[{self.service_name}] El worker ya está en ejecución.")
            return
        self._worker_task = asyncio.create_task(self._process_action_loop())

    async def stop(self):
        """Detiene el worker de forma segura."""
        if not self._running or not self._worker_task:
            logger.warning(f"[{self.service_name}] El worker no está en ejecución.")
            return

        logger.info(f"[{self.service_name}] Deteniendo worker...")
        self._running = False
        try:
            # Esperar a que la tarea del worker termine limpiamente
            await asyncio.wait_for(self._worker_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(f"[{self.service_name}] El worker no se detuvo a tiempo, forzando cancelación.")
            self._worker_task.cancel()
        except asyncio.CancelledError:
            pass # La cancelación es esperada
        logger.info(f"[{self.service_name}] El worker se ha detenido completamente.")
