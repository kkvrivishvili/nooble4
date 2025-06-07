"""
Handler para procesar callbacks de embeddings.

# TODO: Oportunidades de mejora futura:
# 1. Implementar limpieza automática de callbacks pendientes no reclamados
# 2. Estandarizar el manejo de errores de validación con errores específicos
# 3. Considerar usar caché con TTL en lugar de dict simple para evitar memory leaks
# 4. Extraer un BaseCallbackHandler para compartir lógica con otros handlers de callback
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional

from common.models.actions import DomainAction
from embedding_service.models.actions import EmbeddingCallbackAction
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingCallbackHandler:
    """
    Handler para procesar callbacks del servicio de embeddings.
    
    Maneja los resultados asincrónicos de las solicitudes de embeddings
    y los integra en el flujo de consulta RAG.
    """
    
    def __init__(self):
        """Inicializa el handler."""
        # Diccionario para almacenar resultados de callbacks
        self._pending_callbacks = {}
        
        # Eventos para sincronizar espera
        self._callback_events = {}
    
    async def handle_embedding_callback(self, action: DomainAction) -> Dict[str, Any]:
        """
        Procesa un callback de embedding.
        
        Args:
            action: Acción de callback con embeddings
            
        Returns:
            Dict con resultado del procesamiento
        """
        # Convertir la acción genérica a la específica para mejor validación
        try:
            typed_action = EmbeddingCallbackAction.parse_obj(action.dict())
        except Exception as e:
            logger.error(f"Error convirtiendo acción a EmbeddingCallbackAction: {e}")
            return {"success": False, "error": {"type": "validation_error", "message": str(e)}}
        start_time = time.time()
        task_id = typed_action.task_id
        
        try:
            logger.info(f"Procesando callback de embedding para tarea {task_id}")
            
            # Si hay un future pendiente para este callback, resolverlo
            if task_id in self._pending_callbacks:
                if typed_action.status == "completed":
                    # Extraer datos relevantes del callback usando los campos tipados
                    result = {
                        "embeddings": typed_action.embeddings,
                        "model": typed_action.model,
                        "dimensions": typed_action.dimensions,
                        "total_tokens": typed_action.total_tokens,
                        "processing_time": typed_action.processing_time
                    }
                    
                    # Guardar resultado
                    self._pending_callbacks[task_id] = result
                elif typed_action.status == "error":
                    # Extraer datos del error
                    error_info = typed_action.error or {}
                    error_message = error_info.get("message", "Error desconocido")
                    error_type = error_info.get("type", "embedding_error")
                    
                    # Guardar error
                    self._pending_callbacks[task_id] = {
                        "error": {
                            "type": error_type,
                            "message": error_message
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
