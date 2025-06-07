# Ingestion Service

## Descripción General

El Ingestion Service es un servicio moderno y escalable diseñado para procesar documentos y convertirlos en chunks vectorizables para consultas de conocimiento. Este servicio forma parte del ecosistema Nooble, actuando como un componente independiente pero integrado que se comunica con otros servicios del sistema, principalmente con el servicio de embeddings.

El servicio está construido siguiendo principios de arquitectura modular, con un enfoque en patrones de Domain Action, workers asíncronos y comunicación en tiempo real, permitiendo una alta escalabilidad horizontal y una experiencia fluida para los usuarios finales.

![Arquitectura](https://via.placeholder.com/800x400?text=Ingestion+Service+Architecture)

## Características Principales

- **Procesamiento Asíncrono**: Todas las operaciones pesadas se realizan de forma asíncrona mediante workers y colas Redis.
- **WebSockets en Tiempo Real**: Proporciona actualizaciones de progreso en tiempo real a los clientes conectados.
- **Fragmentación Inteligente**: Utiliza LlamaIndex para dividir documentos en chunks semánticos de alta calidad.
- **Múltiples Fuentes de Documentos**: Soporta ingestión desde archivos, URLs o texto plano.
- **Integración con Servicio de Embeddings**: Solicita y recibe embeddings de forma asíncrona.
- **Escalabilidad Horizontal**: Arquitectura diseñada para escalar añadiendo más workers.
- **Domain Actions**: Comunicación basada en acciones de dominio bien definidas.
- **Supervisión y Cancelación**: Permite monitorear y cancelar tareas en curso.

## Arquitectura y Flujos de Trabajo

### Componentes Principales

El servicio está organizado en los siguientes componentes principales:

- **API REST**: Endpoints para recibir documentos y gestionar tareas.
- **WebSocket Server**: Para comunicación en tiempo real con clientes.
- **Workers**: Procesadores asíncronos que consumen tareas de colas Redis.
- **Queue Service**: Gestión de colas y tareas con Redis.
- **Chunking Service**: Procesamiento y fragmentación de documentos con LlamaIndex.
- **Embedding Client**: Cliente para comunicación con el servicio de embeddings.

### Estructura de Carpetas

```
ingestion_service/
│
├── clients/             # Clientes para servicios externos (embedding_client.py)
├── config/              # Configuración centralizada (settings.py)
├── handlers/            # Manejadores de Domain Actions
├── models/              # Modelos de datos y Domain Actions
│   ├── actions.py       # Domain Actions
│   ├── events.py        # Modelos para eventos WebSocket
│   └── tasks.py         # Modelos para tareas y su estado
├── routes/              # Endpoints API REST y WebSocket
│   ├── documents.py     # Rutas para procesamiento de documentos
│   ├── tasks.py         # Rutas para gestión de tareas
│   └── websockets.py    # Endpoints WebSocket
├── services/            # Servicios core
│   ├── chunking.py      # Servicio de fragmentación con LlamaIndex
│   └── queue.py         # Servicio de colas con Redis
├── websockets/          # Gestión de conexiones WebSocket
│   ├── connection_manager.py  # Administrador de conexiones
│   └── event_dispatcher.py    # Despachador de eventos
├── workers/             # Workers asíncronos
│   ├── ingestion_worker.py  # Worker para procesamiento
│   └── worker_pool.py   # Pool de workers
├── main.py              # Punto de entrada de la aplicación
└── README.md            # Este documento
```

### Flujo de Procesamiento de Documentos

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

## Referencia de API

### Endpoints REST

#### Procesamiento de Documentos

**POST** `/api/v1/documents/`

Procesa un documento subido como archivo.

- **Form Params**:
  - `tenant_id`: ID del tenant
  - `collection_id`: ID de la colección de documentos
  - `document_id`: ID del documento
  - `file`: Archivo a procesar (opcional)
  - `url`: URL a procesar (opcional)
  - `text`: Texto a procesar (opcional)
  - `title`: Título del documento (opcional)
  - `description`: Descripción del documento (opcional)
  - `tags`: Tags separados por comas (opcional)
  - `chunk_size`: Tamaño de chunks (opcional)
  - `chunk_overlap`: Overlap entre chunks (opcional)
  - `embedding_model`: Modelo de embeddings (opcional)

- **Response**: `TaskResponse` con ID de tarea

**POST** `/api/v1/documents/text`

Procesa un documento de texto enviado en JSON.

- **Body**:
```json
{
  "tenant_id": "string",
  "collection_id": "string",
  "document_id": "string",
  "text": "string",
  "title": "string",
  "description": "string",
  "tags": ["string"],
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

- **Response**: `TaskResponse` con ID de tarea

**POST** `/api/v1/documents/url`

Procesa un documento desde una URL enviada en JSON.

- **Body**:
```json
{
  "tenant_id": "string",
  "collection_id": "string",
  "document_id": "string",
  "url": "string",
  "title": "string"
}
```

- **Response**: `TaskResponse` con ID de tarea

#### Gestión de Tareas

**GET** `/api/v1/tasks/{task_id}`

Consulta el estado de una tarea.

- **Path Params**:
  - `task_id`: ID de la tarea
  
- **Query Params**:
  - `tenant_id`: ID del tenant

- **Response**: `TaskResponse` con detalles de la tarea

**DELETE** `/api/v1/tasks/{task_id}`

Cancela una tarea en proceso.

- **Path Params**:
  - `task_id`: ID de la tarea
  
- **Query Params**:
  - `tenant_id`: ID del tenant

- **Response**: `TaskResponse` con estado de cancelación

### WebSocket

**WS** `/ws/tasks/{task_id}`

Endpoint WebSocket para recibir actualizaciones de progreso en tiempo real.

- **Path Params**:
  - `task_id`: ID de la tarea
  
- **Query Params**:
  - `tenant_id`: ID del tenant
  - `token`: Token de autenticación

- **Eventos Recibidos**:
  - `TaskProgressEvent`: Actualizaciones de porcentaje de progreso
  - `TaskStatusEvent`: Cambios de estado de la tarea
  - `ErrorEvent`: Errores durante el procesamiento
  - `ProcessingMilestoneEvent`: Hitos importantes en el procesamiento
