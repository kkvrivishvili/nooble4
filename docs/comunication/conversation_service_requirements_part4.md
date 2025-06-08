# Requerimientos y Responsabilidades del Conversation Service (Parte 4)

## Integración con la Arquitectura Nooble4

Basado en el análisis de los servicios existentes, el Conversation Service debe integrarse en la arquitectura global de nooble4 considerando:

### Relaciones con Servicios Existentes

1. **Agent Orchestrator Service**:
   - El Agent Orchestrator maneja WebSockets para comunicación en tiempo real
   - El Conversation Service debe recibir notificaciones de nuevos mensajes y actualizaciones
   - Debe existir sincronización con el estado de las sesiones WebSocket

2. **Agent Execution Service**:
   - Mientras Agent Execution ejecuta agentes con LangChain
   - Conversation Service debe recibir y almacenar los resultados de estas ejecuciones
   - Debe mantener el historial completo de interacciones del agente

3. **Agent Management Service**:
   - La configuración de agentes proviene del Agent Management
   - Conversation Service debe referenciar correctamente agentes y templates
   - Debe respetar los límites y validaciones por tier definidos en Agent Management

4. **Query Service**:
   - Las consultas RAG se realizan a través del Query Service
   - Conversation Service debe almacenar metadatos de las consultas realizadas
   - Debe mantener referencia a documentos recuperados en respuestas RAG

5. **Embedding Service**:
   - Conversation Service debe coordinar con Embedding Service para análisis de conversaciones
   - Puede solicitar embeddings para análisis semántico del historial

### Flujo de Domain Actions

El Conversation Service debe implementar Domain Actions específicas para:

```python
class ConversationDomainAction(DomainAction):
    """Domain Action base para operaciones de conversación."""
    conversation_id: str
    # Campos comunes heredados de DomainAction
    
class StoreMessageAction(ConversationDomainAction):
    """Almacena un mensaje en la conversación."""
    message: Dict[str, Any]
    sender_type: str
    sender_id: str
    content: str
    content_type: str = "text"
    
class SyncCrmAction(ConversationDomainAction):
    """Sincroniza información con CRM."""
    crm_type: str
    crm_entity_id: Optional[str] = None
    conversation_summary: Dict[str, Any]
    customer_info: Dict[str, Any]
    
class AnalyzeConversationAction(ConversationDomainAction):
    """Solicita análisis de la conversación."""
    analysis_type: str  # sentiment, intent, topic, etc.
    messages: List[Dict[str, Any]]
```

### Sistema de Colas y Callbacks

Siguiendo el patrón de otros servicios, el Conversation Service debe implementar:

```python
# En ConversationService
self.queue_manager = DomainQueueManager(
    redis_client=self.redis_client,
    domain="conversation",
    tenant_id=tenant_id,
    tenant_tier=tenant_tier
)

# Encolar acción
await self.queue_manager.enqueue_action(
    tier="standard",  # O tier específico del tenant
    action=StoreMessageAction(
        task_id=str(uuid4()),
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        message={...}
    ),
    callbacks=[
        {
            "queue": f"orchestrator.{tenant_id}.callbacks",
            "action_type": "conversation.message_stored"
        }
    ]
)
```

## Objetivos de Implementación

### Características Mínimas (MVP)

1. **CRUD Básico de Conversaciones**:
   - Crear, leer, actualizar y eliminar conversaciones
   - Almacenar mensajes con metadatos básicos
   - API REST para acceso a conversaciones

2. **Persistencia en MongoDB**:
   - Modelo de datos para conversaciones y mensajes
   - Índices optimizados para consultas frecuentes
   - Arquitectura multi-tenant segura

3. **Integración con Servicios Core**:
   - Recibir mensajes del Agent Orchestrator
   - Almacenar resultados del Agent Execution
   - Mantener referencias a configuraciones del Agent Management

### Características Avanzadas

1. **Análisis Semántico**:
   - Detección de sentimiento por mensaje
   - Clasificación de intenciones
   - Extracción de entidades y conceptos clave
   - Resúmenes automáticos de conversaciones

2. **Integración CRM Completa**:
   - Conectores para Salesforce, HubSpot, y sistemas propietarios
   - Sincronización bidireccional de datos
   - Mapeo configurable de campos

3. **Alertas y Notificaciones**:
   - Sistema de reglas para generar alertas
   - Notificaciones en tiempo real de eventos importantes
   - Integración con sistemas de ticketing

4. **Búsqueda Avanzada**:
   - Búsqueda semántica en el historial de conversaciones
   - Filtrado multi-criterio con facetas
   - Exportación de resultados en múltiples formatos

## Métricas y Monitoreo

El servicio debe implementar métricas para:

1. **Rendimiento**:
   - Tiempo de respuesta en operaciones CRUD
   - Latencia en procesamiento de mensajes
   - Tasa de throughput por tenant

2. **Almacenamiento**:
   - Volumen de mensajes por tenant/conversación
   - Crecimiento de datos por periodo
   - Utilización de almacenamiento por tenant

3. **Operaciones**:
   - Tasa de fallos en operaciones de escritura/lectura
   - Errores en sincronización con CRM
   - Uso de caché (hit ratio)

4. **Negocio**:
   - Duración promedio de conversaciones
   - Mensajes por conversación
   - Tiempo de respuesta humano vs agente

## Conclusiones y Próximos Pasos

El Conversation Service es un componente estratégico para nooble4 que completa la arquitectura de servicios existente, proporcionando persistencia y análisis de conversaciones. 

### Recomendaciones Técnicas

1. Seguir los patrones arquitectónicos establecidos por servicios existentes:
   - Comunicación asíncrona mediante Domain Actions
   - Validación por tier con límites específicos
   - Sistema de colas y callbacks para procesamiento

2. Establecer un plan de migración gradual:
   - Comenzar con almacenamiento en MongoDB para flexibilidad de esquema
   - Implementar caché en Redis para mejorar rendimiento
   - Considerar migración futura a PostgreSQL para consistencia con otros servicios

3. Priorizar seguridad y aislamiento multi-tenant:
   - Encriptación de datos sensibles
   - Estricta validación de acceso por tenant_id
   - Auditoría completa de operaciones

### Plan de Implementación Sugerido

1. **Fase 1 (MVP)**: 
   - Implementar modelo de datos y persistencia básica
   - Desarrollar API REST para CRUD de conversaciones
   - Integrar con Agent Orchestrator para recepción de mensajes

2. **Fase 2 (Integración)**:
   - Implementar sincronización con servicios existentes
   - Desarrollar worker para procesamiento asíncrono
   - Añadir caché para optimización de rendimiento

3. **Fase 3 (Análisis)**:
   - Implementar análisis básico de conversaciones
   - Desarrollar integración CRM inicial
   - Añadir búsqueda y filtrado avanzado

4. **Fase 4 (Optimización)**:
   - Implementar sistema completo de métricas
   - Optimizar rendimiento y escalabilidad
   - Añadir características avanzadas por tier
