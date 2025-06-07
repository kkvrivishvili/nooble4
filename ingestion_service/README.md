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

## Guía de Integración con Frontend

### Configuración Inicial

```javascript
// Configuración global
const API_URL = 'http://localhost:8000/api/v1';
const WS_URL = 'ws://localhost:8000/ws';

// Función auxiliar para peticiones HTTP
async function apiCall(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAuthToken()}`
    }
  };

  if (data) {
    if (method === 'GET') {
      const params = new URLSearchParams(data);
      endpoint = `${endpoint}?${params}`;
    } else {
      options.body = JSON.stringify(data);
    }
  }

  const response = await fetch(`${API_URL}${endpoint}`, options);
  return response.json();
}
```

### Enviar Documento para Procesamiento

#### Enviar Texto

```javascript
async function processTextDocument(text, documentData) {
  const payload = {
    tenant_id: getCurrentTenant(),
    collection_id: documentData.collectionId,
    document_id: documentData.documentId || generateUUID(),
    text: text,
    title: documentData.title,
    description: documentData.description,
    tags: documentData.tags || [],
    chunk_size: documentData.chunkSize || 1000,
    chunk_overlap: documentData.chunkOverlap || 200
  };

  return await apiCall('/documents/text', 'POST', payload);
}
```

#### Subir Archivo

```javascript
async function uploadDocumentFile(file, documentData) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('tenant_id', getCurrentTenant());
  formData.append('collection_id', documentData.collectionId);
  formData.append('document_id', documentData.documentId || generateUUID());
  formData.append('title', documentData.title || file.name);
  
  if (documentData.description) {
    formData.append('description', documentData.description);
  }
  
  if (documentData.tags) {
    formData.append('tags', documentData.tags.join(','));
  }

  const response = await fetch(`${API_URL}/documents`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: formData
  });
  
  return await response.json();
}
```

### Conexión WebSocket para Actualizaciones en Tiempo Real

```javascript
class TaskProgressMonitor {
  constructor(taskId, callbacks) {
    this.taskId = taskId;
    this.tenant_id = getCurrentTenant();
    this.socket = null;
    this.callbacks = callbacks || {
      onProgress: (progress) => {},
      onStatus: (status) => {},
      onError: (error) => {},
      onMilestone: (milestone) => {},
      onComplete: (result) => {}
    };
  }

  connect() {
    const token = getAuthToken();
    this.socket = new WebSocket(
      `${WS_URL}/tasks/${this.taskId}?tenant_id=${this.tenant_id}&token=${token}`
    );

    this.socket.onopen = (event) => {
      console.log(`Conexión establecida para tarea ${this.taskId}`);
    };

    this.socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.event_type) {
        case 'task_progress':
          this.callbacks.onProgress({
            percentage: data.percentage,
            status: data.status,
            message: data.message
          });
          break;
          
        case 'task_status':
          this.callbacks.onStatus({
            current: data.current_status,
            previous: data.previous_status,
            message: data.message
          });
          
          if (data.current_status === 'completed') {
            this.callbacks.onComplete(data);
            this.disconnect();
          }
          break;
          
        case 'error':
          this.callbacks.onError({
            code: data.error_code,
            message: data.error_message,
            details: data.details
          });
          break;
          
        case 'processing_milestone':
          this.callbacks.onMilestone({
            milestone: data.milestone,
            message: data.message,
            details: data.details
          });
          break;
      }
    };

    this.socket.onerror = (error) => {
      console.error(`Error en WebSocket: ${error}`);
      this.callbacks.onError({
        code: 'websocket_error',
        message: 'Error en la conexión WebSocket',
        details: { error: error.toString() }
      });
    };

    this.socket.onclose = (event) => {
      console.log(`Conexión cerrada: ${event.code}`);
    };
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
```

### Ejemplo de Uso Completo

```javascript
// Componente React para subida de documentos con barra de progreso
function DocumentUpload({ collectionId }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState(null);
  
  async function handleFileUpload(file) {
    setUploading(true);
    setProgress(0);
    setStatus('preparing');
    setMessage('Preparando documento...');
    
    try {
      // 1. Enviar archivo
      const response = await uploadDocumentFile(file, {
        collectionId: collectionId,
        title: file.name
      });
      
      if (!response.success) {
        throw new Error(response.message || 'Error al subir documento');
      }
      
      const taskId = response.task.task_id;
      
      // 2. Conectar al WebSocket para actualizaciones
      const monitor = new TaskProgressMonitor(taskId, {
        onProgress: (data) => {
          setProgress(data.percentage);
          setMessage(data.message);
        },
        onStatus: (data) => {
          setStatus(data.current);
        },
        onMilestone: (data) => {
          console.log(`Hito alcanzado: ${data.milestone}`);
        },
        onError: (error) => {
          setError(error.message);
          setUploading(false);
        },
        onComplete: (result) => {
          setProgress(100);
          setStatus('completed');
          setMessage('Documento procesado correctamente');
          setUploading(false);
          // Notificar que el documento está listo
          onDocumentProcessed(response.task.document_id);
        }
      });
      
      monitor.connect();
      
    } catch (err) {
      setError(err.message);
      setUploading(false);
    }
  }
  
  return (
    <div className="document-upload">
      {!uploading ? (
        <FileDropzone onFileSelected={handleFileUpload} />
      ) : (
        <div className="progress-container">
          <ProgressBar value={progress} />
          <div className="status">{status}</div>
          <div className="message">{message}</div>
          {error && <div className="error">{error}</div>}
        </div>
      )}
    </div>
  );
}
```

## Configuración del Servicio

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# Configuración general
DEBUG=true
VERSION=1.0.0
HOST=0.0.0.0
PORT=8000

# Configuración de Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Colas Redis
DOCUMENT_QUEUE=document_process_queue
EMBEDDING_CALLBACK_QUEUE=embedding_callback_queue
TASK_STATUS_QUEUE=task_status_queue

# Workers
WORKER_COUNT=2
WORKER_SLEEP_TIME=0.1
AUTO_START_WORKERS=true

# Límites
MAX_FILE_SIZE=50000000  # 50 MB
MAX_TEXT_LENGTH=1000000  # 1 millón de caracteres

# Configuración de Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
CHUNK_MODEL=text-embedding-3-large

# Servicio de Embeddings
EMBEDDING_SERVICE_URL=http://localhost:8001/api/v1/embeddings
EMBEDDING_MODEL=text-embedding-3-large

# CORS
CORS_ORIGINS=["http://localhost:3000", "https://app.example.com"]
```

### Ejecución del Servicio

```bash
# Instalar dependencias
pip install -r requirements.txt

# Iniciar Redis (si no está corriendo)
docker run -d -p 6379:6379 --name redis redis:alpine

# Ejecutar servicio
uvicorn ingestion_service.main:app --reload
```

## Escalabilidad y Rendimiento

El servicio está diseñado para escalar horizontalmente:

1. **Escalado de Workers**: Aumenta `WORKER_COUNT` para procesar más documentos en paralelo.

2. **Redis Distribuido**: Configura un cluster Redis para alta disponibilidad.

3. **Deployment Distribuido**: Despliega múltiples instancias del servicio con balanceo de carga.

4. **Mecanismo WebSocket Cluster**: El `connection_manager` permite distribución de conexiones WebSocket.

5. **Configuración Recomendada**:
   - Para volumen bajo: 1-2 workers
   - Para volumen medio: 3-5 workers
   - Para volumen alto: 10+ workers con autoscaling
