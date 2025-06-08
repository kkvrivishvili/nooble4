# Análisis del Agent Management Service

## 1. Variables de Entorno Necesarias

El Agent Management Service utiliza las siguientes variables de entorno:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Agent Management Service (con prefijo AGENT_MANAGEMENT_)
- `AGENT_MANAGEMENT_DOMAIN_NAME`: Dominio para la gestión de colas. Valor por defecto: "management"
- `AGENT_MANAGEMENT_INGESTION_SERVICE_URL`: URL del Ingestion Service para validar collections. Valor por defecto: "http://localhost:8006"
- `AGENT_MANAGEMENT_EXECUTION_SERVICE_URL`: URL del Agent Execution Service para cache invalidation. Valor por defecto: "http://localhost:8005"
- `AGENT_MANAGEMENT_DATABASE_URL`: URL de base de datos para agentes. Valor por defecto: "postgresql://user:pass@localhost/nooble_agents"
- `AGENT_MANAGEMENT_AGENT_CONFIG_CACHE_TTL`: TTL del cache de configuraciones de agente en segundos. Valor por defecto: 300
- `AGENT_MANAGEMENT_TIER_LIMITS`: JSON con límites y capacidades por tier. Valor por defecto incluye configuraciones para tiers free, advance, professional y enterprise con sus respectivas limitaciones de agentes, herramientas disponibles, modelos disponibles, etc.
- `AGENT_MANAGEMENT_TEMPLATES_PATH`: Ruta base para templates del sistema. Valor por defecto: "agent_management_service/templates"
- `AGENT_MANAGEMENT_ENABLE_COLLECTION_VALIDATION`: Habilitar validación de collections con Ingestion Service. Valor por defecto: True

## 2. Variables de Configuración para `constants.py`

Para un posible archivo `constants.py` en el Agent Management Service, se recomienda incluir las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: Nombre del servicio ("agent-management-service")
- `DEFAULT_DOMAIN`: Dominio por defecto para colas ("management")

### Constantes de Servicios Externos
- `INGESTION_SERVICE_URL`: "http://localhost:8006"
- `EXECUTION_SERVICE_URL`: "http://localhost:8005"

### Constantes de Base de Datos
- `DEFAULT_DATABASE_URL`: "postgresql://user:pass@localhost/nooble_agents"

### Constantes de Caché
- `DEFAULT_AGENT_CONFIG_CACHE_TTL`: 300  # segundos

### Constantes de Límites por Tier
```python
TIER_LIMITS = {
    "free": {
        "max_agents": 1,
        "available_tools": ["basic_chat", "datetime"],
        "available_models": ["llama3-8b-8192"],
        "max_collections_per_agent": 1,
        "templates_access": ["customer_service"]
    },
    "advance": {
        "max_agents": 3,
        "available_tools": ["basic_chat", "datetime", "rag_query", "calculator"],
        "available_models": ["llama3-8b-8192", "llama3-70b-8192"],
        "max_collections_per_agent": 3,
        "templates_access": ["customer_service", "knowledge_base"]
    },
    "professional": {
        "max_agents": 10,
        "available_tools": ["all"],
        "available_models": ["all"],
        "max_collections_per_agent": 10,
        "templates_access": ["all"],
        "custom_templates": True
    },
    "enterprise": {
        "max_agents": None,
        "available_tools": ["all"],
        "available_models": ["all"],
        "max_collections_per_agent": None,
        "templates_access": ["all"],
        "custom_templates": True,
        "advanced_workflows": True
    }
}
```

### Constantes de Templates
- `DEFAULT_TEMPLATES_PATH`: "agent_management_service/templates"
- `SYSTEM_TEMPLATE_CATEGORIES`: Lista de categorías de templates del sistema (ej: ["customer_service", "knowledge_base", "development", "marketing"])
- `TEMPLATE_FILE_EXTENSION`: ".json"  # Extensión para archivos de template

### Constantes de Validación
- `ENABLE_COLLECTION_VALIDATION`: True
- `DEFAULT_VALIDATION_TIMEOUT`: 30  # segundos

### Constantes para Tipos de Acción
- `ACTION_TYPES`: Enumeración de tipos de acción soportados
  ```python
  {
      "VALIDATE_AGENT": "management.validate_agent",
      "INVALIDATE_CACHE": "management.invalidate_cache"
  }
  ```

### Constantes para URLs Públicas
- `SLUG_LENGTH`: 8  # Longitud de slugs generados para URLs públicas
- `PUBLIC_URL_BASE`: "https://nooble.ai/agents/"  # Base para URLs públicas

### Constantes de Modelos Soportados
- `SUPPORTED_MODELS`: Lista de modelos soportados con sus configuraciones
  ```python
  {
      "llama3-8b-8192": {
          "display_name": "Llama 3 8B",
          "context_length": 8192,
          "tier_access": ["free", "advance", "professional", "enterprise"]
      },
      "llama3-70b-8192": {
          "display_name": "Llama 3 70B",
          "context_length": 8192,
          "tier_access": ["advance", "professional", "enterprise"]
      }
      # Más modelos aquí
  }
  ```

### Constantes de Herramientas Soportadas
- `SUPPORTED_TOOLS`: Lista de herramientas disponibles con sus configuraciones
  ```python
  {
      "basic_chat": {
          "display_name": "Chat Básico",
          "tier_access": ["free", "advance", "professional", "enterprise"]
      },
      "datetime": {
          "display_name": "Fecha y Hora",
          "tier_access": ["free", "advance", "professional", "enterprise"]
      },
      "rag_query": {
          "display_name": "Consulta RAG",
          "tier_access": ["advance", "professional", "enterprise"]
      }
      # Más herramientas aquí
  }
  ```
