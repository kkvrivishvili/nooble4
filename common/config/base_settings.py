from typing import Dict, Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

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
    redis_decode_responses: bool = Field(True, description="Decodificar respuestas de Redis a UTF-8.")
    redis_socket_connect_timeout: int = Field(5, description="Timeout en segundos para la conexión del socket de Redis.")
    redis_socket_keepalive: bool = Field(True, description="Habilitar keepalive para el socket de Redis.")
    redis_socket_keepalive_options: Optional[Dict[str, int]] = Field(None, description="Opciones de keepalive para el socket de Redis.")
    redis_max_connections: int = Field(10, description="Número máximo de conexiones en el pool de Redis.")
    redis_health_check_interval: int = Field(30, description="Intervalo en segundos para el health check de Redis.")
    
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
    

    # Qdrant (configurables desde .env)
    qdrant_url: str = Field("http://localhost:6333", description="URL de conexión a Qdrant.")
    qdrant_api_key: Optional[str] = Field(None, description="API key para Qdrant (SI NO SE USA VERSION LOCAL SERVER).")
    
    # Postgres (configurables desde .env)
    postgres_url: str = Field("postgresql://postgres:postgres@localhost:5432/nooble", description="URL de conexión a Postgres.")
    
    # OpenAI (configurables desde .env)
    openai_api_key: Optional[str] = Field(None, description="API key para OpenAI.")
    openai_base_url: Optional[str] = Field(None, description="URL base para API de OpenAI (SI NO SE USA OPEN AI EMBEDDING Y SE USA OTRO EMBEDDINGS).")

    # Groq API Settings (configurables desde .env)
    groq_api_key: str = Field(..., description="API Key para Groq (usar variable de entorno QUERY_GROQ_API_KEY)")
    
    # CORS
    cors_origins: List[str] = Field(default=["*"], description="Orígenes permitidos para CORS.")

    @field_validator("cors_origins", mode='before')
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        if isinstance(v, list):
            return v
        return ["*"]

