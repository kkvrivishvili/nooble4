"""
Cliente para acceso a vector store.

# TODO: Oportunidades de mejora futura:
# 1. Implementar mecanismos de retry para llamadas a la API
# 2. Mejorar la validación de parámetros y respuestas
# 3. Considerar abstracción para soportar diferentes backends de vector store
# 4. Añadir telemetría y observabilidad para rendimiento de consultas
"""

import logging
from typing import List, Dict, Any, Optional
import time

import aiohttp

from query_service.config.settings import get_settings
from common.errors import ServiceError

logger = logging.getLogger(__name__)
settings = get_settings()

class VectorStoreClient:
    """
    Cliente para buscar documentos en vector store.
    """
    
    def __init__(self):
        """Inicializar cliente con configuración."""
        self.vector_db_url = settings.vector_db_url
        self.timeout = settings.http_timeout_seconds
    
    async def search_by_embedding(
        self,
        tenant_id: str,
        collection_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.7,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca documentos similares en vector store.
        
        Args:
            tenant_id: ID del tenant
            collection_id: ID de la colección
            query_embedding: Embedding de búsqueda
            top_k: Número máximo de resultados
            threshold: Umbral de similitud
            metadata_filter: Filtro por metadatos (opcional)
            
        Returns:
            Lista de documentos con sus metadatos y puntajes
            
        Raises:
            ServiceError: Si hay problema con el vector store
        """
        start_time = time.time()
        
        try:
            # Preparar payload para búsqueda
            request_data = {
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "query_embedding": query_embedding,
                "top_k": top_k,
                "threshold": threshold
            }
            
            if metadata_filter:
                request_data["filter"] = metadata_filter
                
            # Realizar búsqueda
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.vector_db_url}/api/v1/search",
                    json=request_data,
                    timeout=self.timeout,
                    headers={"X-Tenant-ID": tenant_id}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Error vector DB ({response.status}): {error_text}")
                        raise ServiceError(f"Error en vector store: {response.status}")
                    
                    result = await response.json()
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", {}).get("message", "Error desconocido")
                        raise ServiceError(f"Error en búsqueda vectorial: {error_msg}")
                    
                    # Extraer documentos encontrados
                    documents = result.get("data", {}).get("documents", [])
                    
                    # Registrar tiempo y cantidad
                    search_time = time.time() - start_time
                    logger.info(f"Búsqueda completada: {len(documents)} docs en {search_time:.2f}s")
                    
                    return documents
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexión con vector store: {str(e)}")
            raise ServiceError(f"Error conectando con vector store: {str(e)}")
        
        except ServiceError:
            # Re-lanzar errores de servicio
            raise
            
        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {str(e)}")
            raise ServiceError(f"Error en búsqueda vectorial: {str(e)}")
