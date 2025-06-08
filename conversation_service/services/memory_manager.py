"""
Gestor de memoria con integración LangChain.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain.memory import (
    ConversationTokenBufferMemory,
    ConversationSummaryBufferMemory,
    ConversationBufferWindowMemory
)
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.llms.base import BaseLLM

from conversation_service.models.conversation_model import Message, MessageRole
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class MemoryManager:
    """
    Gestor de memoria conversacional con LangChain.
    """
    
    def __init__(self):
        self.memory_instances = {}  # conversation_id -> memory instance
        
    def get_memory_for_conversation(
        self,
        conversation_id: str,
        model_name: str,
        tenant_tier: str
    ) -> ConversationTokenBufferMemory:
        """
        Obtiene instancia de memoria para conversación.
        """
        if conversation_id not in self.memory_instances:
            self.memory_instances[conversation_id] = self._create_memory_instance(
                model_name, tenant_tier
            )
        
        return self.memory_instances[conversation_id]
    
    def _create_memory_instance(
        self,
        model_name: str,
        tenant_tier: str
    ) -> ConversationTokenBufferMemory:
        """
        Crea instancia de memoria según modelo y tier.
        """
        # Obtener límite de tokens para el modelo
        token_limit = settings.model_token_limits.get(model_name, 6000)
        
        # Ajustar según tier (reservar espacio para respuesta)
        tier_config = settings.tier_limits.get(tenant_tier, settings.tier_limits["free"])
        context_messages = tier_config["context_messages"]
        
        # Reservar ~30% para la respuesta del modelo
        max_context_tokens = int(token_limit * 0.7)
        
        memory = ConversationTokenBufferMemory(
            max_token_limit=max_context_tokens,
            return_messages=True,
            memory_key="chat_history"
        )
        
        logger.info(f"Memoria creada: {model_name}, límite: {max_context_tokens} tokens")
        return memory
    
    def add_message_to_memory(
        self,
        conversation_id: str,
        message: Message,
        model_name: str,
        tenant_tier: str
    ):
        """
        Agrega mensaje a la memoria de LangChain.
        """
        memory = self.get_memory_for_conversation(conversation_id, model_name, tenant_tier)
        
        # Convertir a formato LangChain
        langchain_message = self._convert_to_langchain_message(message)
        
        # Agregar a memoria
        if message.role == MessageRole.USER:
            memory.chat_memory.add_user_message(message.content)
        elif message.role == MessageRole.ASSISTANT:
            memory.chat_memory.add_ai_message(message.content)
        elif message.role == MessageRole.SYSTEM:
            memory.chat_memory.add_message(SystemMessage(content=message.content))
    
    def get_context_for_query(
        self,
        conversation_id: str,
        model_name: str,
        tenant_tier: str
    ) -> Dict[str, Any]:
        """
        Obtiene contexto optimizado para Query Service.
        """
        if conversation_id not in self.memory_instances:
            return {
                "messages": [],
                "total_tokens": 0,
                "truncation_applied": False
            }
        
        memory = self.memory_instances[conversation_id]
        
        # Obtener mensajes de la memoria (ya optimizados por LangChain)
        messages = memory.chat_memory.messages
        
        # Convertir a formato para Query Service
        formatted_messages = []
        total_tokens = 0
        
        for msg in messages:
            formatted_msg = {
                "role": self._langchain_to_role(msg),
                "content": msg.content,
                "tokens": len(msg.content.split()) * 1.3  # Estimación simple
            }
            formatted_messages.append(formatted_msg)
            total_tokens += formatted_msg["tokens"]
        
        return {
            "messages": formatted_messages,
            "total_tokens": int(total_tokens),
            "truncation_applied": len(messages) > 0,  # LangChain ya hizo truncamiento
            "model_name": model_name
        }
    
    def _convert_to_langchain_message(self, message: Message) -> BaseMessage:
        """Convierte Message a formato LangChain."""
        if message.role == MessageRole.USER:
            return HumanMessage(content=message.content)
        elif message.role == MessageRole.ASSISTANT:
            return AIMessage(content=message.content)
        elif message.role == MessageRole.SYSTEM:
            return SystemMessage(content=message.content)
        else:
            return HumanMessage(content=message.content)  # Fallback
    
    def _langchain_to_role(self, message: BaseMessage) -> str:
        """Convierte mensaje LangChain a role string."""
        if isinstance(message, HumanMessage):
            return "user"
        elif isinstance(message, AIMessage):
            return "assistant"
        elif isinstance(message, SystemMessage):
            return "system"
        else:
            return "user"
    
    def cleanup_conversation_memory(self, conversation_id: str):
        """Limpia memoria de conversación cuando se transfiere a DB."""
        if conversation_id in self.memory_instances:
            del self.memory_instances[conversation_id]
            logger.info(f"Memoria limpiada para conversación: {conversation_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de memoria."""
        return {
            "active_conversations": len(self.memory_instances),
            "memory_type": "token_buffer_langchain"
        }
