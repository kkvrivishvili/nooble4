"""
Domain Actions para Agent Execution Service.

MODIFICADO: Integración con ExecutionContext y sistema de colas por tier.
"""

from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import Field
from datetime import datetime

from common.models.actions import DomainAction
from pydantic import BaseModel # Added for DocumentProcessSyncActionData

class AgentExecutionAction(DomainAction):
    """Domain Action para solicitar ejecución de agente."""
    
    action_type: str = Field("execution.agent_run", description="Tipo de acción")
    
    # MODIFICADO: Ya no necesitamos campos específicos de contexto
    # porque execution_context viene en DomainAction base
    
    # Datos específicos del mensaje
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field("text", description="Tipo de mensaje")
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    session_id: str = Field(..., description="ID de la sesión")
    
    # NUEVO: Configuración de ejecución específica
    max_iterations: Optional[int] = Field(None, description="Máximo iteraciones del agente")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "agent_run"


class ExecutionCallbackAction(DomainAction):
    """Domain Action para enviar resultados de ejecución como callback."""
    
    action_type: str = Field("execution.callback", description="Tipo de acción")
    
    # Estado de la ejecución
    status: str = Field("completed", description="Estado: completed, failed, timeout")
    
    # Resultado de la ejecución
    result: Dict[str, Any] = Field(..., description="Resultado de la ejecución")
    
    # NUEVO: Métricas de performance
    execution_time: Optional[float] = Field(None, description="Tiempo total de ejecución")
    tokens_used: Optional[Dict[str, int]] = Field(None, description="Tokens utilizados")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "callback"


# NUEVO: Domain Actions para interacción con otros servicios
class EmbeddingRequestAction(DomainAction):
    """Domain Action para solicitar embeddings."""
    
    action_type: str = Field("embedding.request", description="Tipo de acción")
    
    texts: list = Field(..., description="Textos para embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding")
    
    def get_domain(self) -> str:
        return "embedding"
    
    def get_action_name(self) -> str:
        return "request"


class QueryRequestAction(DomainAction):
    """Domain Action para solicitar consulta RAG."""
    
    action_type: str = Field("query.request", description="Tipo de acción")
    
    query: str = Field(..., description="Consulta a procesar")
    collection_id: str = Field(..., description="ID de colección")
    agent_description: Optional[str] = Field(None, description="Descripción del agente")
    
    def get_domain(self) -> str:
        return "query"
    
    def get_action_name(self) -> str:
        return "request"


class DocumentProcessSyncActionData(BaseModel):
    """Data payload for synchronous document processing requests."""
    # Identifiers for the document and its context
    document_id: Optional[str] = Field(None, description="Optional ID for the document if it's being reprocessed or has a known ID.")
    collection_id: str = Field(..., description="ID of the collection where the document will be stored/indexed.")
    # tenant_id will be taken from the root DomainAction's tenant_id

    # Document source (at least one must be provided by the client)
    file_key: Optional[str] = Field(None, description="Key for the document in an object storage (e.g., S3 key).")
    url: Optional[str] = Field(None, description="URL to fetch the document from.")
    text_content: Optional[str] = Field(None, description="Raw text content of the document.")

    # Document metadata
    title: Optional[str] = Field(None, description="Title of the document.")
    description: Optional[str] = Field(None, description="Brief description of the document content.")
    tags: Optional[list[str]] = Field(default_factory=list, description="Tags associated with the document.")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Other arbitrary metadata for the document.")

    # Processing configuration (optional, sensible defaults should be in Ingestion Service)
    chunk_size: Optional[int] = Field(None, description="Target size for text chunks.")
    chunk_overlap: Optional[int] = Field(None, description="Overlap size between consecutive chunks.")
    embedding_model: Optional[str] = Field(None, description="Specific embedding model to use for this document.")

class DocumentProcessSyncAction(DomainAction):
    """Domain Action for synchronously processing a document via Ingestion Service."""
    action_type: str = Field("document.process.sync", const=True, default="document.process.sync")
    data: DocumentProcessSyncActionData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "unique-action-id-for-sync-call",
                "action_type": "document.process.sync",
                "timestamp": "2024-05-21T14:00:00Z",
                "origin_service": "api_gateway_or_client_app",
                "tenant_id": "tenant-xyz",
                "data": {
                    "collection_id": "collection-abc-123",
                    "text_content": "This is the full text of the document to be processed...",
                    "title": "Sample Document for Sync Processing",
                    "embedding_model": "text-embedding-ada-002"
                }
            }
        }

    def get_domain(self) -> str:
        return "document"  # Or 'ingestion' if preferred for routing, but 'document' seems fine for AES to handle

    def get_action_name(self) -> str:
        return "process.sync"


# Models for Conversation Service interactions initiated by AES

class ConversationGetHistoryActionData(BaseModel):
    """Data payload for requesting conversation history."""
    session_id: str = Field(..., description="ID of the session for which history is requested.")
    limit: Optional[int] = Field(None, description="Maximum number of messages to return.")
    # before_timestamp: Optional[datetime] = Field(None, description="Get messages before this timestamp.")

class ConversationGetHistoryAction(DomainAction):
    """Domain Action for AES to request conversation history from Conversation Service."""
    action_type: str = Field("conversation.get_history", const=True, default="conversation.get_history")
    data: ConversationGetHistoryActionData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "aes-generated-action-id-hist",
                "action_type": "conversation.get_history",
                "timestamp": "2024-05-22T10:00:00Z",
                "origin_service": "agent_execution_service", # AES is sending this
                "tenant_id": "tenant-xyz",
                "data": {
                    "session_id": "session-123",
                    "limit": 50
                }
            }
        }

    def get_domain(self) -> str:
        return "conversation" # Target service domain

    def get_action_name(self) -> str:
        return "get_history"


class ConversationGetContextActionData(BaseModel):
    """Data payload for requesting conversation context."""
    session_id: str = Field(..., description="ID of the session for which context is requested.")
    # Potentially other fields like 'context_type' or 'max_tokens' could be added here

class ConversationGetContextAction(DomainAction):
    """Domain Action for AES to request conversation context from Conversation Service."""
    action_type: str = Field("conversation.get_context", const=True, default="conversation.get_context")
    data: ConversationGetContextActionData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "aes-generated-action-id-ctx",
                "action_type": "conversation.get_context",
                "timestamp": "2024-05-22T10:05:00Z",
                "origin_service": "agent_execution_service", # AES is sending this
                "tenant_id": "tenant-xyz",
                "data": {
                    "session_id": "session-123"
                }
            }
        }

    def get_domain(self) -> str:
        return "conversation" # Target service domain

    def get_action_name(self) -> str:
        return "get_context"


# Models for actions RECEIVED BY AgentExecutionService that trigger pseudo-sync calls to OTHER services

class ExecutionGetAgentConfigActionData(BaseModel):
    """Data payload for an AES action to request agent configuration from AgentManagementService."""
    agent_id: str = Field(..., description="ID of the agent whose configuration is requested.")

class ExecutionGetAgentConfigAction(DomainAction):
    """Domain Action received by AES to get agent configuration."""
    action_type: str = Field("execution.management.get_agent_config", const=True, default="execution.management.get_agent_config")
    data: ExecutionGetAgentConfigActionData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "client-request-id-agent-config",
                "action_type": "execution.management.get_agent_config",
                "origin_service": "client_app_or_api_gateway",
                "tenant_id": "tenant-xyz",
                "data": {
                    "agent_id": "agent-007"
                }
            }
        }

    def get_domain(self) -> str:
        return "execution" # This action is handled by the execution domain

    def get_action_name(self) -> str:
        return "management.get_agent_config"


class ExecutionGetConversationHistoryActionData(BaseModel):
    """Data payload for an AES action to request conversation history from ConversationService."""
    session_id: str = Field(..., description="ID of the session for which history is requested.")
    limit: Optional[int] = Field(None, description="Maximum number of messages to return.")

class ExecutionGetConversationHistoryAction(DomainAction):
    """Domain Action received by AES to get conversation history."""
    action_type: str = Field("execution.conversation.get_history", const=True, default="execution.conversation.get_history")
    data: ExecutionGetConversationHistoryActionData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "client-request-id-conv-hist",
                "action_type": "execution.conversation.get_history",
                "origin_service": "client_app_or_api_gateway",
                "tenant_id": "tenant-xyz",
                "data": {
                    "session_id": "session-abc-456",
                    "limit": 20
                }
            }
        }

    def get_domain(self) -> str:
        return "execution"

    def get_action_name(self) -> str:
        return "conversation.get_history"


class ExecutionGetConversationContextActionData(BaseModel):
    """Data payload for an AES action to request conversation context from ConversationService."""
    session_id: str = Field(..., description="ID of the session for which context is requested.")

class ExecutionGetConversationContextAction(DomainAction):
    """Domain Action received by AES to get conversation context."""
    action_type: str = Field("execution.conversation.get_context", const=True, default="execution.conversation.get_context")
    data: ExecutionGetConversationContextActionData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "client-request-id-conv-ctx",
                "action_type": "execution.conversation.get_context",
                "origin_service": "client_app_or_api_gateway",
                "tenant_id": "tenant-xyz",
                "data": {
                    "session_id": "session-abc-456"
                }
            }
        }

    def get_domain(self) -> str:
        return "execution"

    def get_action_name(self) -> str:
        return "conversation.get_context"