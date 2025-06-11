# Propuesta de Refactorización y Estandarización para Agent Execution Service (AES)

## 1. Introducción

Este documento describe una propuesta para refactorizar y estandarizar componentes clave dentro del Agent Execution Service (AES). El objetivo es mejorar la claridad arquitectónica, la separación de responsabilidades, la reutilización de código, la testeabilidad y la mantenibilidad de AES. Esta iniciativa se inspira en los principios delineados en documentos de estandarización general (`standart_handler.md`, `standart_client.md`, `standart_colas.md`, `standart_payload.md`) y busca adaptar dichos principios a la estructura y necesidades específicas de AES, sirviendo como un proyecto piloto para una eventual estandarización en todos los servicios de Nooble4.

## 2. Principios Guía de Estandarización

Nos basaremos en los siguientes pilares, adaptados de la documentación de estándares generales:

*   **Handlers Estandarizados:** Introducir una capa de handlers de acciones bien definida, separada de la lógica del worker, para procesar `DomainAction`s específicas.
*   **Clients Estandarizados:** Adoptar un patrón común para los clientes que AES utiliza para comunicarse con otros servicios, promoviendo consistencia en la inicialización, ejecución de solicitudes y manejo de respuestas/errores.
*   **Gestión de Colas Consistente:** Asegurar que el uso de colas Redis (nomenclatura, patrones de interacción) por parte de AES se alinee estrictamente con los estándares definidos para todo el sistema.
*   **Payloads Estandarizados:** Armonizar las estructuras de datos (payloads) de los `DomainAction`s y `DomainActionResponse`s que AES consume y produce, utilizando modelos Pydantic base comunes cuando sea aplicable.

## 3. Arquitectura Actual de AES (Componentes Relevantes)

Para entender el impacto de la refactorización, revisamos los componentes clave de AES:

*   **`ExecutionWorker` (`workers/execution_worker.py`):** Punto de entrada para `DomainAction`s desde Redis. Actualmente maneja el despacho inicial y la orquestación de algunas llamadas pseudo-síncronas. Ya adaptado a BaseWorker 4.0.
*   **Handlers Actuales (`handlers/`):
    *   `AgentExecutionHandler`: Contiene la lógica (actualmente un stub) para `execution.agent_run`.
    *   `ContextHandler`: Gestiona la obtención y caché de contexto (ej. configuración del agente).
    *   `ExecutionCallbackHandler`, `EmbeddingCallbackHandler`, `QueryCallbackHandler`: Manejan callbacks de otros servicios.
*   **Clients (`clients/`):** Clases para interactuar con servicios externos (AMS, CS, ES, QS) usando comunicación por colas Redis.
*   **Models (`models/`):** Modelos Pydantic para `DomainAction`s específicas de AES, resultados de ejecución, etc.

## 4. Propuesta de Refactorización para AES

### 4.1. Refactorización de Handlers

**Objetivo:** Centralizar la lógica de procesamiento de `DomainAction`s en handlers dedicados, desacoplándolos del `ExecutionWorker`.

**Pasos:**

1.  **Definir `BaseActionHandler` (en `common` o `agent_execution_service/handlers/base_handler.py` si es específico inicialmente):**
    *   Contendrá métodos comunes o una interfaz para la inicialización (`async_init` si es necesario) y el manejo de acciones.
    *   Podría recibir dependencias comunes (ej. `redis_client`, `queue_manager`, `settings`) en su constructor.

2.  **Crear `AESActionHandler(BaseActionHandler)` en `agent_execution_service/handlers/aes_action_handler.py`:**
    *   Este handler consolidará la lógica para la mayoría de los `DomainAction`s que AES procesa directamente.
    *   Métodos específicos por `action_type`:
        *   `async handle_agent_execution(self, action: AgentExecutionAction, context: ExecutionContext)`: Mover la lógica actual de `AgentExecutionHandler.handle_agent_execution` aquí. Esta será el punto de entrada para la futura implementación de la ejecución real del agente.
        *   `async handle_embedding_callback(self, action: EmbeddingCallbackAction, ...)`: Mover lógica de `EmbeddingCallbackHandler`.
        *   `async handle_query_callback(self, action: QueryCallbackAction, ...)`: Mover lógica de `QueryCallbackHandler`.
        *   `async handle_execution_cache_invalidate(self, action: DomainAction, ...)`: Mover lógica de invalidación de caché.
        *   Otros handlers de callbacks o acciones directas que AES maneje.
    *   El `ContextHandler` actual podría ser inyectado como dependencia en `AESActionHandler` o sus métodos ser integrados si la cohesión es alta.
    *   El `ExecutionCallbackHandler` podría ser refactorizado de manera similar si maneja `DomainAction`s entrantes, o sus funcionalidades ser absorbidas por `AESActionHandler` si se simplifica.

3.  **Actualizar `ExecutionWorker`:**
    *   En `initialize`, instanciar `AESActionHandler` (y pasarle las dependencias necesarias).
    *   El método `_handle_action` del worker se simplificará enormemente. Su rol principal será:
        *   Parsear el `DomainAction`.
        *   Determinar el método apropiado en `AESActionHandler` basado en `action.action_type` (usando un mapa o una estructura `if/elif`).
        *   Llamar al método del handler: `handler_result = await self.aes_action_handler.handle_specific_action(action, exec_context)`.
        *   La lógica de `_send_pseudo_sync_response` y `_send_pseudo_sync_error_response` se mantiene en el worker para las acciones que lo requieran, pero la decisión de qué enviar vendrá del resultado del handler.
    *   Los métodos como `_request_conversation_history_sync` (que son esencialmente funciones cliente para orquestar llamadas pseudo-síncronas) podrían permanecer en el worker si se consideran parte de su rol de "orquestador de comunicación", o moverse a una clase cliente interna si la lógica es compleja.

### 4.2. Refactorización de Clients

**Objetivo:** Estandarizar la implementación de clientes para servicios externos.

**Pasos:**

1.  **Definir `BaseServiceClient` (en `common` o `agent_execution_service/clients/base_client.py`):**
    *   Constructor estándar que reciba `redis_client`, `queue_manager`, `settings`.
    *   Método `async_init` para inicialización asíncrona si es necesario.
    *   Utilidades comunes para enviar `DomainAction`s y manejar respuestas pseudo-síncronas (ej. encapsular el patrón de `publish_action` + `blpop` + `expire` + manejo de timeout y errores).
    *   Configuración estándar de reintentos (usando `tenacity`).

2.  **Refactorizar Clientes Existentes en AES (`clients/`):
    *   `AgentManagementClient`, `ConversationServiceClient`, `EmbeddingClient`, `QueryClient` heredarán de `BaseServiceClient`.
    *   Adaptarán sus métodos (`get_agent_config`, etc.) para utilizar las utilidades provistas por `BaseServiceClient`.
    *   Esto promoverá la reutilización de la lógica de comunicación Redis y reducirá el código duplicado entre clientes.

### 4.3. Adherencia a Estándares de Colas

**Objetivo:** Asegurar el cumplimiento estricto de las convenciones de nomenclatura y uso de colas.

**Pasos:**

1.  **Revisión de Nomenclatura:** Verificar que todas las colas a las que AES se suscribe o publica (definidas en `ExecutionWorker` y usadas por los clientes) sigan el formato `{prefijo_global}:{entorno}:{tipo_servicio}:{contexto_especifico}:{tipo_cola}:{detalle_cola}` (basado en Memoria `[9395f05a-ecfb-4003-ad50-a3deff0156af]`).
2.  **Uso de `DomainQueueManager`:** Continuar y reforzar el uso de `DomainQueueManager` para la generación de nombres de cola y la publicación de acciones, asegurando que sus métodos estén alineados con los estándares.
3.  **Patrones de Respuesta:** Confirmar que los patrones para colas de respuesta pseudo-síncrona y colas de callback asíncrono se implementen consistentemente.

### 4.4. Estandarización de Payloads

**Objetivo:** Armonizar los modelos Pydantic para los datos de `DomainAction` y `DomainActionResponse`.

**Pasos:**

1.  **Modelos Base Comunes (en `common/models`):**
    *   Definir (si no existen ya o necesitan mejora) modelos Pydantic base para:
        *   `BaseActionData(BaseModel)`: Un modelo base para el campo `data` de `DomainAction`s.
        *   `BaseResponseData(BaseModel)`: Un modelo base para el campo `data` de `DomainActionResponse`s exitosas.
        *   `StandardErrorDetail(BaseModel)`: Un modelo estándar para el campo `error` de `DomainActionResponse`s fallidas (reemplazando o estandarizando el `ErrorDetail` actual si es necesario).

2.  **Actualizar Modelos de AES (`models/`):
    *   Los modelos en `actions_model.py` (ej. `AgentExecutionActionData`) y `execution_model.py` (ej. `ExecutionResult` que podría ser el `data` de una `DomainActionResponse`) heredarán o se compondrán con estos modelos base comunes.
    *   Asegurar que todos los campos `data` y `error` producidos o consumidos por AES se adhieran a estas estructuras estándar.
    *   Esto es particularmente importante para `ExecutionResult` y para los `data` de las acciones que AES envía a otros servicios.

## 5. Beneficios de la Refactorización para AES

*   **Separación Clara de Responsabilidades:**
    *   Worker: Infraestructura de colas y despacho inicial.
    *   Handler: Lógica de negocio para acciones específicas.
    *   Client: Comunicación con servicios externos.
*   **Código Reutilizable:**
    *   `BaseActionHandler` y `BaseServiceClient` encapsulan lógica común.
    *   Modelos Pydantic base para payloads reducen duplicación.
*   **Testeabilidad Mejorada:**
    *   Handlers y Clients pueden ser testeados unitariamente de forma aislada con mayor facilidad.
*   **Mantenibilidad y Escalabilidad:**
    *   Código más fácil de entender, modificar y extender.
    *   Añadir nuevos `action_type`s o clientes se vuelve más sistemático.
*   **Consistencia:**
    *   Alinea AES con los estándares propuestos para todo Nooble4, facilitando la rotación de desarrolladores y la comprensión global del sistema.

## 6. Plan Detallado para la Refactorización de AES

Se propone un enfoque incremental:

1.  **Fase 0: Preparación y Definición de Bases Comunes (si es necesario en `common`):
    *   [ ] Definir/Finalizar `BaseActionHandler`.
    *   [ ] Definir/Finalizar `BaseServiceClient`.
    *   [ ] Definir/Finalizar modelos Pydantic base para payloads (`BaseActionData`, `BaseResponseData`, `StandardErrorDetail`).

2.  **Fase 1: Refactorización de Handlers en AES:**
    *   [ ] Crear `agent_execution_service/handlers/base_handler.py` (si `BaseActionHandler` no va a `common` inmediatamente) o importar desde `common`.
    *   [ ] Implementar `AESActionHandler` en `handlers/aes_action_handler.py`.
    *   [ ] Migrar lógica de `AgentExecutionHandler` a `AESActionHandler.handle_agent_execution`.
    *   [ ] Migrar lógica de otros handlers (callbacks, cache invalidate) a métodos correspondientes en `AESActionHandler`.
    *   [ ] Refactorizar `ExecutionWorker._handle_action` para usar `AESActionHandler`.
    *   [ ] Actualizar pruebas unitarias y de integración.

3.  **Fase 2: Refactorización de Clients en AES:**
    *   [ ] Crear `agent_execution_service/clients/base_client.py` (si `BaseServiceClient` no va a `common`) o importar.
    *   [ ] Refactorizar `AgentManagementClient` para heredar de/usar `BaseServiceClient`.
    *   [ ] Refactorizar `ConversationServiceClient`.
    *   [ ] Refactorizar `EmbeddingClient`.
    *   [ ] Refactorizar `QueryClient`.
    *   [ ] Actualizar pruebas unitarias.

4.  **Fase 3: Revisión y Alineación de Payloads y Colas en AES:**
    *   [ ] Revisar todos los modelos Pydantic en `agent_execution_service/models/` y alinearlos con los modelos base comunes (Fase 0).
    *   [ ] Verificar la nomenclatura y uso de todas las colas Redis en `ExecutionWorker` y clientes contra los estándares.
    *   [ ] Actualizar pruebas si los modelos cambian significativamente.

5.  **Fase 4: Pruebas End-to-End y Documentación:**
    *   [ ] Realizar pruebas de integración y E2E para asegurar que AES sigue funcionando correctamente con otros servicios.
    *   [ ] Actualizar cualquier documentación interna de AES (READMEs, diagramas) para reflejar la nueva estructura.
    *   [ ] Finalizar este documento `AES_Refactoring_Proposal.md` con lecciones aprendidas.

## 7. Consideraciones Adicionales

*   **Iteración:** Cada fase puede subdividirse en tareas más pequeñas.
*   **Pruebas Continuas:** Es crucial mantener y actualizar el conjunto de pruebas a lo largo de la refactorización.
*   **Comunicación:** Mantener informado al equipo sobre los cambios y el progreso.

## 8. Conclusión

Esta refactorización propuesta para AES, aunque requiere un esfuerzo dedicado, sentará una base sólida para un servicio más robusto, mantenible y alineado con las mejores prácticas y los estándares emergentes dentro de Nooble4. Los beneficios a largo plazo en términos de calidad del código y eficiencia del desarrollo justificarán la inversión inicial.
