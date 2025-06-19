"""
Cliente para comunicación con Query Service.
"""
import logging
from typing import Optional, List, Dict, Any
from common.clients.base_http_client import BaseHTTPClient
from common.errors.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

class QueryClient(BaseHTTPClient):
    """Cliente para Query Service."""

    def __init__(self, base_url: str, timeout: int = 30):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "agent-execution-service/1.0.0"
        }
        super().__init__(base_url=base_url, headers=headers)
        self.timeout = timeout

    async def query_with_rag(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        collection_ids: Optional[List[str]] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza una consulta RAG al Query Service usando DomainAction pattern.
        
        Nota: En el futuro esto debería usar Redis DomainActions,
        por ahora usamos HTTP directo.
        """
        try:
            payload = {
                "query_text": query_text,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "collection_ids": collection_ids or [],
                "llm_config": llm_config or {}
            }
            
            logger.info(f"Enviando query RAG para tenant {tenant_id}")
            
            response = await self.post(
                "/api/v1/query/generate", 
                json=payload,
                timeout=self.timeout
            )
            
            result = response.json()
            logger.info(f"Query RAG completado exitosamente")
            
            return result
            
        except Exception as e:
            logger.error(f"Error en query RAG: {e}")
            raise ExternalServiceError(
                f"Error comunicándose con Query Service: {str(e)}", 
                original_exception=e
            )

    # NUEVO MÉTODO
    async def llm_direct(
        self,
        messages: List[Dict[str, str]],
        tenant_id: str,
        session_id: str,
        llm_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Realiza una llamada directa al LLM sin RAG.
        
        Args:
            messages: Lista de mensajes en formato OpenAI
            tenant_id: ID del tenant
            session_id: ID de sesión  
            llm_config: Configuración del LLM
            tools: Definiciones de herramientas para tool calling
            tool_choice: Control de selección de herramientas
            
        Returns:
            Respuesta del LLM con posibles tool calls
            
        TODO: Migrar a DomainActions via Redis en lugar de HTTP directo
        """
        try:
            payload = {
                "messages": messages,
                "tenant_id": tenant_id,
                "session_id": session_id
            }
            
            # Agregar configuración LLM si se proporciona
            if llm_config:
                payload.update({
                    "llm_model": llm_config.get("model_name") or llm_config.get("llm_model"), # Support both keys
                    "temperature": llm_config.get("temperature"),
                    "max_tokens": llm_config.get("max_tokens"),
                    "top_p": llm_config.get("top_p"),
                    "frequency_penalty": llm_config.get("frequency_penalty"),
                    "presence_penalty": llm_config.get("presence_penalty")
                })
            
            # Agregar tools si se proporcionan
            if tools:
                payload["tools"] = tools
                if tool_choice:
                    payload["tool_choice"] = tool_choice
            
            logger.info(f"Enviando LLM directo para tenant {tenant_id}, session {session_id}")
            
            response = await self.post(
                "/api/v1/query/llm/direct", 
                json=payload,
                timeout=self.timeout
            )
            result = response.json()
            
            logger.info(f"LLM directo completado exitosamente para tenant {tenant_id}, session {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error en LLM directo para tenant {tenant_id}, session {session_id}: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error comunicándose con Query Service para LLM directo: {str(e)}", 
                original_exception=e
            )

    async def search_only(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        collection_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Realiza solo búsqueda vectorial.
        """
        try:
            payload = {
                "query_text": query_text,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "collection_ids": collection_ids or [],
                "top_k": top_k
            }
            
            response = await self.post(
                "/api/v1/query/search", 
                json=payload,
                timeout=self.timeout
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            raise ExternalServiceError(
                f"Error en búsqueda vectorial: {str(e)}", 
                original_exception=e
            )