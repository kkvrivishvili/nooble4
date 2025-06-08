# Análisis del Embedding Service

## 1. Variables de Entorno Necesarias

El Embedding Service utiliza las siguientes variables de entorno:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Embedding Service (con prefijo EMBEDDING_)
- `EMBEDDING_DOMAIN_NAME`: Dominio para la gestión de colas. (Implícito, aparentemente "embedding")
- `EMBEDDING_OPENAI_API_KEY`: API Key para OpenAI. Valor por defecto: "sk-" (en producción debe configurarse correctamente)
- `EMBEDDING_DEFAULT_EMBEDDING_MODEL`: Modelo de embedding predeterminado. Valor por defecto: "text-embedding-3-small"
- `EMBEDDING_PREFERRED_DIMENSIONS`: Dimensiones preferidas para embeddings (0 = usar default del modelo). Valor por defecto: 0
- `EMBEDDING_ENCODING_FORMAT`: Formato de codificación de embeddings (float o base64). Valor por defecto: "float"
- `EMBEDDING_MAX_BATCH_SIZE`: Número máximo de textos por batch. Valor por defecto: 100
- `EMBEDDING_MAX_TEXT_LENGTH`: Longitud máxima de texto en caracteres. Valor por defecto: 8000
- `EMBEDDING_OPENAI_TIMEOUT_SECONDS`: Timeout para llamadas a OpenAI. Valor por defecto: 30

## 2. Variables de Configuración para `constants.py` (implementado)

Se ha implementado el archivo `constants.py` en el Embedding Service con las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: Nombre del servicio ("embedding-service")
- `DEFAULT_DOMAIN`: Dominio por defecto para colas ("embedding")
- `DEFAULT_PORT`: Puerto del servicio (8001)

### Constantes para OpenAI
- `DEFAULT_EMBEDDING_MODEL`: "text-embedding-3-small"
- `DEFAULT_ENCODING_FORMAT`: "float"
- `OPENAI_TIMEOUT_SECONDS`: 30

### Constantes para Modelos de Embedding
```python
OPENAI_MODELS = {
    "text-embedding-3-small": {
        "dimensions": 1536,
        "max_tokens": 8191,
        "description": "Modelo de uso general con excelente balance costo/rendimiento"
    },
    "text-embedding-3-large": {
        "dimensions": 3072,
        "max_tokens": 8191,
        "description": "Modelo de alta precisión para tareas complejas"
    },
    "text-embedding-ada-002": {
        "dimensions": 1536,
        "max_tokens": 8191,
        "description": "Compatibilidad con sistemas legacy"
    }
}
```

### Constantes para Límites Operacionales
- `MAX_BATCH_SIZE`: 100
- `MAX_TEXT_LENGTH`: 8000

### Constantes para Tipos de Acción
```python
ACTION_TYPES = {
    "GENERATE": "embedding.generate",
    "VALIDATE": "embedding.validate",
    "CALLBACK": "embedding.callback"
}
```

### Constantes para Formatos de Codificación
```python
ENCODING_FORMATS = {
    "FLOAT": "float",
    "BASE64": "base64"
}
```

### Constantes para Métricas y Monitoring
- `METRICS_WINDOW_SECONDS`: 3600  # 1 hora para agregación de métricas
- `PERFORMANCE_METRICS_FIELDS`: Lista de campos para tracking de performance

### Constantes para Callbacks
- `DEFAULT_CALLBACK_TIMEOUT_SECONDS`: 10
- `MAX_RETRY_ATTEMPTS`: 3
