"""
Configuración del Conversation Service.
"""

from typing import Dict, Any
from pydantic import Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class ConversationSettings(BaseSettings):
    """Configuración específica para Conversation Service."""
    
    # Domain específico para colas
    domain_name: str = "conversation"
    
    # Database
    database_url: str = Field(
        "postgresql://user:pass@localhost/conversations",
        description="URL de base de datos para conversaciones"
    )
    
    # Cache
    conversation_cache_ttl: int = Field(
        300,
        description="TTL del cache de conversaciones (segundos)"
    )
    
    # Analytics
    enable_realtime_analytics: bool = Field(
        True,
        description="Habilitar analytics en tiempo real"
    )
    analytics_batch_size: int = Field(
        100,
        description="Tamaño de batch para procesamiento de analytics"
    )
    
    # CRM Integration
    crm_enabled: bool = Field(
        False,
        description="Habilitar integración con CRM"
    )
    crm_provider: str = Field(
        "hubspot",
        description="Proveedor de CRM"
    )
    crm_api_key: str = Field(
        "",
        description="API Key del CRM"
    )
    
    # Retention
    default_retention_days: int = Field(
        90,
        description="Días de retención por defecto"
    )
    max_context_window: int = Field(
        50,
        description="Máximo de mensajes en ventana de contexto"
    )
    
    # Performance
    search_index_enabled: bool = Field(
        True,
        description="Habilitar índice de búsqueda"
    )
    
    # Worker
    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls"
    )
    
    class Config:
        env_prefix = "CONVERSATION_"

def get_settings() -> ConversationSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("conversation-service")
    return ConversationSettings(**base_settings.model_dump())


# conversation_service/models/actions_model.py
"""
Domain Actions para Conversation Service.
"""

from typing import Dict, Any, Optional, List
from pydantic import Field
from datetime import datetime
from common.models.actions import DomainAction

class ConversationSaveAction(DomainAction):
    """Domain Action para guardar mensaje."""
    
    action_type: str = Field("conversation.save_message", description="Tipo de acción")
    
    # Datos del mensaje
    conversation_id: Optional[str] = Field(None, description="ID de conversación")
    agent_id: str = Field(..., description="ID del agente")
    user_id: Optional[str] = Field(None, description="ID del usuario")
    role: str = Field(..., description="Rol del mensaje")
    content: str = Field(..., description="Contenido del mensaje")
    message_type: str = Field("text", description="Tipo de mensaje")
    
    # Metadatos
    tokens_used: Optional[int] = Field(None, description="Tokens utilizados")
    processing_time_ms: Optional[int] = Field(None, description="Tiempo de procesamiento")
    
    def get_domain(self) -> str:
        return "conversation"
    
    def get_action_name(self) -> str:
        return "save_message"


class ConversationRetrieveAction(DomainAction):
    """Domain Action para obtener historial."""
    
    action_type: str = Field("conversation.get_history", description="Tipo de acción")
    
    # Parámetros de búsqueda
    conversation_id: Optional[str] = Field(None, description="ID de conversación")
    limit: int = Field(10, description="Límite de mensajes")
    include_system: bool = Field(False, description="Incluir mensajes del sistema")
    order: str = Field("desc", description="Orden de mensajes")
    
    def get_domain(self) -> str:
        return "conversation"
    
    def get_action_name(self) -> str:
        return "get_history"


class ConversationAnalyzeAction(DomainAction):
    """Domain Action para analizar conversación."""
    
    action_type: str = Field("conversation.analyze", description="Tipo de acción")
    
    # Parámetros de análisis
    conversation_id: str = Field(..., description="ID de conversación")
    analysis_types: List[str] = Field(..., description="Tipos de análisis")
    realtime: bool = Field(False, description="Análisis en tiempo real")
    
    def get_domain(self) -> str:
        return "conversation"
    
    def get_action_name(self) -> str:
        return "analyze"
