"""
Constantes para Agent Execution Service.
"""
from enum import Enum
from typing import Dict

class LLMProviders(str, Enum):
    """Proveedores de LLM soportados."""
    OPENAI = "openai"
    GROQ = "groq"
    ANTHROPIC = "anthropic"

class AgentTypes(str, Enum):
    """Tipos de agentes soportados."""
    CONVERSATIONAL = "conversational"  # Modo simple: Chat + RAG
    REACT = "react"  # Modo avanzado: ReAct pattern

class ExecutionModes(str, Enum):
    """Modos de ejecución."""
    SIMPLE = "simple"  # Chat + RAG básico
    ADVANCED = "advanced"  # ReAct con herramientas

# Modelos por defecto por proveedor
DEFAULT_MODELS: Dict[str, str] = {
    LLMProviders.OPENAI: "gpt-4-turbo-preview",
    LLMProviders.GROQ: "llama-3.3-70b-versatile", 
    LLMProviders.ANTHROPIC: "claude-3-5-sonnet-20241022"
}

# Prompts del sistema para ReAct
REACT_SYSTEM_PROMPT = """You are a helpful AI assistant that can reason about problems and use tools to solve them.

You have access to the following tools:
{tools_description}

When responding, follow this format:
Thought: Think about what you need to do
Action: tool_name
Action Input: {{"parameter": "value"}}
Observation: [Tool output will appear here]

You can repeat this cycle as needed. When ready to answer:
Thought: I now have enough information to answer
Final Answer: [Your complete response]

Rules:
- Think step by step
- Use tools when needed
- Provide clear final answers
"""