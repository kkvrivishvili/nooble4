from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl

class CommonAppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

    # Identificación y Entorno del Servicio
    service_name: str = Field(..., description="Nombre del servicio, ej: 'agent-orchestrator'. Requerido.")
    service_version: str = Field("0.1.0", description="Versión del servicio.")
    environment: str = Field("development", description="Entorno de ejecución (development, staging, production).")
    log_level: str = Field("INFO", description="Nivel de logging (DEBUG, INFO, WARNING, ERROR).")
    enable_telemetry: bool = Field(False, description="Habilitar telemetría y seguimiento distribuido.")

    # Configuración HTTP Común
    http_timeout_seconds: int = Field(30, description="Timeout global para clientes HTTP salientes.")
    max_retries: int = Field(3, description="Número máximo de reintentos para operaciones críticas.")
    worker_sleep_seconds: float = Field(0.1, description="Tiempo de espera para los workers entre ciclos de polling.")


    # Configuración de API Key (para proteger los propios endpoints del servicio)
    api_key_header_name: str = Field("X-API-Key", description="Nombre de la cabecera para la API key de acceso al servicio.")

    # Configuración de Redis
    redis_url: Optional[str] = Field(None, description="URL de conexión a Redis completa (ej. redis://user:pass@host:port/db?ssl_cert_reqs=required). Si se provee, otras variables redis_* pueden ser ignoradas.")
    redis_host: str = Field("localhost", description="Host de Redis.")
    redis_port: int = Field(6379, description="Puerto de Redis.")
    redis_password: Optional[str] = Field(None, description="Contraseña de Redis.")
    redis_db: int = Field(0, description="Número de la base de datos Redis.")
    redis_use_ssl: bool = Field(False, description="Usar SSL para la conexión a Redis.")
    redis_socket_connect_timeout: int = Field(5, description="Timeout en segundos para la conexión del socket Redis.")
    redis_max_connections: Optional[int] = Field(None, description="Número máximo de conexiones en el pool de Redis.")
    redis_health_check_interval: int = Field(30, description="Intervalo en segundos para el health check de la conexión Redis.")
    redis_socket_keepalive: bool = Field(True, description="Habilitar SO_KEEPALIVE en los sockets de Redis.")
    redis_socket_keepalive_options: Optional[Dict[int, Union[int, bytes]]] = Field(
        default_factory=dict, 
        description="Opciones específicas de TCP Keepalive para los sockets de Redis (e.g., TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT). Dejar vacío para usar defaults del OS."
    )
    redis_decode_responses: bool = Field(True, description="Decodificar automáticamente las respuestas de Redis a UTF-8.")

    # Configuración de Base de Datos (Opcional por servicio)
    database_url: Optional[str] = Field(None, description="URL de conexión a la base de datos principal (ej. PostgreSQL, MySQL).")
