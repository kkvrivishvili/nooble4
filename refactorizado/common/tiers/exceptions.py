# common/tiers/exceptions.py
from typing import Optional

# Suponiendo que existe una clase base de error en common.errors
# from common.errors import BaseNoobleError 
# Por ahora, usaremos una excepción base de Python
class BaseNoobleError(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code

class TierLimitExceededError(BaseNoobleError):
    """Excepción lanzada cuando un tenant excede un límite definido por su tier."""
    def __init__(self, message: str, resource_key: Optional[str] = None, tier_name: Optional[str] = None, status_code: int = 429):
        super().__init__(
            message=message, 
            error_code="TIER_LIMIT_EXCEEDED", 
            status_code=status_code
        )
        self.resource_key = resource_key
        self.tier_name = tier_name
