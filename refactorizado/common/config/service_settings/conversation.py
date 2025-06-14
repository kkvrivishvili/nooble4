"""
Definición de la configuración específica para Conversation Service.
"""
from typing import Dict, Any, Optional # Optional añadido por si acaso para campos como supabase_key

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..settings import CommonAppSettings

class ConversationSettings(CommonAppSettings):
    """Configuración específica para Conversation Service."""

    model_config = SettingsConfigDict(
        env_prefix='CONVERSATION_',
        extra='ignore',
        env_file='.env'
    )

    # service_name, environment, log_level, redis_url, database_url son heredados de CommonAppSettings.
    # El database_url heredado se usará si CONVERSATION_DATABASE_URL no está definido.

    # Domain específico para colas
    domain_name: str = Field("conversation", description="Dominio para colas y lógica del servicio de conversación.")
    
    # Configuración de Supabase (estos campos son específicos de ConversationSettings)
    # Si las variables de entorno CONVERSATION_SUPABASE_URL y CONVERSATION_SUPABASE_KEY existen, se usarán.
    # De lo contrario, serán None o el valor por defecto si se especifica uno.
    supabase_url: Optional[str] = Field(default=None, description="URL de Supabase")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anon key")
    
    # Redis para conversaciones activas
    conversation_active_ttl: int = Field(
        1800,  # 30 minutos
        description="TTL para conversaciones activas en Redis (segundos)"
    )
    websocket_grace_period: int = Field(
        30,
        description="Segundos de gracia después de cerrar WebSocket antes de limpiar recursos"
    )
    
    # Token limits por modelo
    model_token_limits: Dict[str, int] = Field(
        default_factory=lambda: {
            "llama3-8b-8192": 6000,
            "llama3-70b-8192": 6000,
            "gpt-4": 28000, # Asumiendo que se refiere a gpt-4-turbo o similar con contexto grande
            "gpt-4-32k": 28000, # Podría ser redundante o referirse a un modelo específico
            "claude-3-sonnet": 120000,
            "claude-3-opus": 120000
        },
        description="Límites de tokens para contexto por modelo. Usado para truncar historial."
    )
    
    # Tier limits para conversaciones
    tier_limits: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
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
                "max_active_conversations": None, # Representa ilimitado
                "max_messages_per_conversation": None, # Representa ilimitado
                "retention_days": 365,
                "context_messages": 50
            }
        },
        description="Límites de funcionalidad por tier de usuario."
    )
    
    # Workers configuration
    message_save_worker_batch_size: int = Field(
        50,
        description="Número de mensajes a procesar en batch por el worker de guardado."
    )
    persistence_migration_interval: int = Field(
        60,
        description="Intervalo en segundos para que el worker de migración de persistencia verifique tareas."
    )
    
    # Statistics
    enable_statistics: bool = Field(
        True,
        description="Habilitar recolección y exposición de estadísticas del servicio."
    )
    statistics_update_interval: int = Field(
        300,  # 5 minutos
        description="Intervalo en segundos para actualizar las estadísticas cacheadas."
    )
