"""
Este módulo proporciona una clase para generar claves de caché Redis de manera consistente y centralizada.

Clases:
- CacheKeyManager: Genera claves de caché estandarizadas para diferentes tipos de datos y servicios.
"""

from typing import Optional, List, Union
import uuid

class CacheKeyManager:
    """
    Genera claves de caché Redis estandarizadas.

    La estructura de claves sigue el patrón:
    `{prefix}:{environment}:{service_name}:{cache_type}:{context}`
    """
    def __init__(self, prefix: str = "nooble4", environment: Optional[str] = None, service_name: Optional[str] = None):
        self.prefix = prefix
        self.environment = environment or "dev"
        self.service_name = service_name

    def _build_cache_key(self, service_name: str, cache_type: str, context: Union[str, List[str]]) -> str:
        """
        Construye la clave de caché con el formato estandarizado.
        
        Args:
            service_name: Nombre del servicio (ej: "agent_execution")
            cache_type: Tipo de caché (ej: "history", "config", "embedding")
            context: Contexto específico, puede ser un string o una lista de strings
                    que se unirán con ":"
                    
        Returns:
            La clave de caché formateada
        """
        # Usar el service_name proporcionado o el predeterminado
        service = service_name or self.service_name
        if not service:
            raise ValueError("Se requiere service_name")
            
        # Convertir el contexto a string si es una lista
        if isinstance(context, list):
            context_str = ":".join(context)
        else:
            context_str = str(context)
        
        return f"{self.prefix}:{self.environment}:{service}:{cache_type}:{context_str}"
    
    def get_cache_key(self, cache_type: str, context: Union[str, List[str]], service_name: Optional[str] = None) -> str:
        """
        Obtiene una clave de caché genérica para cualquier tipo de datos.
        
        Args:
            cache_type: Tipo de caché (ej: "history", "config", "embedding", "session", etc.)
            context: Contexto específico (string o lista de strings)
            service_name: Nombre del servicio (opcional, usa el predeterminado si no se proporciona)
            
        Returns:
            Clave de caché estandarizada
            
        Ejemplos:
            get_cache_key("history", ["tenant-uuid", "session-uuid", "agent-uuid"])
            -> "nooble4:dev:agent_execution:history:tenant-uuid:session-uuid:agent-uuid"
            
            get_cache_key("config", "user-uuid")
            -> "nooble4:dev:agent_execution:config:user-uuid"
        """
        service = service_name or self.service_name or "agent_execution"
        return self._build_cache_key(service, cache_type, context)
