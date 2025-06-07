"""
Handler para procesar callbacks del Query Service.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional

from common.models.actions import DomainAction
from query_service.models.actions import QueryCallbackAction
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryCallbackHandler:
    """
    Handler para procesar callbacks del Query Service.
    
    Permite gestionar las respuestas asincrónicas a consultas RAG
    y búsquedas de documentos en el flujo de ejecución del agente.
    """
    
    def __init__(self):
        """Inicializa el handler."""
        # Diccionario para almacenar resultados de callbacks
        self._pending_callbacks = {}
        
        # Eventos para sincronizar espera
        self._callback_events = {}
    
    async def handle_query_callback(self, action: DomainAction) -> Dict[str, Any]:
        """
        Procesa un callback del Query Service.
        
        Args:
            action: Acción de callback con resultado
            
        Returns:
            Dict con resultado del procesamiento
        """
        # Convertir la acción genérica a la específica para mejor validación
        try:
            typed_action = QueryCallbackAction.parse_obj(action.dict())
        except Exception as e:
            logger.error(f"Error convirtiendo acción a QueryCallbackAction: {e}")
            return {"success": False, "error": {"type": "validation_error", "message": str(e)}}
            
        start_time = time.time()
        task_id = typed_action.task_id
        
        try:
            logger.info(f"Procesando callback de Query Service para tarea {task_id}")
            
            # Si hay un future pendiente para este callback, resolverlo
            if task_id in self._pending_callbacks:
                if typed_action.status == "completed":
                    # Guardar resultado
                    self._pending_callbacks[task_id] = typed_action.result
                else:
                    # Guardar error
                    self._pending_callbacks[task_id] = {
                        "error": typed_action.error or {
                            "type": "UnknownError",
                            "message": "Error desconocido en Query Service"
                        }
                    }
                
                # Notificar si hay un evento esperando
                if task_id in self._callback_events:
                    self._callback_events[task_id].set()
            
            return {
                "success": True,
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error procesando callback de query: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "execution_time": time.time() - start_time
            }
    
    async def wait_for_query_result(
        self, 
        task_id: str, 
        timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """
        Espera por el resultado de una consulta RAG.
        
        Args:
            task_id: ID de la tarea
            timeout: Timeout en segundos
            
        Returns:
            Dict con el resultado o None si hay timeout
            
        Raises:
            TimeoutError: Si se excede el timeout
            Exception: Otros errores
        """
        # Inicializar evento para esperar
        if task_id not in self._callback_events:
            self._callback_events[task_id] = asyncio.Event()
        
        # Si ya tenemos resultado, retornarlo inmediatamente
        if task_id in self._pending_callbacks:
            result = self._pending_callbacks.pop(task_id)
            self._callback_events.pop(task_id, None)
            
            # Verificar si es un error
            if "error" in result:
                raise Exception(f"Error en consulta: {result['error'].get('message')}")
                
            return result
        
        # Esperar por el resultado
        try:
            await asyncio.wait_for(self._callback_events[task_id].wait(), timeout)
            
            # Obtener resultado
            result = self._pending_callbacks.pop(task_id, None)
            self._callback_events.pop(task_id, None)
            
            # Verificar si es un error
            if result and "error" in result:
                raise Exception(f"Error en consulta: {result['error'].get('message')}")
                
            return result
        
        except asyncio.TimeoutError:
            # Limpiar
            self._callback_events.pop(task_id, None)
            raise TimeoutError(f"Timeout esperando resultado de consulta para {task_id}")
        
        finally:
            # Asegurar limpieza en caso de otros errores
            if task_id in self._pending_callbacks:
                self._pending_callbacks.pop(task_id)
            if task_id in self._callback_events:
                self._callback_events.pop(task_id)
    
    async def wait_for_search_result(
        self, 
        task_id: str, 
        timeout: float = 15.0
    ) -> Optional[Dict[str, Any]]:
        """
        Espera por el resultado de una búsqueda de documentos.
        
        Args:
            task_id: ID de la tarea
            timeout: Timeout en segundos
            
        Returns:
            Dict con el resultado o None si hay timeout
            
        Raises:
            TimeoutError: Si se excede el timeout
            Exception: Otros errores
        """
        # Reutilizamos la misma lógica que wait_for_query_result
        return await self.wait_for_query_result(task_id, timeout)
