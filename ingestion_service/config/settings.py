"""
Configuración centralizada para el servicio de ingestión.

Este módulo define todas las variables de entorno y configuraciones 
necesarias para el funcionamiento del servicio.
"""

import os
from typing import Dict, Any, List, Optional
from pydantic import BaseSettings, Field, validator
from functools import lru_cache
from common.config import Settings as BaseSettings
from common.config import get_service_settings


class IngestionServiceSettings(BaseSettings):
    """
    Configuración central del servicio de ingestión.
    
    Estandarizado para usar el prefijo INGESTION_ en todas las variables de entorno,
    siguiendo el patrón de los demás servicios del proyecto.
    """
    
    # Configuración general de la aplicación
    domain_name: str = Field(default="ingestion", description="Dominio para colas")
    
    # Configuración del servidor
    host: str = Field(default="0.0.0.0", description="Host del servidor")
    port: int = Field(default=8000, description="Puerto del servidor")
    
    # Redis para colas y caché
    redis_host: str = Field(default="localhost", description="Host de Redis")
    redis_port: int = Field(default=6379, description="Puerto de Redis")
    redis_password: Optional[str] = Field(default=None, description="Contraseña de Redis")
    redis_db: int = Field(default=0, description="Base de datos Redis")
    redis_queue_prefix: str = Field(default="ingestion", description="Prefijo para colas Redis")
    
    # Colas específicas para tareas y callbacks
    document_queue: str = Field(default="document:processing", description="Cola de procesamiento de documentos")
    chunking_queue: str = Field(default="document:chunking", description="Cola de fragmentación")
    embedding_callback_queue: str = Field(default="embedding:callback", description="Cola de callbacks de embeddings")
    task_status_queue: str = Field(default="task:status", description="Cola de estado de tareas")
    
    # Workers y procesamiento
    worker_count: int = Field(default=2, description="Número de workers")
    max_concurrent_tasks: int = Field(default=5, description="Máximo de tareas concurrentes")
    job_timeout: int = Field(default=3600, description="Timeout de trabajos (segundos)")
    redis_lock_timeout: int = Field(default=600, description="Timeout de bloqueos Redis")
    worker_sleep_time: float = Field(default=0.1, description="Tiempo entre polls (segundos)")
    
    # Limites de tamaño y procesamiento
    max_file_size: int = Field(default=10485760, description="Tamaño máximo de archivo (bytes)")
    max_document_size: int = Field(default=1048576, description="Tamaño máximo de documento texto (bytes)")
    max_url_size: int = Field(default=10485760, description="Tamaño máximo de contenido URL (bytes)")
    max_chunks_per_document: int = Field(default=1000, description="Máximo fragmentos por documento")
    
    # Chunking y procesamiento de documentos
    default_chunk_size: int = Field(default=512, description="Tamaño predeterminado de fragmentos")
    default_chunk_overlap: int = Field(default=50, description="Superposición entre fragmentos")
    default_chunking_strategy: str = Field(default="sentence", description="Estrategia de fragmentación")
    
    # Embedding
    embedding_model: str = Field(default="text-embedding-ada-002", description="Modelo de embedding")
    embedding_service_url: str = Field(default="http://embedding-service:8000", description="URL del servicio de embeddings")
    embedding_service_timeout: int = Field(default=60, description="Timeout para servicio de embeddings")
    
    # Storage
    storage_type: str = Field(default="local", description="Tipo de almacenamiento (local, s3, azure)")
    local_storage_path: str = Field(default="/tmp/ingestion", description="Ruta para almacenamiento local")
    
    # Configuración para autenticación y permisos
    api_key_header: str = Field(default="X-API-Key", description="Header para API Key")
    admin_api_key: Optional[str] = Field(default=None, description="API Key para administrador")
    
    # Auto-start workers
    auto_start_workers: bool = Field(default=True, description="Iniciar workers automáticamente")
    
    # CORS
    cors_origins: List[str] = Field(default=["*"], description="Orígenes permitidos para CORS")
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse cors_origins de string a lista si viene como string."""
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        env_prefix = "INGESTION_"


@lru_cache()
def get_settings() -> IngestionServiceSettings:
    """Retorna una instancia cacheada de la configuración."""
    return IngestionServiceSettings()
