# common/tiers/decorators/validate_tier.py
from functools import wraps
from typing import Any, Callable
from ..models.tier_config import TierResourceKey
from ..services.validation_service import TierValidationService

# --- Simulación de Inyección de Dependencias ---
# En una aplicación real, esto sería gestionado por un contenedor de dependencias
# como `fastapi.Depends` o un framework de inyección personalizado.
_validation_service_instance: TierValidationService = None

def set_tier_validation_service(service: TierValidationService):
    """Función para inyectar la dependencia (simulación)."""
    global _validation_service_instance
    _validation_service_instance = service

def get_tier_validation_service() -> TierValidationService:
    """Función para obtener la dependencia (simulación)."""
    if not _validation_service_instance:
        raise RuntimeError("TierValidationService no ha sido inicializado. Llama a set_tier_validation_service() al inicio de la aplicación.")
    return _validation_service_instance

# --- Implementación del Decorador ---

def validate_tier(resource_key: TierResourceKey, value_arg: str = None):
    """
    Decorador para aplicar validaciones de tier de forma declarativa.

    Args:
        resource_key: La clave estandarizada del recurso a validar.
        value_arg: El nombre del argumento en la función decorada que contiene
                   el valor a validar (e.g., 'length' o 'model_name').
    """
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            print(f"(Decorator) Interceptada llamada a '{func.__name__}'. Validando recurso '{resource_key.value}'.")
            
            # 1. Obtener el servicio de validación (vía DI simulada)
            validation_service = get_tier_validation_service()

            # 2. Extraer `tenant_id` del contexto.
            # Se asume que la función decorada recibe un objeto `action` con el `tenant_id`.
            action = kwargs.get("action")
            if not action or not hasattr(action, "tenant_id"):
                raise ValueError("La función decorada debe recibir un argumento 'action' con el atributo 'tenant_id'.")
            tenant_id = action.tenant_id

            # 3. Preparar argumentos para la validación
            validation_kwargs = {}
            if value_arg:
                if value_arg in kwargs:
                    validation_kwargs["value"] = kwargs[value_arg]
                else:
                    # Podríamos buscar en los `args` si es necesario, pero lo mantenemos simple.
                    raise ValueError(f"El argumento especificado '{value_arg}' no se encontró en los kwargs de la función.")

            # 4. Ejecutar la validación
            await validation_service.validate(
                tenant_id=tenant_id,
                resource_key=resource_key,
                **validation_kwargs
            )

            # 5. Si la validación es exitosa, ejecutar la función original.
            print(f"(Decorator) Validación para '{resource_key.value}' superada. Ejecutando '{func.__name__}'.")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

