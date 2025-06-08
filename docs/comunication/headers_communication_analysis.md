# Análisis de Comunicación entre Servicios mediante Headers

## 1. Introducción

Este documento analiza el flujo de información entre los diferentes servicios del ecosistema nooble4, con foco en los headers HTTP y colas Redis. El objetivo es optimizar la comunicación, reducir llamadas redundantes entre servicios y eliminar valores hardcodeados, facilitando una arquitectura más escalable y configurable.

Un aspecto crítico de este análisis es entender el ciclo de vida de los headers (que entran una sola vez desde el frontend) y cómo esta información debe propagarse a través del sistema de colas de Redis para evitar consultas adicionales entre servicios.

## 2. Estado Actual de Comunicación entre Servicios

### 2.1 Flujo de Comunicación

Actualmente, los servicios del ecosistema nooble4 se comunican principalmente mediante:

1. **Headers HTTP** - Información básica que entra una sola vez desde el frontend al Agent Orchestrator
2. **Colas Redis** - Sistema principal de comunicación asincrónica entre servicios internos
3. **Llamadas API directas** - Consultas adicionales para obtener información no disponible en los headers originales
4. **Valores hardcodeados** - Configuraciones estáticas en cada servicio

### 2.2 Ciclo de Vida de las Comunicaciones

```
Frontend ─── Headers HTTP ───► Agent Orchestrator
                                     │
                                ┌────┼───────────────────┐
                                │    │                   │
                          Cola Redis  Cola Redis     Cola Redis
                          (dominio:id:tier)  (diferentes dominios)
                                │    │                   │
                                ▼    ▼                   ▼
                            Servicio A   Servicio B   Servicio C
```

### 2.3 Problemática Actual

- **Consultas redundantes**: Cada servicio consulta al Agent Management Service para información que podría estar en headers
- **Configuraciones hardcodeadas**: Valores como modelos de LLM, umbrales de similitud, etc., están hardcodeados
- **Gestión ineficiente de colas**: Las colas Redis no se limpian automáticamente después de completar tareas
- **Desaprovechamiento de los headers**: No se utilizan como vehículo completo de información técnica

## 3. Headers Actuales y su Propósito

### 3.1 Headers Obligatorios Actuales

| Header | Descripción | Usado en | Propósito |
|--------|-------------|----------|-----------|
| `X-Tenant-ID` | ID del tenant | Todos los servicios | Identificar organización/cliente |
| `X-Agent-ID` | ID del agente | Todos los servicios | Identificar agente conversacional |
| `X-Tenant-Tier` | Nivel de servicio | Todos los servicios | Aplicar límites y funcionalidades |
| `X-Session-ID` | ID de sesión WebSocket | Agent Orchestrator | Gestionar conexiones WebSocket |

### 3.2 Headers Opcionales Actuales

| Header | Descripción | Usado en | Propósito |
|--------|-------------|----------|-----------|
| `X-Context-Type` | Tipo de contexto | Agent Orchestrator, Agent Execution | Definir contexto de ejecución |
| `X-User-ID` | ID del usuario final | Todos los servicios | Personalización y análisis |
| `X-Conversation-ID` | ID de la conversación | Agent Orchestrator, Agent Execution | Mantener contexto conversacional |
| `X-Collection-ID` | ID de collection | Agent Execution, Query Service | Dirigir búsquedas a collection específica |
| `X-Request-Source` | Origen de la solicitud | Todos los servicios | Tracking y análisis |
| `X-Client-Version` | Versión del cliente | Todos los servicios | Compatibilidad |

## 4. Propuesta de Nuevos Headers para Optimización

### 4.1 Headers para Configuración de LLM

| Header Propuesto | Descripción | Servicios Impactados | Beneficio |
|------------------|-------------|---------------------|-----------|
| `X-LLM-Model` | Modelo LLM a utilizar | Agent Execution, Query Service | Eliminar hardcodeo de modelos |
| `X-LLM-Temperature` | Temperatura para generación | Agent Execution, Query Service | Configuración dinámica |
| `X-LLM-Max-Tokens` | Máximo de tokens | Agent Execution, Query Service | Control de costos y rendimiento |
| `X-LLM-Provider` | Proveedor de LLM (OpenAI, Groq) | Agent Execution, Query Service | Flexibilidad de proveedores |

### 4.2 Headers para Configuración de Embeddings

| Header Propuesto | Descripción | Servicios Impactados | Beneficio |
|------------------|-------------|---------------------|-----------|
| `X-Embedding-Model` | Modelo de embedding | Embedding Service, Query Service | Alinear con collections |
| `X-Embedding-Dimensions` | Dimensiones del vector | Embedding Service, Query Service | Compatibilidad con diferentes modelos |
| `X-Embedding-Provider` | Proveedor de embeddings | Embedding Service | Flexibilidad de proveedores |

### 4.3 Headers para Configuración RAG

| Header Propuesto | Descripción | Servicios Impactados | Beneficio |
|------------------|-------------|---------------------|-----------|
| `X-RAG-Collections` | Collections asociadas (JSON) | Agent Execution, Query Service | Evitar consultas a Agent Management |
| `X-RAG-Similarity-Threshold` | Umbral de similitud | Query Service | Personalización por agente |
| `X-RAG-Results-Limit` | Límite de resultados | Query Service | Control de costos y relevancia |
| `X-RAG-Chunk-Size` | Tamaño de chunks | Ingestion Service | Personalización por contenido |

## 5. Flujo de Información Propuesto

### 5.1 Ciclo de Vida Completo de la Información

```
┌──────────────┐       Headers HTTP       ┌───────────────────┐
│   Frontend   │─────────────────────────►│ Agent Orchestrator │
└──────────────┘                        │        Service      │
                                        └──────────┬──────────┘
                                                   │
                                                   ▼
                                     ┌───────────────────────────┐
                                     │  Enriquecimiento Headers  │
                                     │  (Consulta Agent Mgmt)    │
                                     └───────────┬───────────────┘
                                                 │
                                                 ▼
                         ┌─────────────────────────────────────────────┐
                         │           Colas Redis por Tier              │
                         │  {domain}:{context_id}:{tier}              │
                         └───┬─────────────────┬────────────────┬──────┘
                             │                 │                │
                             ▼                 ▼                ▼
                     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                     │ Servicio A   │  │ Servicio B   │  │ Servicio C   │
                     └──────────────┘  └──────────────┘  └──────────────┘
                             │                 │                │
                             └─────────────────┼────────────────┘
                                               │
                                               ▼
                                    ┌────────────────────┐
                                    │   Limpieza Colas   │
                                    │   (post-task)      │
                                    └────────────────────┘
```

### 5.2 Proceso de Propagación de Información

1. **Entrada de Headers (Frontend → Agent Orchestrator)**
   - Frontend envía todos los headers necesarios una sola vez
   - Se incluyen headers básicos y de configuración específica

2. **Enriquecimiento en Agent Orchestrator**
   - Valida headers básicos
   - Consulta Agent Management Service para información adicional (solo una vez)
   - Prepara datos para propagación a todos los servicios

3. **Propagación vía Domain Actions en Redis**
   - Crea objetos `DomainAction` con toda la información necesaria
   - Incluye `execution_context` completo con datos enriquecidos
   - Encola en formato `{domain}:{context_id}:{tier}` para priorización

4. **Consumo en Servicios Receptores**
   - Consumen información directamente de los objetos `DomainAction`
   - No necesitan hacer consultas adicionales a otros servicios
   - Utilizan la información del contexto de ejecución para toda la tarea

5. **Limpieza Post-Tarea**
   - Al completar la tarea, las colas asociadas se limpian automáticamente
   - Se evita acumulación de colas abandonadas y se optimizan recursos

## 6. Implementación en Servicios Específicos

### 6.1 Agent Orchestrator Service

### 6.1.1 Rol Central en la Comunicación

Este servicio debe convertirse en el "gateway de información", actuando como punto central de entrada y enriquecimiento de datos. Es responsable de:

- **Recibir y validar headers** básicos que entran una sola vez desde el frontend
- **Enriquecer el contexto de ejecución** con información adicional
- **Propagar información completa** a través del sistema DomainAction/Redis
- **Mantener caché** de configuraciones por agente para optimizar rendimiento
- **Gestionar limpieza de colas** al finalizar tareas para evitar acumulación

### 6.1.2 Implementación del Enriquecimiento de Contexto

El punto crítico del sistema es cómo el Agent Orchestrator enriquece la información que recibe del frontend. Se propone la siguiente implementación en `context_handler.py`:

```python
async def create_enriched_context_from_headers(
    self,
    tenant_id: str,
    agent_id: str,
    tenant_tier: str,
    session_id: str,
    headers: Dict[str, Any]
) -> ExecutionContext:
    """Crea contexto enriquecido con toda la información necesaria para los servicios."""
    
    # 1. Crear contexto básico
    context = ExecutionContext(
        tenant_id=tenant_id,
        agent_id=agent_id,
        tenant_tier=tenant_tier,
        context_id=str(uuid4()),
        metadata={"session_id": session_id}
    )
    
    # 2. Enriquecer con configuración del agente (cacheada)
    cache_key = f"agent_config:{tenant_id}:{agent_id}"
    agent_config = await self._get_cached_or_fetch(
        cache_key,
        lambda: self._fetch_agent_configuration(tenant_id, agent_id),
        ttl=600  # 10 minutos
    )
    
    # 3. Añadir configuraciones específicas
    context.llm_config = self._extract_llm_config(agent_config, headers)
    context.rag_config = await self._extract_rag_config(agent_config, headers)
    context.embedding_config = self._extract_embedding_config(agent_config, headers)
    
    # 4. Añadir metadatos adicionales
    if headers.get("conversation_id"):
        context.metadata["conversation_id"] = headers["conversation_id"]
    
    return context
```

### 6.1.3 Extracción de Configuración Específica

La extracción de configuraciones toma en cuenta tanto los headers como la configuración del agente:

```python
def _extract_llm_config(self, agent_config: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae configuración de LLM priorizando headers sobre configuración de agente."""
    
    # Prioridad 1: Headers específicos
    llm_model = headers.get("X-LLM-Model")
    llm_provider = headers.get("X-LLM-Provider")
    temperature = headers.get("X-LLM-Temperature")
    
    # Prioridad 2: Configuración del agente
    if not llm_model and "llm" in agent_config:
        llm_model = agent_config["llm"].get("model")
        llm_provider = agent_config["llm"].get("provider")
        temperature = agent_config["llm"].get("temperature")
    
    # Prioridad 3: Valores por defecto según tier
    tier = headers.get("X-Tenant-Tier", "free")
    if not llm_model:
        llm_model = self.default_llm_models.get(tier, "gpt-3.5-turbo")
        llm_provider = "openai"  # Default fallback
        temperature = 0.7  # Default fallback
    
    return {
        "model": llm_model,
        "provider": llm_provider,
        "temperature": float(temperature) if temperature else 0.7,
        "max_tokens": int(headers.get("X-LLM-Max-Tokens", 4000))
    }
```

### 6.1.4 Implementación de Limpieza de Colas

Para gestionar el ciclo de vida de las colas, deberíamos implementar:

```python
# En handlers_domain_actions.py
async def process_execution_callback(self, action: ExecutionCallbackAction):
    """Procesa callback de ejecución y limpia recursos."""
    try:
        # Procesamiento normal del callback (enviar a WebSocket, etc)
        await self._send_result_to_websocket(
            session_id=action.session_id,
            result=action.result,
            status=action.status
        )
        
        # Limpieza de colas asociadas a esta tarea
        await self._clean_task_queues(action.task_id)
        
        logger.info(f"Callback procesado y recursos liberados: {action.task_id}")
        
    except Exception as e:
        logger.error(f"Error procesando callback: {str(e)}")
        
    return {"success": True}

async def _clean_task_queues(self, task_id: str):
    """Limpia todas las colas asociadas a un task_id específico."""
    # Patrones para buscar colas asociadas a esta tarea
    patterns = [f"*:{task_id}:*", f"*:callback:{task_id}"]  
    
    for pattern in patterns:
        # Buscar colas que coincidan con el patrón
        queues = await self.redis_client.keys(pattern)
        
        for queue in queues:
            # Eliminar la cola
            await self.redis_client.delete(queue)
            logger.debug(f"Cola eliminada: {queue}")
```

### 6.2 Agent Execution Service

Debe modificarse para:
- Consumir headers de configuración de LLM
- Utilizar headers RAG sin consultar Agent Management
- Propagar headers relevantes a Query Service

### 6.3 Query Service

### 6.3.1 Estado Actual del Query Service

El Query Service actualmente presenta las siguientes características en su comunicación:

- **Recibe información vía DomainAction**: Obtiene datos a través de `QueryGenerateAction` y `SearchDocsAction` en Redis
- **Tiene múltiples valores hardcodeados**: Modelos de LLM, umbrales de similitud, y parámetros de configuración
- **Realiza consultas adicionales**: Para obtener configuraciones de colecciones y agentes

### 6.3.2 Valores Hardcodeados Identificados

En `query_service/config/constants.py` encontramos varios valores que podrían recibirse de forma dinámica:

```python
# Modelos por defecto para cada proveedor
DEFAULT_MODELS = {
    LLMProviders.GROQ: "llama3-70b-8192",
    LLMProviders.OPENAI: "gpt-4",
    LLMProviders.ANTHROPIC: "claude-3-sonnet-20240229",
    # ...
}

# Parámetros por defecto para LLMs
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 4000

# Constantes para RAG
DEFAULT_MAX_RESULTS = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.75
```

### 6.3.3 Propuesta de Modificación para Query Service

El servicio debe modificarse para:

1. **Consumir configuración directamente de DomainAction**:
   - Obtener modelo LLM específico para el agente
   - Recibir umbral de similitud personalizado
   - Configurar número máximo de resultados según contexto

2. **Eliminar consultas adicionales a Agent Management**:
   - Recibir toda la información de colecciones en el contexto de ejecución
   - Incluir metadatos de embedding en el contexto (dimensiones, modelo)

3. **Implementar configuración dinámica**:
   - Generar prompts según parámetros del agente
   - Adaptar temperatura y parámetros de LLM según tipo de consulta
   - Configurar timeouts y reintentos según el tier

### 6.3.4 Modificación del Contexto de Ejecución

El objeto `ExecutionContext` recibido desde el Agent Orchestrator debe incluir:

```json
{
  "tenant_id": "t123",
  "tenant_tier": "professional",
  "agent_id": "a456",
  "rag_config": {
    "collections": [
      {
        "collection_id": "c789",
        "embedding_model": "text-embedding-3-large",
        "embedding_dimensions": 3072,
        "similarity_threshold": 0.78
      }
    ],
    "max_results": 8,
    "query_expansion_enabled": true
  },
  "llm_config": {
    "provider": "groq",
    "model": "llama3-70b-8192",
    "temperature": 0.4,
    "max_tokens": 4000
  }
}
```

### 6.4 Embedding Service

### 6.4.1 Estado Actual del Embedding Service

El Embedding Service presenta actualmente las siguientes características en su flujo de comunicación:

- **Procesa solicitudes vía DomainAction**: Recibe `EmbeddingRequestAction` desde colas Redis
- **Utiliza configuraciones hardcodeadas**: Modelos de embedding por defecto según el proveedor
- **No dispone de conocimiento del contexto completo**: Recibe textos a procesar sin metadata de la colección

### 6.4.2 Valores Hardcodeados Identificados

En `embedding_service/config/constants.py` encontramos valores críticos que deberían ser dinámicos:

```python
# Modelos por defecto para cada proveedor
DEFAULT_MODELS = {
    EmbeddingProviders.OPENAI: "text-embedding-3-large",
    EmbeddingProviders.AZURE_OPENAI: "text-embedding-ada-002",
    EmbeddingProviders.COHERE: "embed-english-v3.0",
    # ...
}

# Dimensiones por defecto para cada modelo
DEFAULT_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    "embed-english-v3.0": 1024,
    "all-mpnet-base-v2": 768
}

# Constantes para procesamiento por lotes
DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_TEXT_LENGTH = 8192
```

### 6.4.3 Problema Crítico: Compatibilidad de Dimensiones

Un problema significativo en el sistema actual es la falta de sincronización entre:

1. **Dimensiones de vectores almacenados en colecciones** (creados anteriormente)
2. **Dimensiones de nuevos embeddings** (generados para consultas)

Si un agente cambia su configuración de modelo de embedding, las búsquedas fallarín por incompatibilidad dimensional.

### 6.4.4 Propuesta de Modificación para Embedding Service

El servicio debe modificarse para:

1. **Consumir información de configuración de embeddings desde DomainAction**:
   - Recibir modelo específico de embedding requerido
   - Obtener dimensiones esperadas del vector resultante
   - Configurar parámetros de truncado y procesamiento por tipo de contenido

2. **Garantizar compatibilidad con colecciones existentes**:
   - Mantener metadatos sobre el modelo utilizado en cada colección
   - Verificar compatibilidad dimensional antes de procesar
   - Aplicar técnicas de adaptación dimensional cuando sea posible (padding, pooling)

3. **Implementar configuración dinámica por tier**:
   - Ajustar tamaño de lotes según el tier del tenant
   - Aplicar límites de tamaño de texto según tier
   - Configurar prioridad de procesamiento por tier

### 6.4.5 Modificación del DomainAction

La acción `EmbeddingRequestAction` recibida debe enriquecerse con:

```json
{
  "action_type": "embedding.request",
  "tenant_id": "t123",
  "tenant_tier": "professional",
  "execution_context": {
    "embedding_config": {
      "provider": "openai",
      "model": "text-embedding-3-large",
      "dimensions": 3072,
      "encoding_format": "float"
    },
    "collection_config": {
      "collection_id": "c789",
      "created_with_model": "text-embedding-3-large",
      "expected_dimensions": 3072
    },
    "processing_config": {
      "truncation_strategy": "end",
      "max_text_length": 8192
    }
  },
  "texts": ["contenido a vectorizar", "..."]
}
```

## 7. Beneficios y Consideraciones

### 7.1 Beneficios

- **Reducción de Consultas**: Menos llamadas entre servicios
- **Configuración Dinámica**: Sin hardcodeo de valores
- **Personalización**: Experiencia adaptada por agente/tenant
- **Rendimiento**: Menos latencia en procesamiento
- **Escalabilidad**: Servicios más desacoplados

### 7.2 Consideraciones

- **Ciclo de vida de las colas**: Implementar mecanismo para limpiar colas al completar tareas
- **Seguridad**: Validar información en cada servicio para evitar manipulación
- **Caché**: Implementar caché de configuraciones en Redis
- **Valores por Defecto**: Mantener fallbacks para información ausente
- **Tamaño de objetos DomainAction**: Monitorear para optimizar rendimiento

## 8. Plan de Implementación

1. **Fase 1**: Implementar headers básicos adicionales (LLM, Embedding)
2. **Fase 2**: Extender Agent Orchestrator como gateway de headers
3. **Fase 3**: Adaptar servicios para consumir configuración de headers
4. **Fase 4**: Eliminar valores hardcodeados y consultas redundantes
5. **Fase 5**: Implementar sistema de monitoreo de headers

## 9. Gestión del Ciclo de Vida de las Colas

Un aspecto crítico identificado en el análisis es la necesidad de gestionar adecuadamente el ciclo de vida de las colas Redis. Actualmente, las colas pueden acumularse indefinidamente si no se limpian después de completar las tareas asociadas.

### 9.1 Implementación Propuesta

```python
async def clean_queue_after_task(redis_client, task_id, domain):
    """Limpia todas las colas asociadas a un task_id específico."""
    # Buscar todas las colas que contengan el task_id
    pattern = f"{domain}:*"
    all_queues = await redis_client.keys(pattern)
    
    for queue in all_queues:
        # Verificar si hay tareas pendientes para este task_id
        queue_content = await redis_client.lrange(queue, 0, -1)
        has_pending_tasks = any(task_id in item.decode() for item in queue_content)
        
        if not has_pending_tasks:
            # Si no hay tareas pendientes, eliminar la cola
            await redis_client.delete(queue)
            logger.info(f"Cola limpiada: {queue} para task_id: {task_id}")
```

### 9.2 Integración con el Worker

```python
async def process_task(self, task_id, domain_action):
    try:
        # Procesamiento normal
        result = await self._process_action(domain_action)
        
        # Limpiar colas al finalizar
        await clean_queue_after_task(
            self.redis_client,
            task_id,
            domain_action.get_domain()
        )
        
        return result
    except Exception as e:
        logger.error(f"Error en task {task_id}: {str(e)}")
        # También limpiar en caso de error
        await clean_queue_after_task(
            self.redis_client, 
            task_id,
            domain_action.get_domain()
        )
        raise
```

## 10. Conclusiones

La optimización de la comunicación entre servicios mediante una correcta propagación de la información desde los headers iniciales representa una oportunidad significativa para mejorar la arquitectura del sistema nooble4. Este enfoque reduce dependencias entre servicios, permite una configuración más dinámica y personalizada, y elimina la acumulación de recursos en Redis.

La clave está en entender que los headers ingresan una sola vez desde el frontend, y que toda la información necesaria debe propagarse a través del sistema de colas Redis mediante objetos DomainAction enriquecidos, eliminando la necesidad de consultas adicionales entre servicios y asegurando la limpieza de recursos al finalizar cada tarea.
