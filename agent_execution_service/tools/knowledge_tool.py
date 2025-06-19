"""
Herramienta para búsqueda de conocimiento (RAG).
"""
import logging
from typing import Dict, Any, List, Optional
import uuid

from .base_tool import BaseTool
from ..clients.query_client import QueryClient

logger = logging.getLogger(__name__)


class KnowledgeTool(BaseTool):
    """Herramienta que realiza búsqueda RAG a través del Query Service."""

    def __init__(
        self,
        query_client: QueryClient,
        collection_ids: List[str],
        document_ids: Optional[List[str]],
        embedding_config: Dict[str, Any],
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ):
        super().__init__(
            name="knowledge",
            description="Search relevant information from the knowledge base"
        )
        self.query_client = query_client
        self.collection_ids = collection_ids
        self.document_ids = document_ids
        self.embedding_config = embedding_config
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.task_id = task_id
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta búsqueda RAG.
        
        Args:
            query: Consulta de búsqueda
            
        Returns:
            Dict con chunks encontrados y metadata
        """
        try:
            self._logger.info(f"Ejecutando búsqueda RAG: {query[:100]}...")
            
            result = await self.query_client.query_rag(
                query_text=query,
                collection_ids=self.collection_ids,
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                task_id=self.task_id,
                embedding_config=self.embedding_config,
                document_ids=self.document_ids,
                top_k=kwargs.get("top_k", 5),
                similarity_threshold=kwargs.get("similarity_threshold")
            )
            
            # Formatear resultado para el LLM
            formatted_chunks = []
            for chunk in result.get("chunks", []):
                formatted_chunks.append({
                    "content": chunk.get("content", ""),
                    "source": chunk.get("document_id", ""),
                    "score": chunk.get("score", 0.0)
                })
            
            return {
                "query": query,
                "found_chunks": len(formatted_chunks),
                "chunks": formatted_chunks
            }
            
        except Exception as e:
            self._logger.error(f"Error en knowledge tool: {e}")
            return {
                "error": str(e),
                "query": query,
                "found_chunks": 0,
                "chunks": []
            }

    def get_schema(self) -> Dict[str, Any]:
        """Retorna el schema de la herramienta."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to retrieve (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }