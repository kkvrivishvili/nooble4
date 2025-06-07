"""
Modelos comunes para todos los servicios.
"""

from .actions import DomainAction
from .execution_context import ExecutionContext, ExecutionContextResolver

__all__ = [
    'DomainAction',
    'ExecutionContext', 
    'ExecutionContextResolver'
]