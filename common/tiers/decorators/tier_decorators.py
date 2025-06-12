# common/tiers/decorators/tier_decorators.py
import inspect
from functools import wraps
from typing import Optional

from refactorizado.common.models.domain_action import DomainAction
from ..services.validation_service import TierValidationService
from ..services.accounting_service import TierAccountingService

def _get_context_from_args(func_name: str, args, kwargs) -> (object, DomainAction, dict):
    """Función de utilidad para extraer el handler, la acción y los argumentos de la llamada."""
    if not args:
        raise TypeError(f"El decorador de tier en '{func_name}' espera un método de instancia (con 'self').")
    
    handler_instance = args[0]
    
    action = None
    for arg in args:
        if isinstance(arg, DomainAction):
            action = arg
            break
    if not action and 'action' in kwargs and isinstance(kwargs['action'], DomainAction):
        action = kwargs['action']

    if not action:
        raise ValueError(f"No se pudo encontrar 'DomainAction' en los argumentos de '{func_name}'.")

    if not hasattr(handler_instance, 'redis_pool'):
        raise AttributeError(f"La instancia de '{type(handler_instance).__name__}' debe tener un atributo 'redis_pool' para usar los decoradores de tier.")
        
    return handler_instance, action

def validate_tier_access(resource_key: str, amount_arg_name: Optional[str] = None):
    """
    Decorador que valida si un tenant tiene acceso a un recurso antes de ejecutar la función.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler, action = _get_context_from_args(func.__name__, args, kwargs)
            
            request_value = kwargs.get(amount_arg_name, 1) if amount_arg_name else 1

            validation_service = TierValidationService(redis_pool=handler.redis_pool)
            await validation_service.validate(
                tenant_id=action.tenant_id,
                resource_key=resource_key,
                request_value=request_value
            )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def account_for_usage(resource_key: str, amount_arg_name: Optional[str] = None):
    """
    Decorador que contabiliza el uso de un recurso después de que la función se ejecute con éxito.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Ejecutar la función original primero
            result = await func(*args, **kwargs)
            
            # Si la función tuvo éxito, contabilizar el uso
            handler, action = _get_context_from_args(func.__name__, args, kwargs)
            
            request_value = kwargs.get(amount_arg_name, 1) if amount_arg_name else 1

            accounting_service = TierAccountingService(redis_pool=handler.redis_pool)
            await accounting_service.increment_usage(
                tenant_id=action.tenant_id,
                resource_key=resource_key,
                amount=request_value
            )
            
            return result
        return wrapper
    return decorator
