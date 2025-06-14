# common/tiers/exceptions.py
from typing import Optional

from refactorizado.common.exceptions import BaseError

class TierLimitExceededError(BaseError):
    """Excepción lanzada cuando un tenant excede un límite definido por su tier."""
    def __init__(self, message: str, resource_key: Optional[str] = None, tier_name: Optional[str] = None, status_code: int = 429):
        super().__init__(
            message=message, 
            error_code="TIER_LIMIT_EXCEEDED", 
            status_code=status_code
        )
        self.resource_key = resource_key
        self.tier_name = tier_name
