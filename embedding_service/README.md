# Embedding Service

## Descripción General

El Embedding Service es un componente fundamental de la arquitectura Nooble, responsable de la generación de embeddings (representaciones vectoriales) para textos mediante modelos avanzados de OpenAI. Funciona como un servicio independiente y escalable que se comunica con otros componentes a través de colas Redis y proporciona una API para la generación asíncrona de embeddings.

### Características Principales

- **Generación de Embeddings**: Conversión eficiente de textos a vectores de alta dimensionalidad
- **Procesamiento por Lotes**: Soporte para procesamiento de múltiples textos en una sola solicitud
- **Modelo Asincrónico**: Procesamiento no bloqueante mediante sistema de colas Redis
- **Soporte para Múltiples Modelos**: Compatibilidad con diferentes modelos de OpenAI
- **Comunicación por Domain Actions**: Integración con otros servicios mediante patrón Domain Action
- **Gestión de Errores**: Manejo robusto de errores y validaciones
- **Altamente Configurable**: Adaptación a diferentes necesidades mediante variables de entorno

## Estructura de Archivos y Carpetas

```plaintext
embedding_service/
├ __init__.py
├ main.py
├ requirements.txt
├ README.md
├ clients/
│  ├ __init__.py
│  └ openai_client.py
├ config/
│  └ settings.py
├ handlers/
│  ├ __init__.py
│  └ embedding_handler.py
├ models/
│  ├ __init__.py
│  └ actions.py
└ workers/
   ├ __init__.py
   └ embedding_worker.py
```

## Arquitectura y Componentes

El servicio sigue una arquitectura orientada a eventos con procesamiento asíncrono y también expone una API REST para generación síncrona de embeddings:

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clientes                               │
│ Agent Execution Service  │  Query Service  │  Ingestion Service │
└─────────────────────────────────────────────────────────────────┘
            │                      │                     │
            ▼                      ▼                     ▼
      ┌────────────────────────────────────────────────────────┐
      │              Embedding Service                         │
      └────────────────────────────────────────────────────────┘
                          │
                          ▼
       ┌──────────────────────────────────────────────────────┐
       │   Domain Action Queue (Redis)                        │
       └──────────────────────────────────────────────────────┘
                          │
                          ▼
       ┌──────────────────────────────────────────────────────┐
       │   EmbeddingWorker                                    │
       └──────────────────────────────────────────────────────┘ 
                          │
                          ▼
       ┌──────────────────────────────────────────────────────┐
       │   Callback Queue (Redis)                             │
       └──────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│                          Callbacks                          │
│ Agent Execution Service  │  Query Service  │  Ingestion Service │
└───────────────────────────────────────────────────────────────┘
```

### Componentes Principales

1. **EmbeddingWorker**: Escucha las colas de acciones y procesa las solicitudes de embeddings
2. **EmbeddingHandler**: Implementa la lógica de negocio para validar y generar embeddings
3. **OpenAIClient**: Interactúa con la API de OpenAI para generar embeddings
4. **Modelos de Acciones**: Define la estructura de las acciones de dominio para la comunicación

### Flujo de Trabajo

1. **Recepción de Solicitud**: El cliente envía una solicitud para generar embeddings
2. **Encolado de Acción**: La solicitud se convierte en una `EmbeddingGenerateAction` y se coloca en una cola Redis
3. **Procesamiento**: El `EmbeddingWorker` consume la acción y utiliza el `EmbeddingHandler` para procesarla
4. **Generación de Embeddings**: El `OpenAIClient` envía los textos a la API de OpenAI y obtiene los vectores
5. **Callback**: Los resultados se envían de vuelta mediante una acción de callback a la cola especificada

## Modelos de Embedding Soportados

| Modelo | Dimensiones | Max. Tokens | Descripción |
|--------|------------|------------|-------------|
| text-embedding-3-small | 1536 | 8191 | Modelo de uso general con excelente balance costo/rendimiento |
| text-embedding-3-large | 3072 | 8191 | Modelo de alta precisión para tareas complejas |
| text-embedding-ada-002 | 1536 | 8191 | Compatibilidad con sistemas legacy |

## Domain Actions

El servicio procesa las siguientes acciones de dominio:

### EmbeddingGenerateAction

```json
{
  "action_type": "embedding.generate",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "texts": ["Este es un texto de ejemplo para generar embedding"],
  "model": "text-embedding-3-small",
  "callback_queue": "agent.execution.callbacks"
}
```

### EmbeddingValidateAction

```json
{
  "action_type": "embedding.validate",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "texts": ["Texto 1", "Texto 2", "Texto 3"],
  "model": "text-embedding-3-small",
  "callback_queue": "agent.execution.callbacks"
}
```

### EmbeddingCallbackAction

```json
{
  "action_type": "embedding.callback",
  "tenant_id": "client123",
  "session_id": "sess_abc123",
  "embeddings": [[0.1, 0.2, 0.3, 0.4]],
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "total_tokens": 5,
  "processing_time": 0.45,
  "task_id": "task_xyz789",
  "status": "completed"
}
```

## Ejemplos de Uso

### Cliente Python

```python
import json
import asyncio
import aioredis

async def request_embeddings(texts, model=None):
    # Configuración
    redis_url = "redis://localhost:6379"
    request_queue = "embedding.default.actions"
    callback_queue = "my_app.callbacks"
    
    # Conectar a Redis
    redis = await aioredis.create_redis_pool(redis_url)
    
    # Crear acción
    action = {
        "action_type": "embedding.generate",
        "tenant_id": "my_tenant",
        "session_id": "my_session",
        "texts": texts,
        "model": model,
        "callback_queue": callback_queue,
        "task_id": f"task_{int(time.time())}"
    }
    
    # Enviar a cola
    await redis.lpush(request_queue, json.dumps(action))
    print(f"Solicitud enviada para {len(texts)} textos")
    
    # En un caso real, implementarías un listener para la cola de callbacks
    # ...

# Uso
asyncio.run(request_embeddings(
    ["Este es un ejemplo de texto", "Este es otro ejemplo"]
))
```

### HTTP (Suponiendo una API REST)

```python
import requests

def request_embeddings_http(texts, model=None):
    # En una implementación real, esta sería la URL de tu API REST
    url = "http://localhost:8003/api/v1/embeddings"
    
    payload = {
        "texts": texts,
        "model": model,
        "tenant_id": "my_tenant"
    }
    
    response = requests.post(url, json=payload)
    print(f"Solicitud enviada: {response.status_code}")
    print(response.json())

# Uso
request_embeddings_http(
    ["Este es un ejemplo de texto", "Este es otro ejemplo"]
)
```

## Configuración

### Variables de Entorno

```env
# Configuración general
DEBUG=true
VERSION=1.0.0
HOST=0.0.0.0
PORT=8003

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# OpenAI
EMBEDDING_OPENAI_API_KEY=sk-your-api-key
EMBEDDING_DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_PREFERRED_DIMENSIONS=0  # 0 = usar dimensiones default
EMBEDDING_ENCODING_FORMAT=float  # float o base64

# Límites operacionales
EMBEDDING_MAX_BATCH_SIZE=100
EMBEDDING_MAX_TEXT_LENGTH=8000
EMBEDDING_OPENAI_TIMEOUT_SECONDS=30
```

### Configuración de Modelos

El servicio permite configurar distintos aspectos:

- **Modelo de Embedding**: Selección del modelo a utilizar
- **Dimensiones**: Posibilidad de reducir dimensiones para modelos que lo soporten
- **Formato**: Formato de salida de vectores (float o base64)
- **Límites**: Control del tamaño de batch y longitud máxima de textos

## Integración con Otros Servicios

### Con Ingestion Service

El Embedding Service está diseñado para integrarse con el servicio de ingestión:

1. El servicio de ingestión procesa documentos y genera fragmentos (chunks)
2. Para cada fragmento, crea una acción `EmbeddingGenerateAction`
3. Envía las acciones a la cola `embedding.default.actions`
4. El Embedding Service procesa las acciones y genera embeddings
5. Envía callbacks con los resultados a la cola configurada
6. El servicio de ingestión recibe los callbacks y actualiza el estado de la tarea

```python
# Ejemplo de integración desde IngestionWorker
async def process_chunk(self, chunk_text, chunk_id):
    # Crear acción para solicitar embeddings
    action = EmbeddingGenerateAction(
        tenant_id=self.tenant_id,
        session_id=self.session_id, 
        texts=[chunk_text],
        chunk_ids=[chunk_id],
        collection_id=self.collection_id,
        callback_queue="ingestion.embedding.callbacks",
        task_id=self.task_id
    )
    
    # Enviar a cola de embeddings
    await self.action_processor.enqueue_action(
        action, 
        "embedding.default.actions"
    )
```

## Despliegue y Operación

### Requisitos

- Python 3.8+
- Redis
- Acceso a Internet (para API de OpenAI)
- API Key de OpenAI

### Ejecución

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export EMBEDDING_OPENAI_API_KEY=sk-your-api-key

# Iniciar servicio
python -m embedding_service.main
```

### Contenedorización

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "embedding_service.main"]
```

### Monitoreo

Para un entorno de producción, se recomienda monitorear:

1. **Colas Redis**: Longitud y latencia de procesamiento
2. **Consumo de API OpenAI**: Tokens procesados y costos
3. **Errores**: Tasa de errores de validación y comunicación
4. **Rendimiento**: Tiempo de procesamiento por vector y batch

## Mejoras Futuras

- **Caché**: Implementar caché de embeddings para textos frecuentes
- **Retry con Backoff**: Mejorar manejo de errores temporales de la API
- **Métricas Detalladas**: Añadir exportación de métricas para Prometheus
- **Clientes Alternativos**: Soporte para otras APIs de embeddings (e.g., Azure)
- **API REST**: Exponer endpoints REST para uso directo sin colas
- **Bulk Processing**: Optimizaciones para procesar grandes volúmenes de textos
- **Tests Completos**: Ampliar cobertura de pruebas unitarias e integración

---

## Guía Rápida para Desarrolladores

1. **Configurar entorno**:
   ```bash
   cp .env.example .env
   # Editar .env con tus credenciales
   ```

2. **Ejecutar localmente**:
   ```bash
   python -m embedding_service.main
   ```

3. **Enviar acción de test**:
   ```bash
   python -m tools.send_test_action
   ```

4. **Verificar logs**:
   ```bash
   tail -f logs/embedding_service.log
   ```

## Licencia

Este proyecto es propiedad de [Tu Empresa] y está protegido por derechos de autor.
