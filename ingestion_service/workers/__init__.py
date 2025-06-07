"""
Workers asíncronos para procesamiento de tareas de ingestión.

Expone los workers y el pool de workers para procesar documentos.
"""

from ingestion_service.workers.ingestion_worker import IngestionWorker
from ingestion_service.workers.worker_pool import WorkerPool

__all__ = ['IngestionWorker', 'WorkerPool']
