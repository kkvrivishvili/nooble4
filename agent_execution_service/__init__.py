"""
Agent Execution Service.

Servicio para ejecución de agentes conversacionales con modos simple y avanzado (ReAct).
"""

__version__ = "2.0.0"
__author__ = "Nooble4 Team"
__description__ = "Servicio de ejecución con soporte para chat simple + RAG y chat avanzado con ReAct"

# Importar desde los módulos correctos
from .clients import QueryClient, ConversationClient
from common.config.service_settings import ExecutionServiceSettings
from .handlers import AdvanceChatHandler, SimpleChatHandler
from .services import ExecutionService
from .tools import BaseTool, KnowledgeTool, ToolRegistry
from .utils import format_tool_result, format_chunks_for_llm
from .workers import ExecutionWorker

# Importar modelos directamente de common
from common.models.chat_models import ChatRequest, ChatResponse

__all__ = [
    "QueryClient",
    "ConversationClient",
    "ExecutionServiceSettings",
    "AdvanceChatHandler",
    "SimpleChatHandler",
    "ExecutionService",
    "BaseTool",
    "KnowledgeTool",
    "ToolRegistry",
    "format_tool_result",
    "format_chunks_for_llm",
    "ExecutionWorker",
    "ChatRequest",
    "ChatResponse",
]