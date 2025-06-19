"""
Constantes para Agent Execution Service.
"""

# Action types soportados
ACTION_TYPE_SIMPLE_CHAT = "execution.chat.simple"
ACTION_TYPE_ADVANCE_CHAT = "execution.chat.advance"

# Modos de operación
OPERATION_MODE_SIMPLE = "simple"
OPERATION_MODE_ADVANCE = "advance"

# Límites
MAX_CONVERSATION_HISTORY = 50
MAX_THINKING_STEPS = 100
DEFAULT_TOOL_TIMEOUT = 30

# System prompts para ReAct
REACT_SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.
When you need to use a tool, you will receive the results and can continue reasoning.
Think step by step and use tools when necessary to answer the user's question accurately.
Always explain your thinking process."""