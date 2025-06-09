"""
Cliente para comunicarse con Conversation Service.

Implementa el patrón de comunicación pseudo-síncrona sobre Redis, reemplazando
las llamadas HTTP directas por un enfoque basado en colas Redis que mantiene
la misma interfaz y comportamiento sincrónico.

Version: 4.0 - Migrado a comunicación Redis Queue
"""

import logging
import json
import time
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from common.models.actions import DomainAction
from common.services.redis_client import get_redis_client
from common.services.domain_queue_manager import DomainQueueManager

logger = logging.getLogger(__name__)
settings = get_settings()

class ConversationServiceClient:
    """
    Cliente para comunicarse con Conversation Service a través de Redis.
    
    Implementa el patrón de comunicación pseudo-síncrona sobre Redis que permite
    solicitar datos de forma síncrona (esperando respuesta) pero usando la infraestructura
    de colas Redis compartida por todos los servicios.
    """
    
    def __init__(self):
        # Configuración para compatibilidad con la versión anterior
        self.base_url = settings.conversation_service_url  # Mantenido para compatibilidad
        self.timeout = settings.http_timeout_seconds  # Usado como timeout general
        
        # Nuevas propiedades para comunicación Redis
        self.redis_client = None  # Se inicializará de forma asíncrona
        self.queue_manager = None  # Se inicializará de forma asíncrona
        self.initialized = False
    
    async def initialize(self):
        """
        Inicializa el cliente de forma asíncrona, configurando Redis y DomainQueueManager.
        
        Este método debe llamarse antes de usar cualquier otra función del cliente.
        """
        if not self.initialized:
            self.redis_client = await get_redis_client()
            self.queue_manager = DomainQueueManager(self.redis_client)
            self.initialized = True
            logger.info("ConversationServiceClient inicializado con comunicación Redis")
    
    async def ensure_initialized(self):
        """
Asegura que el cliente está inicializado."""
        if not self.initialized:
            await self.initialize()
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_conversation_history(
        self, tenant_id: str, session_id: str, limit: Optional[int] = 100,
        include_system: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de conversación usando el patrón pseudo-síncrono Redis.
        
        Reemplaza la llamada HTTP directa por una comunicación basada en Redis que mantiene
        el mismo comportamiento sincrónico (esperar respuesta) pero usando colas Redis
        como infraestructura subyacente, mejorando la coherencia arquitectónica.
        
        Args:
            tenant_id: ID del tenant
            session_id: ID de la sesión
            limit: Límite de mensajes a obtener
            include_system: Si se deben incluir mensajes de sistema
            
        Returns:
            Lista de mensajes
        """
        await self.ensure_initialized()
        start_time = time.time()
        
        try:
            # Generar correlation_id único para esta solicitud
            correlation_id = str(uuid.uuid4())
            
            # Crear acción para solicitar historial
            action = DomainAction(
                action_type="conversation.get_history",
                tenant_id=tenant_id,
                session_id=session_id,
                data={
                    "limit": limit,
                    "include_system": include_system,
                    "correlation_id": correlation_id
                },
                correlation_id=correlation_id  # Este campo es crucial para el patrón request-response
            )
            
            # Encolar solicitud en la cola del servicio de conversación
            await self.queue_manager.enqueue_action(
                action, "conversation", priority=1
            )
            
            logger.debug(f"Solicitud de historial encolada con correlation_id: {correlation_id}")
            
            # Esperar respuesta en cola específica para este correlation_id
            response = await self._wait_for_response(correlation_id)
            
            if response and response.get("success", False):
                logger.info(f"Historial obtenido en {time.time() - start_time:.2f}s")
                return response.get("data", {}).get("messages", [])
            elif response:
                logger.error(f"Error obteniendo historial: {response.get('error')}")
                raise Exception(response.get("error", "Error desconocido"))
            else:
                raise TimeoutError("Timeout esperando respuesta del servicio de conversación")
                
        except TimeoutError as e:
            logger.error(f"Timeout en get_conversation_history: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado en get_conversation_history: {str(e)}")
            raise
            
        return []
    
    async def _wait_for_response(
        self, correlation_id: str, timeout_seconds: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Espera la respuesta en una cola específica usando BLPOP de Redis.
        
        Esta implementación utiliza BLPOP que bloquea esperando datos en la cola, pero
        no bloquea el event loop de asyncio, permitiendo que otras tareas se ejecuten
        mientras se espera la respuesta.
        
        Args:
            correlation_id: ID único que correlaciona solicitud y respuesta
            timeout_seconds: Tiempo máximo de espera (None para usar el timeout por defecto)
            
        Returns:
            Respuesta deserializada o None si hay timeout
        """
        if timeout_seconds is None:
            timeout_seconds = self.timeout
            
        # Cola específica donde esperar la respuesta
        response_queue = f"conversation:responses:{correlation_id}"
        start_time = time.time()
        
        try:
            # Esperar respuesta usando BLPOP (bloqueante a nivel Redis, no de asyncio)
            result = await self.redis_client.blpop(
                response_queue, 
                timeout=timeout_seconds
            )
            
            if result:
                # result es una tupla (queue_name, value)
                _, value = result
                response = json.loads(value)
                
                # Verificar que el correlation_id coincida como medida de seguridad adicional
                if response.get("correlation_id") == correlation_id:
                    logger.debug(f"Respuesta recibida para {correlation_id} en {time.time() - start_time:.2f}s")
                    return response
                else:
                    logger.warning(f"Correlation ID no coincide en respuesta: {response.get('correlation_id')} != {correlation_id}")
            
            # Si llegamos aquí, no recibimos respuesta o no era válida
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout esperando respuesta para {correlation_id}")
            return None
        except Exception as e:
            logger.error(f"Error esperando respuesta: {str(e)}")
            return None
    
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
