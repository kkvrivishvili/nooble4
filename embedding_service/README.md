# Embedding Service

## Características y Estado

| Característica | Descripción | Estado |
|-----------------|-------------|--------|
| **Generación de Embeddings** | Conversión de textos a vectores | ✅ Completo |
| **Procesamiento por Lotes** | Soporte para procesamiento de múltiples textos | ✅ Completo |
| **Múltiples Modelos** | Soporte para diferentes modelos de OpenAI | ✅ Completo |
| **Domain Actions** | Integración mediante patrón Domain Action | ✅ Completo |
| **Validación por Tier** | Límites y capacidades por nivel de suscripción | ✅ Completo |
| **Sistema Async** | Procesamiento asíncrono mediante colas Redis | ✅ Completo |
| **API Sincrónica** | Endpoints REST para uso sincrónico | ✅ Completo |
| **Caché** | Reducción de llamadas duplicadas a OpenAI | ✅ Completo |
| **Sistema de Métricas** | Seguimiento de uso, tiempos y costos | ⚠️ Parcial |
| **Persistencia** | Almacenamiento de embeddings en PostgreSQL | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
embedding_service/
├ __init__.py
├ main.py
├ requirements.txt
├ clients/
│  ├ __init__.py
│  └ openai_client.py
├ config/
│  ├ __init__.py
│  └ settings.py
├ handlers/
│  ├ __init__.py
│  ├ embedding_handler.py
│  ├ embedding_context_handler.py
│  └ embedding_callback_handler.py
├ models/
│  ├ __init__.py
│  └ actions.py
├ services/
│  ├ __init__.py
│  ├ embedding_processor.py
│  ├ validation_service.py
│  └ cache_service.py
└ workers/
   ├ __init__.py
   └ embedding_worker.py
```

## Arquitectura

El Embedding Service es responsable de convertir texto en representaciones vectoriales (embeddings) utilizando modelos de OpenAI. Este componente es crítico para diversas funcionalidades semánticas en la plataforma, incluyendo búsqueda por similitud, clasificación y recomendaciones.

### Diagrama de Integración

```plaintext
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│                   │ │                   │ │                   │
│ Query Service     │ │ Ingestion Service │ │ Agent Execution   │
│                   │ │                   │ │                   │
└───────────────────┘ └───────────────────┘ └───────────────────┘
          │                    │                     │
          └─────────────┬──────┴─────────────────────┘
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
             │                     │          ┌────────────────┐
             │ Embedding Service   │◄─────────┤    OpenAI      │
             │                     │          │    API         │
             └─────────────────────┘          └────────────────┘
                        │
                        │
                        ▼
             ┌─────────────────────┐
             │                     │
             │   Callback Queues   │
             │                     │
             └─────────────────────┘
                        │
                        ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│                   │ │                   │ │                   │
│ Query Service     │ │ Ingestion Service │ │ Agent Execution   │
│                   │ │                   │ │ Service           │
└───────────────────┘ └───────────────────┘ └───────────────────┘
                                       
          │                    │                     │
          ▼                    ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│                   │ │                   │ │                   │
│Vector Store/Search│ │Document Processing│ │ Agent Tools/Tasks │
│                   │ │                   │ │                   │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

### Flujo de Trabajo del Procesamiento de Embeddings

```plaintext
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │
│  Cliente    │────▶│ Embedding   │────▶│  OpenAI     │
│  Servicio   │     │ Service     │     │  API        │
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │                    │
      │                   │                    │
      │        1. EmbeddingGenerateAction      │
      │───────────────────▶│                   │
      │                     │                   │
      │                     │  2. Verificar Caché
      │                     │──────────┐        │
      │                     │          │        │
      │                     │◀─────────┘        │
      │                     │                   │
      │                     │  3. Procesar Texto│
      │                     │───────────────────▶
      │                     │                   │
      │                     │  4. Retornar     │
      │                     │     Embedding     │
      │                     │◀──────────────────│
      │                     │                   │
      │        5. EmbeddingCallbackAction      │
      │◀──────────────────  │                   │
      │                     │                   │
      │                     │  6. Guardar Caché │
      │                     │──────────┐        │
      │                     │          │        │
      │                     │◀─────────┘        │
```

## Modelos de Embedding Soportados

| Modelo | Dimensiones | Max. Tokens | Descripción |
|--------|------------|------------|-------------|
| text-embedding-3-small | 1536 | 8191 | Modelo de uso general con excelente balance costo/rendimiento |
| text-embedding-3-large | 3072 | 8191 | Modelo de alta precisión para tareas complejas |
| text-embedding-ada-002 | 1536 | 8191 | Compatibilidad con sistemas legacy |

## Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **EmbeddingWorker** | Procesamiento asíncrono de acciones | ✅ Completo |
| **EmbeddingHandler** | Lógica principal de generación | ✅ Completo |
| **OpenAIClient** | Cliente para API de OpenAI | ✅ Completo |
| **ValidationService** | Validación de textos y parámetros | ✅ Completo |
| **EmbeddingProcessor** | Procesamiento y transformación | ✅ Completo |
| **CacheService** | Sistema de caché para embeddings | ✅ Completo |
| **EmbeddingContextHandler** | Manejo de contexto para operaciones | ✅ Completo |
| **EmbeddingCallbackHandler** | Manejo de callbacks asíncronos | ✅ Completo |

## Domain Actions

El servicio procesa las siguientes acciones de dominio:

### 1. Acciones de Entrada

```json
// EmbeddingGenerateAction - Genera embeddings para textos
{
  "action_id": "uuid-action-1",
  "action_type": "embedding.generate",
  "task_id": "task123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "texts": ["Este es un texto de ejemplo para generar embedding"],
    "model": "text-embedding-3-small",
    "use_cache": true
  },
  "callback_queue": "query.callbacks"
}

// EmbeddingValidateAction - Valida textos para embedding
{
  "action_id": "uuid-action-2",
  "action_type": "embedding.validate",
  "task_id": "task456",
  "tenant_id": "tenant1",
  "tenant_tier": "advance",
  "data": {
    "texts": ["Texto 1", "Texto 2", "Texto 3"],
    "model": "text-embedding-3-small"
  },
  "callback_queue": "ingestion.callbacks"
}
```

### 2. Acciones de Salida/Callback

```json
// EmbeddingCallbackAction - Retorna embeddings generados
{
  "action_id": "uuid-callback-1",
  "action_type": "embedding.callback",
  "task_id": "task123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "status": "completed",
    "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
    "model": "text-embedding-3-small",
    "dimensions": 1536,
    "total_tokens": 42,
    "processing_time": 0.352
  }
}

// EmbeddingErrorAction - Error durante generación de embedding
{
  "action_id": "uuid-error-1",
  "action_type": "embedding.error",
  "task_id": "task123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "error": "Error generando embeddings: token limit exceeded",
    "error_code": "EMBEDDING_TOKEN_LIMIT",
    "model": "text-embedding-3-small",
    "texts_count": 5
  }
}
```

## API HTTP

El servicio también expone endpoints REST para generación sincrónica de embeddings:

### Generar Embeddings

**POST** `/api/v1/embeddings`

```json
{
  "texts": ["texto 1", "texto 2"],
  "model": "text-embedding-3-small"
}
```

**Respuesta:**
```json
{
  "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "total_tokens": 42,
  "processing_time": 0.352
}
```

## Configuración

### Variables de Entorno

Todas las variables de entorno tienen el prefijo `EMBEDDING_`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `EMBEDDING_OPENAI_API_KEY` | API Key para OpenAI | - |
| `EMBEDDING_DEFAULT_EMBEDDING_MODEL` | Modelo por defecto | text-embedding-3-small |
| `EMBEDDING_MAX_BATCH_SIZE` | Número máximo de textos por batch | 100 |
| `EMBEDDING_MAX_TEXT_LENGTH` | Longitud máxima por texto en caracteres | 8000 |
| `EMBEDDING_OPENAI_TIMEOUT_SECONDS` | Timeout para llamadas a OpenAI | 30 |
| `EMBEDDING_CACHE_TTL_SECONDS` | Tiempo de vida del caché | 86400 |
| `EMBEDDING_CACHE_MAX_ITEMS` | Número máximo de items en caché | 10000 |
| `EMBEDDING_RETRY_ATTEMPTS` | Número de reintentos | 3 |
| `EMBEDDING_RETRY_BACKOFF_SECONDS` | Tiempo entre reintentos | 1.0 |

## Health Checks

- `GET /health` ➔ 200 OK si el servicio está funcionando correctamente
- `GET /ready` ➔ 200 OK si todas las dependencias (Redis, OpenAI API) están disponibles
- `GET /metrics/overview` ➔ Métricas básicas de uso del servicio
- `GET /metrics/usage` ➔ Métricas de uso de tokens y costos estimados

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Temporal**: Al igual que otros servicios, utiliza Redis para almacenar métricas y resultados. Se planea migrar a PostgreSQL para persistencia permanente.

- **Sistema de Métricas Parcial**: Aunque captura tiempo de procesamiento y tokens utilizados, no hay un dashboard ni análisis detallado.

- **Límites de Tier**: Aunque existe validación por tier, algunas capacidades avanzadas del tier Enterprise no están completamente implementadas.

- **Falta Integración con Vector Store**: Actualmente sólo genera embeddings pero no los almacena en una base de datos vectorial.

### Próximos Pasos

1. **Implementar Persistencia**: Añadir almacenamiento en PostgreSQL para embeddings y métricas para mantener histórico y análisis.

2. **Integrar con Vector Store**: Conectar con un servicio de almacenamiento vectorial (Qdrant, Pinecone) para búsqueda eficiente.

3. **Expandir Métricas**: Añadir métricas detalladas de uso, tiempos y costos por tenant con dashboard visual.

4. **Optimización de Caché**: Mejorar el sistema de caché para reducir llamadas a OpenAI y reducir costos operativos.

5. **Soporte para Múltiples Proveedores**: Añadir integración con otros proveedores de embeddings (Cohere, Azure OpenAI).

6. **Comprimir Embeddings**: Implementar técnicas de compresión para reducir costos de almacenamiento y transmisión.
