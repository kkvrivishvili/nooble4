"""
Workers para Query Service.

Expone los workers disponibles para procesamiento asíncrono.
"""

from query_service.workers.query_worker import QueryWorker

__all__ = ['QueryWorker']
