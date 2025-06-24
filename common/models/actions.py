from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict
import uuid
from datetime import datetime, timezone

# Import de configuraciones específicas
from .config_models import ExecutionConfig, QueryConfig, RAGConfig

# Modelo de Error, alineado con standart_payload.md
class ErrorDetail(BaseModel):
    """
    Representa los detalles de un error ocurrido durante el procesamiento de una acción.
    """
    error_type: str = Field(..., description="Tipo de error general legible por humanos. Ej: 'NotFound', 'ValidationError', 'InternalError', 'AuthenticationError'.")
    error_code: Optional[str] = Field(None, description="Código de error específico de la lógica de negocio, útil para la programática. Ej: 'AGENT_NOT_FOUND', 'INVALID_INPUT_PARAMETER'.")
    message: str = Field(..., description="Mensaje descriptivo del error, orientado al desarrollador o para logs detallados.")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detalles adicionales estructurados sobre el error, como campos fallidos en una validación.")

# Modelo de Acción Principal, alineado con standart_payload.md
class DomainAction(BaseModel):
    """
    Representa una acción o comando a ser ejecutado dentro del dominio del sistema.
    Es el mensaje estándar para la comunicación entre servicios.
    """
    action_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador único universal (UUID) de esta instancia de acción específica.")
    action_type: str = Field(..., description='Tipo de acción en formato "servicio_destino.entidad.verbo". Ej: "management.agent.get_config", "embedding.document.process". Define la operación a realizar.')
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp UTC de la creación de la acción.")
    
    # --- Contexto de Negocio y Enrutamiento ---
    # Estos IDs son cruciales para la lógica de negocio, auditoría y enrutamiento.
    tenant_id: uuid.UUID = Field(..., description="Identificador del tenant (inquilino) al que pertenece esta acción. Obligatorio para sistemas multi-tenant.")
    session_id: uuid.UUID = Field(..., description="Identificador de la sesión de usuario o conversación. Agrupa varias tareas (task_id) dentro de una interacción continua.")
    task_id: uuid.UUID = Field(..., description="Identificador único universal (UUID) para una tarea de alto nivel iniciada por el usuario o sistema (ej. una petición de chat completa). Agrupa múltiples action_id y correlation_id internos.")
    user_id: Optional[uuid.UUID] = Field(None, description="Identificador del usuario que originó la acción, si aplica (ej. no presente para acciones de sistema).")
    agent_id: uuid.UUID = Field(..., description="Identificador del agente que procesa o está asociado con esta acción.")
    
    # --- Información de Origen y Seguimiento ---
    origin_service: str = Field(..., description="Nombre del servicio que emite/origina esta acción. Ej: 'orchestrator-service', 'api-gateway'.")
    correlation_id: Optional[uuid.UUID] = Field(None, description="ID para correlacionar esta acción con una acción previa (si es parte de una cadena) o con su futura respuesta (en patrones pseudo-síncronos). ÚNICO por cada request-response o salto en la cadena.")
    trace_id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, description="ID de rastreo distribuido (span ID o trace ID principal) para seguir la solicitud a través de múltiples servicios. Usado por sistemas de observabilidad.")

    # --- Para Callbacks (Comunicación Asíncrona con Respuesta Diferida) ---
    callback_queue_name: Optional[str] = Field(None, description="Nombre de la cola Redis donde se espera la respuesta/callback (para patrones pseudo-síncronos o async con callback).")
    callback_action_type: Optional[str] = Field(None, description="El action_type que tendrá el mensaje de callback/respuesta.")

    # --- Configuraciones por Servicio ---
    execution_config: Optional[ExecutionConfig] = Field(None, description="Configuración específica para Agent Execution Service")
    query_config: Optional[QueryConfig] = Field(None, description="Configuración específica para Query Service") 
    rag_config: Optional[RAGConfig] = Field(None, description="Configuración específica para RAG en Query Service")

    # --- Payload y Metadatos ---
    data: Dict[str, Any] = Field(..., description="Payload específico de la acción, serializado como un diccionario. El servicio receptor es responsable de deserializar y validar este diccionario en un modelo Pydantic específico basado en el 'action_type'. Este campo contiene los datos primarios necesarios para ejecutar la acción.")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos adicionales opcionales para la acción. Puede usarse para pasar parámetros de configuración específicos de la solicitud (ej. selección de modelo de IA, flags de características) que pueden anular los valores predeterminados del servicio. Los servicios deben estar diseñados para funcionar con sus propios valores predeterminados si 'metadata' o claves específicas dentro de él no se proporcionan.")

    model_config = ConfigDict(populate_by_name=True, extra='allow', validate_assignment=True)

# Modelo de Respuesta, alineado con standart_payload.md
class DomainActionResponse(BaseModel):
    """
    Representa la respuesta a una DomainAction, típicamente en un flujo pseudo-síncrono.
    """
    action_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Identificador único universal (UUID) de esta instancia de respuesta específica. NO es el action_id de la DomainAction original.")
    correlation_id: uuid.UUID = Field(..., description="DEBE coincidir con el correlation_id de la DomainAction original a la que esta respuesta corresponde, para enlazar solicitud y respuesta.")
    
    # --- Contexto propagado de la acción original ---
    # Útil para que el receptor de la respuesta mantenga el contexto sin tener que cachearlo.
    trace_id: uuid.UUID = Field(..., description="DEBE coincidir con el trace_id de la DomainAction original.")
    task_id: uuid.UUID = Field(..., description="DEBE coincidir con el task_id de la DomainAction original.")
    tenant_id: uuid.UUID = Field(..., description="DEBE coincidir con el tenant_id de la DomainAction original.")
    session_id: uuid.UUID = Field(..., description="DEBE coincidir con el session_id de la DomainAction original.")
    # user_id: Optional[str] = Field(None, description="Opcional: DEBE coincidir con el user_id de la DomainAction original, si es relevante para el receptor de la respuesta.")


    success: bool = Field(..., description="Indica si la acción fue procesada exitosamente.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp UTC de la creación de la respuesta.")
    
    data: Optional[Dict[str, Any]] = Field(None, description="Payload de respuesta si success=True. Su estructura puede ser validada por un modelo Pydantic dedicado.")
    error: Optional[ErrorDetail] = Field(None, description="Detalles del error si success=False. Ver modelo ErrorDetail.")

    @model_validator(mode='after')
    def check_data_and_error(self) -> 'DomainActionResponse':
        # En Pydantic V2 con mode='after', los campos ya están asignados a self
        # No es necesario acceder a 'values' como un diccionario.
        # success, data, error = self.success, self.data, self.error
        
        if self.success:
            if self.error is not None:
                raise ValueError("El campo 'error' debe ser nulo si 'success' es True.")
            # Opcional: Requerir 'data' en caso de éxito, o permitir que sea None/{}
            # if data is None: # Si quieres que data siempre exista, incluso como {}
            #     raise ValueError("El campo 'data' no puede ser nulo si 'success' es True. Usar {} si no hay datos.")
        else: # not self.success
            if self.error is None:
                raise ValueError("El campo 'error' es obligatorio y no puede ser nulo si 'success' es False.")
            # Opcional: asegurar que data sea nulo si hay error
            # if data is not None:
            #     raise ValueError("El campo 'data' debe ser nulo si 'success' es False.")
        return self

    model_config = ConfigDict(populate_by_name=True, extra='allow', validate_assignment=True)
