"""
Modelos para Query Service.

Expone los modelos de datos utilizados por el servicio.
"""

from query_service.models.actions import (
    QueryGenerateAction,
    SearchDocsAction,
    QueryCallbackAction,
    DocumentResult,
    QueryResult
)

__all__ = [
    'QueryGenerateAction',
    'SearchDocsAction',
    'QueryCallbackAction',
    'DocumentResult',
    'QueryResult'
]
