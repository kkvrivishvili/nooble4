"""
Cliente para comunicarse con Embedding Service usando Domain Actions.

Implementa el patrón de comunicación pseudo-síncrona sobre Redis, que permite realizar
solicitudes síncronas (esperar respuesta) manteniendo la misma interfaz y comportamiento.

Version: 4.0 - Migrado a comunicación Redis pseudo-síncrona
"""

import logging
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID
from tenacity import retry, stop_after_attempt, wait_exponential

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from common.models.execution_context import ExecutionContext
from common.redis_pool import get_redis_client
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingClient:
    """
    Cliente para solicitar embeddings usando Domain Actions.
    
    Este cliente implementa el patrón de comunicación pseudo-síncrona sobre Redis 
    que permite solicitar datos de forma síncrona (esperando respuesta) pero usando 
    la infraestructura de colas Redis compartida por todos los servicios.
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
            logger.info("EmbeddingClient inicializado con comunicación Redis pseudo-síncrona")
    
    async def ensure_initialized(self):
        """Asegura que el cliente está inicializado."""
        if not self.initialized:
            await self.initialize()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def generate_embeddings_sync(
        self,
        texts: List[str],
        tenant_id: str,
        session_id: str,
        model: Optional[str] = None,
        collection_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ExecutionContext] = None
    ) -> List[List[float]]:
        """
        Genera embeddings y espera el resultado (patrón pseudo-síncrono).
        
        Reemplaza la comunicación asíncrona con callbacks por una comunicación 
        pseudo-síncrona que espera la respuesta usando correlation_id.
        
        Args:
            texts: Textos para generar embeddings
            tenant_id: ID del tenant
            session_id: ID de la sesión
            model: Modelo a utilizar (default si no se especifica)
            collection_id: ID de la colección (opcional)
            metadata: Metadatos adicionales (opcional)
            context: Contexto de ejecución (opcional)
            
        Returns:
            List[List[float]]: Lista de vectors de embeddings generados
            
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
            response_queue = f"embedding:responses:generate:{correlation_id}"
            
            # Crear acción con datos de solicitud
            action = DomainAction(
                action_id=str(uuid.uuid4()),
                action_type="embedding.generate.sync",  # Nueva acción específica para llamadas síncronas
                task_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                data={
                    "texts": texts,
                    "session_id": session_id,
                    "correlation_id": correlation_id,
                    "model": model,
                    "collection_id": str(collection_id) if collection_id else None,
                    "metadata": metadata,
                }
            )
            
            if context:
                action.context = context.dict()
                
            # Publicar solicitud en cola de Embedding Service
            logger.debug(f"Enviando solicitud generate_embeddings_sync con correlation_id={correlation_id}")
            await self.queue_manager.publish_action(action, queue_name="embedding.actions")
            
            # Establecer un tiempo de expiración para la cola de respuesta
            await self.redis_client.expire(response_queue, self.timeout)
            
            # Esperar respuesta en cola específica para este ID de correlación
            response_data = await self.redis_client.blpop(response_queue, timeout=self.timeout)
            
            # Si no hay respuesta en el tiempo límite, lanzar excepción
            if not response_data:
                raise TimeoutError(f"Timeout esperando respuesta de Embedding Service")
            
            # Extraer datos de respuesta (blpop devuelve [queue_name, value])
            _, response_json = response_data
            response = json.loads(response_json)
            
            if response.get("success", False) and "embeddings" in response:
                logger.debug(f"Recibidos embeddings en {time.time() - start_time:.2f}s")
                return response["embeddings"]
            elif not response.get("success", True):
                error_msg = response.get("error", "desconocido")
                logger.warning(f"Error generando embeddings: {error_msg}")
                raise Exception(f"Error en Embedding Service: {error_msg}")
            else:
                logger.warning("Respuesta de Embedding Service no incluye embeddings")
                return []
                
        except TimeoutError as e:
            logger.error(f"Timeout generando embeddings: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error en comunicación con Embedding Service: {str(e)}")
            raise