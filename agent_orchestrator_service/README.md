# Agent Orchestrator Service

## Características y Estado

| Característica | Descripción | Estado |
|-----------------|-------------|--------|
| **WebSockets en Tiempo Real** | Comunicación bidireccional cliente-servidor | ✅ Completo |
| **API REST para Mensajes** | Envío, estado y cancelación de mensajes | ✅ Completo |
| **Procesamiento Asíncrono** | Worker basado en Domain Actions | ✅ Completo |
| **Integración Agent Execution** | Comunicación con servicio de ejecución | ✅ Completo |
| **Validación por Tier** | Límites y capacidades por nivel de suscripción | ✅ Completo |
| **Rate Limiting** | Control de frecuencia de solicitudes | ✅ Completo |
| **Sistema de Métricas** | Seguimiento de uso, tiempos y conexiones | ⚠️ Parcial |
| **Persistencia** | Almacenamiento de mensajes en PostgreSQL | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
agent_orchestrator_service/
├ __init__.py
├ main.py
├ README.md
├ requirements.txt
├ config/
│  ├ __init__.py
│  └ settings.py
├ handlers/
│  ├ __init__.py
│  └ handlers.py
├ models/
│  ├ __init__.py
│  ├ actions_model.py
│  └ websocket_model.py
├ routes/
│  ├ __init__.py
│  ├ chat_routes.py
│  ├ health_routes.py
│  └ websocket_routes.py
├ services/
│  ├ __init__.py
│  └ websocket_manager.py
└ workers/
   ├ __init__.py
   └ orchestrator_worker.py
```

## Arquitectura

El Agent Orchestrator Service actúa como intermediario entre los clientes frontend y el Agent Execution Service, proporcionando WebSockets para comunicación en tiempo real.

```
┌────────────┐        ┌─────────────────────┐        ┌────────────────────┐
│            │        │                     │        │                    │
│  Cliente   │<------>│ Agent Orchestrator  │<------>│  Agent Execution   │
│  Frontend  │   WS   │      Service        │ Redis  │     Service        │
│            │        │                     │ Queue  │                    │
└────────────┘        └─────────────────────┘        └────────────────────┘
```

### Flujo de Comunicación

```
Cliente                Orchestrator               Redis                  Agent Execution
  │                        │                        │                         │
  │ 1. Conexión WebSocket  │                        │                         │
  │───────────────────────>│                        │                         │
  │                        │                        │                         │
  │ 2. Envío mensaje (API) │                        │                         │
  │───────────────────────>│                        │                         │
  │                        │ 3. Enruta mensaje      │                         │
  │                        │────────────────────────────────────────────────>│
  │                        │                        │                         │
  │                        │                        │ 4. Respuesta en cola   │
  │                        │                        │<────────────────────────│
  │                        │ 5. Procesa callback    │                         │
  │                        │<───────────────────────│                         │
  │ 6. Respuesta WS        │                        │                         │
  │<───────────────────────│                        │                         │
```

### Integración con Backend Existente

- **Domain Actions**: Implementa el sistema de Domain Actions para comunicación asíncrona
- **Validación por Tier**: Sistema de validación de acceso basado en el tier del tenant
- **Rate Limiting**: Control de frecuencia de solicitudes por sesión
- **Cache de Validación**: Optimiza validaciones frecuentes con TTL configurable

### Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **WebSocketManager** | Administra conexiones WebSocket activas | ✅ Completo |
| **WebSocketHandler** | Procesa eventos WebSocket | ✅ Completo |
| **ChatHandler** | Procesa acciones de chat y las enruta | ✅ Completo |
| **OrchestratorWorker** | Procesa callbacks y mensajes asíncronos | ✅ Completo |

## Domain Actions

El servicio procesa las siguientes acciones de dominio:

### ChatProcessAction

```json
{
  "action_type": "chat.process",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "agent_id": "agent_xyz789",
  "message": "¿Cuál es la capital de Francia?",
  "user": {
    "id": "user_123",
    "name": "John Doe"
  },
  "callback_queue": "orchestrator:client123:callback"
}
```

### WebSocketSendAction

```json
{
  "action_type": "websocket.send",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "message_type": "chat.response",
  "message_data": {
    "content": "París es la capital de Francia.",
    "role": "assistant"
  }
}
```

## API HTTP

### Envío de Mensajes

**POST** `/api/chat/send`

Envía un mensaje para procesamiento por un agente.

- **Body**:
  ```json
  {
    "message": "¿Cuál es la capital de Francia?",
    "context": {},
    "stream": true
  }
  ```

**Respuesta:**
```json
{
  "task_id": "task_xyz789",
  "status": "processing"
}
```

### Consultar Estado

**POST** `/api/chat/status`

Obtiene el estado de una tarea.

- **Body**:
  ```json
  {
    "task_id": "task_xyz789"
  }
  ```

**Respuesta:**
```json
{
  "task_id": "task_xyz789",
  "status": "completed",
  "result": {
    "content": "París es la capital de Francia.",
    "role": "assistant"
  }
}
```

### WebSocket

**WebSocket** `/ws/{tenant_id}/{session_id}`

Establece una conexión WebSocket para comunicación en tiempo real.

Eventos recibidos:
```json
{
  "type": "chat.response",
  "data": {
    "content": "París es la capital de Francia.",
    "role": "assistant"
  }
}
```

## Configuración

### Variables de Entorno

Todas las variables de entorno utilizan el prefijo `ORCHESTRATOR_`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `ORCHESTRATOR_REDIS_HOST` | Host para conexión Redis | localhost |
| `ORCHESTRATOR_REDIS_PORT` | Puerto para conexión Redis | 6379 |
| `ORCHESTRATOR_WEBSOCKET_PING_INTERVAL` | Intervalo de ping para WebSockets (segundos) | 30 |
| `ORCHESTRATOR_WEBSOCKET_PING_TIMEOUT` | Timeout para pong de WebSockets (segundos) | 10 |
| `ORCHESTRATOR_MAX_WEBSOCKET_CONNECTIONS` | Máximo conexiones WebSocket simultáneas | 1000 |
| `ORCHESTRATOR_WORKER_SLEEP_SECONDS` | Tiempo entre polls del worker | 1.0 |
| `ORCHESTRATOR_MAX_REQUESTS_PER_SESSION` | Límite de solicitudes por sesión | 100 |

## Health Checks

- `GET /health` ➔ 200 OK
- `GET /health/detailed` ➔ Estado detallado de componentes
- `GET /ws/stats` ➔ Estadísticas de conexiones WebSocket

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Temporal**: Al igual que otros servicios, utiliza Redis para estado de mensajes y sesiones. Se planea migrar a PostgreSQL para persistencia permanente.
- **Sistema de Métricas Parcial**: Aunque captura estadísticas de conexiones WebSocket, no hay un dashboard completo ni análisis detallado.
- **Headers Requeridos**: Aunque se validan headers como tenant_id y agent_id, la implementación de diferentes tiers está parcialmente completada.
- **Performance Tracking**: Aunque está habilitado en la configuración, la implementación es básica.

### Próximos Pasos

- **Implementar Persistencia**: Añadir almacenamiento en PostgreSQL para mensajes y sesiones.
- **Expandir Métricas**: Añadir métricas detalladas de uso, tiempos y costos por tenant.
- **Mejorar Rate Limiting**: Implementar sistema avanzado de rate limiting con quotas por tier.
- **Añadir Retry Logic**: Implementar reintentos para tareas fallidas y recuperación de errores.
- **Optimizar WebSockets**: Mejorar escalabilidad y gestión de conexiones para altos volúmenes.

## Desarrollo

Para ejecutar el servicio en modo desarrollo:

```bash
uvicorn main:app --reload --port 8001
```

## Escalabilidad

El servicio está diseñado para escalar horizontalmente:

- Múltiples instancias pueden compartir el mismo Redis
- Las conexiones WebSocket pueden distribuirse entre instancias mediante balanceo de carga
- El worker puede ejecutarse en múltiples instancias para procesar callbacks en paralelo
