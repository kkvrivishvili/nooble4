"""
Configuración base común para todos los servicios Nooble4, utilizando pydantic-settings.
"""
from typing import Optional

from pydantic import Field
# Asegúrate de tener pydantic-settings instalado: pip install pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict

class CommonAppSettings(BaseSettings):
    """Configuración base común para todos los servicios Nooble4."""
    
    # model_config se usa en Pydantic V2+ en lugar de la clase interna Config.
    # Define cómo se cargan las variables de entorno y los archivos .env.
    # 'extra='ignore'' permite que no fallen las settings si hay variables de entorno extra.
    # 'env_file='.env'' indica que se intente cargar un archivo .env.
    # No se define env_prefix aquí; cada servicio lo especificará en su propia model_config.
    model_config = SettingsConfigDict(extra='ignore', env_file='.env')

    service_name: str = Field(..., description="Nombre del servicio (ej: 'agent-orchestrator-service'). Este campo es requerido y debe ser provisto por cada servicio, ya sea como variable de entorno (ej. MI_SERVICIO_SERVICE_NAME) o al instanciar las settings específicas del servicio.")
    environment: str = Field("development", description="Entorno de ejecución (development, staging, production).")
    log_level: str = Field("INFO", description="Nivel de logging (DEBUG, INFO, WARNING, ERROR).")

    # Configuración de Redis
    redis_url: str = Field("redis://localhost:6379/0", description="URL de conexión a Redis completa (ej: redis://user:password@host:port/db).")
    # Los siguientes campos pueden ser inferidos de redis_url o especificados directamente.
    # Pydantic no los inferirá automáticamente; se necesitaría lógica custom con @field_validator si se desea esa inferencia.
    # Por ahora, se definen como opcionales o con defaults si redis_url no es suficiente.
    redis_host: str = Field("localhost", description="Host de Redis.")
    redis_port: int = Field(6379, description="Puerto de Redis.")
    redis_db: int = Field(0, description="Número de base de datos Redis.")
    redis_password: Optional[str] = Field(None, description="Contraseña de Redis (si es requerida).")

    # Configuración de Base de Datos (opcional, si el servicio la requiere)
    database_url: Optional[str] = Field(None, description="URL de conexión a la base de datos principal (ej: postgresql://user:pass@host:port/dbname).")

    # Otros campos comunes podrían incluir:
    # http_timeout_seconds: int = Field(30, description="Timeout para llamadas HTTP salientes.")
    # jwt_secret_key: Optional[str] = Field(None, description="Clave secreta para JWT si se usa autenticación centralizada.")

# Nota: La función get_service_settings() que existía previamente para cargar manualmente
# las variables de entorno ya no es necesaria si se sigue este patrón de herencia
# y Pydantic BaseSettings se utiliza correctamente en cada servicio.
# Cada servicio instanciará su propia clase de settings (que hereda de CommonAppSettings)
# y Pydantic se encargará de cargar las variables de entorno usando el `env_prefix`
# definido en la `model_config` del servicio específico.
