"""
Cliente para comunicación con el servicio de embeddings.

Este cliente es responsable de la comunicación asíncrona con el servicio
de embeddings para solicitar la generación de embeddings para los chunks
de documentos procesados.
"""

import json
import logging
import aiohttp
from typing import Dict, List, Any, Optional

from common.context import with_context, Context
from common.errors import ServiceError, ErrorCode
from ingestion_service.config.settings import get_settings
from ingestion_service.models.actions import EmbeddingRequestAction

settings = get_settings()
logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Cliente para interactuar con el servicio de embeddings."""
    
    def __init__(self):
        """Inicializa el cliente con la configuración del servicio."""
        self.base_url = settings.EMBEDDING_SERVICE_URL
        self.timeout = settings.EMBEDDING_SERVICE_TIMEOUT
    
    @with_context
    async def generate_embeddings(
        self, 
        action: EmbeddingRequestAction,
        ctx: Optional[Context] = None
    ) -> bool:
        """Envía una solicitud para generar embeddings al servicio correspondiente.
        
        Args:
            action: Domain Action con la solicitud de embeddings
            ctx: Contexto de la operación
            
        Returns:
            bool: True si la solicitud se envió correctamente
            
        Raises:
            ServiceError: Si hay un error en la comunicación con el servicio
        """
        url = f"{self.base_url}/api/v1/embeddings/generate"
        
        # Preparar el payload de la solicitud
        payload = action.dict()
        
        logger.info(
            f"Enviando solicitud de embeddings para documento {action.document_id}, "
            f"con {len(action.chunks)} chunks"
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status != 202:  # Esperamos un Accepted (202)
                        error_body = await response.text()
                        logger.error(
                            f"Error al solicitar embeddings: Status={response.status}, "
                            f"Response={error_body}"
                        )
                        raise ServiceError(
                            message=f"Error en servicio de embeddings: {response.status}",
                            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                            details={
                                "status_code": response.status,
                                "response": error_body,
                                "document_id": action.document_id
                            }
                        )
                    
                    logger.info(
                        f"Solicitud de embeddings enviada correctamente para "
                        f"documento {action.document_id}"
                    )
                    return True
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexión con servicio de embeddings: {e}")
            raise ServiceError(
                message=f"Error al conectar con servicio de embeddings: {str(e)}",
                error_code=ErrorCode.CONNECTION_ERROR,
                details={"document_id": action.document_id}
            )
        except Exception as e:
            logger.error(f"Error inesperado al solicitar embeddings: {e}")
            raise ServiceError(
                message=f"Error inesperado al solicitar embeddings: {str(e)}",
                error_code=ErrorCode.UNEXPECTED_ERROR,
                details={"document_id": action.document_id}
            )


# Instancia global del cliente
embedding_client = EmbeddingClient()
