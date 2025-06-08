# Análisis del Conversation Service

## 1. Variables de Entorno Necesarias

El Conversation Service utiliza las siguientes variables de entorno:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Conversation Service (con prefijo CONVERSATION_)
- `CONVERSATION_DOMAIN_NAME`: Dominio para la gestión de colas. Valor por defecto: "conversation"
- `CONVERSATION_DATABASE_URL`: URL de la base de datos para conversaciones. Valor por defecto: "postgresql://user:pass@localhost/conversations"
- `CONVERSATION_CONVERSATION_CACHE_TTL`: TTL del caché de conversaciones en segundos. Valor por defecto: 300
- `CONVERSATION_ENABLE_REALTIME_ANALYTICS`: Habilitar analytics en tiempo real. Valor por defecto: True
- `CONVERSATION_ANALYTICS_BATCH_SIZE`: Tamaño de batch para procesamiento de analytics. Valor por defecto: 100
- `CONVERSATION_CRM_ENABLED`: Habilitar integración con CRM. Valor por defecto: False
- `CONVERSATION_CRM_PROVIDER`: Proveedor de CRM a utilizar. Valor por defecto: "hubspot"
- `CONVERSATION_CRM_API_KEY`: API Key del CRM. Valor por defecto: ""
- `CONVERSATION_DEFAULT_RETENTION_DAYS`: Días de retención por defecto para conversaciones. Valor por defecto: 90
- `CONVERSATION_MAX_CONTEXT_WINDOW`: Máximo de mensajes en ventana de contexto. Valor por defecto: 50
- `CONVERSATION_SEARCH_INDEX_ENABLED`: Habilitar índice de búsqueda. Valor por defecto: True
- `CONVERSATION_WORKER_SLEEP_SECONDS`: Tiempo de espera entre polls del worker. Valor por defecto: 1.0

## 2. Variables de Configuración para `constants.py` (implementado)

Se ha implementado el archivo `constants.py` en el Conversation Service con las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: Nombre del servicio ("conversation-service")
- `DEFAULT_DOMAIN`: Dominio por defecto para colas ("conversation")
- `DEFAULT_PORT`: Puerto del servicio (8004)

### Constantes de Trabajador
- `WORKER_SLEEP_SECONDS`: 1.0

### Constantes de Caché
- `CONVERSATION_CACHE_TTL`: 300  # segundos

### Constantes de Retención de Datos
- `DEFAULT_RETENTION_DAYS`: 90
- `MAX_CONTEXT_WINDOW`: 50

### Constantes para Analytics
- `ENABLE_REALTIME_ANALYTICS`: True
- `ANALYTICS_BATCH_SIZE`: 100

### Constantes para Integración CRM
- `CRM_ENABLED`: False
- `DEFAULT_CRM_PROVIDER`: "hubspot"
- `CRM_PROVIDERS`: Lista de proveedores CRM soportados
  ```python
  {
      "HUBSPOT": "hubspot",
      "SALESFORCE": "salesforce",
      "ZOHO": "zoho"
  }
  ```

### Constantes para Performance
- `SEARCH_INDEX_ENABLED`: True

### Constantes para Tipos de Acción
- `ACTION_TYPES`: Enumeración de tipos de acción soportados
  ```python
  {
      "SAVE_MESSAGE": "conversation.save_message",
      "GET_HISTORY": "conversation.get_history",
      "ANALYZE": "conversation.analyze"
  }
  ```

### Constantes para Roles de Mensaje
- `MESSAGE_ROLES`: Roles de mensaje disponibles
  ```python
  {
      "USER": "user",
      "ASSISTANT": "assistant",
      "SYSTEM": "system"
  }
  ```

### Constantes para Tipos de Mensaje
- `MESSAGE_TYPES`: Tipos de mensaje soportados
  ```python
  {
      "TEXT": "text",
      "IMAGE": "image",
      "FILE": "file",
      "AUDIO": "audio",
      "VIDEO": "video"
  }
  ```

### Constantes para Análisis
- `ANALYSIS_TYPES`: Tipos de análisis disponibles
  ```python
  {
      "SENTIMENT": "sentiment",
      "KEYWORDS": "keywords",
      "INTENTION": "intention",
      "SUMMARY": "summary"
  }
  ```

### Constantes para Ordenamiento
- `SORT_ORDERS`: Opciones de ordenamiento
  ```python
  {
      "ASC": "asc",
      "DESC": "desc"
  }
  ```

### Constantes de Base de Datos
- `DEFAULT_DATABASE_URL`: "postgresql://user:pass@localhost/conversations"
