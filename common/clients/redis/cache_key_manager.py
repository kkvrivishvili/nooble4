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
            context_str = ":".join(str(item) for item in context)
        else:
            context_str = str(context)
            
        return f"{self.prefix}:{self.environment}:{service}:{cache_type}:{context_str}"

    # Métodos específicos para tipos comunes de caché
    
    def get_history_key(self, tenant_id: uuid.UUID, session_id: uuid.UUID, service_name: Optional[str] = None) -> str:
        """
        Obtiene la clave para el historial de conversación.
        Ej: nooble4:dev:agent_execution:history:tenant-uuid:session-uuid
        """
        service = service_name or self.service_name or "agent_execution"
        return self._build_cache_key(service, "history", [str(tenant_id), str(session_id)])
    
    def get_config_key(self, entity_id: uuid.UUID, config_type: str, service_name: Optional[str] = None) -> str:
        """
        Obtiene la clave para configuraciones.
        Ej: nooble4:dev:user_management:config:user:user-uuid
        """
        service = service_name or self.service_name or "user_management"
        return self._build_cache_key(service, "config", [config_type, str(entity_id)])
    
    def get_embedding_key(self, document_id: str, service_name: Optional[str] = None) -> str:
        """
        Obtiene la clave para embeddings.
        Ej: nooble4:dev:embedding_service:embedding:doc-123
        """
        service = service_name or self.service_name or "embedding_service"
        return self._build_cache_key(service, "embedding", document_id)
    
    def get_custom_key(self, cache_type: str, context: Union[str, List[str]], service_name: Optional[str] = None) -> str:
        """
        Obtiene una clave personalizada para cualquier tipo de caché.
        
        Args:
            cache_type: Tipo de caché personalizado
            context: Contexto específico (string o lista de strings)
            service_name: Nombre del servicio (opcional)
            
        Returns:
            La clave de caché formateada
        """
        service = service_name or self.service_name
        if not service:
            raise ValueError("Se requiere service_name para claves personalizadas")
            
        return self._build_cache_key(service, cache_type, context)
