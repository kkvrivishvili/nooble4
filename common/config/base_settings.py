import os
from typing import Dict, Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, field_validator

class CommonAppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

    # Identificación y Entorno del Servicio
    service_name: str = Field(
        os.getenv("SERVICE_NAME"),
        description="Nombre del servicio, ej: 'agent-orchestrator'. Requerido."
    )
    service_version: str = Field(
        os.getenv("SERVICE_VERSION", "0.1.0"),
        description="Versión del servicio."
    )
    environment: str = Field(
        os.getenv("ENVIRONMENT", "development"),
        description="Entorno de ejecución (development, staging, production)."
    )
    log_level: str = Field(
        os.getenv("LOG_LEVEL", "INFO"),
        description="Nivel de logging (DEBUG, INFO, WARNING, ERROR)."
    )
    enable_telemetry: bool = Field(
        os.getenv("ENABLE_TELEMETRY", "False").lower() == "true",
        description="Habilitar telemetría y seguimiento distribuido."
    )
    
    # Configuración de Redis (común a todos los servicios)
    redis_url: str = Field(
        os.getenv("REDIS_URL", "redis://redis:6379"),
        description="URL de conexión a Redis."
    )
    redis_password: Optional[str] = Field(
        os.getenv("REDIS_PASSWORD"),
        description="Contraseña para Redis (si aplica)."
    )
    redis_decode_responses: bool = Field(
        os.getenv("REDIS_DECODE_RESPONSES", "True").lower() == "true",
        description="Decodificar respuestas de Redis a UTF-8."
    )
    redis_socket_connect_timeout: int = Field(
        int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5")),
        description="Timeout en segundos para la conexión del socket de Redis."
    )
    redis_socket_keepalive: bool = Field(
        os.getenv("REDIS_SOCKET_KEEPALIVE", "True").lower() == "true",
        description="Habilitar keepalive para el socket de Redis."
    )
    redis_max_connections: int = Field(
        int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
        description="Número máximo de conexiones en el pool de Redis."
    )
    redis_health_check_interval: int = Field(
        int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")),
        description="Intervalo en segundos para el health check de Redis."
    )
    
    # Puertos de servicios (configurables desde .env)
    agent_orchestrator_port: int = Field(
        int(os.getenv("AGENT_ORCHESTRATOR_PORT", "8001")),
        description="Puerto para Agent Orchestrator Service."
    )
    query_service_port: int = Field(
        int(os.getenv("QUERY_SERVICE_PORT", "8000")),
        description="Puerto para Query Service."
    )
    ingestion_service_port: int = Field(
        int(os.getenv("INGESTION_SERVICE_PORT", "8002")),
        description="Puerto para Ingestion Service."
    )
    agent_management_port: int = Field(
        int(os.getenv("AGENT_MANAGEMENT_PORT", "8003")),
        description="Puerto para Agent Management Service."
    )
    conversation_service_port: int = Field(
        int(os.getenv("CONVERSATION_SERVICE_PORT", "8004")),
        description="Puerto para Conversation Service."
    )
    agent_execution_port: int = Field(
        int(os.getenv("AGENT_EXECUTION_PORT", "8005")),
        description="Puerto para Agent Execution Service."
    )
    embedding_service_port: int = Field(
        int(os.getenv("EMBEDDING_SERVICE_PORT", "8006")),
        description="Puerto para Embedding Service."
    )
    
    # URLs de servicios (configurables desde .env)
    agent_orchestrator_url: str = Field(
        os.getenv("AGENT_ORCHESTRATOR_URL", "http://agent_orchestrator_service:8001"),
        description="URL del Agent Orchestrator Service."
    )
    query_service_url: str = Field(
        os.getenv("QUERY_SERVICE_URL", "http://query_service:8000"),
        description="URL del Query Service."
    )
    ingestion_service_url: str = Field(
        os.getenv("INGESTION_SERVICE_URL", "http://ingestion_service:8002"),
        description="URL del Ingestion Service."
    )
    agent_management_url: str = Field(
        os.getenv("AGENT_MANAGEMENT_URL", "http://agent_management_service:8003"),
        description="URL del Agent Management Service."
    )
    conversation_service_url: str = Field(
        os.getenv("CONVERSATION_SERVICE_URL", "http://conversation_service:8004"),
        description="URL del Conversation Service."
    )
    agent_execution_url: str = Field(
        os.getenv("AGENT_EXECUTION_URL", "http://agent_execution_service:8005"),
        description="URL del Agent Execution Service."
    )
    embedding_service_url: str = Field(
        os.getenv("EMBEDDING_SERVICE_URL", "http://embedding_service:8006"),
        description="URL del Embedding Service."
    )
    

    # Qdrant (configurables desde .env)
    qdrant_url: str = Field(
        os.getenv("QDRANT_URL", "http://qdrant:6333"),
        description="URL de conexión a Qdrant."
    )
    qdrant_api_key: Optional[str] = Field(
        os.getenv("QDRANT_API_KEY"),
        description="API key para Qdrant (SI NO SE USA VERSION LOCAL SERVER)."
    )
    
    # Postgres (configurables desde .env)
    postgres_url: str = Field(
        os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@postgres:5432/postgres"),
        description="URL de conexión a Postgres."
    )
    
    # OpenAI (configurables desde .env)
    openai_api_key: Optional[str] = Field(
        os.getenv("OPENAI_API_KEY"),
        description="API key para OpenAI."
    )
    openai_base_url: Optional[str] = Field(
        os.getenv("OPENAI_BASE_URL"),
        description="URL base para API de OpenAI (SI NO SE USA OPEN AI EMBEDDING Y SE USA OTRO EMBEDDINGS)."
    )

    # Groq API Settings (configurables desde .env)
    groq_api_key: str = Field(
        os.getenv("GROQ_API_KEY"),
        description="API Key para Groq (usar variable de entorno GROQ_API_KEY)"
    )
    
    # CORS
    cors_origins: List[str] = Field(
        default=os.getenv("CORS_ORIGINS", "*").split(","),
        description="Orígenes permitidos para CORS."
    )

    @field_validator("cors_origins", mode='before')
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        if isinstance(v, list):
            return v
        return ["*"]

