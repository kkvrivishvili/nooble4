"""
Excepciones personalizadas para el Query Service.
"""

class QueryServiceError(Exception):
    """Clase base para errores del servicio."""
    pass

class CacheError(QueryServiceError):
    """Errores relacionados con la caché."""
    pass

class PromptGenerationError(QueryServiceError):
    """Errores durante la generación del prompt."""
    pass
