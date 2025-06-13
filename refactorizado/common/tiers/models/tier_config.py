# common/tiers/models/tier_config.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum

class TierResourceKey(str, Enum):
    """Enumeración estandarizada para los recursos controlados por tiers."""
    # Agent Management
    MAX_AGENTS = "agents.max_agents"
    ALLOW_CUSTOM_TEMPLATES = "agents.allow_custom_templates"

    # Conversation
    MAX_CONVERSATION_HISTORY = "conversation.max_history"
    ALLOW_CONVERSATION_PERSISTENCE = "conversation.allow_persistence"

    # Query Service
    MAX_QUERY_LENGTH = "query.max_length"
    ALLOWED_QUERY_MODELS = "query.allowed_models"

    # Embedding Service
    MAX_EMBEDDING_BATCH_SIZE = "embedding.max_batch_size"
    MAX_DAILY_EMBEDDING_TOKENS = "embedding.daily_tokens"

    # Ingestion Service
    MAX_FILE_SIZE_MB = "ingestion.max_file_size_mb"
    MAX_DAILY_DOCUMENTS = "ingestion.daily_documents"

    # General
    RATE_LIMIT_PER_MINUTE = "general.rate_limit_per_minute"


class TierLimits(BaseModel):
    """Define los límites específicos para un tier."""
    # Agent Management
    max_agents: int = Field(..., description="Número máximo de agentes que se pueden crear.")
    allow_custom_templates: bool = Field(False, description="Permite crear templates personalizados.")

    # Conversation
    max_conversation_history: int = Field(..., description="Máximo de mensajes a retener en el historial.")
    allow_conversation_persistence: bool = Field(True, description="Permite persistir las conversaciones.")

    # Query Service
    max_query_length: int = Field(..., description="Longitud máxima del query en caracteres.")
    allowed_query_models: List[str] = Field(..., description="Modelos de lenguaje permitidos para consultas.")

    # Embedding Service
    max_embedding_batch_size: int = Field(..., description="Tamaño máximo del lote para embeddings.")
    max_daily_embedding_tokens: int = Field(..., description="Cuota diaria de tokens para embedding.")

    # Ingestion Service
    max_file_size_mb: int = Field(..., description="Tamaño máximo de archivo para ingesta (MB).")
    max_daily_documents: int = Field(..., description="Número máximo de documentos a ingestar por día.")

    # General
    rate_limit_per_minute: int = Field(..., description="Límite de peticiones por minuto.")


class TierConfig(BaseModel):
    """Representa la configuración completa de un único tier."""
    tier_name: str
    limits: TierLimits


class AllTiersConfig(BaseModel):
    """Contiene el mapeo de todos los tiers y sus configuraciones de límites."""
    tiers: Dict[str, TierLimits]

