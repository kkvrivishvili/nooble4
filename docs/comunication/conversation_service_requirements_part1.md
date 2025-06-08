# Requerimientos y Responsabilidades del Conversation Service (Parte 1)

## Introducción

El Conversation Service es un componente clave en la arquitectura de nooble4 que se encarga de la gestión del historial de conversaciones, integración con sistemas CRM y la persistencia de conversaciones. Este documento detalla los requerimientos, responsabilidades y consideraciones de diseño para implementar correctamente este servicio.

## Responsabilidades Principales

### 1. Gestión del Historial de Conversaciones

El Conversation Service debe ser el repositorio central para el historial completo de todas las conversaciones, proporcionando:

- **Almacenamiento Persistente**: Guardar cada mensaje de la conversación con metadatos relevantes.
- **Consultas Eficientes**: Permitir búsqueda y recuperación rápida por diferentes criterios.

### 2. Integración con CRM

Debe proporcionar una capa de integración con sistemas CRM que permita:

- **Sincronización Bidireccional**: Actualizar sistemas CRM con información relevante de las conversaciones.
- **Enriquecimiento de Perfiles**: Agregar información de conversaciones a perfiles de usuario en CRM.
- **Tracking de Métricas**: Integrar métricas de conversación con análisis de CRM.

### 3. Persistencia de Estado

Debe gestionar el estado persistente de las conversaciones:

- **Estado de Conversación**: Mantener el estado actual de cada conversación activa.
- **Contexto Enriquecido**: Almacenar el contexto completo incluyendo variables de estado.
- **Recuperación de Estado**: Permitir reanudar conversaciones desde el último estado conocido.
- **Manejo de Sesiones**: Vincular sesiones WebSocket con conversaciones persistentes.

### 4. Notificaciones y Eventos

El servicio debe generar y consumir eventos relacionados con conversaciones:

- **Notificaciones de Cambio**: Generar eventos cuando haya cambios en las conversaciones.
- **Integraciones Webhook**: Permitir notificaciones a sistemas externos.
- **Alertas y Escalamiento**: Generar alertas basadas en reglas de negocio.

## Modelo de Datos Propuesto

### Entidades Principales

1. **Conversation**
   ```python
   class Conversation(BaseModel):
       conversation_id: str = Field(default_factory=lambda: str(uuid4()))
       tenant_id: str
       created_at: datetime = Field(default_factory=datetime.now)
       updated_at: datetime = Field(default_factory=datetime.now)
       status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
       metadata: Dict[str, Any] = Field(default_factory=dict)
       tags: List[str] = Field(default_factory=list)
       participants: List[Participant] = Field(default_factory=list)
       
       # Campos CRM
       crm_references: Dict[str, Any] = Field(default_factory=dict)
       customer_info: Optional[Dict[str, Any]] = None
   ```

2. **Message**
   ```python
   class Message(BaseModel):
       message_id: str = Field(default_factory=lambda: str(uuid4()))
       conversation_id: str
       tenant_id: str
       timestamp: datetime = Field(default_factory=datetime.now)
       sender_type: SenderType  # USER, AGENT, SYSTEM
       sender_id: str
       content: str
       content_type: str = "text"  # text, image, file, etc.
       
       # Campos para análisis
       sentiment: Optional[float] = None
       intent: Optional[str] = None
       entities: List[Dict[str, Any]] = Field(default_factory=list)
       
       # Campos para tracking
       agent_id: Optional[str] = None
       model_used: Optional[str] = None
       tokens_used: Optional[int] = None
   ```

3. **ConversationState**
   ```python
   class ConversationState(BaseModel):
       state_id: str = Field(default_factory=lambda: str(uuid4()))
       conversation_id: str
       tenant_id: str
       timestamp: datetime = Field(default_factory=datetime.now)
       state_type: str  # context, memory, variable, etc.
       state_key: str
       state_value: Any
       ttl: Optional[int] = None  # Tiempo de vida en segundos
   ```
