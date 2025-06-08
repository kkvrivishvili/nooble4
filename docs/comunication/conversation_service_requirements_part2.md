# Requerimientos y Responsabilidades del Conversation Service (Parte 2)

## Arquitectura e Integración

### Integración con otros Servicios

El Conversation Service debe integrarse con los demás servicios de nooble4:

1. **Agent Orchestrator Service**:
   - Recibir notificaciones de nuevos mensajes vía WebSocket
   - Proporcionar historial de conversaciones para contexto
   - Almacenar mensajes enviados a través del WebSocket

2. **Agent Execution Service**:
   - Recibir información sobre la ejecución de agentes
   - Almacenar resultados de ejecución como parte del historial
   - Proporcionar contexto de conversaciones previas

3. **Query Service**:
   - Almacenar consultas y respuestas RAG
   - Vincular fuentes documentales con mensajes de la conversación

4. **Servicios CRM**:
   - Sincronizar información con sistemas CRM externos
   - Consultar información de clientes para enriquecer contexto

```
Frontend <--> Agent Orchestrator <--> Conversation Service <--> Base de Datos
                   |                         |
                   v                         v
          Agent Execution Service         Sistemas CRM
                   |
                   v
           Query/Embedding Service
```

### API y Endpoints Principales

El servicio debe exponer los siguientes endpoints:

```python
# Routes para conversaciones
@router.post("/api/v1/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Crea una nueva conversación."""
    
@router.get("/api/v1/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Obtiene detalles de una conversación específica."""
    
@router.get("/api/v1/conversations", response_model=ConversationListResponse)
async def list_conversations(
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    user_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    tags: Optional[List[str]] = Query(None),
    page: int = Query(1, gt=0),
    page_size: int = Query(20, gt=0, le=100)
):
    """Lista conversaciones con filtrado y paginación."""
    
# Routes para mensajes
@router.post("/api/v1/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: str,
    message: CreateMessageRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Añade un nuevo mensaje a la conversación."""
    
@router.get("/api/v1/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    from_timestamp: Optional[datetime] = Query(None),
    limit: int = Query(50, gt=0, le=100)
):
    """Obtiene mensajes de una conversación con paginación."""
    
# Routes para estados de conversación
@router.post("/api/v1/conversations/{conversation_id}/state", response_model=StateResponse)
async def update_conversation_state(
    conversation_id: str,
    state: UpdateStateRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Actualiza el estado de una conversación."""
    
@router.get("/api/v1/conversations/{conversation_id}/state/{state_key}", response_model=StateResponse)
async def get_conversation_state(
    conversation_id: str,
    state_key: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Obtiene un valor específico del estado de una conversación."""
```

### Worker para Procesamiento Asíncrono

El servicio debe incluir workers para procesar eventos y acciones relacionadas con las conversaciones:

```python
class ConversationWorker(BaseWorker):
    """Worker para procesar acciones relacionadas con conversaciones."""
    
    def __init__(self, redis_client=None, action_processor=None, db_client=None, crm_client=None):
        super().__init__(redis_client, action_processor)
        self.db = db_client
        self.crm = crm_client
        
        # Registrar handlers
        self.action_processor.register_handler(
            "conversation.create",
            self._handle_create_conversation
        )
        self.action_processor.register_handler(
            "conversation.add_message",
            self._handle_add_message
        )
        self.action_processor.register_handler(
            "conversation.update_state",
            self._handle_update_state
        )
        self.action_processor.register_handler(
            "conversation.sync_crm",
            self._handle_sync_crm
        )
```
