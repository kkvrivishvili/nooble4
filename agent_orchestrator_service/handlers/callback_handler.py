"""
Callback Handler - Procesamiento de callbacks desde Agent Execution Service.

Este módulo maneja:
- Callbacks de ejecución completada
- Callbacks de errores
- Envío de respuestas via WebSocket
- Tracking de performance
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

import redis.asyncio as redis_async # Importar redis.asyncio

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from agent_orchestrator_service.models.actions_model import ExecutionCallbackAction
from agent_orchestrator_service.models.websocket_model import WebSocketMessage, WebSocketMessageType
from agent_orchestrator_service.services.websocket_manager import WebSocketManager
# from agent_orchestrator_service.config.settings import get_settings # settings ya no se usa directamente aquí

logger = logging.getLogger(__name__)
# settings = get_settings() # settings se obtendrá de app_settings si es necesario, o no se usará.


class CallbackHandler:
    """
    Maneja callbacks desde servicios de ejecución.
    """

    def __init__(self, websocket_manager: WebSocketManager, async_redis_conn: Optional[redis_async.Redis] = None):
        """
        Inicializa handler.

        Args:
            websocket_manager: Manager de conexiones WebSocket
            async_redis_conn: Conexión Redis asíncrona para tracking (opcional)
        """
        self.websocket_manager = websocket_manager
        self.async_redis_conn = async_redis_conn # Renombrado para claridad y tipo

    async def handle_execution_callback(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Procesa callback de ejecución de agente.

        Args:
            action: Callback action desde Agent Execution Service
            context: Contexto de ejecución (opcional)

        Returns:
            Resultado del procesamiento
        """
        start_time = datetime.utcnow()

        try:
            callback = ExecutionCallbackAction.parse_obj(action.dict())
            logger.info(f"Procesando callback de ejecución: task_id={callback.task_id}, status={callback.status}")

            if callback.status == "completed":
                await self._handle_successful_execution(callback)
            elif callback.status == "failed":
                await self._handle_failed_execution(callback)
            else:
                logger.warning(f"Estado de callback desconocido: {callback.status}")
                await self._handle_unknown_status(callback)

            await self._track_callback_performance(callback, start_time)

            return {
                "success": True,
                "callback_processed": True,
                "task_id": callback.task_id
            }

        except Exception as e:
            logger.error(f"Error procesando callback: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }

    async def _handle_successful_execution(self, callback: ExecutionCallbackAction):
        """Maneja ejecución exitosa."""
        result = callback.result
        response_text = result.get("response", "")
        sources = result.get("sources", [])
        agent_info = result.get("agent_info", {})

        ws_message = WebSocketMessage(
            type=WebSocketMessageType.AGENT_RESPONSE,
            data={
                "response": response_text,
                "sources": sources,
                "agent_info": agent_info,
                "task_id": callback.task_id,
                "status": "completed",
                "metadata": {
                    "processing_time": callback.execution_time,
                    "tokens_used": callback.tokens_used,
                    "model_used": agent_info.get("model_used")
                }
            },
            task_id=callback.task_id,
            session_id=callback.session_id,
            tenant_id=callback.tenant_id,
            tenant_tier=callback.tenant_tier
        )

        sent = await self.websocket_manager.send_to_session(
            session_id=callback.session_id,
            message=ws_message
        )

        if sent:
            logger.info(f"Respuesta enviada via WebSocket: session={callback.session_id}, task={callback.task_id}")
        else:
            logger.warning(f"No se pudo enviar WebSocket: session={callback.session_id} no encontrada")

    async def _handle_failed_execution(self, callback: ExecutionCallbackAction):
        """Maneja ejecución fallida."""
        error_info = callback.result.get("error", {})
        error_message = error_info.get("message", "Error desconocido en ejecución")
        error_type = error_info.get("type", "ExecutionError")

        ws_message = WebSocketMessage(
            type=WebSocketMessageType.ERROR,
            data={
                "error": error_message,
                "error_type": error_type,
                "task_id": callback.task_id,
                "status": "failed",
                "metadata": {
                    "processing_time": callback.execution_time,
                    "error_details": error_info
                }
            },
            task_id=callback.task_id,
            session_id=callback.session_id,
            tenant_id=callback.tenant_id,
            tenant_tier=callback.tenant_tier
        )

        await self.websocket_manager.send_to_session(
            session_id=callback.session_id,
            message=ws_message
        )
        logger.error(f"Error en ejecución enviado: session={callback.session_id}, error={error_message}")

    async def _handle_unknown_status(self, callback: ExecutionCallbackAction):
        """Maneja estados desconocidos."""
        ws_message = WebSocketMessage(
            type=WebSocketMessageType.ERROR,
            data={
                "error": f"Estado de ejecución desconocido: {callback.status}",
                "task_id": callback.task_id,
                "status": callback.status
            },
            task_id=callback.task_id,
            session_id=callback.session_id,
            tenant_id=callback.tenant_id,
            tenant_tier=callback.tenant_tier
        )

        await self.websocket_manager.send_to_session(
            session_id=callback.session_id,
            message=ws_message
        )

    async def _track_callback_performance(self, callback: ExecutionCallbackAction, start_time: datetime):
        """Registra métricas de performance del callback."""
        if not self.async_redis_conn:
            return

        try:
            # callback_processing_time = (datetime.utcnow() - start_time).total_seconds() # No se usa actualmente
            tenant_metrics_key = f"callback_metrics:{callback.tenant_id}:{datetime.now().date().isoformat()}"

            await self.async_redis_conn.hincrby(tenant_metrics_key, "total_callbacks", 1)
            await self.async_redis_conn.hincrby(tenant_metrics_key, f"status_{callback.status}", 1)

            if callback.execution_time:
                # Usar una clave unificada para los tiempos de ejecución
                execution_time_key = f"callback_metrics:{callback.tenant_id}:execution_times_ms"
                await self.async_redis_conn.lpush(execution_time_key, int(callback.execution_time * 1000)) # Guardar en ms como entero
                await self.async_redis_conn.ltrim(execution_time_key, 0, 999) # Mantener últimos 1000 tiempos
                await self.async_redis_conn.expire(execution_time_key, 604800) # 7 días

            await self.async_redis_conn.expire(tenant_metrics_key, 604800) # 7 días para las métricas diarias

        except redis_async.RedisError as e: # Ser específico con la excepción de Redis
            logger.error(f"Redis error tracking callback performance: {str(e)}")
        except Exception as e:
            logger.error(f"Error tracking callback performance: {str(e)}")

    async def get_callback_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de callbacks para un tenant."""

        if not self.async_redis_conn:
            return {"metrics": "disabled"}

        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"callback_metrics:{tenant_id}:{today}"

            # hgetall devuelve un diccionario de bytes a bytes
            metrics_bytes = await self.async_redis_conn.hgetall(metrics_key)
            # Decodificar a str para facilitar el uso, asumiendo UTF-8
            metrics = {k.decode('utf-8'): v.decode('utf-8') for k, v in metrics_bytes.items()}

            return {
                "date": today,
                "total_callbacks": int(metrics.get("total_callbacks", 0)),
                "completed": int(metrics.get("status_completed", 0)),
                "failed": int(metrics.get("status_failed", 0)),
                "success_rate": self._calculate_success_rate(metrics) # Pasar el dict decodificado
            }

        except redis_async.RedisError as e: # Ser específico con la excepción de Redis
            logger.error(f"Redis error obteniendo stats de callback: {str(e)}")
            return {"error": str(e), "type": "RedisError"}
        except Exception as e:
            logger.error(f"Error obteniendo stats de callback: {str(e)}")
            return {"error": str(e)}

    def _calculate_success_rate(self, metrics: Dict[str, str]) -> float: # Métricas ahora son str:str
        """Calcula tasa de éxito."""
        total = int(metrics.get("total_callbacks", 0))
        completed = int(metrics.get("status_completed", 0))

        if total == 0:
            return 0.0

        
        return round((completed / total) * 100, 2)