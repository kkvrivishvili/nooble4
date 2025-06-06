"""
Cliente para comunicarse con Conversation Service.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ConversationServiceClient:
    """Cliente para comunicarse con Conversation Service."""
    
    def __init__(self):
        self.base_url = settings.conversation_service_url
        self.timeout = settings.http_timeout_seconds
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_conversation_history(
        self,
        session_id: str,
        tenant_id: str,
        limit: int = 10,
        include_system: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene historial de conversación.
        
        Args:
            session_id: ID de la sesión
            tenant_id: ID del tenant
            limit: Número máximo de mensajes
            include_system: Si incluir mensajes del sistema
            
        Returns:
            Lista de mensajes
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/internal/history/{session_id}",
                    params={
                        "tenant_id": tenant_id,
                        "limit": limit,
                        "include_system": include_system
                    }
                )
                response.raise_for_status()
                
                result = response.json()
                if result.get("success", False):
                    return result.get("data", {}).get("messages", [])
                
                return []
                
        except httpx.RequestError as e:
            logger.error(f"Error comunicando con Conversation Service: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error en Conversation Service: {str(e)}")
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def save_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        processing_time: Optional[float] = None
    ) -> bool:
        """
        Guarda un mensaje en la conversación.
        
        Args:
            session_id: ID de la sesión
            tenant_id: ID del tenant
            role: Rol del mensaje (user/assistant/system)
            content: Contenido del mensaje
            message_type: Tipo de mensaje
            metadata: Metadatos adicionales
            processing_time: Tiempo de procesamiento
            
        Returns:
            bool: True si se guardó exitosamente
        """
        request_data = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "role": role,
            "content": content,
            "message_type": message_type,
            "metadata": metadata or {},
            "processing_time": processing_time
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/internal/save-message",
                    json=request_data
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("success", False)
                
        except Exception as e:
            logger.error(f"Error guardando mensaje: {str(e)}")
            return False
