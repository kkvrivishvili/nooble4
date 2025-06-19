"""
Modelos Pydantic para payloads entrantes del Agent Execution Service.
Contiene únicamente el modo de operación, ya que los payloads detallados
se definen en common.models.chat_models.
"""
from enum import Enum


class OperationMode(str, Enum):
    """Modos de operación soportados."""
    SIMPLE = "simple"
    ADVANCE = "advance"