# Análisis del Agent Execution Service

## 1. Variables de Entorno Necesarias

El Agent Execution Service utiliza las siguientes variables de entorno:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Execution Service (con prefijo EXECUTION_)
- `EXECUTION_DOMAIN_NAME`: Dominio para la gestión de colas. Valor por defecto: "execution"
- `EXECUTION_EMBEDDING_SERVICE_URL`: URL del Embedding Service. Valor por defecto: "http://localhost:8001"
- `EXECUTION_QUERY_SERVICE_URL`: URL del Query Service. Valor por defecto: "http://localhost:8002"
- `EXECUTION_CONVERSATION_SERVICE_URL`: URL del Conversation Service. Valor por defecto: "http://localhost:8004"
- `EXECUTION_AGENT_MANAGEMENT_SERVICE_URL`: URL del Agent Management Service. Valor por defecto: "http://localhost:8003"
- `EXECUTION_DEFAULT_AGENT_TYPE`: Tipo de agente por defecto. Valor por defecto: "conversational"
- `EXECUTION_MAX_ITERATIONS`: Máximo de iteraciones para agentes. Valor por defecto: 5
- `EXECUTION_MAX_EXECUTION_TIME`: Tiempo máximo de ejecución en segundos. Valor por defecto: 120
- `EXECUTION_CALLBACK_QUEUE_PREFIX`: Prefijo para colas de callback hacia orchestrator. Valor por defecto: "orchestrator"
- `EXECUTION_AGENT_CONFIG_CACHE_TTL`: TTL del caché de configuraciones de agente en segundos. Valor por defecto: 300
- `EXECUTION_TIER_LIMITS`: JSON con límites por tier. Valor por defecto: `{"free": {"max_iterations": 3, "max_tools": 2, "timeout": 30}, "advance": {"max_iterations": 5, "max_tools": 5, "timeout": 60}, "professional": {"max_iterations": 10, "max_tools": 10, "timeout": 120}, "enterprise": {"max_iterations": 20, "max_tools": null, "timeout": 300}}`
- `EXECUTION_WORKER_SLEEP_SECONDS`: Tiempo de espera entre polls del worker. Valor por defecto: 1.0
- `EXECUTION_ENABLE_EXECUTION_TRACKING`: Habilita tracking de métricas de ejecución. Valor por defecto: True

## 2. Variables de Configuración para `constants.py` (implementado)

Se ha implementado el archivo `constants.py` en el Agent Execution Service con las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: Nombre del servicio ("agent-execution-service")
- `DEFAULT_DOMAIN`: Dominio por defecto para colas ("execution")

### Constantes de Servicios Externos
- `EMBEDDING_SERVICE_URL`: "http://localhost:8001"
- `QUERY_SERVICE_URL`: "http://localhost:8002"
- `CONVERSATION_SERVICE_URL`: "http://localhost:8004"
- `AGENT_MANAGEMENT_SERVICE_URL`: "http://localhost:8003"

### Constantes de LangChain
- `DEFAULT_AGENT_TYPE`: "conversational"
- `DEFAULT_MAX_ITERATIONS`: 5
- `DEFAULT_MAX_EXECUTION_TIME`: 120  # segundos
- `SUPPORTED_AGENT_TYPES`: Lista de tipos de agentes soportados (ej: ["conversational", "tool_use", "custom"])

### Constantes de Colas y Processing
- `CALLBACK_QUEUE_PREFIX`: "orchestrator"
- `DEFAULT_WORKER_SLEEP_SECONDS`: 1.0

### Constantes de Caché
- `DEFAULT_AGENT_CONFIG_CACHE_TTL`: 300  # segundos

### Constantes de Límites por Tier
```python
TIER_LIMITS = {
    "free": {"max_iterations": 3, "max_tools": 2, "timeout": 30},
    "advance": {"max_iterations": 5, "max_tools": 5, "timeout": 60},
    "professional": {"max_iterations": 10, "max_tools": 10, "timeout": 120},
    "enterprise": {"max_iterations": 20, "max_tools": None, "timeout": 300}
}
```

### Constantes de Métricas
- `EXECUTION_METRICS_FIELDS`: Lista de campos para tracking de ejecución
- `DEFAULT_METRICS_WINDOW`: 3600  # ventana de 1 hora para métricas básicas

### Constantes para Tipos de Acción
- `ACTION_TYPES`: Enumeración de tipos de acción soportados
  ```python
  {
      "AGENT_RUN": "execution.agent_run",
      "CALLBACK": "execution.callback",
      "EMBEDDING_CALLBACK": "embedding.callback",
      "QUERY_CALLBACK": "query.callback"
  }
  ```

### Constantes HTTP
- `DEFAULT_HTTP_TIMEOUT`: 30  # segundos
