# common/tiers/models/tier_config.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class TierLimits(BaseModel):
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
    tier_name: str
    limits: TierLimits

# Ejemplo de configuración completa para todos los tiers
class AllTiersConfig(BaseModel):
    tiers: Dict[str, TierLimits]
