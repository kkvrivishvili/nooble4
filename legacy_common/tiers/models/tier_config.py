# common/tiers/models/tier_config.py
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Modelos de Límites por Servicio ---

class AgentLimits(BaseModel):
    max_count: int = Field(..., description="Número máximo de agentes que se pueden crear.")
    allow_custom_templates: bool = Field(False, description="Permite crear templates personalizados.")

class ConversationLimits(BaseModel):
    max_history: int = Field(..., description="Máximo de mensajes a retener en el historial.")
    allow_persistence: bool = Field(True, description="Permite persistir las conversaciones.")

class QueryLimits(BaseModel):
    max_length: int = Field(..., description="Longitud máxima del query en caracteres.")
    allowed_models: List[str] = Field(..., description="Modelos de lenguaje permitidos para consultas.")

class EmbeddingLimits(BaseModel):
    max_batch_size: int = Field(..., description="Tamaño máximo del lote para embeddings.")
    daily_token_quota: int = Field(..., description="Cuota diaria de tokens para embedding.")

class IngestionLimits(BaseModel):
    max_file_size_mb: int = Field(..., description="Tamaño máximo de archivo para ingesta (MB).")
    daily_document_quota: int = Field(..., description="Número máximo de documentos a ingestar por día.")

# --- Modelo Principal de Límites ---

class TierLimits(BaseModel):
    """Agrupa todos los límites específicos por servicio."""
    agents: AgentLimits
    conversation: ConversationLimits
    query: QueryLimits
    embedding: EmbeddingLimits
    ingestion: IngestionLimits
    
    rate_limit_per_minute: int = Field(..., description="Límite de peticiones por minuto para el API Gateway.")

# --- Modelo de Configuración de Tier ---

class TierConfig(BaseModel):
    """Define la configuración completa para un único tier."""
    name: str = Field(..., description="El nombre del tier (ej. 'free', 'pro').")
    limits: TierLimits
