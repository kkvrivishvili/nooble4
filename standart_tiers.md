# Análisis del Uso de Tiers en Servicios Nooble4

Este documento tiene como objetivo analizar y documentar cómo se utilizan los "tiers" (niveles de servicio, capacidades, funcionalidades restringidas por plan, etc.) en los diferentes microservicios del sistema Nooble4.

La estructura será la siguiente:
1.  Análisis individual por servicio.
2.  Propuesta de centralización y diseño de un módulo común para la gestión de tiers.

## 1. Análisis por Servicio

### 1.1. Agent Orchestrator Service (AOS)

El Agent Orchestrator Service (AOS) ya tiene una integración considerable del concepto de "tier". Los hallazgos principales son:

*   **Configuración y Headers:**
    *   `config/constants.py` define `RATE_LIMITING_TIERS`.
    *   Se utiliza y espera el header HTTP `X-Tenant-Tier` para las solicitudes.
    *   La configuración del servicio (`config/settings.py`) menciona explícitamente la "Integración con sistema de colas por tier".

*   **Modelos de Datos:**
    *   Los modelos para WebSockets (`WebSocketConnectionInfo`, `WebSocketMessage` en `models/websocket_model.py`) incluyen un campo `tenant_tier`.
    *   Los modelos de acciones (`models/actions_model.py`) están adaptados para la integración con el sistema de colas basado en tiers.

*   **Lógica de Negocio y Handlers:**
    *   `handlers/context_handler.py`:
        *   Define una lista de tiers válidos: `{"free", "advance", "professional", "enterprise"}`.
        *   Valida el `tenant_tier` recibido en las solicitudes (proveniente de headers o query parameters).
        *   Incorpora `tenant_tier` dentro del `ExecutionContext` para uso posterior.
    *   `handlers/callback_handler.py`:
        *   Usa `tenant_tier` (con "professional" como valor por defecto si no se encuentra en el contexto) para operaciones de logging.
        *   Utiliza el tier para construir claves dinámicas en Redis (ej., `execution_times:{callback.tenant_tier}`).
    *   La documentación del servicio (`documentation_AOS.md`, `README.md`) resalta:
        *   El uso de `tenant_tier` como parámetro en las conexiones WebSocket.
        *   Que el `DomainQueueManager` (ahora `QueueManager` en `refactorizado/common`) gestiona nombres de colas que incluyen el componente `{tier}` (ej., `nooble4:dev:agent_execution_service:actions:{tier}`).
        *   La responsabilidad del `ContextHandler` en el "enrutamiento por tier".
        *   La capacidad del `WebSocketManager` de rastrear conexiones por `tenant_tier` y potencialmente realizar difusiones (broadcast) segmentadas por tier.
        *   Menciones explícitas a la "Validación por Tier" y "Límites y capacidades por nivel de suscripción".

*   **Rate Limiting:**
    *   Existe la intención documentada de "Mejorar Rate Limiting" implementando un sistema avanzado con cuotas específicas por tier.
    *   `services/websocket_manager.py` incluye lógica para el rastreo de la tasa de mensajes, aunque la aplicación efectiva de límites está marcada como una tarea pendiente (TODO).

*   **Puntos de Entrada y Enrutamiento:**
    *   Las rutas de chat (`routes/chat_routes.py`) validan el header `X-Tenant-Tier`.
    *   Las conexiones WebSocket (`/ws/{session_id}`) esperan `tenant_tier` como un query parameter.

En resumen, AOS utiliza los tiers principalmente para la contextualización de las solicitudes, el enrutamiento hacia colas específicas de servicios downstream (como AES) y tiene planes para una gestión de rate limiting más granular basada en tiers. La información del tier parece ser un componente fundamental del `ExecutionContext`.

### 1.2. Agent Management Service (AMS)

El Agent Management Service (AMS) utiliza los "tiers" de forma central para la validación y gestión de capacidades de los agentes. Los hallazgos principales son:

*   **Configuración Centralizada de Tiers:**
    *   `config/settings.py`: La clase `AgentManagementSettings` incluye un diccionario `tier_limits`. Este se carga desde variables de entorno y define las capacidades y restricciones para cada tier (ej., `max_agents`, `available_tools`, `available_models`, `max_collections_per_agent`, `templates_access`).
    *   `config/constants.py`: Define constantes más granulares para los límites por tier, como `MAX_AGENTS_BY_TIER`, `MAX_COLLECTIONS_PER_AGENT_BY_TIER`, `MAX_TOOLS_PER_AGENT_BY_TIER`, `ALLOWED_TEMPLATE_TYPES_BY_TIER`, y `CUSTOM_PROMPTS_ALLOWED_BY_TIER`.
    *   El `README.md` del servicio incluye una tabla detallada que resume los "Límites por Tier" para diferentes recursos (Agentes, Herramientas, Modelos, etc.).

*   **Headers y Puntos de Entrada API:**
    *   Los endpoints de la API REST, como los de gestión de agentes (`/api/v1/agents` en `routes/agents.py`), requieren y utilizan los headers HTTP `X-Tenant-ID` y `X-Tenant-Tier` para identificar al solicitante y su nivel de servicio.

*   **Lógica de Validación Basada en Tiers (`ValidationService`):**
    *   El `ValidationService` (`services/validation_service.py`) es el núcleo de la aplicación de reglas de negocio basadas en tiers.
    *   El método `validate_tenant_limits()` verifica si un tenant ha alcanzado los límites definidos para su tier (ej., número máximo de agentes). *Nota: Existe una tarea pendiente (TODO) para obtener el conteo actual de agentes desde una base de datos persistente; la validación actual podría estar incompleta en este aspecto.*
    *   El método `validate_agent_config()` comprueba que la configuración de un agente (herramientas, modelos LLM, número de colecciones) se adhiere a las capacidades permitidas para el tier del tenant.
    *   Este servicio consulta `settings.tier_limits` para obtener las restricciones específicas de cada tier.

*   **Lógica de Negocio en `AgentService`:**
    *   El `AgentService` (`services/agent_service.py`) recibe el `tenant_tier` como parámetro en sus métodos principales (crear, actualizar agentes).
    *   Delega las validaciones relacionadas con los tiers al `ValidationService`.
    *   Incluye una función `_get_default_model()` que puede seleccionar un modelo LLM por defecto para un agente basándose en el `tenant_tier`.

*   **Workers y Contexto:**
    *   El `ManagementWorker` (`workers/management_worker.py`), al procesar acciones, puede acceder al `tenant_tier` desde el contexto de ejecución y utilizarlo para logging o para enriquecer acciones subsecuentes (ej., `validation_action.tenant_tier = context.tenant_tier`).

*   **Gestión de Templates:**
    *   El `TemplateService` (`services/template_service.py`) utiliza el `tenant_tier` para determinar a qué templates tiene acceso un tenant, basándose en la configuración `templates_access` dentro de `tier_limits`.

*   **Documentación:**
    *   La documentación del servicio (`documentation_AMS.md`, `README.md`) destaca la "Validación por Tier" como una funcionalidad principal y completa.
    *   Se menciona la intención de desarrollar "Flujos avanzados para tier Enterprise" como una característica futura.
    *   Se indica que el `DomainQueueManager` (ahora `QueueManager`) está integrado con "colas por tier para priorización de tareas". Sin embargo, también se observó que los clientes internos de AMS (como `ExecutionClient` e `IngestionClient`) podrían estar enviando acciones a colas específicas del tenant (`{tenant_id}`), lo que podría necesitar una revisión para asegurar la coherencia con la estrategia global de nomenclatura de colas (por tier vs. por tenant para servicios downstream).

En resumen, AMS tiene un sistema de tiers bien definido y aplicado, principalmente enfocado en la validación de límites y capacidades al crear y gestionar agentes y templates. El `ValidationService` y la configuración `tier_limits` son cruciales para esta funcionalidad.

### 1.3. Agent Execution Service (AES)

El Agent Execution Service (AES) integra el concepto de "tier" profundamente para gestionar recursos, controlar el acceso y diferenciar el comportamiento del servicio. Los hallazgos clave son:

*   **Configuración Detallada por Tier (`config/settings.py`, `config/constants.py`):**
    *   La configuración principal reside en `config/settings.py` dentro de la clase `AgentExecutionSettings`, específicamente en el diccionario `tier_limits`. Este define parámetros cruciales por tier, tales como:
        *   `conversation_cache_limit`: Número máximo de mensajes en la caché de conversación.
        *   `cache_ttl_seconds`: Tiempo de vida para las entradas de caché.
        *   `wait_for_persistence`: Un booleano que determina si el sistema debe esperar la confirmación de la persistencia de datos (ej. mensajes). Este comportamiento puede variar por tier (ej., `True` para el tier "free" y `False` para tiers superiores, optimizando la latencia).
        *   `max_iterations`, `max_execution_time`: Límites impuestos a la ejecución de los agentes para controlar el uso de recursos.
        *   `allowed_tools`, `allowed_models`: Listas que especifican qué herramientas y modelos LLM están disponibles para cada tier.
    *   El archivo `config/constants.py` también contiene definiciones relacionadas con tiers (ej., temperaturas por defecto para LLMs). La documentación del servicio señala una posible duplicación o solapamiento con `settings.py`, lo que sugiere una necesidad de consolidación o clarificación.

*   **Handlers y Lógica de Ejecución (`AgentExecutionHandler`, `ContextHandler`):**
    *   `AgentExecutionHandler`:
        *   Extrae el `tenant_tier` del `ExecutionContext` para tomar decisiones.
        *   Utiliza un método como `_get_execution_timeout()` para determinar los tiempos de espera máximos para la ejecución de agentes, basándose en el `tenant_tier`.
        *   Emplea el `tenant_tier` en el logging y para construir claves específicas en Redis destinadas a la recolección de métricas de rendimiento y uso (ej., `execution_times:{context.tenant_tier}`, `execution_metrics:tier:{context.tenant_tier}:{today}`).
    *   `ContextHandler`:
        *   Obtiene el `tenant_tier` del contexto de la solicitud (usualmente con "free" como valor por defecto si no se especifica).
        *   Aplica configuraciones de `tier_limits` para gestionar:
            *   Límites de la caché de conversación (`conversation_cache_limit`).
            *   TTLs de la caché (`cache_ttl_seconds`).
            *   El comportamiento de la persistencia de datos (`wait_for_persistence`).
        *   Implementa lógica de validación para determinar si herramientas (`_is_tool_allowed_for_tier()`) y modelos LLM (`_is_model_allowed_for_tier()`) específicos están permitidos para un `tenant_tier` dado.
        *   Puede realizar comprobaciones de acceso comparando el nivel del tier del usuario (`user_tier_level`) con un tier mínimo requerido por un agente (`agent_tier_required`).

*   **Gestión de Colas y Priorización:**
    *   AES utiliza colas de Redis específicas por tier para procesar acciones. El `QueueManager` (antes `DomainQueueManager`) se encarga de dirigir las `DomainAction` a colas como `nooble4:dev:agent_execution_service:{TIER}:actions` (ej., `...:free:actions`, `...:enterprise:actions`). Esto permite diferenciar la prioridad y los recursos asignados al procesamiento de tareas según el nivel de servicio del tenant.
    *   Los callbacks de servicios externos (como Embedding Service o Query Service) también se esperan en colas de callback segmentadas por tier (ej., `agent_execution_service:{tier}:callbacks`).

*   **Caching Diferenciado por Tier:**
    *   El `ExecutionContextHandler` es responsable de la gestión de la caché para las configuraciones de los agentes y el historial de conversaciones. Tanto los Tiempos de Vida (TTLs) de estas cachés como sus límites de tamaño son dependientes del `tenant_tier`.

*   **Parámetros de Ejecución y Control de Recursos:**
    *   AES ajusta dinámicamente los parámetros de ejecución de los agentes, como el número máximo de iteraciones y los tiempos de espera, basándose en los límites establecidos para cada tier. Esto es fundamental para la gestión eficiente de los recursos del sistema y para asegurar una calidad de servicio consistente.

*   **Documentación:**
    *   La documentación del servicio (`documentation_AES.md`, `README.md`) enfatiza la "Validación de Permisos" (Permission Validation) como una función clave que opera en base al tier del tenant.

En conclusión, AES hace un uso extensivo de los tiers para controlar el consumo de recursos, regular el acceso a funcionalidades avanzadas (herramientas y modelos), y optimizar el rendimiento del sistema mediante colas priorizadas y políticas de caché adaptativas. La configuración `tier_limits` en `settings.py` es el pilar de esta funcionalidad.

### 1.4. Conversation Service

El Conversation Service utiliza los "tiers" para gobernar la persistencia, el acceso y la gestión de los datos de las conversaciones, aplicando límites diferenciados según el nivel de servicio del tenant.

*   **Configuración Centralizada de Límites por Tier (`config/settings.py`):**
    *   La clase `ConversationServiceSettings` en `config/settings.py` contiene un diccionario fundamental llamado `tier_limits`.
    *   Este diccionario define las capacidades y restricciones para cada tier. Basado en el código y la documentación (`README.md`), estos límites pueden incluir:
        *   `max_active_conversations`: El número máximo de conversaciones que un tenant puede tener activas simultáneamente.
        *   `max_messages_per_conversation`: El límite de mensajes que se pueden almacenar dentro de una única conversación.
        *   `retention_days`: El período durante el cual se conservan los datos de la conversación antes de una posible purga o archivado.
        *   `context_messages`: El número de mensajes recientes que se recuperan para formar el contexto enviado a los modelos de lenguaje (aunque el `MemoryManager` también considera límites de tokens específicos del modelo).
        *   `max_history_retrieval`: El número máximo de mensajes que se pueden obtener en una única solicitud de historial.
        *   `persistence_priority`: Podría influir en la prioridad de las operaciones de guardado en la base de datos o caché.
        *   `allow_long_term_storage`: Un booleano que podría determinar si las conversaciones del tier son elegibles para almacenamiento a largo plazo (ej. en PostgreSQL).

*   **Propagación del Tier y Handlers (`ConversationHandler`):**
    *   El `ConversationHandler` es el punto de entrada para las `DomainAction` relacionadas con conversaciones.
    *   Extrae el `tenant_tier` del `ExecutionContext` (si es propagado por el servicio solicitante, como AOS o AES) o directamente de los datos de la `DomainAction`.
    *   La principal función del handler respecto a los tiers es pasar esta información (`tenant_tier`) a los servicios internos que realmente aplican la lógica de negocio y los límites.

*   **Aplicación de Límites en Servicios Internos (`ConversationPersistenceService`, `MemoryManager`):**
    *   `ConversationPersistenceService` (o un servicio con un nombre similar encargado de la interacción con la base de datos y la caché Redis):
        *   Recibe el `tenant_tier` como parámetro en sus métodos.
        *   Es responsable de aplicar los límites definidos en `settings.tier_limits` al crear, actualizar, o recuperar conversaciones. Por ejemplo, antes de crear una nueva conversación, verificaría si el tenant ha alcanzado su límite de `max_active_conversations` para su tier.
        *   El método `_extract_tier_from_metadata()` sugiere que el `tenant_tier` podría almacenarse junto con los metadatos de la conversación para facilitar estas comprobaciones.
    *   `MemoryManager`:
        *   También recibe el `tenant_tier`.
        *   Si bien su enfoque principal es gestionar el contexto de la conversación basándose en los `model_token_limits` (límites de tokens de los LLM), existen indicaciones en el código (comentarios como `# tier_config = settings.tier_limits.get(...)`) que sugieren que los límites del tier (ej. `context_messages`) también podrían influir en la cantidad de mensajes que se incluyen en el contexto para el LLM, complementando los límites de tokens.

*   **Límites de Tokens por Modelo (Coexistencia con Tiers):**
    *   El servicio también gestiona `model_token_limits` en `config/settings.py`, que son límites técnicos impuestos por los modelos LLM. El `MemoryManager` usa estos para asegurar que el contexto enviado al LLM no exceda su capacidad. Estos límites técnicos operan en conjunto con los límites de negocio definidos por los tiers.

*   **Documentación Explícita (`README.md`):**
    *   El archivo `README.md` del servicio declara explícitamente la existencia de "Tier-aware limits" (límites conscientes del tier) y proporciona una tabla de ejemplo que ilustra cómo varían las cuotas (Conversaciones Activas, Mensajes/Conversación, Retención, Contexto) entre diferentes tiers (ej. Free, Basic, Professional, Enterprise).

En resumen, Conversation Service implementa una estrategia basada en tiers para controlar el uso de recursos de almacenamiento y la retención de datos. Los límites se definen centralmente y se aplican en los servicios de persistencia y gestión de memoria, asegurando que cada tenant opere dentro de las cuotas asignadas a su nivel de servicio.

### 1.5. Query Service

El Query Service (QS) hace un uso integral de los "tiers" para gestionar el acceso a datos, controlar el uso de recursos, aplicar límites de tasa y diferenciar las capacidades de consulta ofrecidas a los tenants.

*   **Configuración Centralizada y Detallada por Tier (`config/settings.py`):**
    *   La clase `QueryServiceSettings` en `config/settings.py` es el núcleo de la configuración por tier, conteniendo un diccionario `tier_limits`.
    *   Este diccionario especifica diversos parámetros y restricciones para cada nivel de servicio. Ejemplos de configuraciones por tier incluyen:
        *   `max_queries_per_hour`: El número máximo de consultas que un tenant puede ejecutar en una hora.
        *   `max_tokens_per_query`: El límite de tokens que una consulta puede consumir, relevante para las operaciones de generación de lenguaje natural (LLM).
        *   `max_search_results`: El número máximo de resultados que una operación de búsqueda puede devolver.
        *   `allowed_llm_models`: Una lista de los modelos LLM que están permitidos para su uso en cada tier.
        *   `allow_advanced_search_features`: Un booleano para habilitar o deshabilitar funcionalidades de búsqueda avanzada específicas del tier.
        *   `default_top_k`: El valor predeterminado para el número de resultados a recuperar en una búsqueda si el cliente no especifica uno.
        *   `cache_ttl_seconds`: El tiempo de vida (TTL) para los resultados de consulta almacenados en caché.
    *   `QueryServiceSettings` incluye un método `get_tier_limits(tier)` que facilita la obtención de la configuración para un tier específico, utilizando "free" como tier por defecto si el solicitado no se encuentra.
    *   Aunque `config/constants.py` también define algunas constantes relacionadas con tiers (ej. `MAX_QUERIES_PER_HOUR_BY_TIER`), la documentación enfatiza que `settings.py` (configurable por entorno) debe ser la fuente autoritativa para estos límites.

*   **Handlers y Validación de Tiers (`ContextHandler`, `QueryHandler`):**
    *   `ContextHandler`:
        *   Extrae el `tenant_tier` del `ExecutionContext` (propagado desde servicios como AOS o AES).
        *   Realiza una validación crucial: comprueba si el `tenant_tier` del usuario es suficiente para acceder a una colección de datos específica. Esto se hace comparando el tier del usuario con un atributo `minimum_tier` definido en la configuración de la colección (que podría obtenerse de una fuente externa o estar simulada). Se utiliza una jerarquía de tiers (ej. free: 0, advance: 1, professional: 2) para esta comparación.
        *   Invoca un método `_validate_query_limits()` que aplica los límites específicos del tier. Este método:
            *   Obtiene los `limits` del diccionario `tier_limits`.
            *   Implementa la lógica de rate limiting (ej., `max_queries_per_hour`) utilizando Redis para rastrear el número de consultas recientes realizadas por el tenant.
    *   `QueryHandler`:
        *   Recibe el `ExecutionContext` (que ya contiene el `tenant_tier` validado por el `ContextHandler`).
        *   Utiliza el parámetro `limit` de la `DomainAction` (que podría haber sido ajustado o validado por el `ContextHandler` según las restricciones del tier) para pasarlo como `top_k` al motor de búsqueda vectorial subyacente.

*   **Gestión de Colas Específicas por Tier (`QueryWorker`, `QueueManager`):
    *   El `QueryWorker` está diseñado para escuchar y procesar `DomainAction`s desde colas Redis que son específicas para cada tier (ej. `nooble4:dev:query:free:query.generate`, `nooble4:dev:query:enterprise:query.search`).
    *   El `QueueManager` (anteriormente `DomainQueueManager`) se encarga de la suscripción a estas colas segmentadas y del envío de respuestas o callbacks a las colas apropiadas, manteniendo la nomenclatura y la lógica de tiering.

*   **Callbacks Conscientes del Tier (`QueryCallbackHandler`):**
    *   El `QueryCallbackHandler`, al procesar los resultados de las operaciones asíncronas y preparar los callbacks, también tiene acceso al `ExecutionContext` y, por ende, al `tenant_tier`.
    *   Esta información se incluye en los logs al enviar los callbacks, lo que subraya la importancia del tier como parte del contexto de la operación completa.

*   **Documentación Explícita (`documentation_QS.md`, `README.md`):**
    *   La documentación del Query Service destaca explícitamente que el servicio ha sido diseñado para soportar diferentes tiers, cada uno con capacidades y límites de uso distintos.
    *   Se menciona la "Validación de permisos y límites basada en el tier del tenant" como una característica clave.

En resumen, el Query Service aprovecha los tiers para un control granular sobre el acceso a datos (colecciones), la limitación de la tasa de solicitudes, la gestión de recursos (resultados de búsqueda, uso de LLM) y la posible priorización del procesamiento mediante colas dedicadas. La configuración `tier_limits` en `settings.py` es el pilar de esta estrategia, con la lógica de validación y aplicación implementada principalmente en el `ContextHandler`.

### 1.6. Embedding Service

El Embedding Service (ES) utiliza los "tiers" de forma explícita y detallada para gobernar el acceso a los recursos de embedding, controlar la capacidad de procesamiento, aplicar límites de uso y diferenciar las funcionalidades ofrecidas a los tenants.

*   **Configuración Centralizada y Detallada por Tier (`config/settings.py`):**
    *   La clase `EmbeddingServiceSettings` en `config/settings.py` es la piedra angular de la gestión de tiers. Contiene un método crucial: `get_tier_limits(tier: str) -> Dict[str, Any]`.
    *   Este método construye y devuelve un diccionario de configuración para un tier específico (ej. "free", "basic", "professional", "enterprise"), fusionando unos `base_limits` (comunes a todos los tiers) con configuraciones `tier_specific`.
    *   Los parámetros clave que se definen y controlan por tier son:
        *   `max_texts_per_request`: El número máximo de textos que se pueden incluir en una única solicitud para generar embeddings (controla el tamaño del batch).
        *   `max_text_length`: La longitud máxima permitida para un texto individual que se va a embeber.
        *   `max_requests_per_hour`: El límite de tasa que restringe el número de solicitudes de embedding que un tenant puede realizar por hora.
        *   `allowed_models`: Una lista que especifica qué modelos de embedding están permitidos para su uso por los tenants de ese tier.
        *   `cache_enabled`: Un valor booleano que indica si los resultados de los embeddings deben ser cacheados para este tier, para optimizar respuestas futuras.
        *   `daily_quota`: Aunque este parámetro se define en la configuración de tiers, la documentación del servicio (`documentation_ES.md`) señala que la lógica para verificar o decrementar esta cuota diaria no está implementada actualmente.

*   **Handlers y Validación de Tiers (`EmbeddingContextHandler`):**
    *   El `EmbeddingContextHandler` es el principal punto de entrada donde se aplica la lógica de validación basada en tiers.
    *   Extrae el `tenant_tier` del `ExecutionContext`.
    *   Invoca dos métodos de validación internos importantes:
        *   `_validate_tier_limits()`: Este método obtiene la configuración específica del tier mediante `settings.get_tier_limits()` y luego verifica que la solicitud cumpla con `max_texts_per_request` y `max_text_length`.
            *   **Brecha Identificada**: Una observación importante (destacada en `documentation_ES.md` y confirmada por el análisis del código) es que, si bien este método verifica si un modelo de embedding es soportado globalmente por el servicio, *no* realiza la validación cruzada contra la lista `tier_limits["allowed_models"]`. Por lo tanto, actualmente no se asegura que el modelo solicitado esté específicamente permitido para el tier del tenant.
        *   `_validate_rate_limits()`: Este método obtiene el límite `max_requests_per_hour` de la configuración del tier y utiliza Redis (con claves como `embedding_rate_limit:{tenant_id}:hour:{current_hour}`) para rastrear el número de solicitudes recientes y aplicar el rate limiting horario.

*   **Servicios de Soporte y Validación (`ValidationService`, `EmbeddingProcessor`):**
    *   `ValidationService`: Antes de que el `EmbeddingHandler` procese la solicitud, este servicio también utiliza `settings.get_tier_limits()` para obtener las restricciones del tier. Realiza validaciones detalladas sobre los textos (tamaño de batch, longitud) y la compatibilidad de los modelos solicitados con estas restricciones.
    *   `EmbeddingProcessor`: Al generar los embeddings, este servicio consulta la configuración del tier (específicamente `tier_limits.get("cache_enabled", True)`) para determinar si los resultados deben ser almacenados en la caché.

*   **Gestión de Colas Específicas por Tier (`main.py`, `EmbeddingWorker`):**
    *   El servicio está diseñado para procesar solicitudes de `DomainAction`s desde colas Redis que están segregadas por tier (ej. `nooble4:{env}:embedding:actions:free`, `nooble4:{env}:embedding:actions:enterprise`).
    *   El `EmbeddingWorker` se suscribe a estas colas específicas, lo que permite una gestión de la carga de trabajo y una posible priorización de solicitudes diferenciada según el nivel de servicio del tenant.

*   **Documentación Explícita (`documentation_ES.md`, `README.md`):**
    *   Ambos documentos proporcionan información valiosa y confirman el uso extensivo de tiers en el servicio.
    *   `documentation_ES.md` es particularmente útil, ya que identifica explícitamente la brecha en la validación de `allowed_models` por tier dentro del `EmbeddingContextHandler` y la no implementación de la `daily_quota`.
    *   El `README.md` también menciona que "algunas capacidades avanzadas del tier Enterprise no están completamente implementadas", lo que podría estar relacionado con límites más generosos o características adicionales que aún no se han incorporado completamente en la lógica de tiers.

*   **Posible Conflicto entre Constantes y Settings (`config/constants.py`):**
    *   El archivo `config/constants.py` define algunas constantes relacionadas con tiers (ej. `MAX_EMBEDDINGS_PER_HOUR_BY_TIER`). Aunque la documentación y la práctica general apuntan a `settings.py` como la fuente autoritativa y configurable por entorno, la existencia de estas constantes podría ser un remanente de una etapa anterior o una duplicación que podría necesitar ser consolidada para evitar inconsistencias.

En resumen, el Embedding Service utiliza los tiers para:
*   **Controlar el volumen y la naturaleza del procesamiento**: A través de límites en el tamaño del batch de textos (`max_texts_per_request`) y la longitud de cada texto (`max_text_length`).
*   **Gestionar la carga y prevenir abusos**: Mediante la aplicación de rate limiting (`max_requests_per_hour`).
*   **Diferenciar el acceso a diferentes modelos de embedding**: A través de la configuración `allowed_models` (aunque la validación de este aspecto necesita ser reforzada).
*   **Optimizar el rendimiento y los costos**: Decidiendo si se utiliza o no el cacheo de embeddings (`cache_enabled`) según el tier.
*   **Segmentar y priorizar el flujo de trabajo**: Utilizando colas de procesamiento dedicadas por tier.

Las áreas clave para una futura mejora o revisión incluyen la implementación completa de la validación de `allowed_models` por tier en el `EmbeddingContextHandler`, tomar una decisión sobre la implementación o eliminación de la funcionalidad de `daily_quota`, y clarificar/consolidar el uso de constantes versus la configuración en `settings.py`.

### 1.7. Ingestion Service

El Ingestion Service (IS) reconoce y utiliza el concepto de "tiers", aunque su implementación para aplicar límites específicos parece menos centralizada en la configuración de `settings.py` en comparación con servicios como Embedding Service o Query Service. La influencia del tier se manifiesta principalmente a través de constantes definidas y en la documentación del servicio, así como en la gestión de colas.

*   **Configuración y Constantes Relacionadas con Tiers (`config/constants.py`):**
    *   A diferencia de otros servicios que presentan un método `get_tier_limits()` en su archivo `settings.py` para obtener una configuración detallada por tier, el Ingestion Service parece apoyarse más en constantes predefinidas en `config/constants.py` para la diferenciación de capacidades y límites por tier.
    *   Se identificaron las siguientes constantes clave que sugieren una intención de aplicar límites diferenciados por tier:
        *   `MAX_DOCUMENTS_PER_HOUR_BY_TIER`: Un diccionario que probablemente tiene como objetivo definir cuántos documentos un tenant puede ingestar por hora, variando según su nivel de servicio (tier).
        *   `MAX_FILE_SIZE_BY_TIER`: Un diccionario diseñado para limitar el tamaño máximo de un archivo que puede ser subido para ingestión, con umbrales específicos para cada tier.
        *   `MAX_CHUNKS_PER_DOCUMENT_BY_TIER`: Un diccionario para restringir el número máximo de fragmentos (chunks) que pueden generarse a partir de un único documento, con límites ajustados por tier.
    *   Es importante notar que el archivo `config/settings.py` del Ingestion Service define un `MAX_CHUNKS_PER_DOCUMENT` global. La existencia de la constante `MAX_CHUNKS_PER_DOCUMENT_BY_TIER` en `constants.py` sugiere una intención de refinar este límite de manera más granular por tier, aunque la aplicación activa de esta constante específica por tier no es evidente en el código de los servicios de procesamiento.

*   **Documentación (`README.md`, `documentation_IS.md`):**
    *   El archivo `README.md` del servicio afirma que la funcionalidad de "Validación por Tier" está "✅ Completo".
    *   También se menciona que el `DomainQueueManager` (ahora `QueueManager`) está "Integrado con colas por tier para priorización de tareas". Esto indica que las solicitudes de ingestión se enrutan a diferentes colas de procesamiento basadas en el tier del tenant, lo cual es una forma de aplicar tiering a nivel de infraestructura.
    *   Una nota importante en el `README.md` señala: "- **Límites de Tier**: Aunque existe validación por tier, algunas capacidades avanzadas del tier Enterprise no están completamente implementadas." Esta observación es consistente con hallazgos similares en otros servicios de la plataforma.
    *   La documentación técnica (`documentation_IS.md`) menciona que el proceso de fragmentación de documentos limita el número de chunks utilizando el valor `settings.MAX_CHUNKS_PER_DOCUMENT`. Este es un punto donde la lógica de `MAX_CHUNKS_PER_DOCUMENT_BY_TIER` (definida en `constants.py`) podría o debería aplicarse en lugar del valor global de `settings.py` para una gestión de recursos más afinada por tier.

*   **Aplicación de Límites por Tier:**
    *   No se observó en los handlers (si existieran de forma análoga a otros servicios) o en los servicios principales de procesamiento (como `ChunkingService`, `ProcessingService`) una llamada directa a un método como `settings.get_tier_limits()` ni una carga y aplicación dinámica de los diccionarios `*_BY_TIER` desde `constants.py`.
    *   Esto sugiere que la aplicación de los límites numéricos por tier podría estar:
        *   **Implícita o Asumida**: La lógica del servicio podría estar esperando que el `ExecutionContext` ya contenga información sobre el tier y que ciertas validaciones hayan sido realizadas por un servicio aguas arriba (ej. Agent Orchestrator Service).
        *   **No Implementada Completamente**: Las constantes para los límites por tier existen, pero la lógica de código para leerlas y aplicarlas activamente durante el flujo de ingestión podría no estar completamente desarrollada o integrada.
        *   **Delegada a la Infraestructura de Colas**: Es plausible que el `IngestionWorker` o el `QueueManager` utilicen la información del tier principalmente para enrutar las tareas a colas que tengan diferentes configuraciones de recursos o prioridades (ej. workers con más capacidad asignados a tiers más altos), en lugar de aplicar límites numéricos directos sobre el contenido o la frecuencia de las solicitudes dentro del propio Ingestion Service.

*   **Puntos Clave para la Aplicación de Tiers:**
    *   **Rate Limiting**: La constante `MAX_DOCUMENTS_PER_HOUR_BY_TIER` debería ser utilizada para implementar un control sobre la frecuencia de las solicitudes de ingestión por tenant.
    *   **Límites de Recursos**: Las constantes `MAX_FILE_SIZE_BY_TIER` y `MAX_CHUNKS_PER_DOCUMENT_BY_TIER` deberían emplearse para controlar el "tamaño" y la complejidad de las tareas de ingestión individuales, ajustándose a las capacidades de cada tier.
    *   **Priorización y Segmentación de Colas**: Como ya se menciona en el `README.md`, el uso de colas diferenciadas por tier es un mecanismo de tiering válido y aparentemente en uso.

En resumen, el Ingestion Service tiene conciencia del concepto de tiers y posee definiciones (principalmente como constantes) para diferenciar límites y capacidades. Además, utiliza colas segregadas por tier. Sin embargo, la aplicación explícita y dinámica de los límites numéricos (tamaño de archivo, número de chunks, frecuencia de documentos) basados en el tier, dentro de la lógica interna del servicio (por ejemplo, en handlers de contexto o servicios de procesamiento), no es tan evidente o centralizada como en otros microservicios de la plataforma. Parece haber una mayor dependencia de la infraestructura de colas y, potencialmente, de validaciones realizadas en etapas previas del flujo de la solicitud, o bien una implementación aún parcial de la lógica detallada de límites por tier.

Una mejora significativa sería asegurar que los límites definidos en `constants.py` (o, idealmente, centralizados en una función `get_tier_limits()` dentro de `settings.py`, siguiendo el patrón de otros servicios) se lean y apliquen activamente durante el proceso de ingestión. Esto podría realizarse, por ejemplo, en un `ContextHandler` específico para la ingestión o al inicio del procesamiento de cada documento, para garantizar el cumplimiento de las restricciones del tier.

## 2. Propuesta de Centralización

*(Esta sección se completará después del análisis individual de los servicios)*

### 2.1. Requisitos Identificados

### 2.2. Diseño del Módulo Común de Tiers

#### 2.2.1. Modelos de Datos (Pydantic)

#### 2.2.2. Lógica de Verificación de Tiers

#### 2.2.3. Puntos de Integración Sugeridos

### 2.3. Estrategia de Implementación
