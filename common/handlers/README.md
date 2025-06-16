# Common Handlers (`common.handlers`)

Este módulo define la capa de handlers base para los microservicios dentro del sistema Nooble4.

Con la refactorización hacia `BaseService` como orquestador principal de la lógica de negocio, el rol de los handlers comunes se ha simplificado significativamente.

## `BaseHandler`

`BaseHandler` (`base_handler.py`) es una clase base abstracta y mínima diseñada para ser el ancestro de clases de utilidad de dominio. Estas clases de utilidad (handlers) encapsulan lógica de negocio específica o interacciones con otros sistemas (por ejemplo, una API externa, una consulta compleja a base de datos) y son utilizadas por la `Capa de Servicio` (`common.services.BaseService` y sus implementaciones) para mantener su código limpio, organizado y promover la reutilización.

### Características Clave:

1.  **Constructor Simple:**
    *   Se inicializa con:
        *   `app_settings: CommonAppSettings`: La configuración común de la aplicación, que incluye `service_name` para el logger.
        *   `direct_redis_conn: Optional[AIORedis] = None`: Una conexión Redis asíncrona directa opcional, si el handler necesita realizar operaciones Redis muy específicas. Generalmente, es preferible que el `Service` maneje las interacciones Redis principales.
    *   Automáticamente configura un `self._logger` contextualizado usando el `service_name` de `app_settings` y el nombre de la clase del handler.

2.  **Sin Lógica de Ejecución Predefinida:**
    *   `BaseHandler` ya no impone un método `execute()` abstracto ni un patrón de inicialización asíncrona complejo.
    *   Si un handler específico necesita una inicialización asíncrona (por ejemplo, para cargar recursos), puede implementar un método `async def setup(self)` que el `Service` llamará explícitamente después de instanciarlo.
    *   Los métodos de un handler serán específicos de su dominio y serán llamados directamente por el `Service` que lo utiliza.

### Ejemplo de Implementación (en un handler específico del servicio):

```python
# my_feature_service/handlers/calculation_handler.py
import logging
from common.handlers import BaseHandler
from common.config import CommonAppSettings

class CalculationHandler(BaseHandler):
    # def __init__(self, app_settings: CommonAppSettings, specific_config: Any):
    #     super().__init__(app_settings)
    #     self.specific_config = specific_config
    #     self._logger.info("CalculationHandler inicializado con configuración específica.")

    async def perform_complex_calculation(self, data: dict) -> float:
        self._logger.debug(f"Realizando cálculo complejo para: {data}")
        # ... lógica de cálculo ...
        result = sum(data.values()) # Ejemplo simple
        return float(result)

# Uso en el Service:
# class FeatureService(BaseService):
#     def __init__(self, app_settings, ...):
#         super().__init__(app_settings, ...)
#         self.calc_handler = CalculationHandler(app_settings)
#
#     async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
#         if action.action_type == "feature.calculate":
#             # ...
#             calc_result = await self.calc_handler.perform_complex_calculation(action.data)
#             return {"calculation_result": calc_result}
#         # ...
```

## Filosofía

Los handlers deben ser vistos como componentes de apoyo al `Service`. El `Service` decide si los usa y cómo. Esta estructura promueve la cohesión dentro del `Service` y el bajo acoplamiento con los `Handlers`.

**Interacción con la Validación de Datos:**

Generalmente, la responsabilidad de deserializar y validar el `action.data` (proveniente de una `DomainAction`) en un modelo Pydantic específico recae en la capa de `Service`. Una vez que el `Service` ha validado exitosamente el payload, puede pasar la instancia del modelo Pydantic resultante a los métodos del `Handler`.

Esto significa que los `Handlers` suelen operar con datos ya estructurados y validados, lo que simplifica su lógica interna y les permite centrarse en la tarea de negocio específica para la que fueron diseñados. Por ejemplo:

```python
# En el Service:
# async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
#     if action.action_type == "feature.calculate":
#         try:
#             payload_model = CalculationPayload(**action.data) # Validación en el Service
#         except ValidationError as e:
#             # ... manejar error de validación ...
#             return # o retornar error
#
#         # Pasar el modelo validado al handler
#         calc_result = await self.calc_handler.perform_complex_calculation(payload_model)
#         return {"calculation_result": calc_result}

# En el Handler:
# class CalculationHandler(BaseHandler):
#     async def perform_complex_calculation(self, payload: CalculationPayload) -> float:
#         # Aquí, 'payload' ya es una instancia validada de CalculationPayload
#         self._logger.debug(f"Realizando cálculo complejo para: {payload}")
#         result = sum(payload.values_to_sum) # Ejemplo
#         return float(result)
```

Esta separación de responsabilidades (validación en el `Service`, lógica de negocio en el `Handler`) contribuye a un diseño más limpio y mantenible.
