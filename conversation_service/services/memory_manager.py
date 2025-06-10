"""
Gestor de memoria conversacional.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from conversation_service.models.conversation_model import Message, MessageRole
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Estimación simple de tokens por palabra. Podría mejorarse con tiktoken.
# Se asume un promedio, ya que la tokenización real depende del modelo.
# OpenAI sugiere que 1 token es aprox. 4 caracteres en inglés o ~0.75 palabras.
# Invertido: 1 palabra ~ 1.33 tokens.
TOKEN_ESTIMATE_FACTOR = 1.33 

def _estimate_tokens(text: str) -> int:
    """Estima el número de tokens en un texto."""
    if not text:
        return 0
    return int(len(text.split()) * TOKEN_ESTIMATE_FACTOR)

class MemoryManager:
    """
    Gestor de memoria conversacional.
    Mantiene un buffer de mensajes por conversación, limitado por tokens.
    """
    
    def __init__(self):
        # conversation_id -> {"messages": List[Message], "max_tokens": int, "current_tokens": int}
        self.memory_instances: Dict[str, Dict[str, Any]] = {}
        
    def _get_or_create_memory_instance(
        self,
        conversation_id: str,
        model_name: str,
        tenant_tier: str
    ) -> Dict[str, Any]:
        """
        Obtiene o crea la instancia de memoria para una conversación.
        La instancia es un diccionario que contiene la lista de mensajes y el límite de tokens.
        """
        if conversation_id not in self.memory_instances:
            # Obtener límite de tokens para el modelo
            token_limit = settings.model_token_limits.get(model_name, 6000)
            
            # Ajustar según tier (reservar espacio para respuesta)
            # tier_config = settings.tier_limits.get(tenant_tier, settings.tier_limits["free"])
            # context_messages = tier_config["context_messages"] # No se usa directamente aquí ahora
            
            # Reservar ~30% para la respuesta del modelo, el resto para contexto
            max_context_tokens = int(token_limit * 0.7)
            
            self.memory_instances[conversation_id] = {
                "messages": [],
                "max_tokens": max_context_tokens,
                "current_tokens": 0
            }
            logger.info(
                f"Memoria creada para conv_id {conversation_id}: "
                f"modelo={model_name}, límite_contexto={max_context_tokens} tokens"
            )
        
        return self.memory_instances[conversation_id]
    
    def add_message_to_memory(
        self,
        conversation_id: str,
        message: Message,
        model_name: str, # Necesario para crear la instancia si no existe
        tenant_tier: str  # Necesario para crear la instancia si no existe
    ):
        """
        Agrega un mensaje a la memoria de la conversación y gestiona el truncamiento.
        """
        memory_instance = self._get_or_create_memory_instance(
            conversation_id, model_name, tenant_tier
        )
        
        messages_list: List[Message] = memory_instance["messages"]
        max_tokens: int = memory_instance["max_tokens"]
        current_tokens: int = memory_instance.get("current_tokens", 0)

        # Estimar tokens del nuevo mensaje
        new_message_tokens = _estimate_tokens(message.content)
        
        # Añadir el nuevo mensaje (temporalmente, para cálculo)
        messages_list.append(message)
        current_tokens += new_message_tokens
        
        # Aplicar truncamiento si se excede el límite de tokens
        # Se eliminan mensajes desde el más antiguo (excepto mensajes de sistema si los hubiera y quisiéramos preservarlos)
        # Por ahora, se eliminan los más antiguos FIFO.
        while current_tokens > max_tokens and messages_list:
            oldest_message = messages_list.pop(0) # Elimina el primer mensaje (el más antiguo)
            current_tokens -= _estimate_tokens(oldest_message.content)
            logger.debug(
                f"Conv {conversation_id}: Mensaje truncado. Tokens actuales: {current_tokens}"
            )

        memory_instance["current_tokens"] = max(0, current_tokens) # Asegurar que no sea negativo
        
        logger.debug(
            f"Conv {conversation_id}: Mensaje añadido. "
            f"Total mensajes: {len(messages_list)}, "
            f"Tokens estimados: {memory_instance['current_tokens']}"
        )

    def get_context_for_query(
        self,
        conversation_id: str,
        model_name: str, # Usado para crear la instancia si no existe y para el output
        tenant_tier: str  # Usado para crear la instancia si no existe
    ) -> Dict[str, Any]:
        """
        Obtiene el contexto de la conversación optimizado para el Query Service.
        Los mensajes ya están truncados según el límite de tokens.
        """
        if conversation_id not in self.memory_instances:
            # Si no hay memoria, es una conversación nueva o sin interacciones previas guardadas en memoria RAM.
            # El QueryService podría necesitar cargar el historial desde DB si este es el caso.
            # Aquí devolvemos un contexto vacío.
            return {
                "messages": [],
                "total_tokens": 0,
                "truncation_applied": False, # No hay mensajes, no se aplicó truncamiento aquí.
                "model_name": model_name
            }
        
        memory_instance = self.memory_instances[conversation_id]
        messages_list: List[Message] = memory_instance["messages"]
        
        formatted_messages = []
        calculated_total_tokens = 0
        
        for msg_model in messages_list:
            role_str = "user" # Default
            if msg_model.role == MessageRole.USER:
                role_str = "user"
            elif msg_model.role == MessageRole.ASSISTANT:
                role_str = "assistant"
            elif msg_model.role == MessageRole.SYSTEM:
                role_str = "system"
            
            msg_tokens = _estimate_tokens(msg_model.content)
            formatted_msg = {
                "role": role_str,
                "content": msg_model.content,
                "tokens": msg_tokens 
            }
            formatted_messages.append(formatted_msg)
            calculated_total_tokens += msg_tokens
        
        # `truncation_applied` es verdadero si el número de tokens actual es cercano al máximo
        # o si alguna vez se tuvo que truncar. Una heurística simple es si current_tokens > 0.
        # O, más precisamente, si la suma de tokens de todos los mensajes *originales* hubiera excedido max_tokens.
        # Por ahora, si hay mensajes y current_tokens está cerca del límite, es probable.
        # Langchain lo marcaba como true si había mensajes.
        # La lógica actual de truncamiento asegura que no se exceda.
        # Podemos decir que si hay mensajes, el buffer está activo y potencialmente ha truncado o truncará.
        truncation_was_applied = memory_instance.get("current_tokens", 0) > 0 and \
                                 len(messages_list) > 0 
                                 # Podríamos añadir una bandera explícita si se realizó un pop.

        return {
            "messages": formatted_messages,
            "total_tokens": calculated_total_tokens, # Usamos el cálculo fresco de los mensajes actuales
            "truncation_applied": truncation_was_applied, 
            "model_name": model_name
        }
    
    def cleanup_conversation_memory(self, conversation_id: str):
        """
        Limpia la memoria de una conversación, típicamente cuando se persiste
        o la sesión se cierra.
        """
        if conversation_id in self.memory_instances:
            del self.memory_instances[conversation_id]
            logger.info(f"Memoria en RAM limpiada para conversación: {conversation_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la memoria en RAM."""
        active_conversations = len(self.memory_instances)
        total_tokens_in_memory = 0
        for conv_id in self.memory_instances:
            total_tokens_in_memory += self.memory_instances[conv_id].get("current_tokens",0)

        return {
            "active_conversations": active_conversations,
            "total_tokens_in_memory": total_tokens_in_memory,
            "memory_type": "custom_token_buffer"
        }
