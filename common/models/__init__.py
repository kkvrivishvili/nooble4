"""Módulo de Modelos Comunes Pydantic.

Este módulo exporta los modelos de datos Pydantic centrales utilizados en la plataforma Nooble4,
facilitando la estandarización de la estructura de datos para acciones, respuestas y contextos de ejecución.
"""

from .actions import DomainAction, DomainActionResponse, ErrorDetail

__all__ = [
    "DomainAction",
    "DomainActionResponse",
    "ErrorDetail",
]
