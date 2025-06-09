"""
Handler para procesar callbacks de embeddings.

Maneja los callbacks recibidos desde el servicio de embeddings
e integra los resultados en el flujo de ejecución de agentes.

# TODO: Oportunidades de mejora futura:
# 1. Implementar cleanup periódico para evitar memory leaks en _pending_callbacks
# 2. Usar validación de modelo específico (EmbeddingCallbackAction) de forma consistente
# 3. Compartir lógica común con QueryCallbackHandler usando un BaseCallbackHandler
# 4. Mejorar el manejo de timeouts y reintentos para sincronización de eventos
"""

import logging
from typing import Dict, Any, Optional

from common.models.execution_context import ExecutionContext
import time
import json
import asyncio

from common.models.actions import DomainAction
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingCallbackHandler:
    """
    Handler para procesar callbacks de embeddings.
    
    Integra los resultados de embeddings en el flujo de ejecución
    de agentes o en el almacenamiento según corresponda.
    """
    
    def __init__(self):
        """Inicializa el handler."""
        # Aquí se inicializarían servicios necesarios
        self._pending_callbacks = {}
        self._callback_events = {}
    
    async def handle_embedding_callback(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Procesa un callback de embedding.
        
        Args:
            action: Acción de callback con embeddings
            context: Contexto de ejecución (opcional)
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando callback de embedding para tarea {task_id}")
            
            # Si hay un future pendiente para este callback, resolverlo
            if task_id in self._pending_callbacks:
                if action.status == "completed":
                    # Extraer datos relevantes del callback
                    result = {
                        "embeddings": action.result.get("embeddings", []),
                        "model": action.result.get("model", ""),
                        "dimensions": action.result.get("dimensions", 0),
                        "total_tokens": action.result.get("total_tokens", 0),
                        "processing_time": action.result.get("processing_time", 0.0)
                    }
                    
                    # Guardar resultado
                    self._pending_callbacks[task_id] = result
                else:
                    # Guardar error
                    self._pending_callbacks[task_id] = {
                        "error": action.result.get("error", {
                            "type": "UnknownError",
                            "message": "Error desconocido en servicio de embeddings"
                        })
                    }
                
                # Notificar si hay un evento esperando
                if task_id in self._callback_events:
                    self._callback_events[task_id].set()
            
            # Aquí podrían implementarse flujos adicionales según el contexto
            # Por ejemplo, almacenar embeddings en caché o base de datos
            
            return {
                "success": True,
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error procesando callback de embedding: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "execution_time": time.time() - start_time
            }
    
    async def wait_for_embedding_result(
        self, 
        task_id: str, 
        timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """
        Espera por el resultado de un embedding.
        
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
                raise Exception(f"Error en embedding: {result['error'].get('message')}")
                
            return result
        
        # Esperar por el resultado
        try:
            await asyncio.wait_for(self._callback_events[task_id].wait(), timeout)
            
            # Obtener resultado
            result = self._pending_callbacks.pop(task_id, None)
            self._callback_events.pop(task_id, None)
            
            # Verificar si es un error
            if result and "error" in result:
                raise Exception(f"Error en embedding: {result['error'].get('message')}")
                
            return result
        
        except asyncio.TimeoutError:
            # Limpiar
            self._callback_events.pop(task_id, None)
            raise TimeoutError(f"Timeout esperando embedding para {task_id}")
        
        finally:
            # Asegurar limpieza en caso de otros errores
            if task_id in self._pending_callbacks:
                self._pending_callbacks.pop(task_id)
            if task_id in self._callback_events:
                self._callback_events.pop(task_id)
