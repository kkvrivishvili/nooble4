import asyncio
import importlib
import logging
import traceback
import uuid
from typing import Optional, Type, Dict, Any

from pydantic import BaseModel

import redis
from pydantic import ValidationError

from refactorizado.common.redis_pool import RedisPool
from refactorizado.common.handlers.base_handler import BaseHandler
from refactorizado.common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from refactorizado.common.utils.queue_manager import QueueManager

logger = logging.getLogger(__name__)


class HandlerNotFoundError(Exception):
    """Excepción para cuando no se encuentra un handler para un action_type."""
    pass


class BaseWorker:
    """
    Worker genérico que procesa acciones de Redis de forma dinámica.

    Descubre, instancia y ejecuta el handler apropiado para cada `DomainAction`
    basándose en una convención de nombres y estructura de carpetas.

    VERSIÓN: 6.0 - Refactorizado para descubrimiento dinámico de handlers.
    """

    def __init__(self, service_name: str, redis_pool: RedisPool, handler_base_package_path: str):
        if not service_name:
            raise ValueError("El nombre del servicio (service_name) es obligatorio.")
        if redis_pool is None:
            raise ValueError("El pool de Redis (redis_pool) es obligatorio.")
        if not handler_base_package_path:
            raise ValueError("La ruta base del paquete de handlers (handler_base_package_path) es obligatoria.")

        self.service_name = service_name
        self.redis_pool = redis_pool
        self.handler_base_package_path = handler_base_package_path
        self.queue_manager = QueueManager(service_name=self.service_name)
        self.action_queue_name = self.queue_manager.get_service_action_queue()

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

            logger.debug(f"Intentando importar handler: {full_module_to_import}.{class_name_camel}")
            handler_module = importlib.import_module(full_module_to_import)
            handler_class = getattr(handler_module, class_name_camel)
            return handler_class
        except (ImportError, AttributeError) as e:
            raise HandlerNotFoundError(
                f"No se pudo encontrar o cargar el handler para action_type='{action_type}'. "
                f"Detalle: {e}"
            )

    async def _get_handler_instance(self, action: DomainAction) -> BaseHandler:
        """Obtiene una instancia inicializada del handler para una acción."""
        handler_class = self._get_handler_class(action.action_type)
        handler_instance = handler_class(action=action, redis_pool=self.redis_pool, service_name=self.service_name)
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
        """Bucle principal que escucha y procesa acciones de la cola Redis."""
        logger.info(f"[{self.service_name}] Worker iniciando. Escuchando en cola: {self.action_queue_name}")
        self._running = True

        while self._running:
            try:
                with self.redis_pool.get_connection() as conn:
                    message_data = conn.brpop(self.action_queue_name, timeout=1)

                if message_data is None:
                    await asyncio.sleep(0.01)
                    continue

                _, message_json = message_data
                action = None
                try:
                    action = DomainAction.model_validate_json(message_json)
                    logger.info(f"[{self.service_name}] Acción recibida: {action.action_id} ({action.action_type})", extra=action.get_log_extra())

                    response = await self._handle_action(action)

                    if response and action.callback_queue_name:
                        self._send_response(response)
                    
                except ValidationError as e:
                    logger.error(f"[{self.service_name}] Error de validación de DomainAction: {e}. Mensaje: {message_json}")
                    if action and action.callback_queue_name:
                        error_response = self._create_error_response(action, f"Error de validación: {e}", "VALIDATION_ERROR")
                        self._send_response(error_response)
                
                except Exception as e:
                    logger.error(f"[{self.service_name}] Error inesperado procesando acción {getattr(action, 'action_id', 'N/A')}: {e}", extra=getattr(action, 'get_log_extra', lambda: {})())
                    traceback.print_exc()
                    if action and action.callback_queue_name:
                        error_response = self._create_error_response(action, f"Error interno del worker: {e}", "WORKER_EXECUTION_ERROR")
                        self._send_response(error_response)

            except redis.ConnectionError as e:
                logger.error(f"[{self.service_name}] Error de conexión con Redis: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.critical(f"[{self.service_name}] Error crítico en el bucle del worker: {e}")
                self._running = False

        logger.info(f"[{self.service_name}] Worker detenido.")

    def _send_response(self, response: DomainActionResponse):
        """Envía una DomainActionResponse a su cola de callback correspondiente."""
        if not response.callback_queue_name:
            logger.warning(f"[{self.service_name}] Se intentó enviar respuesta para {response.correlation_id} sin callback_queue_name.")
            return

        try:
            with self.redis_pool.get_connection() as conn:
                conn.lpush(response.callback_queue_name, response.model_dump_json())
            logger.info(f"[{self.service_name}] Respuesta {response.action_id} para {response.correlation_id} enviada a {response.callback_queue_name}.", extra=response.get_log_extra())
        except redis.RedisError as e:
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
