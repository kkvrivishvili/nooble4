"""
Constantes para Agent Execution Service.
"""
from enum import Enum
from typing import Dict

class AgentTypes(str, Enum):
    """Tipos de agentes soportados."""
    CONVERSATIONAL = "conversational"  # Modo simple: Chat + RAG
    REACT = "react"  # Modo avanzado: ReAct pattern

class ExecutionModes(str, Enum):
    """Modos de ejecución."""
    SIMPLE = "simple"  # Chat + RAG básico
    ADVANCED = "advanced"  # ReAct con herramientas

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

# System prompt for ReAct when using direct tool calling (e.g., OpenAI functions/tools)
REACT_TOOL_SYSTEM_PROMPT = """You are a helpful AI assistant.

You have access to the following tools. Use them when necessary to answer the user's request.
{tools_description}

If you need to use a tool, call it by its name and provide the required arguments.
If you can answer directly without a tool, please do so.
"""