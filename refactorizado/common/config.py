"""
Configuración base para todos los servicios.
"""

import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    """Configuración base para todos los servicios."""
    
    # Configuración básica
    service_name: str = Field(..., description="Nombre del servicio")
    service_version: str = Field("1.0.0", description="Versión del servicio")
    log_level: str = Field("INFO", description="Nivel de logging")
    
    # Redis
    redis_url: str = Field("redis://localhost:6379", description="URL de Redis")
    
    # Database (si aplica)
    database_url: str = Field("", description="URL de base de datos")
    
    class Config:
        env_file = ".env"
        extra = 'ignore' # Ignorar variables de entorno extra que no mapean a campos
