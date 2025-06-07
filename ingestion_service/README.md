# Ingestion Service

## Características y Estado

| Característica | Descripción | Estado |
|-----------------|-------------|--------|
| **Procesamiento de Documentos** | Extracción de texto de múltiples formatos | ✅ Completo |
| **Fragmentación Inteligente** | División de documentos en chunks semánticos usando LlamaIndex | ✅ Completo |
| **Múltiples Fuentes** | Soporte para archivos, URLs y texto plano | ✅ Completo |
| **WebSockets en Tiempo Real** | Actualizaciones de progreso a clientes conectados | ✅ Completo |
| **Domain Actions** | Integración mediante patrón Domain Action | ✅ Completo |
| **Validación por Tier** | Límites y capacidades por nivel de suscripción | ✅ Completo |
| **Sistema Async** | Procesamiento asíncrono mediante colas Redis | ✅ Completo |
| **Worker Pool** | Escalabilidad horizontal mediante pool de workers | ✅ Completo |
| **Sistema de Métricas** | Seguimiento de uso, tiempos y costos | ⚠️ Parcial |
| **Persistencia** | Almacenamiento de documentos y chunks en PostgreSQL | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
ingestion_service/
├ __init__.py
├ main.py
├ README.md
├ clients/
│  ├ __init__.py
│  └ embedding_client.py
├ config/
│  ├ __init__.py
│  └ settings.py
├ handlers/
│  └ __init__.py
├ models/
│  ├ __init__.py
│  ├ actions.py
│  ├ events.py
│  └ tasks.py
├ routes/
│  ├ __init__.py
│  ├ documents.py
│  ├ tasks.py
│  └ websockets.py
├ services/
│  ├ __init__.py
│  ├ chunking.py
│  └ queue.py
├ websockets/
│  ├ __init__.py
│  ├ connection_manager.py
│  └ event_dispatcher.py
└ workers/
   ├ __init__.py
   ├ ingestion_worker.py
   └ worker_pool.py
```

## Arquitectura

### Flujo de Procesamiento de Documentos

```
┌────────────────────┐      ┌─────────────────────────┐      ┌───────────────────┐
│   Cliente          │      │   Ingestion Service     │      │  Embedding Service │
└────────────────────┘      └─────────────────────────┘      └───────────────────┘
        │                              │                              │
        │  1. Enviar documento         │                              │
        │─────────────────────────────>│                              │
        │                              │                              │
        │  2. Retornar ID de tarea     │                              │
        │<─────────────────────────────│                              │
        │                              │                              │
        │  3. Conectar WebSocket       │                              │
        │─────────────────────────────>│                              │
        │                              │                              │
        │                              │  4. Procesar documento       │
        │                              │─────────┐                    │
        │                              │         │                    │
        │                              │<────────┘                    │
        │                              │                              │
        │  5. Eventos de progreso      │                              │
        │<─────────────────────────────│                              │
        │                              │                              │
        │                              │  6. Solicitar embeddings     │
        │                              │─────────────────────────────>│
        │                              │                              │
        │                              │  7. Retornar embeddings      │
        │                              │<─────────────────────────────│
        │                              │                              │
        │  8. Notificar finalización   │                              │
        │<─────────────────────────────│                              │
        │                              │                              │
```

### Integración con Backend Existente
- **Domain Actions**: Implementa el sistema de Domain Actions para comunicación asíncrona
- **DomainQueueManager**: Integrado con colas por tier para priorización de tareas
- **Common Utilities**: Utiliza helpers, configuración y workers base del sistema
- **Redis**: Utiliza Redis para colas de mensajes, estado de tareas y eventos
- **LlamaIndex**: Utiliza LlamaIndex para fragmentación inteligente de documentos

### Servicios Integrados
- **Embedding Service**: Para generar embeddings de los chunks de documentos
- **Query Service**: Indirectamente para consultas sobre documentos procesados
- **Agent Execution Service**: Indirectamente para uso con agentes

### Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **IngestionWorker** | Procesamiento asíncrono de documentos | ✅ Completo |
| **WorkerPool** | Pool de workers para procesamiento paralelo | ✅ Completo |
| **ChunkingService** | Fragmentación semántica de documentos | ✅ Completo |
| **QueueService** | Gestión de colas Redis y tareas | ✅ Completo |
| **ConnectionManager** | Administración de conexiones WebSocket | ✅ Completo |
| **EventDispatcher** | Envío de eventos en tiempo real | ✅ Completo |
| **EmbeddingClient** | Cliente para comunicación con Embedding Service | ✅ Completo |

## Flujo de Trabajo Detallado

1. **Recepción de Documentos**:
   - Cliente envía documento vía API REST (archivo, URL o texto)
   - Se crea una tarea con ID único y se encola una `DocumentProcessAction`
   - Se retorna inmediatamente el ID de tarea al cliente

2. **Conexión WebSocket**:
   - Cliente establece conexión WebSocket usando el ID de tarea
   - Recibe eventos de progreso en tiempo real

3. **Procesamiento Asíncrono**:
   - Worker consume la tarea de la cola Redis
   - Extrae texto del documento (PDF, DOCX, HTML, etc.)
   - Fragmenta el documento usando LlamaIndex
   - Envía chunks al servicio de embeddings vía `EmbeddingRequestAction`

4. **Generación de Embeddings**:
   - Servicio de embeddings procesa los chunks
   - Retorna embeddings vía `EmbeddingCallbackAction`

5. **Finalización**:
   - Worker recibe embeddings y completa procesamiento
   - Actualiza estado y notifica al cliente vía WebSocket
   - Marca tarea como completada en Redis

## Domain Actions

El servicio procesa las siguientes acciones de dominio:

### IngestionTaskAction

```json
{
  "action_type": "ingestion.task",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "document_type": "file",
  "document_data": "base64_encoded_content",
  "document_metadata": {
    "filename": "document.pdf",
    "mime_type": "application/pdf"
  },
  "callback_queue": "client.callbacks"
}
```

### IngestionProcessAction

```json
{
  "action_type": "ingestion.process",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "task_id": "task_xyz789",
  "document_chunks": ["Chunk 1", "Chunk 2", "..."],
  "callback_queue": "client.callbacks"
}
```

## API HTTP

### Procesamiento de Documentos

**POST** `/api/v1/documents/`

Procesa un documento subido como archivo.

- **Form Params**:
  - `tenant_id`: ID del tenant
  - `document`: Archivo a procesar
  - `metadata`: Metadatos del documento (JSON)

**Respuesta:**
```json
{
  "task_id": "task_xyz789",
  "status": "processing",
  "websocket_url": "ws://ingestion-service/ws/tasks/task_xyz789"
}
```

### Consulta de Tareas

**GET** `/api/v1/tasks/{task_id}`

Obtiene el estado de una tarea.

**Respuesta:**
```json
{
  "task_id": "task_xyz789",
  "status": "completed",
  "progress": 100,
  "created_at": "2025-06-07T15:32:45Z",
  "completed_at": "2025-06-07T15:33:12Z",
  "result": {
    "document_id": "doc_abc123",
    "chunk_count": 15,
    "total_tokens": 4230
  }
}
```

### WebSocket

**WebSocket** `/ws/tasks/{task_id}`

Establece una conexión WebSocket para recibir actualizaciones en tiempo real.

Eventos recibidos:
```json
{
  "event_type": "task.progress",
  "task_id": "task_xyz789",
  "progress": 50,
  "message": "Procesando chunks 7/15"
}
```

## Configuración

### Variables de Entorno

Todas las variables de entorno no tienen un prefijo específico:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Host para conexión Redis | localhost |
| `REDIS_PORT` | Puerto para conexión Redis | 6379 |
| `WORKER_COUNT` | Número de workers concurrentes | 2 |
| `MAX_FILE_SIZE` | Tamaño máximo de archivo (bytes) | 10MB |
| `DEFAULT_CHUNK_SIZE` | Tamaño predeterminado de chunks | 512 |
| `EMBEDDING_SERVICE_URL` | URL del servicio de embeddings | http://embedding-service:8000 |

## Health Checks

- `GET /health` ➔ 200 OK
- `GET /ready`  ➔ 200 OK
- `GET /metrics/overview` ➔ Métricas básicas de uso del servicio (parcial)

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Temporal**: Al igual que otros servicios, utiliza Redis para almacenar el estado de las tareas. Se planea migrar a PostgreSQL para persistencia permanente.
- **Sistema de Métricas Parcial**: Aunque captura progreso de tareas, no hay un dashboard ni análisis detallado.
- **Límites de Tier**: Aunque existe validación por tier, algunas capacidades avanzadas del tier Enterprise no están completamente implementadas.
- **Directorio Handlers Vacío**: El directorio de handlers está presente pero no tiene clases implementadas, la lógica está en workers y services.
- **Variables de Entorno Sin Prefijo**: A diferencia de otros servicios que usan prefijos específicos, las variables de entorno no tienen un prefijo consistente.

### Próximos Pasos

- **Implementar Persistencia**: Añadir almacenamiento en PostgreSQL para documentos procesados y estado de tareas.
- **Expandir Métricas**: Añadir métricas detalladas de uso, tiempos y costos por tenant.
- **Reorganizar Handlers**: Implementar handlers faltantes para seguir la arquitectura estándar con otros servicios.
- **Estandarizar Variables**: Adoptar un prefijo de variable de entorno consistente (`INGESTION_`).
- **Mejorar Estrategias de Chunking**: Añadir más algoritmos de fragmentación inteligente.
- **Añadir Retry Logic**: Implementar reintentos para tareas fallidas y recuperación de errores.

## Desarrollo

Para ejecutar el servicio en modo desarrollo:

```bash
uvicorn main:app --reload --port 8003
```
