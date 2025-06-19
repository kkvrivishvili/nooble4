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