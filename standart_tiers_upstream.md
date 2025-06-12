# Estándar de Gestión de Tiers - Interacción Upstream (AOS) (`standart_tiers_upstream.md`)

Este documento detalla cómo el Agent Orchestrator Service (AOS), actuando como el principal punto de entrada y orquestador, interactúa con los componentes comunes de gestión de tiers para validar las solicitudes de los usuarios antes de despacharlas a los servicios downstream.

## 1. Objetivos de la Validación en AOS

*   **Prevención Proactiva:** Asegurar que las solicitudes que excederían los límites del tier del tenant sean rechazadas tempranamente, evitando el consumo innecesario de recursos en servicios downstream.
*   **Punto Único de Control:** Centralizar la lógica de validación de límites de tier en AOS para mantener la coherencia y simplificar el mantenimiento.
*   **Experiencia de Usuario Clara:** Proveer respuestas informativas al usuario cuando una acción es denegada debido a restricciones de tier.

## 2. Integración de Componentes Comunes en AOS

AOS integrará y utilizará los siguientes componentes del módulo `common.tiers` y `common.exceptions`:

*   De `common.tiers.tiers_constants`:
    *   `TierName` (Enum)
    *   `TierResourceKey` (Enum)
*   De `common.tiers.usage_service`:
    *   `get_static_limit(tier: TierName, resource_key: TierResourceKey) -> Any`
    *   `get_current_usage(tenant_id: str, resource_key: TierResourceKey, time_window_dt: Optional[datetime.datetime] = None) -> int`
    *   `is_limit_exceeded(tenant_id: str, tier: TierName, resource_key: TierResourceKey, requested_value: Union[int, str] = 1, current_dt: Optional[datetime.datetime] = None) -> bool`
*   De `common.exceptions.tier_exceptions`:
    *   `TierLimitExceededError`

Además, el modelo `ExecutionContext` (definido en `refactorizado/common/models/execution_context.py`) será crucial. Se espera que contenga un campo:
`tenant_tier: Optional[TierName] = None`

Este campo `tenant_tier` deberá ser populado por AOS al inicio del procesamiento de una solicitud, típicamente obteniendo la información del tier del tenant a partir de su `tenant_id` (posiblemente consultando un servicio de gestión de tenants o una base de datos de configuración).

## 3. Lógica de Validación en AOS

La validación de tiers se realizará principalmente dentro del `OrchestratorContextHandler` (o un componente similar que actúe como middleware o pre-procesador antes de que las `DomainAction` sean manejadas por los handlers específicos de AOS o reenviadas).

El flujo general de validación para una `DomainAction` entrante será:

1.  **Obtener Contexto:**
    *   Extraer `tenant_id` de la `DomainAction` o del `ExecutionContext` ya establecido.
    *   Asegurar que `tenant_tier` en el `ExecutionContext` esté populado. Si no es posible determinar el tier, se debe asumir el tier más restrictivo o denegar la solicitud.

2.  **Identificar Recursos a Validar:**
    *   Basado en el `action_type` de la `DomainAction` y, potencialmente, su `data`, determinar qué `TierResourceKey`(s) son relevantes para la validación.
    *   AOS mantendrá un mapeo o lógica para asociar `action_type` con los `TierResourceKey`(s) correspondientes.

3.  **Realizar Validación:**
    *   Para cada `TierResourceKey` relevante:
        *   Llamar a `await is_limit_exceeded(tenant_id, execution_context.tenant_tier, resource_key, requested_value, current_datetime)`.
        *   `requested_value` dependerá del recurso:
            *   Para contadores (ej. `MAX_AGENTS` al crear un agente), será `1`.
            *   Para listas (ej. `ALLOWED_LLM_MODELS`), será el nombre del modelo solicitado.
            *   Para flags booleanos (ej. `CAN_USE_CUSTOM_PROMPTS`), la llamada a `is_limit_exceeded` manejará la lógica interna basada en el valor booleano del límite.

4.  **Manejo del Resultado de la Validación:**
    *   Si `is_limit_exceeded` devuelve `True` para CUALQUIER recurso validado:
        *   Lanzar una `TierLimitExceededError` con un mensaje descriptivo, el `error_code` apropiado (ej. `TIER_LIMIT_REACHED`, `FEATURE_NOT_ALLOWED_FOR_TIER`), el `resource_key` y el `tier_name`.
        *   Esta excepción será capturada por el `BaseWorker` o un manejador de errores global en AOS.
        *   Se generará y enviará una `DomainActionResponse` al solicitante con `success=False` y un `ErrorDetail` que refleje la información de la `TierLimitExceededError`.
    *   Si todas las validaciones pasan (`is_limit_exceeded` devuelve `False` para todos los recursos):
        *   La `DomainAction` continúa su procesamiento normal (ej. se pasa al handler correspondiente en AOS o se reenvía a un servicio downstream).

## 4. Ejemplos de Puntos de Validación en AOS

| Acción del Usuario (Conceptual) | `action_type` (Ejemplo)        | `TierResourceKey`(s) a Validar en AOS                                  | `requested_value` (Ejemplo)                               |
| :------------------------------ | :----------------------------- | :--------------------------------------------------------------------- | :-------------------------------------------------------- |
| Crear un nuevo agente           | `agent.create`                 | `MAX_AGENTS`                                                           | `1`                                                       |
| Usuario intenta usar un LLM X   | `query.ask` / `agent.execute`  | `ALLOWED_LLM_MODELS`                                                   | Nombre del modelo LLM X                                   |
| Ejecutar una query              | `query.ask`                    | `QUERIES_PER_HOUR` (si aplica a nivel de AOS)                          | `1`                                                       |
| Usar prompts personalizados     | `agent.configure`              | `CAN_USE_CUSTOM_PROMPTS`                                               | (La lógica está en `is_limit_exceeded`)                   |
| Persistir una conversación      | `conversation.save_message`    | `CAN_PERSIST_CONVERSATIONS`                                            | (La lógica está en `is_limit_exceeded`)                   |

## 5. Responsabilidades NO Cubiertas por AOS en este Flujo

*   **Actualización de Contadores de Uso:** AOS **NO** llama a `publish_usage_update`. La responsabilidad de reportar el consumo efectivo de un recurso recae en el servicio downstream que realiza la acción final que consume dicho recurso. AOS solo valida contra el estado actual y los límites estáticos.

## 6. Consideraciones Adicionales

*   **Caching de Límites:** Para optimizar, los `TierLimitSettings` podrían ser cacheados en memoria en AOS al inicio, ya que se espera que cambien con poca frecuencia.
*   **Determinación del Tier del Tenant:** El mecanismo exacto para que AOS determine el `tenant_tier` a partir del `tenant_id` está fuera del alcance de este documento, pero es un prerrequisito crítico.
