"""
Context management común para todos los servicios.
"""

from typing import Optional, Dict, Any
from fastapi import Depends
from pydantic import BaseModel

class Context(BaseModel):
    """Contexto de request común."""
    request_id: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

def with_context(tenant: bool = False):
    """Decorator para agregar contexto a endpoints."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Por ahora retorna contexto simple
            # En el futuro se puede expandir con JWT, etc.
            return await func(*args, **kwargs)
        return wrapper
    return decorator
