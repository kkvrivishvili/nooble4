# Análisis del Query Service

## 1. Variables de Entorno Necesarias

El Query Service utiliza las siguientes variables de entorno:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Query Service (con prefijo QUERY_)
- `QUERY_DOMAIN_NAME`: Dominio para la gestión de colas. Valor por defecto: "query"
- `QUERY_REDIS_URL`: URL específica de Redis para el Query Service. Valor por defecto: "redis://localhost:6379/0"
- `QUERY_QUERY_ACTIONS_QUEUE_PREFIX`: Prefijo para las colas de acciones. Valor por defecto: "query"
- `QUERY_CALLBACK_QUEUE_PREFIX`: Prefijo para colas de callback hacia servicios solicitantes. Valor por defecto: "execution"
- `QUERY_GROQ_API_KEY`: API Key para Groq (proveedor de LLM). Valor por defecto: ""
- `QUERY_DEFAULT_LLM_MODEL`: Modelo LLM a utilizar por defecto. Valor por defecto: "llama3-8b-8192"
- `QUERY_LLM_TEMPERATURE`: Temperatura para generación LLM. Valor por defecto: 0.3
- `QUERY_LLM_MAX_TOKENS`: Máximo número de tokens en respuestas LLM. Valor por defecto: 1024
- `QUERY_LLM_TIMEOUT_SECONDS`: Timeout para llamadas a LLM en segundos. Valor por defecto: 30
- `QUERY_LLM_TOP_P`: Parámetro top_p para generación LLM. Valor por defecto: 1.0
- `QUERY_LLM_N`: Número de completions a generar por el LLM. Valor por defecto: 1
- `QUERY_VECTOR_DB_URL`: URL de la base de datos vectorial. Valor por defecto: "http://localhost:8006"
- `QUERY_SIMILARITY_THRESHOLD`: Umbral de similitud para búsquedas vectoriales. Valor por defecto: 0.7
- `QUERY_DEFAULT_TOP_K`: Número predeterminado de resultados a devolver. Valor por defecto: 5
- `QUERY_SEARCH_CACHE_TTL`: TTL del cache de búsquedas en segundos. Valor por defecto: 300
- `QUERY_COLLECTION_CONFIG_CACHE_TTL`: TTL del cache de configuraciones de colección en segundos. Valor por defecto: 600
- `QUERY_TIER_LIMITS`: JSON con límites por tier (free, advance, professional, enterprise)
- `QUERY_HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP específico del servicio. Valor por defecto: 15
- `QUERY_MAX_RETRIES`: Número máximo de reintentos para peticiones. Valor por defecto: 3
- `QUERY_LLM_RETRY_ATTEMPTS`: Intentos de retry específicos para LLM. Valor por defecto: 3
- `QUERY_LLM_RETRY_MIN_SECONDS`: Segundos mínimos entre reintentos de LLM. Valor por defecto: 1
- `QUERY_LLM_RETRY_MAX_SECONDS`: Segundos máximos entre reintentos de LLM. Valor por defecto: 10
- `QUERY_LLM_RETRY_MULTIPLIER`: Multiplicador para backoff exponencial en reintentos. Valor por defecto: 1.0
- `QUERY_WORKER_SLEEP_SECONDS`: Tiempo de espera entre polls del worker. Valor por defecto: 1.0
- `QUERY_ENABLE_QUERY_TRACKING`: Habilita tracking de métricas de consulta. Valor por defecto: True
- `QUERY_LLM_MODELS_INFO`: JSON con información sobre modelos LLM disponibles (configuración de contexto, pricing, etc.)

## 2. Variables de Configuración para `constants.py` (implementado)

Se ha implementado el archivo `constants.py` en el Query Service con las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: Nombre del servicio ("query-service")
- `DEFAULT_DOMAIN`: Dominio por defecto para colas ("query")

### Constantes de Cola
- `DEFAULT_QUEUE_PREFIX`: "query"
- `CALLBACK_QUEUE_PREFIX`: "execution"
- `DEFAULT_WORKER_SLEEP_SECONDS`: 1.0

### Constantes de LLM (Groq)
- `DEFAULT_LLM_MODEL`: "llama3-8b-8192"
- `LLM_TEMPERATURE`: 0.3
- `LLM_MAX_TOKENS`: 1024
- `LLM_TIMEOUT_SECONDS`: 30
- `LLM_TOP_P`: 1.0
- `LLM_N_COMPLETIONS`: 1

### Constantes de Modelos LLM
```python
LLM_MODELS_INFO = {
    "llama3-8b-8192": {
        "name": "Llama-3 8B",
        "context_window": 8192,
        "pricing_input": 0.20,
        "pricing_output": 0.80,
        "provider": "groq"
    },
    "llama3-70b-8192": {
        "name": "Llama-3 70B",
        "context_window": 8192,
        "pricing_input": 0.70,
        "pricing_output": 1.60,
        "provider": "groq"
    }
}
```

### Constantes de Vector Store
- `VECTOR_DB_URL`: "http://localhost:8006"
- `DEFAULT_SIMILARITY_THRESHOLD`: 0.7
- `DEFAULT_TOP_K`: 5

### Constantes para Caché
- `DEFAULT_SEARCH_CACHE_TTL`: 300  # segundos
- `DEFAULT_COLLECTION_CONFIG_CACHE_TTL`: 600  # segundos

### Constantes para Límites por Tier
```python
TIER_LIMITS = {
    "free": {
        "max_queries_per_hour": 50,
        "max_results": 5,
        "max_query_length": 500,
        "cache_enabled": True
    },
    "advance": {
        "max_queries_per_hour": 200,
        "max_results": 10,
        "max_query_length": 1000,
        "cache_enabled": True
    },
    "professional": {
        "max_queries_per_hour": 1000,
        "max_results": 20,
        "max_query_length": 2000,
        "cache_enabled": True
    },
    "enterprise": {
        "max_queries_per_hour": None,  # Sin límites
        "max_results": 50,
        "max_query_length": 5000,
        "cache_enabled": True
    }
}
```

### Constantes para HTTP y Reintentos
- `HTTP_TIMEOUT_SECONDS`: 15
- `MAX_RETRIES`: 3

### Constantes para Reintentos de LLM
- `LLM_RETRY_ATTEMPTS`: 3
- `LLM_RETRY_MIN_SECONDS`: 1
- `LLM_RETRY_MAX_SECONDS`: 10
- `LLM_RETRY_MULTIPLIER`: 1.0

### Constantes para Tipos de Acción
- `ACTION_TYPES`: Enumeración de tipos de acción soportados
  ```python
  {
      "QUERY_GENERATE": "query.generate",
      "SEARCH_DOCS": "query.search",
      "QUERY_CALLBACK": "query.callback"
  }
  ```

### Constantes para Métricas
- `DEFAULT_QUERY_TRACKING_ENABLED`: True
- `METRICS_WINDOW_SECONDS`: 3600  # 1 hora para agregación de métricas
- `PERFORMANCE_METRICS_FIELDS`: Lista de campos para tracking de performance de consultas
