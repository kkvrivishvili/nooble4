from typing import Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class CommonAppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

    # Identificación y Entorno del Servicio
    service_name: str = Field(..., description="Nombre del servicio, ej: 'agent-orchestrator'. Requerido.")
    service_version: str = Field("0.1.0", description="Versión del servicio.")
    environment: str = Field("development", description="Entorno de ejecución (development, staging, production).")
    log_level: str = Field("INFO", description="Nivel de logging (DEBUG, INFO, WARNING, ERROR).")
    enable_telemetry: bool = Field(False, description="Habilitar telemetría y seguimiento distribuido.")
    
    # Configuración de Redis (común a todos los servicios)
    redis_url: str = Field("redis://localhost:6379", description="URL de conexión a Redis.")
    redis_password: Optional[str] = Field(None, description="Contraseña para Redis (si aplica).")
    
    # Puertos de servicios (configurables desde .env)
    agent_orchestrator_port: int = Field(8001, description="Puerto para Agent Orchestrator Service.")
    query_service_port: int = Field(8000, description="Puerto para Query Service.")
    ingestion_service_port: int = Field(8002, description="Puerto para Ingestion Service.")
    agent_management_port: int = Field(8003, description="Puerto para Agent Management Service.")
    conversation_service_port: int = Field(8004, description="Puerto para Conversation Service.")
    agent_execution_port: int = Field(8005, description="Puerto para Agent Execution Service.")
    embedding_service_port: int = Field(8006, description="Puerto para Embedding Service.")
    
    # URLs de servicios (configurables desde .env)
    agent_orchestrator_url: str = Field("http://localhost:8001", description="URL del Agent Orchestrator Service.")
    query_service_url: str = Field("http://localhost:8000", description="URL del Query Service.")
    ingestion_service_url: str = Field("http://localhost:8002", description="URL del Ingestion Service.")
    agent_management_url: str = Field("http://localhost:8003", description="URL del Agent Management Service.")
    conversation_service_url: str = Field("http://localhost:8004", description="URL del Conversation Service.")
    agent_execution_url: str = Field("http://localhost:8005", description="URL del Agent Execution Service.")
    embedding_service_url: str = Field("http://localhost:8006", description="URL del Embedding Service.")
    
    # Configuración de bases de datos externas
    # Qdrant
    qdrant_url: str = Field("http://localhost:6333", description="URL de conexión a Qdrant.")
    qdrant_api_key: Optional[str] = Field(None, description="API key para Qdrant (si aplica).")
    
    # Postgres
    postgres_url: str = Field("postgresql://postgres:postgres@localhost:5432/nooble", description="URL de conexión a Postgres.")
    
    # OpenAI (para Embedding Service)
    openai_api_key: Optional[str] = Field(None, description="API key para OpenAI.")
    openai_base_url: Optional[str] = Field(None, description="URL base para API de OpenAI (si se usa un endpoint alternativo).")
    openai_timeout_seconds: int = Field(60, description="Timeout en segundos para peticiones a la API de OpenAI.")
    openai_max_retries: int = Field(2, description="Número máximo de reintentos para peticiones a OpenAI.")
    
    # Groq (para Query Service)
    groq_api_key: Optional[str] = Field(None, description="API key para Groq.")
    groq_timeout_seconds: int = Field(60, description="Timeout en segundos para peticiones a la API de Groq.")
    groq_max_retries: int = Field(2, description="Número máximo de reintentos para peticiones a Groq.")
    
    # Qdrant (para búsqueda vectorial)
    search_timeout_seconds: int = Field(30, description="Timeout en segundos para búsquedas vectoriales.")

