"""
Herramienta para búsqueda de conocimiento (RAG).
Simplificada para usar modelos estándar.
"""
import logging
from typing import Dict, Any, List, Optional
import uuid

from common.models.chat_models import RAGConfig, RAGSearchResult

from .base_tool import BaseTool
from ..clients.query_client import QueryClient

logger = logging.getLogger(__name__)


class KnowledgeTool(BaseTool):
    """Herramienta que realiza búsqueda RAG a través del Query Service."""

    def __init__(
        self,
        query_client: QueryClient,
        rag_config: RAGConfig,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ):
        super().__init__(
            name="knowledge",
            description="Search relevant information from the knowledge base"
        )
        self.query_client = query_client
        self.rag_config = rag_config
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
            
            # Usar la configuración RAG del constructor, permitiendo override de algunos params
            top_k = kwargs.get("top_k", self.rag_config.top_k)
            similarity_threshold = kwargs.get("similarity_threshold", self.rag_config.similarity_threshold)
            
            # Llamar a query_rag con configuración simplificada
            result = await self.query_client.query_rag(
                query_text=query,
                rag_config=self.rag_config.model_dump(),  # Serializar a dict
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                task_id=self.task_id,
                # Permitir override de algunos parámetros
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            
            # El resultado ya viene como RAGSearchResult
            search_result = RAGSearchResult.model_validate(result)
            
            # Formatear para el LLM
            if search_result.chunks:
                formatted_chunks = []
                for chunk in search_result.chunks[:3]:  # Top 3
                    formatted_chunks.append(f"[Source: {chunk.collection_id}, Score: {chunk.similarity_score:.2f}]\n{chunk.content}")
                
                return {
                    "found": search_result.total_found,
                    "content": "\n\n".join(formatted_chunks),
                    "summary": f"Found {search_result.total_found} relevant results"
                }
            else:
                return {
                    "found": 0,
                    "content": "No relevant information found",
                    "summary": "No results"
                }
            
        except Exception as e:
            self._logger.error(f"Error en knowledge tool: {e}")
            return {
                "error": str(e),
                "found": 0,
                "content": "",
                "summary": "Search failed"
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
                        "description": f"Number of results to retrieve (default: {self.rag_config.top_k})",
                        "default": self.rag_config.top_k
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": f"Minimum similarity score (0-1, default: {self.rag_config.similarity_threshold})",
                        "default": self.rag_config.similarity_threshold
                    }
                },
                "required": ["query"]
            }
        }