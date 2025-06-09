"""
Cliente para comunicarse con Agent Management Service.

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
from uuid import UUID
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.redis_client import get_redis_client
from common.services.domain_queue_manager import DomainQueueManager

logger = logging.getLogger(__name__)
settings = get_settings()

class AgentManagementClient:
    """
    Cliente para comunicarse con Agent Management Service a través de Redis.
    
    Implementa el patrón de comunicación pseudo-síncrona sobre Redis que permite
    solicitar datos de forma síncrona (esperando respuesta) pero usando la infraestructura
    de colas Redis compartida por todos los servicios.
    """
    
    def __init__(self):
        # Configuración para compatibilidad con la versión anterior
        self.base_url = settings.agent_management_service_url  # Mantenido para compatibilidad
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
            logger.info("AgentManagementClient inicializado con comunicación Redis")
    
    async def ensure_initialized(self):
        """Asegura que el cliente está inicializado."""
        if not self.initialized:
            await self.initialize()
        
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_agent_config(
        self,
        agent_id: UUID,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene la configuración completa de un agente usando el patrón pseudo-síncrono Redis.
        
        TODO: Este método debería ampliar su respuesta para incluir toda la información necesaria
        del agente, incluyendo:
        1. Configuración básica del agente (system prompt, modelo, configuraciones)
        2. Collections asociadas para RAG con sus IDs
        3. Modelos de embeddings asignados a cada collection
        4. Cualquier otra configuración relevante para la ejecución
        
        Esta información debería almacenarse directamente en la estructura del agente en la base
        de datos, evitando así consultas adicionales al Ingestion Service.
        
        Args:
            agent_id: ID del agente
            tenant_id: ID del tenant
            
        Returns:
            Dict con configuración completa del agente o None si no existe
        """
        start_time = time.time()
        
        # Asegurar inicialización
        await self.ensure_initialized()
        
        try:
            # Crear ID de correlación único para esta solicitud
            correlation_id = str(uuid.uuid4())
            response_queue = f"management:responses:get_agent_config:{correlation_id}"
            
            # Crear acción con datos de solicitud
            action = DomainAction(
                action_type="management.get_agent_config",
                data={
                    "agent_id": str(agent_id),
                    "tenant_id": tenant_id,
                    "correlation_id": correlation_id
                }
            )
            
            # Publicar solicitud en cola de Management Service
            logger.debug(f"Enviando solicitud get_agent_config para {agent_id} con correlation_id={correlation_id}")
            await self.queue_manager.publish_action(action, queue_name="management.actions")
            
            # Establecer un tiempo de expiración para la cola de respuesta
            await self.redis_client.expire(response_queue, self.timeout)
            
            # Esperar respuesta en cola específica para este ID de correlación
            response_data = await self.redis_client.blpop(response_queue, timeout=self.timeout)
            
            # Si no hay respuesta en el tiempo límite, lanzar excepción
            if not response_data:
                raise TimeoutError(f"Timeout esperando respuesta de Management Service para agent_id={agent_id}")
            
            # Extraer datos de respuesta (blpop devuelve [queue_name, value])
            _, response_json = response_data
            response = json.loads(response_json)
            
            if response.get("success", False) and response.get("agent_config"):
                logger.debug(f"Recibida configuración completa de agente {agent_id} en {time.time() - start_time:.2f}s")
                return response["agent_config"]
            elif not response.get("success", True):
                logger.warning(f"Error obteniendo configuración de agente {agent_id}: {response.get('error', 'desconocido')}")
                return None
            else:
                logger.warning(f"Configuración de agente no encontrada: {agent_id}")
                return None
                
        except TimeoutError as e:
            logger.error(f"Timeout obteniendo configuración de agente {agent_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error en comunicación con Management Service: {str(e)}")
            raise
