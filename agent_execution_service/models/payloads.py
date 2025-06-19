"""
Modelos Pydantic para Agent Execution Service.
"""
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime

class AgentType(str, Enum):
    CONVERSATIONAL = "conversational"
    REACT = "react"

class ExecutionMode(str, Enum):
    SIMPLE = "simple"
    ADVANCED = "advanced"

class LLMProvider(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    ANTHROPIC = "anthropic"

class LLMConfig(BaseModel):
    """Configuración para el modelo de lenguaje."""
    provider: LLMProvider = Field(default=LLMProvider.GROQ)
    model_name: str = Field(default="llama-3.3-70b-versatile")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0, le=8192)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stream: bool = Field(default=False)
    frequency_penalty: float = Field(default=0.0, ge=0.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=0.0, le=2.0)

class Message(BaseModel):
    """Mensaje en una conversación."""
    role: str = Field(..., description="Rol: user, assistant, system, tool")
    content: str = Field(..., description="Contenido del mensaje")
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['user', 'assistant', 'system', 'tool']
        if v not in allowed_roles:
            raise ValueError(f"Role debe ser uno de: {allowed_roles}")
        return v

class ToolConfig(BaseModel):
    """Configuración de herramienta."""
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=30, gt=0)

# ===============================================
# Payloads de Domain Actions
# ===============================================

class ExecuteSimpleChatPayload(BaseModel):
    """Payload para execution.chat.simple"""
    user_message: str = Field(..., min_length=1, description="Mensaje del usuario")
    system_prompt: Optional[str] = Field(None, description="Prompt del sistema personalizado")
    
    # Configuración RAG
    use_rag: bool = Field(default=True)
    collection_ids: Optional[List[str]] = Field(None, description="IDs de colecciones para RAG")
    rag_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Configuración LLM
    llm_config: Optional[LLMConfig] = Field(None)
    
    # Historial de conversación
    conversation_history: List[Message] = Field(default_factory=list)

    @field_validator('conversation_history')
    @classmethod
    def validate_conversation_history(cls, v):
        if len(v) > 50:  # Límite razonable
            raise ValueError("Historial de conversación demasiado largo (máximo 50 mensajes)")
        return v

class ExecuteReactPayload(BaseModel):
    """Payload para execution.react.execute"""
    user_message: str = Field(..., min_length=1, description="Mensaje del usuario")
    agent_id: str = Field(..., min_length=1, description="ID del agente ReAct")
    
    # Herramientas disponibles
    available_tools: List[ToolConfig] = Field(default_factory=list)
    
    # Configuración de ejecución
    max_iterations: int = Field(default=10, gt=0, le=20)
    max_execution_time: int = Field(default=120, gt=0, le=300)
    
    # Configuración LLM
    llm_config: Optional[LLMConfig] = Field(None)
    
    # System prompt personalizado
    react_system_prompt: Optional[str] = Field(None)
    
    # Contexto adicional
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ExecuteAgentPayload(BaseModel):
    """Payload general para execution.agent.execute"""
    user_message: str = Field(..., min_length=1, description="Mensaje del usuario")
    agent_id: str = Field(..., min_length=1, description="ID del agente")
    
    # Modo de ejecución
    execution_mode: ExecutionMode = Field(default=ExecutionMode.SIMPLE)
    agent_type: Optional[AgentType] = Field(None)
    
    # Configuración específica
    execution_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    collection_ids: Optional[List[str]] = Field(None)
    conversation_history: List[Message] = Field(default_factory=list)
    
    # Configuración LLM
    llm_config: Optional[LLMConfig] = Field(None)

# ===============================================
# Respuestas
# ===============================================

class ExecutionStep(BaseModel):
    """Un paso en la ejecución ReAct."""
    step_number: int = Field(..., gt=0)
    thought: Optional[str] = Field(None)
    action: Optional[str] = Field(None)
    action_input: Optional[Dict[str, Any]] = Field(None)
    observation: Optional[str] = Field(None)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    execution_time_ms: Optional[float] = Field(None, ge=0)

class ExecutionResult(BaseModel):
    """Resultado de ejecución."""
    success: bool
    final_answer: str
    execution_mode: ExecutionMode
    
    # Pasos de ejecución (para ReAct)
    execution_steps: List[ExecutionStep] = Field(default_factory=list)
    
    # Métricas
    total_iterations: int = Field(default=0, ge=0)
    execution_time_seconds: float = Field(default=0.0, ge=0)
    tokens_used: Optional[int] = Field(None, ge=0)
    
    # Metadatos
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ExecuteSimpleChatResponse(BaseModel):
    """Respuesta de chat simple."""
    response: str
    sources_used: List[str] = Field(default_factory=list)
    rag_context: Optional[str] = Field(None)
    execution_time_seconds: float = Field(default=0.0, ge=0)
    tokens_used: Optional[int] = Field(None, ge=0)

class ExecuteReactResponse(BaseModel):
    """Respuesta de ejecución ReAct."""
    execution_result: ExecutionResult
    tools_used: List[str] = Field(default_factory=list)

class ExecuteAgentResponse(BaseModel):
    """Respuesta general de agente."""
    execution_result: ExecutionResult
    conversation_id: Optional[str] = Field(None)
    message_id: Optional[str] = Field(None)

# ===============================================
# Error Models
# ===============================================

class ExecutionErrorResponse(BaseModel):
    """Respuesta de error en ejecución."""
    error_type: str
    error_code: str
    message: str
    step_number: Optional[int] = Field(None)
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())