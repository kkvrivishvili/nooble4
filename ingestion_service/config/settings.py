"""
Configuración centralizada para el servicio de ingestión.

Este módulo define todas las variables de entorno y configuraciones 
necesarias para el funcionamiento del servicio.
"""

import os
from typing import Dict, Any, List, Optional
from pydantic import BaseSettings, Field, validator
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración central del servicio de ingestión."""
    
    # Configuración general de la aplicación
    APP_NAME: str = "ingestion-service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    # Configuración del servidor
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # Redis para colas y caché
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = Field(default=0)
    REDIS_QUEUE_PREFIX: str = Field(default="ingestion")
    
    # Colas específicas para tareas y callbacks
    DOCUMENT_QUEUE: str = Field(default="document:processing")
    CHUNKING_QUEUE: str = Field(default="document:chunking")
    EMBEDDING_CALLBACK_QUEUE: str = Field(default="embedding:callback")
    TASK_STATUS_QUEUE: str = Field(default="task:status")
    
    # Workers y procesamiento
    WORKER_COUNT: int = Field(default=2)
    MAX_CONCURRENT_TASKS: int = Field(default=5)
    JOB_TIMEOUT: int = Field(default=3600)  # 1 hora
    REDIS_LOCK_TIMEOUT: int = Field(default=600)  # 10 minutos
    WORKER_SLEEP_TIME: float = Field(default=0.1)  # 100ms
    
    # Limites de tamaño y procesamiento
    MAX_FILE_SIZE: int = Field(default=10485760)  # 10MB
    MAX_DOCUMENT_SIZE: int = Field(default=1048576)  # 1MB texto
    MAX_URL_SIZE: int = Field(default=10485760)  # 10MB
    MAX_CHUNKS_PER_DOCUMENT: int = Field(default=1000)
    
    # Chunking y procesamiento de documentos
    DEFAULT_CHUNK_SIZE: int = Field(default=512)
    DEFAULT_CHUNK_OVERLAP: int = Field(default=50)
    DEFAULT_CHUNKING_STRATEGY: str = Field(default="sentence")
    
    # Embedding
    EMBEDDING_MODEL: str = Field(default="text-embedding-ada-002")
    EMBEDDING_SERVICE_URL: str = Field(default="http://embedding-service:8000")
    EMBEDDING_SERVICE_TIMEOUT: int = Field(default=60)
    
    # Storage
    STORAGE_TYPE: str = Field(default="local")  # local, s3, azure
    LOCAL_STORAGE_PATH: str = Field(default="/tmp/ingestion")
    
    # Configuración para autenticación y permisos
    API_KEY_HEADER: str = Field(default="X-API-Key")
    ADMIN_API_KEY: Optional[str] = None
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default=["*"])
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS de string a lista si viene como string."""
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        env_prefix = ""


@lru_cache()
def get_settings() -> Settings:
    """Retorna una instancia cacheada de la configuración."""
    return Settings()
