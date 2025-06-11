# Análisis de Inconsistencias Post-Refactorización

Este documento analiza el estado de las inconsistencias previamente identificadas después de la refactorización de `ExecutionClient` e `IngestionClient`, que reemplazó la comunicación HTTP por `DomainActions` a través de Redis.

---

## 1. Agent Execution Service (AES)

#### Problema #1 a #3: Interacciones con ConversationService y AgentManagementService
- **Descripción**: Problemas con nombres de colas, respuestas síncronas faltantes y handlers no implementados en las interacciones de AES con CS y AMS.
- **Estado de Refactorización**: **PENDIENTE**. La refactorización se centró en los clientes *dentro* de AMS (`ExecutionClient`, `IngestionClient`) y en los workers correspondientes (`ExecutionWorker`, `IngestionWorker`). No se modificaron las interacciones iniciadas *desde* AES hacia otros servicios.

#### Problema #4: Redundancia de `correlation_id`
- **Descripción**: `correlation_id` presente tanto en la raíz del `DomainAction` como en el `data`.
- **Estado de Refactorización**: **PARCIALMENTE RESUELTO**. En las nuevas implementaciones de `ExecutionClient` e `IngestionClient`, el `correlation_id` se ha estandarizado para que exista únicamente en el nivel raíz del `DomainAction`, promoviendo un payload más limpio. Sin embargo, no se ha realizado una auditoría completa en todos los demás servicios.

#### Problema #5: Callbacks Asíncronos No Utilizados
- **Descripción**: `ExecutionWorker` escucha en colas de callback que no parecen ser utilizadas por los clientes.
- **Estado de Refactorización**: **PENDIENTE**. El objetivo era reemplazar HTTP, no eliminar lógica de callbacks potencialmente legacy. Este punto sigue pendiente de análisis y limpieza.

#### Problema #6: Inconsistencia en `session_id`
- **Descripción**: La ubicación de `session_id` varía entre los payloads de diferentes clientes.
- **Estado de Refactorización**: **PENDIENTE**. La estandarización de este campo no formó parte del alcance de la refactorización actual.

---

## 2. Conversation Service (CS)

#### Problema #7 y #8: Inconsistencias en Colas y Triggers
- **Descripción**: Problemas con el patrón de colas de respuesta y la falta de triggers para el `MigrationWorker`.
- **Estado de Refactorización**: **PENDIENTE**. No se ha trabajado sobre el `ConversationService`.

---

## 3. Agent Management Service (AMS)

#### Problema #9: Múltiples `action_types` para la misma operación
- **Descripción**: Confusión sobre qué `action_type` usar para obtener la configuración de un agente.
- **Estado de Refactorización**: **PARCIALMENTE RESUELTO**. Para las operaciones refactorizadas, se ha establecido un `action_type` único y claro:
    - Invalidación de caché: `execution.cache.invalidate`.
    - Validación de colecciones: `ingestion.collections.validate`.
    - Listado de colecciones: `ingestion.collections.list`.
  Esto sienta un precedente para resolver la ambigüedad en otras operaciones, aunque el problema original de `get_agent_config` persiste.

#### Problema #10: `tenant_id` inconsistente en payloads
- **Descripción**: `tenant_id` a veces en la raíz, a veces en `data`.
- **Estado de Refactorización**: **PARCIALMENTE RESUELTO**. Al igual que con `correlation_id`, se ha estandarizado el uso de `tenant_id` a nivel raíz en todos los `DomainActions` generados por los clientes refactorizados.

---

## 4 & 5. Embedding Service (ES) y Query Service (QS)

#### Problema #11 a #14: Inconsistencias de Diseño e Integración
- **Descripción**: Problemas relacionados con callbacks, documentación y lógica de negocio interna de ES y QS.
- **Estado de Refactorización**: **PENDIENTE**. Estos servicios no fueron parte de la refactorización.

---

## 6. Ingestion Service (IS)

#### Problema #15: Almacenamiento de Embeddings - TODO
- **Descripción**: El `IngestionWorker` no implementa la lógica para guardar los embeddings en el vector store.
- **Estado de Refactorización**: **PENDIENTE**. Aunque se modificó el `IngestionWorker` para manejar nuevas acciones, la lógica de negocio principal (como la escritura en el vector store) no se alteró y sigue marcada como `TODO`.

#### Problema #16: Notificación a AMS No Implementada
- **Descripción**: IS no notifica a AMS sobre el estado de la ingesta.
- **Estado de Refactorización**: **PARCIALMENTE RESUELTO**. Se ha implementado una comunicación directa y pseudo-síncrona desde AMS hacia IS para validar y listar colecciones. Esto resuelve una parte de la comunicación necesaria, pero no aborda las notificaciones asíncronas sobre el estado de tareas de ingesta de larga duración.

---

## 7 & 8. Inconsistencias Generales y de Nomenclatura

#### Problema #17: `action_type` para Ejecución
- **Descripción**: Múltiples `action_types` para la ejecución de agentes.
- **Estado de Refactorización**: **PENDIENTE**. No se ha trabajado sobre el `Agent Orchestrator Service`.

#### Problema #18: Separadores en Nombres de Colas
- **Descripción**: Uso inconsistente de `:` y `.` como separadores.
- **Estado de Refactorización**: **PARCIALMENTE RESUELTO**. La refactorización ha adoptado y reforzado el estándar de usar `:` para separar los componentes de los nombres de las colas (ej. `ingestion:actions`) y `.` para los `action_types` (ej. `execution.cache.invalidate`). Esto ayuda a estandarizar el sistema, aunque requiere ser aplicado en todos los servicios.

#### Problema #19: Ubicación Inconsistente de Campos Comunes
- **Descripción**: `correlation_id`, `tenant_id`, `session_id` en diferentes lugares.
- **Estado de Refactorización**: **PARCIALMENTE RESUELTO**. Se ha avanzado significativamente en la estandarización de `correlation_id` y `tenant_id` a nivel raíz en los flujos de comunicación refactorizados. `session_id` sigue pendiente.

#### Problema #20: Mezcla de Patrones de Comunicación
- **Descripción**: Uso de diferentes patrones (pseudo-síncrono, fire-and-forget, callbacks) sin una justificación clara.
- **Estado de Refactorización**: **RESUELTO**. La refactorización ha servido para clarificar y documentar implícitamente el propósito de cada patrón a través de ejemplos concretos:
    - **Fire-and-Forget**: Utilizado para `execution.cache.invalidate`. Ideal para notificaciones donde el emisor no necesita una respuesta.
    - **Pseudo-Síncrono**: Utilizado para `ingestion.collections.validate` y `list`. Perfecto para operaciones donde el emisor necesita un resultado para continuar su propio flujo.
    - **Callbacks Asíncronos**: Se mantiene para procesos largos y complejos como la ingesta de documentos, donde se requiere notificar el progreso sin bloquear al emisor.

## Conclusión

La refactorización ha sido un éxito en su objetivo de eliminar la comunicación HTTP en los clientes seleccionados y ha sentado bases sólidas para la estandarización de la comunicación vía `DomainActions`. Se han resuelto o avanzado significativamente en varias inconsistencias de diseño y nomenclatura (`#4`, `#9`, `#10`, `#16`, `#18`, `#19`, `#20`).

Sin embargo, la mayoría de las inconsistencias críticas, especialmente aquellas relacionadas con la lógica de negocio interna de cada servicio (`#1`, `#3`, `#7`, `#15`), siguen pendientes y requerirán trabajo enfocado en cada microservicio específico.
