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
    
    # Database (preparado para Supabase)
    # IMPORTANTE: Estas credenciales deben configurarse correctamente en producción
    # TODO: Cambiar a os.getenv() cuando se implemente el manejo de .env
    database_url: str = Field(
        "",  # Temporalmente vacío, configurar en producción
        description="URL de Supabase (cuando esté implementado auth)"
    )
    supabase_url: str = Field(
        "",  # Temporalmente vacío, configurar en producción
        description="URL de Supabase"
    )
    supabase_key: str = Field(
        "",  # Temporalmente vacío, configurar en producción
        description="Supabase anon key"
    )
    
    # Redis para conversaciones activas
    conversation_active_ttl: int = Field(
        1800,  # 30 minutos
        description="TTL para conversaciones activas en Redis"
    )
    websocket_grace_period: int = Field(
        30,
        description="Segundos de gracia después de cerrar WebSocket"
    )
    

    
    # Token limits por modelo
    model_token_limits: Dict[str, int] = Field(
        default={
            "llama3-8b-8192": 6000,
            "llama3-70b-8192": 6000,
            "gpt-4": 28000,
            "gpt-4-32k": 28000,
            "claude-3-sonnet": 120000,
            "claude-3-opus": 120000
        },
        description="Límites de tokens para contexto por modelo"
    )
    
    # Tier limits para conversaciones
    tier_limits: Dict[str, Dict[str, Any]] = Field(
        default={
            "free": {
                "max_active_conversations": 3,
                "max_messages_per_conversation": 50,
                "retention_days": 7,
                "context_messages": 5
            },
            "advance": {
                "max_active_conversations": 10,
                "max_messages_per_conversation": 200,
                "retention_days": 30,
                "context_messages": 15
            },
            "professional": {
                "max_active_conversations": 50,
                "max_messages_per_conversation": 1000,
                "retention_days": 90,
                "context_messages": 30
            },
            "enterprise": {
                "max_active_conversations": None,
                "max_messages_per_conversation": None,
                "retention_days": 365,
                "context_messages": 50
            }
        },
        description="Límites por tier"
    )
    
    # Workers configuration
    message_save_worker_batch_size: int = Field(
        50,
        description="Batch size para guardar mensajes"
    )
    persistence_migration_interval: int = Field(
        60,
        description="Intervalo para verificar migraciones (segundos)"
    )
    
    # Statistics
    enable_statistics: bool = Field(
        True,
        description="Habilitar recolección de estadísticas"
    )
    statistics_update_interval: int = Field(
        300,  # 5 minutos
        description="Intervalo para actualizar estadísticas"
    )
    
    class Config:
        env_prefix = "CONVERSATION_"

def get_settings() -> ConversationSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("conversation-service")
    return ConversationSettings(**base_settings.model_dump())
