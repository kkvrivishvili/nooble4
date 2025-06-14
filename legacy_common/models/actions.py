"""
Actions: Modelo base para comunicación entre servicios.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4


class DomainAction(BaseModel):
    """
    Acción base para comunicación estandarizada entre servicios.
    Permite definir un formato consistente para todas las acciones
    independientemente del dominio o servicio.
    """
    
    # Identificadores
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: str = Field(..., description="Tipo de acción en formato dominio.accion")
    task_id: str = Field(..., description="ID de la tarea relacionada")
    
    # Contexto - NUEVO
    tenant_id: str = Field(..., description="ID del tenant")

    session_id: Optional[str] = Field(None, description="ID de la sesión si aplica")
    
    # Execution Context - NUEVO
    execution_context: Optional[Dict[str, Any]] = Field(None, description="Contexto de ejecución completo")
    
    # Datos y metadatos
    data: Dict[str, Any] = Field(default_factory=dict, description="Datos específicos de la acción")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")
    
    # Control - NUEVO
    callback_queue: Optional[str] = Field(None, description="Cola para enviar resultados")
    timeout: Optional[int] = Field(None, description="Timeout específico para esta acción")
    
    # Queue metadata - NUEVO (se agrega automáticamente por DomainQueueManager)
    queue_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadatos de encolado")
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp de creación")
    
    def get_domain(self) -> str:
        """Extrae el dominio del action_type."""
        if "." in self.action_type:
            return self.action_type.split(".")[0]
        return "unknown"
    
    def get_action_name(self) -> str:
        """Extrae el nombre de la acción del action_type."""
        if "." in self.action_type:
            return self.action_type.split(".", 1)[1]
        return self.action_type
    
    def get_execution_context(self) -> Optional['ExecutionContext']:
        """
        Obtiene el execution context como objeto tipado.
        
        Returns:
            ExecutionContext o None si no está disponible
        """
        if not self.execution_context:
            return None
            
        from .execution_context import ExecutionContext
        return ExecutionContext.from_dict(self.execution_context)