"""
Módulo de errores personalizados para Query Service.
"""

from .exceptions import (
    CacheError,
    PromptGenerationError
)

__all__ = [
    'CacheError',
    'PromptGenerationError'
]
