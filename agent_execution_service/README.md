# Agent Execution Service

## Características y Estado

| Característica | Descripción | Estado |
|---------------|-------------|--------|
| **Ejecución LangChain** | Ejecución de agentes con framework LangChain | ✅ Operativo |
| **Integración con servicios** | Comunicación con otros servicios backend | ✅ Operativo |
| **Domain Actions** | Comunicación asíncrona vía Redis | ✅ Operativo |
| **Validación por tier** | Límites y capacidades según tier | ✅ Operativo |
| **Gestión de herramientas** | Configuración y ejecución de tools de agente | ✅ Operativo |
| **Control de contexto** | Gestión del historial de conversación | ✅ Operativo |
| **Callbacks asíncronos** | Notificación de resultados | ✅ Operativo |
| **Métricas básicas** | Endpoints para métricas de performance | ⚠️ Parcial |
| **Caché de configuraciones** | Optimización mediante caché | ⚠️ Parcial |
| **Persistencia avanzada** | Almacenamiento de datos en PostgreSQL | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
agent_execution_service/
├ __init__.py
├ main.py
├ requirements.txt
├ clients/
│  ├ __init__.py
│  ├ agent_management_client.py
│  ├ conversation_client.py
│  ├ embedding_client.py
│  └ query_client.py
├ config/
│  ├ __init__.py
│  └ settings.py
├ handlers/
│  ├ __init__.py
│  ├ agent_execution_handler.py
│  ├ execution_context_handler.py
│  ├ execution_callback_handler.py
│  └ langchain_integrator.py
├ models/
│  ├ __init__.py
│  ├ actions.py
│  └ execution.py
├ services/
│  ├ __init__.py
│  └ agent_executor.py
└ workers/
   ├ __init__.py
   └ execution_worker.py
```

## Arquitectura

El Agent Execution Service es el componente responsable de procesar la ejecución de agentes conversacionales utilizando LangChain. Este servicio gestiona el ciclo de vida de ejecución de los agentes, interactuando con múltiples servicios externos para resolver tareas y generar respuestas basadas en configuraciones predefinidas.

### Diagrama de Integración

```plaintext
┌───────────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│                           │  │                    │  │                    │
│   Agent Orchestrator      │  │  Frontend Client   │  │  Other Services    │
│                           │  │                    │  │                    │
└───────────────────────────┘  └────────────────────┘  └────────────────────┘
            │                            │                      │
            └────────────────┬───────────┴──────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │                     │
                  │    Redis Queues     │
                  │                     │
                  └─────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │                     │
                  │ Agent Execution     │
                  │ Service             │
                  │                     │
                  └─────────────────────┘
                             │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
┌──────────────────┐ ┌─────────────┐ ┌────────────────────┐
│                  │ │             │ │                    │
│ Agent Management │ │ Embedding   │ │ Conversation       │
│ Service          │ │ Service     │ │ Service            │
│                  │ │             │ │                    │
└──────────────────┘ └─────────────┘ └────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │                     │
                  │    Query Service    │
                  │                     │
                  └─────────────────────┘
```

### Flujo de Ejecución de Agentes

```plaintext
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│ Orchestrator │────▶│  Execution   │────▶│    Agent     │
│  Service     │     │   Service    │     │ Management   │
└──────────────┘     └──────────────┘     └──────────────┘
                           │                     │
                           │     1. Obtener      │
                           │     configuración   │
                           │     de agente       │
                           │◀────────────────────┘
                           │
                           ▼
                     ┌──────────────┐
                     │              │
                     │Conversation  │◀───┐
                     │Service       │    │
                     └──────────────┘    │ 2. Obtener/Guardar
                           │            │ historial de
                           │            │ conversación
                           │            │
                           ▼            │
                     ┌──────────────┐   │
                     │              │   │
                     │ LangChain    │───┘
                     │ Framework    │
                     └──────────────┘
                           │
                           │ 3. Ejecutar agente
                           │ con herramientas
                           │
                           ▼
          ┌────────────────────────────────┐
          │                                │
          │  Tools (Embedding/Query/etc)   │
          │                                │
          └────────────────────────────────┘
                           │
                           │ 4. Generar
                           │ respuesta
                           ▼
                     ┌──────────────┐
                     │              │
                     │   Callback   │
                     │   Queue      │
                     └──────────────┘
                           │
                           │
                           ▼
                     ┌──────────────┐
                     │              │
                     │ Orchestrator │
                     │ (Response)   │
                     └──────────────┘
```

## Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **ExecutionWorker** | Procesamiento asíncrono de acciones | ✅ Completo |
| **AgentExecutionHandler** | Lógica principal de ejecución de agentes | ✅ Completo |
| **LangChainIntegrator** | Integración con framework LangChain | ✅ Completo |
| **AgentExecutor** | Ejecutor de agentes con herramientas configurables | ✅ Completo |
| **ExecutionContextHandler** | Manejo de contexto para ejecuciones | ✅ Completo |
| **ExecutionCallbackHandler** | Manejo de callbacks asíncronos | ✅ Completo |

## Domain Actions

El servicio implementa y procesa los siguientes Domain Actions:

### 1. Acciones de Entrada

```json
// AgentExecuteAction - Ejecutar un agente con input
{
  "action_id": "uuid-action-1",
  "action_type": "execution.execute",
  "task_id": "conversation-123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "agent_id": "agent-abc",
    "input": "Necesito información sobre productos",
    "conversation_id": "conv-123",
    "session_id": "session-xyz",
    "tools_config": {
      "web_search": true,
      "calculator": true
    },
    "execution_params": {
      "max_iterations": 5,
      "max_execution_time": 120
    }
  },
  "callback_queue": "orchestrator.callback"
}
```

### 2. Acciones de Salida/Callback

```json
// ExecutionCallbackAction - Respuesta de ejecución
{
  "action_id": "uuid-callback-1",
  "action_type": "execution.callback",
  "task_id": "conversation-123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "agent_id": "agent-abc",
    "conversation_id": "conv-123",
    "response": "De acuerdo a la información disponible, los productos más vendidos son...",
    "execution_info": {
      "execution_time_ms": 3240,
      "tools_used": ["web_search", "rag_query"],
      "iterations": 3,
      "tokens_used": 560
    },
    "status": "success"
  }
}

// ExecutionErrorAction - Error durante ejecución
{
  "action_id": "uuid-error-1",
  "action_type": "execution.error",
  "task_id": "conversation-123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "agent_id": "agent-abc",
    "conversation_id": "conv-123",
    "error": "Timeout error: Agent execution exceeded maximum time.",
    "error_code": "EXECUTION_TIMEOUT",
    "error_details": {
      "max_execution_time": 120,
      "actual_execution_time": 132
    }
  }
}
```

## Configuración

El servicio utiliza variables de entorno con el prefijo `EXECUTION_`:

```env
# Configuración básica
EXECUTION_SERVICE_NAME=agent-execution-service
EXECUTION_SERVICE_VERSION=0.1.0
EXECUTION_LOG_LEVEL=INFO

# Redis
EXECUTION_REDIS_URL=redis://localhost:6379/0

# URLs de servicios externos
EXECUTION_EMBEDDING_SERVICE_URL=http://localhost:8001
EXECUTION_QUERY_SERVICE_URL=http://localhost:8002
EXECUTION_CONVERSATION_SERVICE_URL=http://localhost:8004
EXECUTION_AGENT_MANAGEMENT_SERVICE_URL=http://localhost:8003

# Configuración de ejecución
EXECUTION_DEFAULT_AGENT_TYPE=conversational
EXECUTION_MAX_ITERATIONS=5
EXECUTION_MAX_EXECUTION_TIME=120

# Worker
EXECUTION_WORKER_SLEEP_SECONDS=1.0
```

## Health Checks

- `GET /health` ➔ 200 OK si el servicio está funcionando correctamente
- `GET /ready` ➔ 200 OK si todas las dependencias (Redis, servicios externos) están disponibles
- `GET /metrics/overview` ➔ Métricas básicas de uso del servicio (parcial)

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Temporal**: Al igual que otros servicios, utiliza Redis para almacenar métricas y datos de estado. Se planea migrar a PostgreSQL para persistencia permanente.

- **Sistema de Caché**: El caché de configuraciones de agentes está implementado parcialmente y requiere optimización.

- **Métricas Limitadas**: Los endpoints de métricas proporcionan información básica pero no hay un dashboard ni análisis detallado.

- **Configuración de Tier Enterprise**: Las capacidades del tier Enterprise para ejecutar agentes avanzados no están completamente implementadas.

### Próximos Pasos

1. **Implementar Persistencia**: Migrar métricas y datos de ejecución a PostgreSQL para almacenamiento permanente.

2. **Optimizar Caché**: Mejorar el sistema de caché para configuraciones de agentes y resultados frecuentes.

3. **Expandir Métricas**: Añadir métricas detalladas de uso, tiempos de ejecución y éxito de tareas con dashboard.

4. **Herramientas Avanzadas**: Implementar más herramientas nativas para agentes del tier Enterprise.

5. **Integración con Frontend**: Mejorar la experiencia con el frontend para visualizar el progreso de ejecución.

6. **Documentación Avanzada**: Expandir la documentación de uso con ejemplos concretos.
