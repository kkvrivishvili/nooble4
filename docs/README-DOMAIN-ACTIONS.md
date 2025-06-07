# Arquitectura de Domain Actions

## Descripción General

La arquitectura de Domain Actions implementa un sistema estandarizado para la comunicación entre microservicios, utilizando un formato unificado de acciones y un sistema de procesamiento centralizado. Esta arquitectura:

- Permite una comunicación estructurada y consistente entre servicios
- Facilita la extensibilidad y el mantenimiento del código
- Soporta procesamiento asíncrono y multi-tenant
- Separa claramente las responsabilidades de cada componente

## Componentes Principales

### 1. Modelos de Domain Actions

La base de toda la arquitectura son las clases de acciones que extienden el modelo base `DomainAction`:

```python
# Ejemplo de definición de acción
class AgentExecutionAction(DomainAction):
    action_type: str = "execution.agent_run"
    agent_id: UUID
    session_id: str
    message: str
    # ...
```

Cada acción tiene un tipo único y contiene todos los datos necesarios para su procesamiento.

### 2. Action Processor

El `ActionProcessor` centraliza el registro y procesamiento de acciones:

```python
# Registrar handler
action_processor.register_handler("execution.agent_run", execution_handler.handle_agent_run)

# Procesar acción
result = await action_processor.process(action)

# Encolar acción
await action_processor.enqueue_action(action)
```

### 3. Base Worker

La clase `BaseWorker` abstrae el trabajo de monitoreo y procesamiento de colas:

```python
# Extender BaseWorker
class DomainExecutionWorker(BaseWorker):
    def get_queue_names(self) -> List[str]:
        return ["execution.*.actions"]
        
    def create_action_from_data(self, action_data: Dict) -> DomainAction:
        # ...
```

### 4. Handlers Específicos

Los handlers implementan la lógica de procesamiento para cada tipo de acción:

```python
class ExecutionHandler:
    async def handle_agent_run(self, action: AgentExecutionAction) -> Dict[str, Any]:
        # Implementación específica
        return {"success": True, "result": {...}}
```

## Estructura de Carpetas

La arquitectura se implementa siguiendo esta estructura de carpetas limpia y optimizada:

```plaintext
common/
├── models/
│   └── actions.py         # Modelo base DomainAction
├── services/
│   └── action_processor.py # Procesador central de acciones
└── workers/
    └── base_worker.py     # Worker base para procesar acciones

agent_execution_service/
├── models/
│   ├── actions.py        # AgentExecutionAction, ExecutionCallbackAction
│   └── execution.py
├── handlers/
│   └── handlers.py
└── workers/
    └── execution_worker.py

agent_orchestrator_service/
├── models/
│   ├── actions.py        # Orchestration Domain Actions
│   └── websocket.py
├── handlers/
│   └── handlers.py
└── workers/
    └── orchestrator_worker.py

embedding_service/
├── clients/
│   └── openai_client.py
├── config/
│   └── settings.py
├── handlers/
│   └── embedding_handler.py
├── models/
│   └── actions.py
└── workers/
    └── embedding_worker.py

query_service/
├── clients/
│   ├── groq_client.py
│   ├── vector_store_client.py
│   └── embedding_client.py
├── config/
│   └── settings.py
├── handlers/
│   ├── query_handler.py
│   └── embedding_callback_handler.py
├── models/
│   └── actions.py
└── workers/
    └── query_worker.py

ingestion_service/
├── clients/
│   └── some_client.py    # e.g. HTTP clients
├── config/
│   └── settings.py
├── handlers/
│   └── handlers.py
├── models/
│   └── actions.py        # Ingestion Domain Actions
├── routes/
│   └── api_routes.py
├── services/
│   └── ingestion_service.py
└── workers/
    └── ingestion_worker.py
```

## Flujo de Datos

1. **API/WebSocket recibe una petición** y crea una Domain Action correspondiente
2. La acción se encola en Redis usando `action_processor.enqueue_action()`
3. El **BaseWorker** monitora las colas y recupera acciones pendientes
4. El worker extrae la acción y la envía al **ActionProcessor** para procesamiento
5. El **ActionProcessor** invoca el handler correspondiente para ese tipo de acción
6. El **handler** implementa la lógica específica y devuelve un resultado
7. Si hay una cola de callback, se encola el resultado para que otro servicio lo procese

## Mejores Prácticas

- **Nomenclatura de acciones**: Usar `dominio.accion` (ej: `execution.agent_run`)
- **Nombres de colas**: Usar formato `dominio.tenant_id.actions` (ej: `execution.tenant123.actions`)
- **Acciones autosuficientes**: Cada acción debe contener todos los datos necesarios
- **Registro centralizado**: Los handlers deben registrarse al iniciar la aplicación
- **Error handling**: Siempre manejar excepciones en handlers y enviar callbacks de error
- **Logging**: Registrar información relevante en cada paso del procesamiento

## Ventajas de la Nueva Arquitectura

1. **Estandarización**: Formato único para toda comunicación entre servicios
2. **Desacoplamiento**: Servicios independientes que se comunican a través de acciones
3. **Claridad**: Cada tipo de acción tiene un handler específico y bien definido
4. **Extensibilidad**: Fácil añadir nuevos tipos de acciones y handlers
5. **Multi-tenant**: Soporte integrado para múltiples tenants con aislamiento
6. **Monitoreo**: Facilita la observabilidad del sistema

## Ejemplo de Uso

```python
# 1. Crear una acción
action = AgentExecutionAction(
    tenant_id="tenant123",
    agent_id=agent_id,
    session_id=session_id,
    message="Hola, ¿cómo estás?",
    callback_queue="orchestrator.tenant123.callbacks"
)

# 2. Encolar la acción
await action_processor.enqueue_action(action)

# 3. El worker procesa la acción (automáticamente)

# 4. Recibir callback (en otro servicio)
# El callback llegará a la cola especificada
```

## Mantenimiento y Extensión

El sistema está completamente migrado a la arquitectura de Domain Actions. Para mantenerlo y extenderlo:

1. **Nuevas acciones**: Crear subclases de `DomainAction` en los archivos `actions.py` del servicio correspondiente
2. **Nuevos handlers**: Implementar handlers en los archivos `handlers.py` y registrarlos en el ActionProcessor
3. **Nuevos workers**: No debería ser necesario, pero de serlo, extender de BaseWorker
4. **Nuevos servicios**: Seguir la misma estructura de carpetas y convenciones
