"""
Cliente para interactuar con Query Service usando Domain Actions.

Implementa el patrón de comunicación pseudo-síncrona sobre Redis, que permite realizar
solicitudes síncronas (esperar respuesta) manteniendo la misma interfaz y comportamiento.

# TODO: Oportunidades de mejora futura:
# 1. Implementar un BaseClient compartido con QueryClient del Query Service
# 2. Estandarizar más la conversión entre modelos específicos y DomainAction genérico
# 3. Centralizar la configuración de nombres de colas para evitar inconsistencias

Version: 4.0 - Migrado a comunicación Redis pseudo-síncrona
"""

import logging
import json
import time
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
from tenacity import retry, stop_after_attempt, wait_exponential

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from common.models.execution_context import ExecutionContext
from common.redis_pool import get_redis_client
from agent_execution_service.config.settings import get_settings

# Los modelos de acciones se crean localmente en el método

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryClient:
    """
    Cliente para enviar solicitudes al Query Service.
    
    Este cliente implementa el patrón de comunicación pseudo-síncrona sobre Redis 
    que permite solicitar datos de forma síncrona (esperando respuesta) pero usando 
    la infraestructura de colas Redis compartida por todos los servicios.
    
    Mantiene compatibilidad con el modo asíncrono original para casos de uso que lo requieran.
    """
    
    def __init__(self, queue_manager: Optional[DomainQueueManager] = None):
        """
        Inicializa el cliente.
        
        Args:
            queue_manager: Gestor de colas de dominio opcional
        """
        self.timeout = settings.http_timeout_seconds  # Usado como timeout general
        
        # Componentes para comunicación Redis (se inicializan de forma asíncrona)
        self.redis_client = None
        self.queue_manager = queue_manager
        self.initialized = False
        self.callback_queue = f"execution.{settings.service_id}.callbacks"  # Mantenido por compatibilidad
    
    async def initialize(self):
        """
        Inicializa el cliente de forma asíncrona, configurando Redis y DomainQueueManager.
        
        Este método debe llamarse antes de usar cualquier otra función del cliente.
        """
        if not self.initialized:
            self.redis_client = get_redis_client(settings.redis_url)
            if not self.queue_manager:
                self.queue_manager = DomainQueueManager(self.redis_client)
            
            self.initialized = True
            logger.info("QueryClient inicializado con comunicación Redis pseudo-síncrona")
    
    async def ensure_initialized(self):
        """Asegura que el cliente está inicializado."""
        if not self.initialized:
            await self.initialize()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def generate_rag_sync(
        self,
        tenant_id: str,
        query: str,
        session_id: str,
        collection_ids: List[str],
        llm_model: Optional[str] = None,
        search_limit: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ExecutionContext] = None
    ) -> Dict[str, Any]:
        """
        Genera una respuesta RAG y espera el resultado (patrón pseudo-síncrono).
        
        Reemplaza la comunicación asíncrona con callbacks por una comunicación 
        pseudo-síncrona que espera la respuesta usando correlation_id.
        
        Args:
            tenant_id: ID del tenant
            query: Consulta en texto natural
            session_id: ID de la sesión
            collection_ids: Lista de IDs de colecciones para buscar
            llm_model: Modelo LLM a utilizar (opcional)
            search_limit: Límite de resultados de búsqueda
            metadata: Metadatos adicionales (opcional)
            context: Contexto de ejecución (opcional)
            
        Returns:
            Dict con la respuesta generada y documentos relevantes
            
        Raises:
            TimeoutError: Si no hay respuesta en el tiempo límite
            Exception: Si hay un error en la comunicación
        """
        start_time = time.time()
        
        # Asegurar inicialización
        await self.ensure_initialized()
        
        try:
            # Crear ID de correlación único para esta solicitud
            correlation_id = str(uuid.uuid4())
            response_queue = f"query:responses:generate:{correlation_id}"
            
            # Crear acción con datos de solicitud
            action = DomainAction(
                action_id=str(uuid.uuid4()),
                action_type="query.rag.sync",  # Nueva acción específica para llamadas síncronas
                task_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                data={
                    "query": query,
                    "session_id": session_id,
                    "collection_ids": collection_ids,
                    "correlation_id": correlation_id,
                    "llm_model": llm_model,
                    "search_limit": search_limit,
                    "metadata": metadata
                }
            )
            
            if context:
                action.context = context.dict()
                
            # Publicar solicitud en cola de Query Service
            logger.debug(f"Enviando solicitud generate_rag_sync con correlation_id={correlation_id}")
            await self.queue_manager.publish_action(action, queue_name="query.actions")
            
            # Establecer un tiempo de expiración para la cola de respuesta
            await self.redis_client.expire(response_queue, self.timeout)
            
            # Esperar respuesta en cola específica para este ID de correlación
            response_data = await self.redis_client.blpop(response_queue, timeout=self.timeout)
            
            # Si no hay respuesta en el tiempo límite, lanzar excepción
            if not response_data:
                raise TimeoutError(f"Timeout esperando respuesta de Query Service")
            
            # Extraer datos de respuesta (blpop devuelve [queue_name, value])
            _, response_json = response_data
            response = json.loads(response_json)
            
            if response.get("success", False):
                logger.debug(f"Recibida respuesta RAG en {time.time() - start_time:.2f}s")
                return {
                    "answer": response.get("answer", ""),
                    "documents": response.get("documents", []),
                    "metadata": response.get("metadata", {})
                }
            else:
                error_msg = response.get("error", "desconocido")
                logger.warning(f"Error generando respuesta RAG: {error_msg}")
                raise Exception(f"Error en Query Service: {error_msg}")
                
        except TimeoutError as e:
            logger.error(f"Timeout generando respuesta RAG: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error en comunicación con Query Service: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def search_documents_sync(
        self,
        tenant_id: str,
        query: str,
        collection_ids: List[str],
        search_limit: int = 5,
        context: Optional[ExecutionContext] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca documentos relevantes y espera el resultado (patrón pseudo-síncrono).
        
        Args:
            tenant_id: ID del tenant
            query: Consulta en texto natural
            collection_ids: Lista de IDs de colecciones para buscar
            search_limit: Límite de resultados de búsqueda
            context: Contexto de ejecución (opcional)
            
        Returns:
            Lista de documentos relevantes encontrados
            
        Raises:
            TimeoutError: Si no hay respuesta en el tiempo límite
            Exception: Si hay un error en la comunicación
        """
        start_time = time.time()
        
        # Asegurar inicialización
        await self.ensure_initialized()
        
        try:
            # Crear ID de correlación único para esta solicitud
            correlation_id = str(uuid.uuid4())
            response_queue = f"query:responses:search:{correlation_id}"
            
            # Crear acción con datos de solicitud
            action = DomainAction(
                action_id=str(uuid.uuid4()),
                action_type="query.search.sync",  # Nueva acción específica para llamadas síncronas
                task_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                data={
                    "query": query,
                    "collection_ids": collection_ids,
                    "correlation_id": correlation_id,
                    "search_limit": search_limit
                }
            )
            
            if context:
                action.context = context.dict()
                
            # Publicar solicitud en cola de Query Service
            logger.debug(f"Enviando solicitud search_documents_sync con correlation_id={correlation_id}")
            await self.queue_manager.publish_action(action, queue_name="query.actions")
            
            # Establecer un tiempo de expiración para la cola de respuesta
            await self.redis_client.expire(response_queue, self.timeout)
            
            # Esperar respuesta en cola específica para este ID de correlación
            response_data = await self.redis_client.blpop(response_queue, timeout=self.timeout)
            
            # Si no hay respuesta en el tiempo límite, lanzar excepción
            if not response_data:
                raise TimeoutError(f"Timeout esperando respuesta de Query Service")
            
            # Extraer datos de respuesta (blpop devuelve [queue_name, value])
            _, response_json = response_data
            response = json.loads(response_json)
            
            if response.get("success", False) and "documents" in response:
                logger.debug(f"Recibidos documentos en {time.time() - start_time:.2f}s")
                return response["documents"]
            elif not response.get("success", True):
                error_msg = response.get("error", "desconocido")
                logger.warning(f"Error buscando documentos: {error_msg}")
                raise Exception(f"Error en Query Service: {error_msg}")
            else:
                logger.warning("Respuesta de Query Service no incluye documentos")
                return []
                
        except TimeoutError as e:
            logger.error(f"Timeout buscando documentos: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error en comunicación con Query Service: {str(e)}")
            raise
