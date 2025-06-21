"""
Ingestion Service - Servicio de ingestión de documentos.

Este servicio maneja el procesamiento de documentos,
su división en chunks, enriquecimiento y almacenamiento
en la base de datos vectorial.
"""

__version__ = "1.0.0"

# Importaciones desde los submódulos
from .api import router
from .config import get_settings
from .handlers import DocumentProcessorHandler, ChunkEnricherHandler, QdrantHandler
from .models import (
    DocumentIngestionRequest,
    ChunkModel,
    IngestionStatus,
    IngestionTask,
    ProcessingProgress
)
from .services import IngestionService
from .websocket import WebSocketManager
from .workers import IngestionWorker

# Definir exportaciones públicas
__all__ = [
    # API
    "router",
    
    # Configuración
    "get_settings",
    
    # Handlers
    "DocumentProcessorHandler",
    "ChunkEnricherHandler",
    "QdrantHandler",
    
    # Modelos
    "DocumentIngestionRequest",
    "ChunkModel",
    "IngestionStatus",
    "IngestionTask",
    "ProcessingProgress",
    
    # Servicios
    "IngestionService",
    
    # WebSocket
    "WebSocketManager",
    
    # Workers
    "IngestionWorker"
]