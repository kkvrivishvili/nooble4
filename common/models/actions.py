from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, root_validator
import uuid
from datetime import datetime, timezone

# Modelo de Error, alineado con standart_payload.md
class ErrorDetail(BaseModel):
    error_type: str = Field(..., description="Tipo de error general. Ej: 'NotFound', 'ValidationError', 'InternalError'.")
    error_code: Optional[str] = Field(None, description="Código de error específico de la lógica de negocio. Ej: 'AGENT_NOT_FOUND'.")
    message: str = Field(..., description="Mensaje descriptivo del error, orientado al desarrollador.")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detalles adicionales estructurados.")

# Modelo de Acción Principal, alineado con standart_payload.md
class DomainAction(BaseModel):
    action_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador único de esta acción específica.")
    action_type: str = Field(..., description='Tipo de acción en formato "servicio_destino.entidad.verbo". Ej: "management.agent.get_config".')
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp UTC de creación de la acción.")
    
    # --- Contexto de Negocio y Enrutamiento ---
    tenant_id: Optional[str] = Field(None, description="Identificador del tenant al que pertenece esta acción.")
    user_id: Optional[str] = Field(None, description="Identificador del usuario que originó la acción, si aplica.")
    session_id: Optional[str] = Field(None, description="Identificador de la sesión de conversación.")
    
    # --- Información de Origen y Seguimiento ---
    origin_service: Optional[str] = Field(None, description="Nombre del servicio que emite la acción.")
    correlation_id: Optional[uuid.UUID] = Field(None, description="ID para correlacionar esta acción con otras en un flujo o con una respuesta.")
    trace_id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, description="ID de rastreo para seguir la solicitud a través de múltiples servicios.")

    # --- Para Callbacks ---
    callback_queue_name: Optional[str] = Field(None, description="Nombre de la cola Redis donde se espera el callback.")
    callback_action_type: Optional[str] = Field(None, description="El action_type que tendrá el mensaje de callback.")

    # --- Payload y Metadatos ---
    data: Dict[str, Any] = Field(..., description="Payload específico de la acción, validado por un modelo Pydantic dedicado.")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos adicionales no críticos para la lógica principal.")

    class Config:
        validate_assignment = True

# Modelo de Respuesta, alineado con standart_payload.md
class DomainActionResponse(BaseModel):
    action_id: uuid.UUID = Field(..., description="ID de la DomainAction original a la que esta respuesta corresponde.")
    correlation_id: uuid.UUID = Field(..., description="DEBE coincidir con el correlation_id de la DomainAction original.")
    trace_id: uuid.UUID = Field(..., description="DEBE coincidir con el trace_id de la DomainAction original.")
    
    success: bool = Field(..., description="Indica si la acción fue procesada exitosamente.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp UTC de creación de la respuesta.")
    
    data: Optional[Dict[str, Any]] = Field(None, description="Payload de respuesta si success=True.")
    error: Optional[ErrorDetail] = Field(None, description="Detalles del error si success=False.")

    @root_validator
    def check_data_and_error(cls, values):
        success, data, error = values.get('success'), values.get('data'), values.get('error')
        if success and error is not None:
            raise ValueError("El campo 'error' debe ser nulo si 'success' es True.")
        if not success and error is None:
            raise ValueError("El campo 'error' es obligatorio si 'success' es False.")
        # Opcional: requerir 'data' en caso de éxito, dependiendo de la acción
        # if success and data is None:
        #     raise ValueError("El campo 'data' no puede ser nulo si 'success' es True.")
        return values

