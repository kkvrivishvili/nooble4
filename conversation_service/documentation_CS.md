# Documentación Detallada: Conversation Service

## 1. Objetivo del Servicio

El **Conversation Service** es un componente central de la plataforma Nooble4, responsable de la gestión integral de las interacciones conversacionales entre los usuarios y los agentes de IA. Sus principales objetivos son:

*   **Persistencia de Conversaciones:** Almacenar y recuperar el historial de mensajes de las conversaciones, incluyendo el contenido, roles (usuario, asistente, sistema), metadatos y timestamps.
*   **Gestión de Estado de Sesión:** Mantener el estado de las sesiones de conversación activas, identificando cuándo una sesión inicia, está en curso o ha finalizado.
*   **Provisión de Contexto:** Construir y proveer el contexto conversacional necesario para otros servicios, principalmente el **Query Service** y el **Agent Execution Service**, optimizando este contexto según los límites de tokens de los modelos de IA y las necesidades del solicitante.
*   **Manejo de Memoria a Corto Plazo:** Implementar una capa de memoria "caliente" (actualmente en RAM y Redis) para las conversaciones activas, permitiendo un acceso rápido a los mensajes recientes.
*   **Migración de Datos:** Facilitar la migración de conversaciones completadas o inactivas desde el almacenamiento primario (Redis) a un almacenamiento secundario a largo plazo (PostgreSQL), aunque esta última parte está mayormente como placeholder.
*   **Exposición de Datos para CRM/Admin:** Proveer endpoints API para que herramientas de CRM o dashboards administrativos puedan consultar datos de conversaciones y estadísticas básicas.
*   **Cálculo de Estadísticas:** Generar estadísticas básicas sobre el uso de conversaciones a nivel de tenant y agente.

Este servicio actúa como la "memoria" del sistema para todas las interacciones, asegurando que los agentes puedan mantener conversaciones coherentes y que los datos relevantes estén disponibles para análisis y operación.

## 2. Comunicaciones con Otros Servicios

El Conversation Service se comunica con otros servicios principalmente a través de **Domain Actions sobre colas de Redis** y, en algunos casos (posiblemente legacy o internos), mediante **endpoints HTTP directos**.

### A. Comunicaciones Entrantes (Acciones que procesa):

*   **Vía Domain Actions (Redis):**
    *   `conversation.save_message`:
        *   **Enviado por:** Agent Execution Service (tras la respuesta de un agente).
        *   **Propósito:** Guardar un nuevo mensaje (de usuario o asistente) en una conversación existente.
        *   **Payload Esperado:** `SaveMessageAction` (definido en `models/actions_model.py`).
    *   `conversation.get_context`:
        *   **Enviado por:** Query Service (antes de consultar un LLM para RAG), Agent Execution Service (para construir el prompt inicial del agente).
        *   **Propósito:** Solicitar el historial de mensajes formateado como contexto para un modelo de IA.
        *   **Payload Esperado:** `GetContextAction`.
    *   `conversation.get_history` (Pseudo-síncrono):
        *   **Enviado por:** Agent Execution Service (cuando necesita el historial para alguna lógica interna).
        *   **Propósito:** Solicitar un historial de mensajes más crudo.
        *   **Payload Esperado:** `GetHistoryAction` (incluye `correlation_id` y `callback_queue_name`).
    *   `conversation.session_closed`:
        *   **Enviado por:** Agent Execution Service (o el componente que maneje WebSockets/estado de conexión del usuario, cuando detecta que la sesión del usuario ha terminado).
        *   **Propósito:** Notificar al Conversation Service que una sesión ha finalizado, para que pueda marcar la conversación y potencialmente prepararla para migración.
        *   **Payload Esperado:** `SessionClosedAction`.
    *   `migration.start_migration_loop`, `migration.stop_migration_loop`, `migration.migrate_conversation_explicitly`, `migration.get_migration_stats`:
        *   **Enviado por:** Potencialmente un servicio de administración o una herramienta de CLI.
        *   **Propósito:** Controlar y monitorear el `MigrationWorker`.

*   **Vía HTTP API (Endpoints en `routes/old_conversations.py` - posible legacy para AES):
    *   `POST /api/v1/conversations/internal/save-message`:
        *   **Usado por (según comentarios):** Agent Execution Service.
        *   **Propósito:** Guardar un mensaje. Parece una alternativa HTTP al Domain Action `conversation.save_message`.
    *   `GET /api/v1/conversations/internal/history/{session_id}`:
        *   **Usado por (según comentarios):** Agent Execution Service.
        *   **Propósito:** Obtener historial de conversación. Parece una alternativa HTTP al Domain Action `conversation.get_history`.

### B. Comunicaciones Salientes (Acciones/Respuestas que envía):

*   **Vía Domain Actions (Redis) - Respuestas a Patrones Pseudo-Síncronos:**
    *   Cuando recibe `conversation.get_history`, responde a la `callback_queue_name` especificada en la acción con el historial solicitado o un error, usando el `correlation_id`.
    *   Cuando los workers procesan acciones que tienen `callback_queue_name`, envían el resultado o error a dicha cola.

*   **Vía HTTP API (Endpoints en `routes/crm_routes.py` y `routes/health.py`):
    *   Responde a solicitudes HTTP de clientes (ej. CRM/Dashboard) con datos de conversaciones, estadísticas o estado del servicio.

### C. Dependencias de Datos:

*   **Redis:** Utilizado extensivamente como:
    *   Broker de mensajes para Domain Actions (colas de entrada/salida).
    *   Almacén primario para datos de conversaciones activas (modelos `Conversation`, `Message` serializados en JSON).
    *   Caché para mapeos `session_id` -> `conversation_id`.
    *   Almacén para el buffer de memoria en RAM (`MemoryManager` podría cachear/sincronizar con Redis, aunque su descripción principal es en RAM).
*   **PostgreSQL (Planeado):** Destino para la migración de conversaciones a largo plazo. La integración está mayormente como placeholder.

## 3. Responsabilidades de Archivos y Directorios Internos

*   **`__init__.py`**: Define `__version__` para el servicio.
*   **`main.py`**: Punto de entrada de la aplicación FastAPI. Configura la app, routers, y el pool de Redis. Inicializa y arranca los workers (`ConversationWorker`, `MigrationWorker`).
*   **`config/settings.py`**: Define `ConversationServiceSettings` (modelo Pydantic) para cargar la configuración del servicio desde variables de entorno (ej. `REDIS_URL`, `LOG_LEVEL`, `MIGRATION_INTERVAL_SECONDS`).
*   **`workers/`**: Contiene los procesadores de Domain Actions en segundo plano.
    *   `conversation_worker.py` (`ConversationWorker`): Hereda de `BaseWorker`. Procesa acciones como `conversation.save_message`, `conversation.get_context`, `conversation.get_history`, `conversation.session_closed`. Delega la lógica de negocio a `ConversationHandler`.
    *   `migration_worker.py` (`MigrationWorker`): Hereda de `BaseWorker`. Gestiona la migración de conversaciones de Redis a PostgreSQL. Tiene un bucle autónomo para migraciones periódicas y también puede procesar acciones explícitas de control de migración.
*   **`handlers/conversation_handler.py` (`ConversationHandler`)**: Clase central que recibe los `DomainAction` desde los workers (específicamente `ConversationWorker`). Parsea el payload de la acción a modelos Pydantic (`actions_model.py`), enriquece con `ExecutionContext` y delega la lógica de negocio a `ConversationService`. Construye y devuelve la respuesta.
*   **`services/`**: Contiene la lógica de negocio principal.
    *   `conversation_service.py` (`ConversationService`): Orquesta las operaciones sobre conversaciones. Interactúa con `PersistenceManager` para el almacenamiento y `MemoryManager` para la gestión de contexto en memoria. Métodos principales: `save_message`, `get_conversation_context_for_query` (optimizado para Query Service), `get_conversation_history`, `mark_session_closed_and_schedule_migration`, `get_conversation_list`, `get_conversation_full`, `get_tenant_stats`, `create_conversation`, `update_conversation_status`, `search_conversations`.
    *   `memory_manager.py` (`MemoryManager`): Gestiona un buffer en RAM de mensajes de conversaciones activas. Implementa truncado FIFO basado en tokens para no exceder límites. Provee métodos para agregar mensajes, obtener contexto, limpiar memoria y estadísticas. Es una solución custom, no directamente LangChain, y se enfoca en sesiones "calientes".
    *   `persistence_manager.py` (`PersistenceManager`): Capa de abstracción para la persistencia. Actualmente implementada sobre Redis (para conversaciones activas, mensajes, mapeos de sesión, etc., usando JSON y TTLs). Contiene lógica para marcar conversaciones para migración y métodos placeholder para la migración real a PostgreSQL y limpieza de Redis post-migración.
*   **`models/`**: Define los modelos de datos Pydantic.
    *   `actions_model.py`: Define los modelos para los payloads de los `DomainAction` específicos del Conversation Service (ej. `SaveMessageAction`, `GetContextAction`, `SessionClosedAction`, `GetHistoryAction`).
    *   `conversation_model.py`: Define los modelos de datos principales del dominio: `Message`, `Conversation`, `ConversationStatus` (Enum), `MessageRole` (Enum), `ConversationContext` (para Query Service), `ConversationStats`.
*   **`routes/`**: Define los endpoints HTTP API (FastAPI).
    *   `crm_routes.py`: Endpoints para un CRM/Dashboard (`/api/v1/crm`). Incluye listado de conversaciones, detalle de conversación y estadísticas de tenant. Usa `ConversationService`.
    *   `health.py`: Endpoints de salud y estado (`/internal`). Incluye `/metrics` (actualmente con placeholders) y `/status` (con estado hardcodeado de features y dependencias).
    *   `old_analytics.py`: Endpoints de analíticas (`/api/v1/analytics`) que parecen ser legacy, con TODOs y datos mock. Probablemente código muerto/obsoleto.
    *   `old_conversations.py`: Endpoints CRUD para conversaciones (`/api/v1/conversations`) que también parecen legacy para la API pública. Sin embargo, contiene endpoints `/internal/history/{session_id}` y `/internal/save-message` que, según comentarios, son usados por Agent Execution Service, sugiriendo un canal de comunicación HTTP alternativo a los Domain Actions para estas operaciones específicas.
*   **`utils/`**: Directorio vacío. No hay utilidades específicas del servicio centralizadas aquí.
*   **`tests/`**: (No revisado en esta sesión, pero se asume su existencia para pruebas unitarias/integración).
*   **`requirements.txt`**: Lista las dependencias Python del servicio (ej. `fastapi`, `pydantic`, `redis[hiredis]`, `uvicorn`).
*   **`README.md`**: Documentación de alto nivel del servicio (revisada previamente).
*   **`ArquitecturaServicio.md`**: Documentación de arquitectura específica (revisada previamente).

## 4. Mecanismos de Comunicación Interna y Patrones

*   **Domain Actions sobre Redis:** Es el patrón principal para la comunicación inter-servicios desacoplada y asíncrona. Los workers (`ConversationWorker`, `MigrationWorker`) escuchan colas de Redis específicas.
*   **Patrón Pseudo-Síncrono sobre Redis:** Utilizado para acciones que requieren una respuesta más inmediata sin una llamada HTTP directa (ej. `conversation.get_history`). El `DomainAction` incluye un `correlation_id` y un `callback_queue_name` donde el Conversation Service (vía su worker/handler) envía la respuesta.
*   **FastAPI para APIs Externas y Posibles Internas:**
    *   **CRM/Admin:** `crm_routes.py` expone una API RESTful para la gestión y visualización externa.
    *   **Health Checks:** `health.py` expone endpoints para monitoreo.
    *   **Comunicación AES (Potencial):** Los endpoints `/internal/...` en `old_conversations.py` sugieren que Agent Execution Service podría estar usando HTTP para obtener historial y guardar mensajes, lo cual es una desviación del patrón de Domain Actions.
*   **Inyección de Dependencias (FastAPI):** Usado en las rutas para obtener instancias de `ConversationService`.
*   **Patrón Worker (BaseWorker 4.0):** Los `ConversationWorker` y `MigrationWorker` están estandarizados al `BaseWorker 4.0`, que define un ciclo de vida y un método `_handle_action` para procesar mensajes de las colas.
*   **Delegación de Lógica:**
    *   Workers -> `ConversationHandler` -> `ConversationService`.
    *   `ConversationService` -> `PersistenceManager` / `MemoryManager`.
    Esto mantiene las responsabilidades separadas.

## 5. Inconsistencias y Puntos a Mejorar

*   **Doble Canal de Comunicación con Agent Execution Service:** La mayor inconsistencia es el aparente uso dual de Domain Actions (ej. `conversation.get_history`, `conversation.save_message`) y endpoints HTTP internos (`/internal/history/...`, `/internal/save-message` en `old_conversations.py`) por parte del Agent Execution Service para interactuar con el Conversation Service. Esto debería unificarse, preferiblemente hacia el patrón de Domain Actions para mantener la coherencia arquitectónica y el desacoplamiento.
*   **Rutas Legacy (`old_analytics.py`, `old_conversations.py`):** Estos archivos contienen endpoints que parecen obsoletos o incompletos (llenos de TODOs y datos mock). Deberían ser formalmente deprecados y eliminados si no están en uso, o completados si la funcionalidad es necesaria. La existencia de `crm_routes.py` sugiere que parte de `old_conversations.py` ha sido reemplazada.
*   **Métricas y Health Checks Incompletos:**
    *   El endpoint `/internal/metrics` en `health.py` devuelve placeholders y tiene un TODO para implementar métricas reales.
    *   El endpoint `/internal/status` en `health.py` devuelve un estado mayormente hardcodeado. Debería verificar dinámicamente la salud de sus dependencias (ej. conexión a Redis).
*   **Integración con PostgreSQL Incompleta:** La migración a PostgreSQL y la persistencia a largo plazo es una característica clave mencionada pero no implementada. `PersistenceManager` tiene muchos placeholders al respecto.
*   **Lógica de Cierre de Sesión (TODO):** `ConversationHandler` tiene un TODO pendiente en `handle_session_closed`, indicando que la lógica para el cierre completo de sesión (ej. limpieza final, marcado definitivo para migración) podría no estar completa.
*   **Potencial Escalabilidad de `PersistenceManager` con Redis:** El uso de `KEYS` o patrones similares en Redis para búsquedas (si se usa extensivamente, como en `get_conversations_by_keys_pattern`) puede tener implicaciones de rendimiento en instancias de Redis grandes. Se mencionó la necesidad de un cleanup post-migración.
*   **Consistencia en `tenant_id` (Header vs. Path):** Las rutas en `crm_routes.py` toman `tenant_id` como path parameter, mientras que las rutas en `old_analytics.py` y `old_conversations.py` lo esperan del header `X-Tenant-ID`. Si alguna de las rutas "old" sigue activa, esto es una inconsistencia en el diseño de la API.
*   **`MemoryManager` y Persistencia:** Aunque `MemoryManager` se describe como un buffer en RAM, su interacción exacta con Redis para la persistencia de este buffer o su recuperación tras reinicios no está completamente detallada (se asume que `PersistenceManager` es la fuente de verdad para la carga inicial si es necesario).
*   **Conteo Real en Listados:** El endpoint de listado en `old_conversations.py` tiene un TODO para implementar el conteo real de conversaciones para la paginación.

## 6. Código Muerto o Duplicado

*   **`routes/old_analytics.py`**: Muy probablemente código muerto. Sus funcionalidades están incompletas (placeholders, TODOs) y no parece haber sido reemplazado por una funcionalidad equivalente en las rutas activas.
*   **Endpoints públicos en `routes/old_conversations.py`**: Los endpoints como `POST /`, `GET /{id}`, `PATCH /{id}`, `POST /{id}/messages`, `GET /` (listado) son probablemente código duplicado o reemplazado por la funcionalidad expuesta a través de `crm_routes.py` (aunque `crm_routes.py` es más limitado, enfocado a admin) o por la comunicación vía Domain Actions. Si la intención es que los servicios se comuniquen vía Domain Actions, estos endpoints HTTP públicos para manipulación directa de conversaciones podrían ser innecesarios o conflictivos.
*   **Funcionalidad de `update_conversation` en `old_conversations.py`**: El TODO para actualizar campos más allá del status indica que esta funcionalidad está incompleta y podría ser considerada parcialmente muerta si no se usa.

**Recomendación:** Realizar un análisis de uso de los endpoints en `old_analytics.py` y `old_conversations.py` (especialmente los no internos) para confirmar si pueden ser eliminados de forma segura. Clarificar el canal de comunicación preferido y único para Agent Execution Service.
