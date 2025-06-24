"""
Definición de la configuración específica para Ingestion Service.
"""
from typing import List, Optional, Dict
from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings

# --- Enums and constants specific to Ingestion Service configuration ---
class ChunkingStrategies(str, Enum):
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    TOKEN = "token"
    CHARACTER = "character"

class StorageTypes(str, Enum):
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"

class IngestionServiceSettings(CommonAppSettings):
    """Configuración específica para Ingestion Service."""

    model_config = SettingsConfigDict(
        env_prefix='INGESTION_',
        extra='ignore',
        env_file='.env'
    )

    # Configuración del servidor (ya en CommonAppSettings, pero puede sobreescribirse si es necesario)
    # host: str = Field(default="0.0.0.0", description="Host del servidor")
    # port: int = Field(default=8000, description="Puerto del servidor")

    # Redis (parcialmente en CommonAppSettings, aquí se añaden/especifican los de Ingestion)
    # redis_host: str = Field(default="localhost", description="Host de Redis")
    # redis_port: int = Field(default=6379, description="Puerto de Redis")
    # redis_password: Optional[str] = Field(default=None, description="Contraseña de Redis")
    # redis_db: int = Field(default=0, description="Base de datos Redis para Ingestion") # Especificar si es diferente a la común
    redis_queue_prefix: str = Field(default="ingestion", description="Prefijo para colas Redis específicas de Ingestion")

    # Colas específicas para tareas y callbacks
    # Los nombres completos de las colas. Se podrían construir con domain_name o redis_queue_prefix.
    document_processing_queue_name: str = Field(default="document:processing", description="Cola de procesamiento de documentos")
    chunking_queue_name: str = Field(default="document:chunking", description="Cola de fragmentación")
    # embedding_callback_queue_name: str = Field(default="embedding:callback", description="Cola de callbacks de embeddings, podría ser más genérico si Ingestion llama a otros servicios")
    task_status_queue_name: str = Field(default="task:status", description="Cola de estado de tareas")
    ingestion_actions_queue_name: str = Field(default="ingestion:actions", description="Cola para acciones de dominio entrantes para Ingestion")

    # Workers y procesamiento
    worker_count: int = Field(default=2, description="Número de workers de ingestión")
    max_concurrent_tasks: int = Field(default=5, description="Máximo de tareas de ingestión concurrentes")
    job_timeout_seconds: int = Field(default=3600, description="Timeout de trabajos de ingestión (segundos)")
    redis_lock_timeout_seconds: int = Field(default=600, description="Timeout de bloqueos Redis para ingestión")
    worker_sleep_time_seconds: float = Field(default=0.1, description="Tiempo de espera entre polls para workers de ingestión (segundos)")

    # Límites de tamaño y procesamiento
    max_file_size_bytes: int = Field(default=10485760, description="Tamaño máximo de archivo subido (bytes) - 10MB")
    max_document_content_size_bytes: int = Field(default=1048576, description="Tamaño máximo de contenido de documento extraído para texto (bytes) - 1MB")
    max_url_content_size_bytes: int = Field(default=10485760, description="Tamaño máximo de contenido descargado de URL (bytes) - 10MB")
    max_chunks_per_document: int = Field(default=1000, description="Máximo número de fragmentos por documento")

    # Chunking y procesamiento de documentos
    default_chunk_size: int = Field(default=512, description="Tamaño predeterminado de fragmentos (en tokens o caracteres según estrategia)")
    default_chunk_overlap: int = Field(default=50, description="Superposición predeterminada entre fragmentos")
    default_chunking_strategy: ChunkingStrategies = Field(default=ChunkingStrategies.SENTENCE, description="Estrategia de fragmentación predeterminada")

    # Integración con Embedding Service
    embedding_model_default: str = Field(default="text-embedding-ada-002", description="Modelo de embedding a solicitar por defecto")
    embedding_service_url: Optional[str] = Field(default=None, description="URL base del Embedding Service (e.g., http://embedding-service:8001)")
    embedding_service_timeout_seconds: int = Field(default=60, description="Timeout para llamadas al Embedding Service")

    # Storage
    storage_type: StorageTypes = Field(default=StorageTypes.LOCAL, description="Tipo de almacenamiento para archivos subidos/temporales (local, s3, azure)")
    local_storage_path: str = Field(default="/tmp/nooble4_ingestion_storage", description="Ruta base para almacenamiento local si storage_type es 'local'")
    # Aquí irían configuraciones específicas de S3 (bucket, keys, region) o Azure (connection string, container) si se implementan.

    # Configuración para autenticación y permisos (API keys)
    # api_key_header: str = Field(default="X-API-Key", description="Nombre del header para la API Key de cliente") # Podría heredar de CommonAppSettings si es estándar
    admin_api_key: Optional[str] = Field(default=None, description="API Key para operaciones de administración del Ingestion Service")

    # Auto-start workers
    auto_start_workers: bool = Field(default=True, description="Indica si los workers de ingestión deben iniciarse automáticamente con la aplicación")

    # CORS (ya en CommonAppSettings, se puede sobreescribir si es necesario)
    # cors_origins: List[str] = Field(default=["*"], description="Orígenes permitidos para CORS en Ingestion Service")



    # Podrían añadirse validadores para asegurar que las URLs de servicios tienen scheme, etc.
