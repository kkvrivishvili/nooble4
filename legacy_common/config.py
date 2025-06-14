"""
Configuración base para todos los servicios.
"""

import os
from typing import Dict, Any
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
    
    # HTTP
    http_timeout_seconds: int = Field(30, description="Timeout HTTP")
    
    class Config:
        env_file = ".env"

def get_service_settings(service_name: str) -> Dict[str, Any]:
    """
    Obtiene configuración base para un servicio específico.
    
    Args:
        service_name: Nombre del servicio
        
    Returns:
        Dict con configuración base
    """
    return {
        "service_name": service_name,
        "service_version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "database_url": os.getenv("DATABASE_URL", ""),
        "http_timeout_seconds": int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
    }
