# Agent Orchestrator Service

Servicio de orquestación para la comunicación entre agentes y clientes mediante WebSockets.

## Arquitectura

El Agent Orchestrator Service actúa como intermediario entre los clientes (frontend) y el Agent Execution Service, proporcionando:

1. **API REST** para envío de mensajes y gestión de tareas
2. **WebSockets** para comunicación en tiempo real con clientes
3. **Worker** para procesamiento asíncrono de callbacks y tareas

### Componentes principales

- **Chat Handler**: Procesa acciones de chat y las enruta al Agent Execution Service
- **WebSocket Handler**: Gestiona envío de mensajes a través de WebSockets
- **WebSocket Manager**: Administra conexiones WebSocket activas
- **Orchestrator Worker**: Procesa callbacks y tareas asíncronas

## Flujo de comunicación

1. Cliente se conecta vía WebSocket al Orchestrator
2. Cliente envía mensaje a través de API REST
3. Orchestrator enruta el mensaje al Agent Execution Service
4. Agent Execution procesa el mensaje y envía resultados a cola de callbacks
5. Orchestrator Worker procesa callbacks y envía respuestas al cliente vía WebSocket

```
Cliente <--WebSocket--> Orchestrator <--Redis Queue--> Agent Execution
```

## Configuración

El servicio utiliza variables de entorno con prefijo `ORCHESTRATOR_`:

- `ORCHESTRATOR_REDIS_URL`: URL de conexión a Redis
- `ORCHESTRATOR_WEBSOCKET_PING_INTERVAL`: Intervalo de ping para WebSockets (segundos)
- `ORCHESTRATOR_WEBSOCKET_PING_TIMEOUT`: Timeout para pong de WebSockets (segundos)
- `ORCHESTRATOR_MAX_WEBSOCKET_CONNECTIONS`: Máximo de conexiones WebSocket simultáneas
- `ORCHESTRATOR_WORKER_SLEEP_SECONDS`: Tiempo de espera entre polls del worker

## Endpoints

### API REST

- `POST /api/chat/send`: Envía mensaje para procesamiento
- `POST /api/chat/status`: Obtiene estado de una tarea
- `POST /api/chat/cancel`: Cancela una tarea en progreso
- `GET /ws/stats`: Obtiene estadísticas de conexiones WebSocket
- `GET /health`: Health check básico
- `GET /health/detailed`: Health check detallado

### WebSocket

- `WebSocket /ws/{tenant_id}/{session_id}`: Endpoint WebSocket para comunicación en tiempo real

## Domain Actions

El servicio utiliza Domain Actions para comunicación entre componentes:

- `ChatSendMessageAction`: Envío de mensaje de chat
- `ChatGetStatusAction`: Consulta de estado de tarea
- `ChatCancelTaskAction`: Cancelación de tarea
- `WebSocketSendAction`: Envío de mensaje WebSocket a sesión específica
- `WebSocketBroadcastAction`: Broadcast a múltiples conexiones

## Desarrollo

### Requisitos

- Python 3.9+
- Redis

### Instalación

```bash
pip install -r requirements.txt
```

### Ejecución

```bash
uvicorn main:app --reload --port 8001
```

### Testing

```bash
pytest
```

## Integración con otros servicios

- **Agent Execution Service**: Procesamiento de mensajes de agentes
- **Common Module**: Utilidades compartidas, modelos base y gestión de colas

## Escalabilidad

El servicio está diseñado para escalar horizontalmente:

- Múltiples instancias pueden compartir el mismo Redis
- Las conexiones WebSocket pueden distribuirse entre instancias mediante balanceo de carga
- El worker puede ejecutarse en múltiples instancias para procesar callbacks en paralelo
