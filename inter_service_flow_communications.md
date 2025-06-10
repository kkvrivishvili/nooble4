# Documentación de Flujos de Comunicación Inter-Servicios

## Introducción Global

Este documento describe los flujos de comunicación de extremo a extremo entre los microservicios del proyecto nooble4. A diferencia del documento `inter_service_communication_v2.md` que detalla cada interacción desde la perspectiva de un solo servicio, este documento se centra en el "viaje" de una solicitud a través del sistema para cumplir con un objetivo de negocio o una operación completa.

Se utilizarán las mismas convenciones y terminología definidas en el documento de interacciones por servicio.

---

## Principales Flujos de Comunicación

A continuación se detallan los flujos de negocio y operativos de extremo a extremo, mostrando cómo los servicios colaboran para lograr funcionalidades completas.

### Flujo A: Ejecución Completa de un Agente por un Usuario Final

**Descripción General:**
Este flujo traza el ciclo de vida completo de una interacción del usuario: desde que envía un mensaje a través de un cliente (ej. WebSocket) hasta que recibe la respuesta generada por el agente. Es el flujo operativo más crítico del sistema.

**Servicios Principales Involucrados:**
*   Agent Orchestrator Service (AOS)
*   Agent Execution Service (AES)
*   Agent Management Service (AMS)
*   Conversation Service (CS)
*   Query Service (QS)
*   Embedding Service (ES)

**Diagrama de Secuencia (ASCII):**
```
Usuario          AOS                AES                AMS                CS                 QS                 ES
   |               |                  |                  |                  |                  |                  |
   |--[1. msg]-->|                  |                  |                  |                  |                  |
   |               |---[2. run]----->|                  |                  |                  |                  |
   |               |                  |---[3. config]-->|                  |                  |                  |
   |               |                  |<--[4. config]----|                  |                  |                  |
   |               |                  |---[5. history]->|                  |                  |                  |
   |               |                  |<--[6. history]--|                  |                  |                  |
   |               |                  |------------------[7. RAG query]--------------------->|                  |
   |               |                  |                  |                  |                  |---[8. embed]-->|
   |               |                  |                  |                  |                  |<--[9. embed]----|
   |               |                  |                  |                  |<----[10. search results]-----------|
   |               |                  |<-----------------[11. RAG results]------------------|                  |
   |               |                  |---[12. save user msg]-->|                  |                  |
   |               |                  |---[13. LLM call (externo)]--->...                     |                  |
   |               |                  |<--[14. LLM response]----...                     |                  |
   |               |                  |---[15. save agent msg]-->|                  |                  |
   |               |<--[16. response]-|                  |                  |                  |                  |
   |<--[17. msg]--|                  |                  |                  |                  |                  |
```

**Detalle de Pasos e Interacciones:**

#### Paso A.1: Usuario -> AOS: Envío de Mensaje
Un cliente frontend envía un mensaje a través de una conexión WebSocket establecida con AOS.

#### Paso A.2: AOS -> AES: Iniciar Ejecución de Agente
*   **Interacción de Referencia**: `8.1.1` (del doc. `inter_service_communication_v2.md`)
*   **Contexto**: AOS actúa como pasarela, traduciendo el mensaje WebSocket en una acción de dominio para AES.
*   **Acción**: `execution.agent_run` en la cola `agent_execution_service:actions`.
*   **Payload Clave**: `user_input`, `agent_id`, `session_id`, `tenant_id`, y un `correlation_id` generado por AOS para rastrear la respuesta.

#### Paso A.3 & A.4: AES <-> AMS: Obtener Configuración del Agente
*   **Interacción de Referencia**: `2.1.1`
*   **Contexto**: AES necesita la configuración completa del agente (system prompt, herramientas, modelo LLM, configuración RAG) para saber cómo ejecutarlo.
*   **Acción**: `agent.get_config` en `ams.actions`.
*   **Payload Clave**: AES solicita con `agent_id`; AMS responde con el objeto de configuración completo.

#### Paso A.5 & A.6: AES <-> CS: Obtener Historial de Conversación
*   **Interacción de Referencia**: `2.1.2`
*   **Contexto**: Para mantener el contexto, AES recupera los mensajes anteriores de la sesión actual.
*   **Acción**: `conversation.get_context` en `conversation.actions`.
*   **Payload Clave**: AES solicita con `session_id`; CS responde con una lista de mensajes.

#### Paso A.7 - A.11: AES -> QS -> ES: Flujo de RAG
*   **Contexto**: Si el agente tiene RAG habilitado, AES orquesta la búsqueda de conocimiento relevante antes de llamar al LLM.
*   **Paso A.7 (AES -> QS)**:
    *   **Interacción de Referencia**: `2.1.5`
    *   **Acción**: `query.rag.sync` en `query.actions`.
    *   **Payload Clave**: `query` (el input del usuario), y la lista de `collections` con sus `embedding_model` específicos.
*   **Paso A.8 & A.9 (QS <-> ES)**:
    *   **Interacción de Referencia**: `6.2.2`
    *   **Contexto**: QS delega la generación del embedding para la consulta del usuario a ES. Esto se repite para cada `embedding_model` distinto en la solicitud.
    *   **Acción**: `embedding.generate.sync` en `embedding.actions`.
*   **Paso A.10 (Búsqueda en Vector Store)**: QS usa el embedding de la consulta para buscar en la base de datos vectorial (no es una comunicación por Redis).
*   **Paso A.11 (QS -> AES)**: QS consolida los resultados de la búsqueda y los devuelve a AES en la cola de respuesta temporal.

#### Paso A.12: AES -> CS: Guardar Mensaje del Usuario
*   **Interacción de Referencia**: `2.1.3`
*   **Contexto**: AES guarda el mensaje del usuario en el historial de la conversación de forma asíncrona (fire-and-forget).
*   **Acción**: `conversation.save_message` en `conversation.actions`.
*   **Payload Clave**: El mensaje del usuario, `session_id`, y `role: "user"`.

#### Paso A.13 & A.14: AES -> LLM Provider (Externo)
AES construye el prompt final (con system prompt, historial, contexto RAG, y mensaje del usuario) y realiza una llamada a la API del proveedor de LLM (ej. OpenAI, Groq). Esta no es una comunicación interna vía Redis.

#### Paso A.15: AES -> CS: Guardar Respuesta del Agente
*   **Interacción de Referencia**: `2.1.3`
*   **Contexto**: Tras recibir la respuesta del LLM, AES la guarda en el historial de la conversación.
*   **Acción**: `conversation.save_message` en `conversation.actions`.
*   **Payload Clave**: La respuesta del agente, `session_id`, y `role: "agent"`.

#### Paso A.16: AES -> AOS: Devolver Respuesta del Agente
*   **Interacción de Referencia**: `8.2.1`
*   **Contexto**: AES envía la respuesta final a AOS para que pueda ser retransmitida al usuario.
*   **Acción**: `execution.agent_response` en la cola `aos.callbacks`.
*   **Payload Clave**: `agent_response` (con `content`, `type`, etc.) y el `correlation_id` original de la solicitud de AOS.

#### Paso A.17: AOS -> Usuario: Envío de Respuesta
AOS usa el `correlation_id` para encontrar la conexión WebSocket correcta y envía la respuesta del agente al cliente frontend.

**Conclusiones Específicas del Flujo:**
*   **Complejidad y Latencia**: Este flujo es el más largo y complejo, involucrando hasta 6 servicios internos en una sola solicitud. La latencia total es la suma de múltiples llamadas síncronas y asíncronas.
*   **Dependencias Críticas**: El flujo depende críticamente de la disponibilidad y rendimiento de todos los servicios involucrados, especialmente AMS (para configuración) y el proveedor de LLM externo.
*   **Punto Central de Orquestación**: AES actúa como el orquestador principal, coordinando las llamadas a otros servicios. Su lógica es fundamental para el correcto funcionamiento.
*   **Importancia del `correlation_id`**: El `correlation_id` generado por AOS es esencial para mantener el estado de la transacción a través de la comunicación asíncrona y devolver la respuesta al cliente correcto.

---

### Flujo B: Ingesta y Procesamiento de Documentos para RAG

**Descripción General:**
Este flujo describe el proceso de ingesta de documentos para que estén disponibles para búsquedas RAG. Comienza cuando un administrador o sistema inicia la ingesta de un conjunto de documentos para una colección específica y termina cuando los documentos han sido procesados, embebidos y (teóricamente) almacenados en una base de datos vectorial, con una notificación de estado final.

**Servicios Principales Involucrados:**
*   Agent Management Service (AMS) (o un cliente API directo)
*   Ingestion Service (IS)
*   Embedding Service (ES)
*   Vector Database (Conceptual, no es un microservicio con cola Redis)

**Diagrama de Secuencia (ASCII):**
```
AMS/Admin          IS                 ES            VectorDB
    |                |                  |                  |
    |--[1. ingest]-->|                  |                  |
    |                |--[2. chunking]-->|                  |
    |                |                  |                  |
    |                |--[3. embed]----->|                  |
    |                |<--[4. embed]-----|                  |
    |                |                  |                  |
    |                |--[5. save]------------------------>|
    |                |<--[6. save_ack]--------------------|
    |                |                  |                  |
    |<--[7. notify]--|                  |                  |
    |                |                  |                  |
```

**Detalle de Pasos e Interacciones:**

#### Paso B.1: AMS -> IS: Iniciar Ingesta de Documentos
*   **Interacción de Referencia**: `3.2.1` (del doc. `inter_service_communication_v2.md`)
*   **Contexto**: Un administrador, a través de la interfaz de AMS, o un proceso automatizado, solicita la ingesta de documentos (e.g., desde una URL, S3, etc.) para una `collection_id` específica.
*   **Acción**: `ingestion.start` en la cola `ingestion.actions`.
*   **Payload Clave**: `collection_id`, `tenant_id`, y una lista de `documents` con su `source_type` y `source_uri`.

#### Paso B.2: IS: Descarga y Chunking de Documentos
*   **Contexto**: El Ingestion Service recibe la solicitud. Su worker descarga el contenido de las `source_uri` y lo divide en trozos (chunks) manejables según la estrategia definida (e.g., por párrafos, tamaño fijo).
*   **Comunicación**: Este es un proceso interno de IS.

#### Paso B.3 & B.4: IS <-> ES: Generar Embeddings para Chunks
*   **Interacción de Referencia**: `7.2.1`
*   **Contexto**: IS necesita convertir cada chunk de texto en un vector numérico (embedding) para poder realizar búsquedas semánticas. Delega esta tarea a ES.
*   **Acción**: `embedding.generate.sync` en `embedding.actions`.
*   **Payload Clave**: IS envía lotes (`batches`) de chunks de texto (`texts`) a ES. ES responde con una lista de embeddings.
*   **Análisis Crítico**: IS debe manejar el `embedding_model` correcto para la colección, que debería haber sido parte de la solicitud inicial de AMS o ser recuperado por IS desde AMS. Esta es una dependencia de información implícita que debe ser explícita.

#### Paso B.5 & B.6: IS -> VectorDB: Guardar Embeddings
*   **Contexto**: IS toma los chunks de texto y sus correspondientes embeddings y los almacena en la base de datos vectorial asociada a la `collection_id`.
*   **Comunicación**: Llamada directa a la API o SDK de la base de datos vectorial (e.g., Pinecone, Weaviate, Qdrant). No es una comunicación por Redis.

#### Paso B.7: IS -> AMS: Notificar Estado de la Ingesta
*   **Interacción de Referencia**: `7.2.2`
*   **Contexto**: Una vez que todos los documentos de la solicitud han sido procesados (o si ha ocurrido un error terminal), IS envía una notificación a AMS para informar el resultado.
*   **Acción**: `ingestion.status_update` o `ingestion.completed` en la cola `ams.notifications` (o una cola similar).
*   **Payload Clave**: `collection_id`, `status` (`COMPLETED`, `FAILED`, `PARTIAL_SUCCESS`), estadísticas (`total_documents`, `processed_chunks`), y una lista de `errors` si los hubo.
*   **Análisis Crítico**: Este paso es crucial para cerrar el ciclo de ingesta. Permite a AMS actualizar el estado de la colección (e.g., de `INGESTING` a `READY`) y hacerlo visible para los agentes.

**Conclusiones Específicas del Flujo:**
*   **Flujo Asíncrono**: Este es un flujo inherentemente asíncrono y de larga duración. La notificación final (Paso B.7) es fundamental.
*   **Manejo de Errores**: IS debe ser robusto para manejar fallos en la descarga de documentos, en la generación de embeddings (e.g., límites de tasa de ES) o en el guardado en la VectorDB. La notificación a AMS debe reflejar estos errores.
*   **Dependencia de Información**: IS depende críticamente de conocer el `embedding_model` correcto para la colección. Este dato debe fluir desde AMS en la solicitud inicial.
*   **Escalabilidad**: IS y ES deben ser capaces de manejar grandes volúmenes de documentos y chunks en paralelo.

---

### Flujo C: Gestión de la Configuración de Agentes (Administración)

**Descripción General:**
Este flujo cubre las operaciones administrativas de Crear, Leer, Actualizar y Eliminar (CRUD) las configuraciones de los agentes. Estas acciones son típicamente iniciadas por un administrador del sistema a través de una interfaz de usuario de administración o una API, y afectan directamente el estado y comportamiento de los agentes disponibles en el sistema.

**Servicios Principales Involucrados:**
*   Cliente de Administración (e.g., Admin UI, CLI)
*   Agent Management Service (AMS)

**Diagrama de Secuencia (ASCII):**
```
AdminClient          AMS
    |                  |
    |---[1. CRUD Op]--->|
    |<--[2. Response]--|
    |                  |
```

**Detalle de Pasos e Interacciones:**

#### Paso C.1: Cliente Admin -> AMS: Realizar Operación CRUD
*   **Interacciones de Referencia (Conceptuales)**: Estas interacciones no han sido detalladas en `inter_service_communication_v2.md` pero seguirían el patrón de las acciones de AMS. Ejemplos:
    *   `management.create_agent`
    *   `management.update_agent`
    *   `management.get_agent` (similar a la `2.1.1` pero iniciada por un admin)
    *   `management.list_agents`
    *   `management.delete_agent`
*   **Contexto**: Un administrador necesita gestionar el ciclo de vida de las configuraciones de los agentes.
*   **Acción**: `management.<operation>` en la cola `ams.actions`.
*   **Patrón de Comunicación**: Pseudo-Síncrono. El cliente envía una solicitud y espera una respuesta directa con el resultado (éxito, error, o datos solicitados).
*   **Payload Clave**:
    *   **Create/Update**: El payload contiene el objeto de configuración del agente, completo o parcial.
    *   **Get/Delete**: El payload contiene el `agent_id` a consultar o eliminar.
    *   **List**: Puede contener parámetros de paginación o filtrado.
*   **Análisis Crítico**:
    *   **Validación**: AMS es responsable de validar exhaustivamente la configuración del agente. Esto incluye verificar que los modelos LLM especificados existan, que las herramientas listadas sean válidas, que las `collection_ids` para RAG sean correctas, etc.
    *   **Seguridad**: Estas son operaciones privilegiadas. AMS debe asegurarse de que el `tenant_id` y el iniciador de la solicitud tengan los permisos necesarios para realizar cambios.
    *   **Atomicidad**: Las actualizaciones deben ser atómicas para evitar estados de configuración inconsistentes.

**Conclusiones Específicas del Flujo:**
*   **Simplicidad del Flujo**: A diferencia de los flujos de ejecución o ingesta, este es un flujo de solicitud-respuesta muy directo y síncrono en su naturaleza.
*   **Complejidad Interna de AMS**: La principal complejidad no reside en la comunicación, sino en la lógica de negocio y validación dentro de AMS.
*   **Fundacional**: Este flujo es fundamental para el funcionamiento del sistema, ya que provisiona y configura los agentes que se utilizan en el "Flujo A".

---

### Flujo D: Callbacks Asíncronos (Análisis Transversal)

**Descripción General:**
Este no es un flujo de negocio de extremo a extremo, sino un análisis transversal del patrón de comunicación por "callbacks" asíncronos que existe en el sistema, particularmente en el `Agent Execution Service`. Se centra en las colas `embedding:callbacks` y `query:callbacks` y su estado de uso actual en comparación con el patrón pseudo-síncrono dominante.

**Servicios Principales Involucrados:**
*   Agent Execution Service (AES)
*   Embedding Service (ES)
*   Query Service (QS)

**Contexto y Justificación del Análisis:**
A lo largo de la Fase 1, observamos que la mayoría de las interacciones (e.g., `AES -> AMS`, `AES -> CS`, `AES -> QS`) utilizan un patrón pseudo-síncrono: el servicio solicitante (cliente) envía una solicitud con un `correlation_id` y espera activamente (`blpop`) en una cola de respuesta única y temporal (e.g., `agent_execution_service:responses:agent_config:{correlation_id}`).

Sin embargo, el código de AES, específicamente el `agent_execution_service.workers.execution_worker.ExecutionWorker`, también está configurado para escuchar en colas de callback genéricas: `embedding:callbacks` y `query:callbacks`. Esto sugiere la existencia (o intención) de un patrón de comunicación totalmente asíncrono.

**Análisis del Patrón y Discrepancias:**

1.  **Patrón de Callback Asíncrono (Intención Teórica):**
    *   **Paso 1**: AES envía una solicitud a ES (e.g., `embedding.generate.async`). En el payload, en lugar de un `correlation_id` para una cola de respuesta única, indicaría que la respuesta debe enviarse a la cola genérica `embedding:callbacks`.
    *   **Paso 2**: AES *no espera* la respuesta. Continúa con otras tareas o simplemente termina su ejecución actual.
    *   **Paso 3**: Cuando ES completa la tarea, publica el resultado en la cola `embedding:callbacks`.
    *   **Paso 4**: El `ExecutionWorker` de AES, que está escuchando constantemente en esa cola, recibe el resultado y lo procesa. Necesitaría un `correlation_id` u otro identificador en el payload de respuesta para saber a qué ejecución o sesión original pertenece este resultado.

2.  **Patrón Pseudo-Síncrono (Implementación Observada):**
    *   Como se documentó en las interacciones `2.1.4 (AES -> ES)` y `2.1.5 (AES -> QS)`, los clientes (`EmbeddingClient`, `QueryClient`) utilizan el método `..._sync`.
    *   Estos métodos crean una cola de respuesta única y temporal usando un `correlation_id` y realizan una espera bloqueante (`blpop`) en esa cola.
    *   **Observación Clave**: Aunque el `ExecutionWorker` *escucha* en las colas de callback, los clientes que AES usa para comunicarse con otros servicios *no parecen estar utilizando* este mecanismo en los flujos principales. En su lugar, optan por la espera activa.

**Posibles Interpretaciones y Conclusiones:**

*   **Funcionalidad Legacy**: El mecanismo de callback podría ser un remanente de una versión anterior de la arquitectura que ha sido reemplazado por el patrón pseudo-síncrono, que es más simple de razonar en flujos lineales. Sin embargo, el código para escuchar los callbacks no ha sido eliminado.
*   **Doble Implementación / Híbrido**: El sistema podría soportar ambos patrones. El patrón síncrono se usa para flujos donde la respuesta es necesaria inmediatamente para continuar (como obtener la configuración del agente o los resultados de RAG antes de llamar al LLM). El patrón de callback podría estar destinado a operaciones "fire-and-forget" o notificaciones que no bloquean el flujo principal.
*   **Funcionalidad Futura o Incompleta**: El patrón de callback podría ser una característica planificada para flujos más complejos y totalmente asíncronos que aún no se ha implementado por completo. Por ejemplo, para un agente que inicia múltiples tareas de larga duración en paralelo y procesa los resultados a medida que llegan.

**Recomendación:**
Es crucial clarificar el propósito de las colas `embedding:callbacks` y `query:callbacks` y el código del worker que las consume.
*   Si son legacy, deberían ser eliminadas para reducir la complejidad del código y evitar confusiones.
*   Si están destinadas a un uso futuro o a flujos específicos, esto debe ser documentado explícitamente, incluyendo cuándo y cómo deben usarse en contraposición al patrón pseudo-síncrono.
*   Actualmente, la documentación debe reflejar que, para los flujos principales analizados, el patrón pseudo-síncrono es el que está en uso activo.

---

# Resumen de Inconsistencias, Riesgos y Recomendaciones Globales

Esta sección consolida los hallazgos clave de los análisis de Fase 1 (por servicio) y Fase 2 (por flujo) para proporcionar una visión global del estado de la arquitectura de comunicación y las áreas de mejora.

## Inconsistencias y Ambigüedades Identificadas

1.  **Doble Patrón de Comunicación**: La inconsistencia más significativa es la coexistencia de un patrón **pseudo-síncrono** (usado activamente en todos los flujos principales) y un patrón de **callback asíncrono** (código existente en `ExecutionWorker` pero no utilizado por los clientes actuales). Esto aumenta la complejidad cognitiva y el riesgo de un uso incorrecto.
2.  **Dependencias de Datos Implícitas**: En el "Flujo B" (Ingesta), el `Ingestion Service` necesita el `embedding_model` para una colección, pero la interacción `AMS -> IS` no lo incluye explícitamente. Esto fuerza a IS a tener una dependencia implícita de consultar a AMS, violando la autonomía del servicio.
3.  **Nomenclatura de Colas y Acciones**: Aunque en general es consistente, hay variaciones menores en la nomenclatura que podrían estandarizarse aún más (e.g., `ams.actions` vs `agent_execution_service:actions`, `execution.agent_response` vs `agent.callback.result`).

## Riesgos Arquitectónicos

1.  **Latencia en Cascada (Flujo A)**: El flujo de ejecución del agente es una larga cadena de llamadas pseudo-síncronas. Un retraso en cualquier servicio de la cadena (AMS, CS, QS, ES) impacta directamente la latencia total percibida por el usuario. No hay paralelismo en las llamadas de obtención de datos (config, historial).
2.  **Puntos Únicos de Fallo (SPOF)**: 
    *   `Agent Execution Service (AES)`: Actúa como el orquestador central en el flujo de usuario. Un fallo en AES paraliza toda la capacidad de conversación.
    *   `Agent Management Service (AMS)`: Es la fuente de verdad para toda la configuración. Si AMS está inactivo, ningún agente puede ser ejecutado correctamente.
3.  **Manejo de Errores Complejo**: La naturaleza distribuida del "Flujo A" hace que el manejo de errores sea complejo. Un fallo en un paso intermedio (e.g., QS no puede generar RAG) debe ser manejado y comunicado adecuadamente al usuario final a través de varios servicios.

## Recomendaciones Globales

1.  **Estandarizar el Patrón de Comunicación**: Tomar una decisión arquitectónica sobre el patrón de callback. 
    *   **Opción A (Recomendado)**: Eliminar el código del listener de callback si es legacy para simplificar la arquitectura.
    *   **Opción B**: Si se desea un modelo híbrido, documentar explícitamente los casos de uso para el patrón asíncrono y refactorizar los clientes para que puedan usarlo.
2.  **Hacer Explícitas las Dependencias de Datos**: Refactorizar las interacciones para que los servicios reciban toda la información que necesitan para realizar su tarea. Por ejemplo, la acción `ingestion.start` de AMS a IS debería incluir el `embedding_model` de la colección.
3.  **Optimizar la Latencia del Flujo Crítico (Flujo A)**: Investigar la paralelización de las llamadas de obtención de datos en AES. Por ejemplo, las llamadas a AMS para la configuración del agente y a CS para el historial de la conversación podrían realizarse en paralelo usando `asyncio.gather`.
4.  **Implementar Tracing Distribuido**: Para mejorar la observabilidad, introducir un sistema de tracing distribuido (e.g., OpenTelemetry). El `correlation_id` existente en los payloads es una base excelente para esto, ya que permitiría rastrear una solicitud a través de todos los servicios que toca.
5.  **Reforzar la Resiliencia del Sistema**: Implementar patrones de resiliencia de forma sistemática en todos los clientes de servicio:
    *   **Reintentos (Retries)** con backoff exponencial para fallos transitorios.
    *   **Circuit Breakers** para evitar sobrecargar servicios que están fallando.
    *   **Timeouts** agresivos y bien configurados para cada llamada de red.
