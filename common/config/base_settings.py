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
