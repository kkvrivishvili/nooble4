"""
Cliente para la comunicación con el Embedding Service.
"""

from typing import List, Dict, Any, Optional
import logging

from common.models.actions import DomainAction
from common.clients.base_redis_client import BaseRedisClient
from common.config.base_settings import CommonAppSettings
from common.models.embeddings import RAGConfig


class EmbeddingClient:
    """
    Cliente para la comunicación con el Embedding Service.
    Encapsula la lógica de envío de acciones y recepción de respuestas.
    """
    
    def __init__(
        self,
        app_settings: CommonAppSettings,
        redis_client: BaseRedisClient
    ):
        """
        Inicializa el cliente con los componentes necesarios.
        
        Args:
            app_settings: Configuración de la aplicación
            redis_client: Cliente Redis para comunicación entre servicios
        """
        self.app_settings = app_settings
        self.redis_client = redis_client
        self._logger = logging.getLogger(f"{app_settings.service_name}.EmbeddingClient")
    
    async def batch_process(
        self,
        texts: List[str],
        chunk_ids: List[str],
        agent_id: str,
        model: str,
        rag_config: Optional[RAGConfig] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Envía un lote de textos para procesamiento de embeddings.
        
        Args:
            texts: Lista de textos para procesar
            chunk_ids: Lista de IDs de chunks correspondientes a los textos
            agent_id: ID del agente propietario de los chunks
            model: Modelo de embedding a utilizar
            rag_config: Configuración RAG para el procesamiento
            trace_id: ID de trace para seguimiento
            metadata: Metadatos adicionales para el procesamiento
        
        Returns:
            None - La respuesta se procesa de forma asíncrona mediante callback
        """
        self._logger.info(f"Enviando batch de {len(texts)} textos para embedding con model={model}")
        
        # Crear acción de dominio
        embedding_action = DomainAction(
            action_type="embedding.batch_process",
            task_id=f"embedding-{chunk_ids[0]}" if chunk_ids else None,
            tenant_id=metadata.get("tenant_id", "") if metadata else "",
            trace_id=trace_id,
            rag_config=rag_config,
            data={
                "texts": texts,
                "chunk_ids": chunk_ids,
                "agent_id": agent_id,
                "model": model
            },
            metadata=metadata
        )
        
        # Enviar acción con callback
        await self.redis_client.send_action_async_with_callback(
            embedding_action,
            callback_event_name="ingestion.embedding_result"
        )
        
        self._logger.debug(f"Batch enviado para embedding con callback a 'ingestion.embedding_result'")
