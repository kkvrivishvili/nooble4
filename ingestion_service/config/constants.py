"""
Constantes para el Ingestion Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de procesamiento y fragmentación de documentos. Los valores configurables
se gestionan a través de IngestionServiceSettings.

Las Enums ChunkingStrategies y StorageTypes ahora se definen en
'refactorizado.common.config.service_settings.ingestion.py' junto con IngestionServiceSettings.
"""
from enum import Enum

# Versión del servicio (puede ser útil para logs o health checks)
VERSION = "1.0.0" 

# Constantes para Estados de Tareas
class TaskStates(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Constantes para Tipos de Documentos Soportados
class DocumentTypes(str, Enum):
    TEXT = "text"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    MD = "markdown"
    URL = "url"
    UNKNOWN = "unknown" # Para tipos no identificados o no soportados

# Constantes para Endpoints del API del Ingestion Service
class EndpointPaths:
    HEALTH = "/health"
    DOCUMENTS = "/documents"  # Para crear y listar documentos
    DOCUMENT_DETAIL = "/documents/{document_id}" # Para obtener, actualizar o eliminar un documento
    DOCUMENT_CONTENT = "/documents/{document_id}/content" # Para obtener el contenido original
    CHUNKS = "/documents/{document_id}/chunks" # Para listar chunks de un documento
    CHUNK_DETAIL = "/documents/{document_id}/chunks/{chunk_id}" # Para obtener un chunk específico
    TASKS = "/tasks" # Para listar tareas de ingestión
    TASK_DETAIL = "/tasks/{task_id}" # Para obtener el estado de una tarea específica
    WEBSOCKET_TASK_STATUS = "/ws/tasks/{task_id}" # WebSocket para el estado de la tarea
    UPLOAD_RAW_FILE = "/upload/file" # Endpoint para subir archivos directamente

# Podrían añadirse otras constantes específicas del dominio de ingestión que no sean configurables.
# Por ejemplo, nombres de eventos fijos, metadatos clave esperados, etc.
