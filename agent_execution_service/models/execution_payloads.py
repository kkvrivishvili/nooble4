"""
Modelos específicos del Agent Execution Service.
Solo mantiene lo que no está en common.
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum

# Importar modelos compartidos
from common.models.chat_models import SimpleChatPayload, ChatMessage


class OperationMode(str, Enum):
    """Modos de operación soportados."""
    SIMPLE = "simple"
    ADVANCE = "advance"


class ExecutionSimpleChatPayload(SimpleChatPayload):
    """
    Payload específico para Agent Execution con metadatos adicionales.
    Extiende SimpleChatPayload con campos específicos del servicio.
    """
    operation_mode: OperationMode = Field(default=OperationMode.SIMPLE)
    
    # Campos adicionales específicos de Agent Execution
    request_id: Optional[str] = Field(None, description="ID de request del cliente")
    client_metadata: Optional[dict] = Field(None, description="Metadata del cliente")
    
    model_config = {"extra": "forbid"}