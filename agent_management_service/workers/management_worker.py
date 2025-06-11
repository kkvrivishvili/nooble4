"""
Worker mejorado para Agent Management Service.

Implementación estandarizada con inicialización asíncrona y
manejo de validación de agentes y cache.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con procesamiento directo
"""

import logging
from typing import Dict, Any

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from agent_management_service.models.actions_model import (
    AgentValidationAction, CacheInvalidationAction, GetAgentConfigAction, 
    UpdateAgentConfigAction, DeleteAgentConfigAction, CollectionIngestionStatusAction
)
from agent_management_service.services.agent_service import AgentService
import time # For execution_time
from agent_management_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ManagementWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de gestión de agentes.
    
    Características:
    - Inicialización asíncrona segura
    - Validación de configuración de agentes
    - Invalidación de cache
    """
    
    def __init__(self, redis_client, queue_manager=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            queue_manager: Gestor de colas por dominio (opcional)
        """
        queue_manager = queue_manager or DomainQueueManager(redis_client)
        super().__init__(redis_client, queue_manager)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "management"
        
        # Control de inicialización
        self.initialized = False
        self.agent_service: Optional[AgentService] = None
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
        
        # Ya no registramos handlers sino que procesamos directamente
        # las acciones en el método _process_action
        self.agent_service = AgentService(redis_client=self.redis_client)
        self.initialized = True
        logger.info("ManagementWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()

    async def _send_pseudo_sync_response(self, action: DomainAction, handler_result: Dict[str, Any]):
        response = DomainActionResponse(
            success=handler_result.get("success", False),
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            data=handler_result.get("data") if handler_result.get("success", False) else None,
            error=ErrorDetail(message=str(handler_result.get("error", {}).get("message", "Unknown error")), code=str(handler_result.get("error", {}).get("type"))) if not handler_result.get("success", False) else None
        )
        
        try:
            action_suffix = action.action_type.split('.', 1)[1]
            callback_queue = f"{self.domain}:responses:{action_suffix}:{action.correlation_id}"
        except IndexError:
            logger.error(f"Could not determine action_suffix for action_type: {action.action_type}. Cannot send response.")
            callback_queue = None

        if callback_queue and action.callback_queue_name:
            await self.redis_client.rpush(callback_queue, response.json())
            logger.info(f"Sent pseudo-sync response for {action.action_type} to {callback_queue}")
        else:
            logger.info(f"Action {action.action_type} completed but no response sent (likely fire-and-forget).")

    async def _send_pseudo_sync_error_response(self, action: DomainAction, error_message: str, error_code: Optional[str] = None):
        error_response = DomainActionResponse(
            success=False,
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            error=ErrorDetail(message=error_message, code=error_code)
        )
        try:
            action_suffix = action.action_type.split('.', 1)[1]
            callback_queue = f"{self.domain}:responses:{action_suffix}:{action.correlation_id}"
        except IndexError:
            logger.error(f"Could not determine action_suffix for action_type: {action.action_type}. Cannot send error response.")
            callback_queue = None

        if callback_queue and action.callback_queue_name:
            await self.redis_client.rpush(callback_queue, error_response.json())
            logger.info(f"Sent pseudo-sync error response for {action.action_type} to {callback_queue}")
        else:
            logger.warning(f"No callback_queue could be determined for pseudo-sync error action {action.action_type}, error response not sent.")
    
    # Ya no es necesario sobrescribir _process_queue_loop
    # porque BaseWorker ahora proporciona la implementación correcta
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """Crea objeto de acción apropiado según los datos."""
        action_type = action_data.get("action_type")
        
        if action_type == "management.validate_agent":
            return AgentValidationAction.parse_obj(action_data)
        elif action_type == "management.invalidate_cache":
            return CacheInvalidationAction.parse_obj(action_data)
        elif action_type == "management.get_agent_config":
            return GetAgentConfigAction.parse_obj(action_data)
        elif action_type == "management.update_agent_config":
            return UpdateAgentConfigAction.parse_obj(action_data)
        elif action_type == "management.delete_agent_config":
            return DeleteAgentConfigAction.parse_obj(action_data)
        elif action_type == "management.collection_ingestion_status":
            return CollectionIngestionStatusAction.parse_obj(action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
    # Ya no necesitamos sobrescribir _process_action ya que ahora
    # implementamos _handle_action en su lugar
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Optional[Dict[str, Any]]:
        """
        Implementa el método abstracto de BaseWorker para manejar acciones específicas
        del dominio de management.
        """
        action_type = action.action_type
        handler_map = {
            "management.validate_agent": self._handle_agent_validation,
            "management.invalidate_cache": self._handle_cache_invalidation,
            "management.get_agent_config": self._handle_get_agent_config,
            "management.update_agent_config": self._handle_update_agent_config,
            "management.delete_agent_config": self._handle_delete_agent_config,
            "management.collection_ingestion_status": self._handle_collection_ingestion_status,
        }

        handler = handler_map.get(action_type)

        if not handler:
            error_msg = f"No hay handler implementado para la acción: {action_type}"
            logger.warning(error_msg)
            if action.callback_queue_name:
                await self._send_pseudo_sync_error_response(action, error_msg, "UNHANDLED_ACTION")
            return None

        try:
            handler_result = await handler(action, context)
            if handler_result:
                await self._send_pseudo_sync_response(action, handler_result)
            return None  # Stop further processing by BaseWorker
        except Exception as e:
            error_message = f"Exception in ManagementWorker._handle_action for {action_type}: {str(e)}"
            logger.error(error_message, exc_info=True)
            if action.callback_queue_name:
                await self._send_pseudo_sync_error_response(action, str(e), "HANDLER_EXCEPTION")
            return None
    
    async def _handle_agent_validation(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler para validación de agentes.
        
        Args:
            action: Acción de validación
            context: Contexto de ejecución opcional con metadatos adicionales
            
        Returns:
            Resultado de la validación
        """
        try:
            # Ya no necesitamos verificar inicialización aquí
            validation_action = AgentValidationAction.parse_obj(action.dict())
            
            # Enriquecer acción con contexto si está disponible
            if context:
                logger.info(f"Validando agente con tier: {context.tenant_tier}")
                validation_action.tenant_tier = context.tenant_tier
                
            # TODO: Implementar lógica de validación
            logger.info(f"Validando configuración de agente: {validation_action.task_id}")
            
            return {
                "success": True,
                "message": "Validación completada",
                "valid": True
            }
            
        except Exception as e:
            logger.error(f"Error en validación de agente: {str(e)}")
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
    
    async def _handle_cache_invalidation(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler para invalidación de cache.
        
        Args:
            action: Acción de invalidación
            context: Contexto de ejecución opcional con metadatos adicionales
            
        Returns:
            Resultado de la invalidación
        """
        try:
            # Ya no necesitamos verificar inicialización aquí
            cache_action = CacheInvalidationAction.parse_obj(action.dict())
            
            # Enriquecer acción con contexto si está disponible
            if context:
                logger.info(f"Invalidando cache con tier: {context.tenant_tier}")
                cache_action.tenant_tier = context.tenant_tier
            
            # TODO: Implementar lógica de invalidación
            logger.info(f"Invalidando cache para agente: {cache_action.agent_id}")
            
            return {
                "success": True,
                "message": "Cache invalidado exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error invalidando cache: {str(e)}")
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
    
    async def _handle_update_agent_config(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """Handler para actualizar la configuración de un agente."""
        start_time = time.time()
        try:
            update_action = UpdateAgentConfigAction.parse_obj(action.dict())
            
            updated_agent = await self.agent_service.update_agent_config(
                agent_id=update_action.data.agent_id,
                tenant_id=update_action.data.tenant_id,
                update_data=update_action.data.update_data
            )

            if updated_agent:
                return {
                    "success": True,
                    "data": updated_agent.dict(),
                    "execution_time": time.time() - start_time
                }
            else:
                return {
                    "success": False,
                    "error": {"type": "NotFound", "message": f"Agent {update_action.data.agent_id} not found"},
                    "execution_time": time.time() - start_time
                }
        except Exception as e:
            logger.error(f"Error en _handle_update_agent_config: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)},
                "execution_time": time.time() - start_time
            }

    async def _handle_delete_agent_config(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """Handler para eliminar la configuración de un agente."""
        start_time = time.time()
        try:
            delete_action = DeleteAgentConfigAction.parse_obj(action.dict())

            success = await self.agent_service.delete_agent_config(
                agent_id=delete_action.data.agent_id,
                tenant_id=delete_action.data.tenant_id
            )

            if success:
                return {
                    "success": True,
                    "data": {"message": f"Agent {delete_action.data.agent_id} deleted successfully."},
                    "execution_time": time.time() - start_time
                }
            else:
                return {
                    "success": False,
                    "error": {"type": "NotFound", "message": f"Agent {delete_action.data.agent_id} not found"},
                    "execution_time": time.time() - start_time
                }
        except Exception as e:
            logger.error(f"Error en _handle_delete_agent_config: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)},
                "execution_time": time.time() - start_time
            }

    async def _handle_collection_ingestion_status(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> None:
        """Handler for collection ingestion status notifications from IngestionService."""
        logger.info(f"Received collection ingestion status update: {action.data}")
        try:
            status_action = CollectionIngestionStatusAction.parse_obj(action.dict())
            
            # This is a fire-and-forget action, so we just log and call the service.
            # The service method will handle the business logic (e.g., update DB, cache).
            await self.agent_service.update_collection_status(
                collection_id=status_action.data.collection_id,
                tenant_id=status_action.data.tenant_id,
                status=status_action.data.status,
                message=status_action.data.message
            )
            logger.info(f"Successfully processed ingestion status for collection {status_action.data.collection_id}")

        except Exception as e:
            # For fire-and-forget, we just log the error and move on.
            # No client is waiting for a response.
            logger.error(f"Error processing collection ingestion status: {str(e)}", exc_info=True)
        
        # Return None because this is a fire-and-forget action.
        return None

    async def _handle_get_agent_config(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler para obtener la configuración de un agente.
        
        Args:
            action: Acción de obtener configuración (GetAgentConfigAction)
            context: Contexto de ejecución opcional
            
        Returns:
            Resultado con la configuración del agente o error
        """
        start_time = time.time()
        try:
            if not self.initialized or not self.agent_service:
                logger.error("AgentService no inicializado en ManagementWorker.")
                return {
                    "success": False,
                    "error": {"type": "WorkerNotInitialized", "message": "AgentService not available."},
                    "execution_time": time.time() - start_time
                }

            # Type hint for clarity, create_action_from_data should ensure this type
            get_config_action: GetAgentConfigAction = action 

            agent = await self.agent_service.get_agent(
                agent_id=get_config_action.data.agent_id, 
                tenant_id=get_config_action.data.tenant_id
            )
            
            if agent:
                return {
                    "success": True,
                    "data": agent.dict(), # Return the full agent model as data
                    "execution_time": time.time() - start_time
                }
            else:
                return {
                    "success": False,
                    "error": {"type": "NotFound", "message": f"Agent {get_config_action.data.agent_id} not found for tenant {get_config_action.data.tenant_id}"},
                    "execution_time": time.time() - start_time
                }

        except Exception as e:
            logger.error(f"Error en _handle_get_agent_config: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)},
                "execution_time": time.time() - start_time
            }

    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        En Management Service, normalmente no se envían callbacks
        pero se mantiene la implementación por compatibilidad.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        # Para management service, usualmente no necesitamos enviar callbacks
        # pero si fuera necesario, debemos crearlo con ExecutionContext
        if action.callback_queue and result.get("success"):
            logger.debug(f"Callback disponible para {action.task_id} pero no implementado")
            # Si implementáramos callbacks, se haría así:
            # context = ExecutionContext(
            #     tenant_id=action.tenant_id,
            #     tenant_tier=action.tenant_tier,
            #     session_id=action.session_id
            # )
            # await self.queue_manager.enqueue_execution(
            #     action=callback_action,
            #     target_domain=action.callback_queue.split(".")[0],
            #     context=context
            # )
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        logger.error(f"Error en worker de management: {error_message}")
        
        # Si fuera necesario implementar callbacks de error:
        callback_queue = action_data.get("callback_queue")
        if callback_queue:
            logger.debug(f"Callback de error disponible pero no implementado: {error_message}")
    
    # Método auxiliar para estadísticas específicas del management service
    async def get_management_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del management service."""
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        try:
            # Stats de colas
            queue_stats = await self.get_queue_stats()
            stats["queue_stats"] = queue_stats
            
            # Estadísticas específicas del servicio
            # (se podrían implementar métricas adicionales)
            stats["validation_info"] = {
                "tier_limits": {
                    "free": {"max_agents": 3, "max_tools": 5},
                    "pro": {"max_agents": 10, "max_tools": 15},
                    "enterprise": {"max_agents": -1, "max_tools": -1}  # ilimitado
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
