# Estándar de Gestión de Tiers - Validación Upstream (AOS) (`standart_tiers_upstream.md`)

Este documento detalla cómo el Agent Orchestrator Service (AOS), actuando como el principal punto de entrada y orquestador, interactúa con los componentes comunes de gestión de tiers para validar las solicitudes de los usuarios antes de despacharlas a los servicios downstream.

## 1. Objetivos de la Validación en AOS

*   **Prevención Proactiva:** Asegurar que las solicitudes que excederían los límites del tier del tenant sean rechazadas tempranamente, evitando el consumo innecesario de recursos en servicios downstream.
*   **Punto Único de Control:** Centralizar la lógica de validación de límites de tier en AOS para mantener la coherencia y simplificar el mantenimiento.
*   **Experiencia de Usuario Clara:** Proveer respuestas informativas al usuario cuando una acción es denegada debido a restricciones de tier.

## 2. Integración de Componentes Comunes en AOS

AOS integrará y utilizará los componentes definidos en `standart_tiers_common.md`. La interacción se centrará en:

*   **`common.tiers.services.TierValidationService`**: El servicio principal para realizar validaciones complejas.
*   **`common.tiers.decorators.validate_tier`**: El mecanismo preferido para aplicar validaciones de forma declarativa y limpia en los `ActionHandlers`.
*   **`common.tiers.clients.TierClient`**: Para obtener información sobre los tiers cuando sea necesario fuera del flujo de validación estándar.
*   **`common.tiers.exceptions.TierLimitExceededError`**: La excepción que se lanzará cuando una validación falle.

El `ExecutionContext` seguirá siendo crucial y deberá contener el `tenant_tier`, que AOS debe obtener al inicio de la solicitud.

## 3. Lógica de Validación en AOS: Patrón Recomendado

El método **preferido y estándar** para la validación de tiers en AOS es el uso del decorador `@validate_tier` directamente sobre los métodos `handle` de los `ActionHandlers`.

### 3.1. Patrón 1: Uso del Decorador (Recomendado)

Este enfoque es declarativo, limpio y mantiene la lógica de validación junto a la acción que la requiere.

**Ejemplo: Validar la creación de un nuevo agente.**

```python
# En agent_orchestrator_service/handlers/agent_handler.py (ejemplo)

from common.models.actions import DomainAction
from common.handlers import BaseActionHandler
from common.tiers.decorators import validate_tier
from common.tiers.models import TierResourceKey

class CreateAgentHandler(BaseActionHandler):
    # El decorador intercepta la llamada ANTES de que se ejecute el método handle.
    # Automáticamente extrae tenant_id y tenant_tier del contexto y realiza la validación.
    # Si la validación falla, lanza TierLimitExceededError y el método nunca se ejecuta.
    @validate_tier(resource=TierResourceKey.MAX_AGENTS)
    async def handle(self, action: DomainAction) -> CreateAgentResponse:
        # Si el código llega a este punto, la validación del tier fue exitosa.
        logger.info(f"Validación de tier superada para la creación de agente del tenant {action.tenant_id}.")
        # ... lógica para continuar con la creación del agente ...
        return CreateAgentResponse(...)
```

**Ventajas:**
*   **Limpio y Declarativo:** La intención es inmediatamente clara.
*   **Reutilizable:** La lógica compleja de validación está encapsulada en el decorador.
*   **Separación de Responsabilidades:** El handler se enfoca en su lógica de negocio, no en la fontanería de la validación.

### 3.2. Patrón 2: Uso Programático del Servicio (Alternativa)

Para escenarios más complejos donde la validación depende de múltiples factores dinámicos, se puede inyectar y usar el `TierValidationService` directamente.

```python
# En un handler de AOS

class ComplexActionHandler(BaseActionHandler):
    def __init__(self, validation_service: TierValidationService, ...):
        self.validation_service = validation_service
        # ...

    async def handle(self, action: DomainAction) -> ComplexActionResponse:
        # 1. Obtener el tier del tenant del contexto
        tenant_tier = self.get_tenant_tier_from_context(action)

        # 2. Realizar la validación programáticamente
        await self.validation_service.validate(
            tenant_id=action.tenant_id,
            tier=tenant_tier,
            resource=TierResourceKey.ALLOWED_LLM_MODELS,
            requested_value=action.data.get("model_name")
        )
        # La función validate() lanzará TierLimitExceededError si falla

        # ... lógica de negocio si la validación pasa ...
        return ComplexActionResponse(...)
```

## 4. Ejemplos de Puntos de Validación en AOS

| Acción del Usuario (Conceptual) | `action_type` (Ejemplo)        | `TierResourceKey` a Validar | Implementación Sugerida en AOS                                     |
| :------------------------------ | :----------------------------- | :-------------------------- | :----------------------------------------------------------------- |
| Crear un nuevo agente           | `agent.create`                 | `MAX_AGENTS`                | `@validate_tier(resource=TierResourceKey.MAX_AGENTS)`              |
| Usar un LLM específico          | `query.ask` / `agent.execute`  | `ALLOWED_LLM_MODELS`        | `@validate_tier(resource=TierResourceKey.ALLOWED_LLM_MODELS, value_path="data.model_name")` (el decorador extraería el valor del payload) |
| Ejecutar una query              | `query.ask`                    | `QUERIES_PER_HOUR`          | `@validate_tier(resource=TierResourceKey.QUERIES_PER_HOUR)`        |
| Usar prompts personalizados     | `agent.configure`              | `CAN_USE_CUSTOM_PROMPTS`    | `@validate_tier(resource=TierResourceKey.CAN_USE_CUSTOM_PROMPTS)`  |

## 5. Responsabilidades NO Cubiertas por AOS en este Flujo

*   **Actualización de Contadores de Uso:** AOS **NO** llama a `tier_usage_service.increment_usage`. La responsabilidad de reportar el consumo efectivo de un recurso recae en el servicio downstream que realiza la acción final. AOS solo valida contra el estado actual y los límites estáticos.

## 6. Consideraciones Adicionales

*   **Determinación del Tier del Tenant:** El mecanismo exacto para que AOS determine el `tenant_tier` a partir del `tenant_id` está fuera del alcance de este documento, pero es un prerrequisito crítico para que el decorador y el servicio de validación funcionen.

---

## 7. Estado de la Implementación

**La lógica de validación descrita ha sido implementada en el módulo `refactorizado/common/tiers` y está lista para ser integrada en los `ActionHandlers` de AOS.**

La implementación del decorador `@validate_tier` se encarga de:

1.  **Obtener el `TierValidationService`** a través de un mecanismo de inyección de dependencias (simulado).
2.  **Extraer el `tenant_id`** del objeto `DomainAction` pasado al handler.
3.  **Extraer argumentos adicionales** (como el `value_arg` para la longitud de un query) de los `kwargs` de la función.
4.  **Invocar `validation_service.validate()`** con todos los datos recopilados.
5.  **Propagar la excepción `TierLimitExceededError`** si la validación falla, lo que detiene la ejecución del handler.
