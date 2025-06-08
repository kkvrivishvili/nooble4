# Análisis del Agent Orchestrator Service

## 1. Variables de Entorno Necesarias

El Agent Orchestrator Service utiliza las siguientes variables de entorno:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Orchestrator (con prefijo ORCHESTRATOR_)
- `ORCHESTRATOR_DOMAIN_NAME`: Dominio para la gestión de colas. Valor por defecto: "orchestrator"
- `ORCHESTRATOR_WEBSOCKET_PING_INTERVAL`: Intervalo de ping para WebSocket en segundos. Valor por defecto: 30
- `ORCHESTRATOR_WEBSOCKET_PING_TIMEOUT`: Timeout para recibir pong en WebSocket en segundos. Valor por defecto: 10
- `ORCHESTRATOR_MAX_WEBSOCKET_CONNECTIONS`: Máximo de conexiones WebSocket simultáneas. Valor por defecto: 1000
- `ORCHESTRATOR_CALLBACK_QUEUE_PREFIX`: Prefijo para las colas de callback. Valor por defecto: "orchestrator"
- `ORCHESTRATOR_MAX_REQUESTS_PER_SESSION`: Máximo de requests por sesión por hora. Valor por defecto: 100
- `ORCHESTRATOR_WORKER_SLEEP_SECONDS`: Tiempo de espera entre polls del worker. Valor por defecto: 1.0
- `ORCHESTRATOR_ENABLE_ACCESS_VALIDATION`: Habilita validación de acceso tenant->agent. Valor por defecto: True
- `ORCHESTRATOR_VALIDATION_CACHE_TTL`: TTL del cache de validaciones en segundos. Valor por defecto: 300
- `ORCHESTRATOR_REQUIRED_HEADERS`: Lista de headers requeridos para requests. Valor por defecto: "X-Tenant-ID,X-Agent-ID,X-Tenant-Tier,X-Session-ID"
- `ORCHESTRATOR_ENABLE_PERFORMANCE_TRACKING`: Habilita tracking de performance. Valor por defecto: True

## 2. Variables de Configuración para `constants.py` (implementado)

Se ha implementado el archivo `constants.py` en el Agent Orchestrator Service con las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: Nombre del servicio ("agent-orchestrator-service")
- `DEFAULT_DOMAIN`: Dominio por defecto para colas ("orchestrator")

### Constantes de WebSocket
- `WEBSOCKET_PING_INTERVAL_SECONDS`: 30
- `WEBSOCKET_PING_TIMEOUT_SECONDS`: 10
- `MAX_WEBSOCKET_CONNECTIONS`: 1000
- `WEBSOCKET_MESSAGE_TYPES`: Enumeración de tipos de mensajes WebSocket (ERROR, INFO, RESPONSE, CHUNK, etc.)

### Constantes de Colas y Processing
- `CALLBACK_QUEUE_PREFIX`: "orchestrator"
- `DEFAULT_WORKER_SLEEP_SECONDS`: 1.0

### Constantes de Rate Limiting
- `MAX_REQUESTS_PER_SESSION_DEFAULT`: 100
- `RATE_LIMITING_TIERS`: Diccionario con límites específicos por tier
  ```python
  {
      "free": 50,      # 50 requests por sesión por hora
      "advance": 100,  # 100 requests por sesión por hora
      "professional": 300,  # 300 requests por sesión por hora
      "enterprise": 500  # 500 requests por sesión por hora
  }
  ```

### Constantes de Validación
- `DEFAULT_VALIDATION_CACHE_TTL`: 300
- `REQUIRED_HEADERS`: ["X-Tenant-ID", "X-Agent-ID", "X-Tenant-Tier", "X-Session-ID"]

### Constantes de Métricas
- `PERFORMANCE_METRICS_FIELDS`: Lista de campos para tracking de performance
- `CONNECTION_STATUS_TYPES`: Enumeración de estados de conexión WebSocket

### Constantes de HTTP
- `DEFAULT_HTTP_TIMEOUT_SECONDS`: 30
