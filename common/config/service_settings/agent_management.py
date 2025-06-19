"""
Definición de la configuración específica para Agent Management Service.
"""
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings # Ajustado para la nueva ubicación

class AgentManagementSettings(CommonAppSettings):
    """Configuración específica para Agent Management Service."""

    model_config = SettingsConfigDict(
        env_prefix='AMS_',
        extra='ignore',
        env_file='.env'
    )
# Campos específicos de AgentManagementSettings o que anulan/especifican valores de CommonAppSettings.
# service_name, environment, log_level, redis_url, http_timeout_seconds son heredados de CommonAppSettings.
# database_url se hereda pero se le da un valor por defecto específico aquí.

    service_version: str = Field("1.0.0", description="Versión del servicio")

    # database_url es heredado de CommonAppSettings, pero aquí especificamos un default particular para AMS.
    # Pydantic tomará este default si AMS_DATABASE_URL no está en el entorno.
    database_url: str = Field(
        "postgresql://user:pass@localhost/nooble_agents", 
        description="URL de base de datos para agentes. Hereda de CommonAppSettings pero con default específico para AMS."
    )

    # Campos específicos del Agent Management Service
    domain_name: str = Field("management", description="Dominio específico para colas y lógica del servicio de gestión de agentes.")


    

    # Configuración de Colas
    callback_queue_prefix: str = Field(
        "agent-management", 
        description="Prefix for callback queues used by AMS."
    )
