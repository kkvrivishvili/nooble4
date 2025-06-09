"""
Worker mejorado para Domain Actions en Agent Execution Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de callbacks y acciones de ejecución.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con procesamiento directo
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from common.models.execution_context import ExecutionContext
from agent_execution_service.models.actions_model import (
    AgentExecutionAction, ExecutionCallbackAction
)
from agent_execution_service.handlers.execution_handler import AgentExecutionHandler
from agent_execution_service.handlers.context_handler import get_context_handler
from agent_execution_service.handlers.execution_callback_handler import ExecutionCallbackHandler
from agent_execution_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from agent_execution_service.handlers.query_callback_handler import QueryCallbackHandler
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ExecutionWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de ejecución de agentes.
    
    Características:
    - Inicialización asíncrona segura
    - Integración con context handlers
    - Manejo de callbacks específicos
    - Estadísticas detalladas
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
        self.domain = settings.domain_name  # "execution"
        
        # Variables que se inicializarán de forma asíncrona
        self.context_handler = None
        self.execution_callback_handler = None
        self.agent_execution_handler = None
        self.embedding_callback_handler = None
        self.query_callback_handler = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        # Inicializar servicios y handlers necesarios
        # Context handler
        self.context_handler = await get_context_handler(self.redis_client)
        
        # Execution callback handler
        self.execution_callback_handler = ExecutionCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Agent execution handler
        self.agent_execution_handler = AgentExecutionHandler(
            self.context_handler, self.redis_client
        )
        
        # Callback handlers para servicios externos
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        self.query_callback_handler = QueryCallbackHandler()
        
        # Definir las colas adicionales para callbacks
        self.callback_queues = [
            "embedding:callbacks",
            "query:callbacks"
        ]
        
        self.initialized = True
        logger.info("ExecutionWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el método start para monitorear colas adicionales."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Iniciar procesamiento estándar
        await super().start()
    
    async def _process_action_loop(self):
        """Sobrescribe el loop de procesamiento para incluir colas adicionales."""
        self.running = True
        
        # Combinar colas estándar con colas de callback
        action_queues = [
            f"{self.domain}:{tenant_id}:actions" 
            for tenant_id in settings.supported_tenants
        ]
        all_queues = action_queues + self.callback_queues
        
        logger.info(f"Escuchando en colas: {all_queues}")
        
        while self.running:
            try:
                # Escuchar con timeout en todas las colas
                result = await self.redis_client.brpop(all_queues, timeout=5)
                
                if result:
                    queue_name, action_data = result
                    action_dict = json.loads(action_data)
                    
                    # Convertir a objeto de acción
                    action = self.create_action_from_data(action_dict)
                    
                    # Extraer contexto si existe
                    context = None
                    if hasattr(action, 'execution_context') and action.execution_context:
                        context = ExecutionContext(
                            tenant_id=action.tenant_id,
                            tenant_tier=action.tenant_tier if hasattr(action, 'tenant_tier') else "standard",
                            session_id=action.session_id if hasattr(action, 'session_id') else None
                        )
                    
                    # Procesar la acción con el método centralizado
                    await self._handle_action(action, context)
            
            except asyncio.CancelledError:
                logger.info("Procesamiento de acciones cancelado")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error en execution worker: {str(e)}")
                await asyncio.sleep(1)
        
        logger.info("ExecutionWorker: Handlers inicializados")
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Implementa el método abstracto de BaseWorker para manejar acciones específicas
        del dominio de execution.
        
        Args:
            action: La acción a procesar
            context: Contexto opcional de ejecución
            
        Returns:
            Diccionario con el resultado del procesamiento
            
        Raises:
            ValueError: Si no hay handler implementado para ese tipo de acción
        """
        if not self.initialized:
            await self.initialize()
            
        action_type = action.action_type
        
        try:
            if action_type == "execution.agent_run":
                logger.info(f"Procesando ejecución de agente: {action.task_id}")
                return await self._handle_agent_execution(action, context)
            # La funcionalidad de session.closed ha sido eliminada intencionalmente
            # elif action_type == "session.closed":
            #     return await self._handle_session_closed(action, context)
            elif action_type == "embedding.callback":
                logger.info(f"Procesando callback de embedding: {action.task_id}")
                return await self.embedding_callback_handler.handle_embedding_callback(action, context)
            elif action_type == "query.callback":
                logger.info(f"Procesando callback de query: {action.task_id}")
                return await self.query_callback_handler.handle_query_callback(action, context)
            else:
                error_msg = f"No hay handler implementado para la acción: {action_type}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error procesando acción {action_type}: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def _handle_session_closed(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Este método ha sido deshabilitado intencionalmente.
        Se mantiene la firma para compatibilidad con el código existente.
        
        Args:
            action: Acción no procesada
            context: Contexto opcional (no utilizado)
            
        Returns:
            Dict con mensaje indicando que la funcionalidad está deshabilitada
        """
        logger.debug(f"Método _handle_session_closed deshabilitado para sesión {action.session_id if hasattr(action, 'session_id') else 'desconocida'}")
        
        return {
            "success": True,
            "message": "La funcionalidad de cierre de sesión ha sido deshabilitada"
        }
        
    async def _handle_agent_execution(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler específico para ejecución de agentes.
        
        Args:
            action: Acción de ejecución
            context: Contexto de ejecución opcional con metadatos adicionales
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
            
            # Convertir a tipo específico
            agent_action = AgentExecutionAction.parse_obj(action.dict())
            
            # Enriquecer acción con contexto si está disponible
            if context:
                logger.info(f"Procesando acción con tier: {context.tenant_tier}")
                agent_action.tenant_tier = context.tenant_tier
            
            # Procesar ejecución
            result = await self.agent_execution_handler.handle_agent_execution(agent_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_agent_execution: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }

    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "execution.agent_run":
            return AgentRunAction.parse_obj(action_data)
        elif action_type == "execution.callback":
            return ExecutionCallbackAction.parse_obj(action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        try:
            # Validar que haya cola de callback
            if not action.callback_queue:
                logger.warning(f"No se especificó cola de callback para {action.task_id}")
                return
            
            # Crear contexto de ejecución para el callback
            context = ExecutionContext(
                tenant_id=action.tenant_id,
                tenant_tier=action.tenant_tier or "free",  # Asegurar tier por defecto
                session_id=action.session_id
            )
            
            # Determinar tipo de callback según resultado
            if result.get("success", False) and "execution_result" in result:
                # Callback de ejecución exitosa con contexto
                await self.execution_callback_handler.send_success_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    tenant_tier=action.tenant_tier,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    execution_result=result["execution_result"],
                    context=context
                )
            else:
                # Callback de error
                await self.execution_callback_handler.send_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    tenant_tier=action.tenant_tier,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    execution_time=result.get("execution_time")
                )
            
        except Exception as e:
            logger.error(f"Error enviando callback: {str(e)}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_msg: str):
        """
        Envía callback de error para una acción.
        
        Args:
            action_data: Datos originales de la acción
            error_msg: Mensaje de error
        """
        try:
            # Extraer datos mínimos necesarios
            task_id = action_data.get("task_id", "unknown")
            tenant_id = action_data.get("tenant_id", "unknown")
            tenant_tier = action_data.get("tenant_tier", "free")
            session_id = action_data.get("session_id", "unknown")
            callback_queue = action_data.get("callback_queue", "")
            
            if not callback_queue:
                logger.warning(f"No hay cola de callback para error: {task_id}")
                return
            
            # Crear contexto de ejecución para el callback
            context = ExecutionContext(
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id
            )
                
            # Enviar callback de error con contexto
            await self.execution_callback_handler.send_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id,
                callback_queue=callback_queue,
                error_message=error_msg,
                context=context
            )
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # Método auxiliar para estadísticas específicas del execution service
    async def get_execution_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del execution service."""
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
        
        try:
            # Stats de colas
            queue_stats = await self.get_queue_stats()
            
            # Stats de ejecución si están disponibles
            execution_stats = {}
            if self.agent_execution_handler and hasattr(self.agent_execution_handler, 'get_execution_stats'):
                execution_stats = await self.agent_execution_handler.get_execution_stats("all")
            
            # Stats de callbacks
            callback_stats = {}
            if self.execution_callback_handler and hasattr(self.execution_callback_handler, 'get_callback_stats'):
                callback_stats = await self.execution_callback_handler.get_callback_stats("all")
            
            # Añadir estadísticas específicas
            stats.update({
                "queue_stats": queue_stats,
                "execution_stats": execution_stats,
                "callback_stats": callback_stats
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
