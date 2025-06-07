"""
Administrador del pool de workers para procesamiento asíncrono.

Este módulo implementa un sistema para gestionar múltiples workers
que procesan tareas en paralelo, permitiendo escalabilidad horizontal.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import uuid

from common.context import create_context, Context, with_context
from ingestion_service.config.settings import get_settings
from ingestion_service.workers.ingestion_worker import IngestionWorker

settings = get_settings()
logger = logging.getLogger(__name__)


class WorkerPool:
    """Administrador de un pool de workers para procesamiento asíncrono."""
    
    def __init__(self, worker_count: int = None):
        """Inicializa el pool de workers.
        
        Args:
            worker_count: Número de workers a crear (por defecto, usa WORKER_COUNT)
        """
        self.worker_count = worker_count or settings.WORKER_COUNT
        self.workers: List[IngestionWorker] = []
        self.running = False
        self.pool_id = f"pool-{uuid.uuid4()}"
        self.context = create_context(component="worker_pool", pool_id=self.pool_id)
        logger.info(f"Inicializando pool de workers con {self.worker_count} workers")
    
    @with_context
    async def start(self, ctx: Optional[Context] = None):
        """Inicia todos los workers del pool.
        
        Args:
            ctx: Contexto de la operación
        """
        if self.running:
            logger.warning("El pool de workers ya está en ejecución")
            return
        
        logger.info(f"Iniciando pool de workers con {self.worker_count} instancias")
        self.running = True
        
        # Crear workers
        self.workers = [
            IngestionWorker(worker_id=f"{self.pool_id}-{i}")
            for i in range(self.worker_count)
        ]
        
        # Iniciar todos los workers en paralelo
        worker_tasks = [worker.start() for worker in self.workers]
        asyncio.gather(*worker_tasks)
        
        logger.info(f"Pool de workers iniciado con {len(self.workers)} instancias")
    
    @with_context
    async def stop(self, ctx: Optional[Context] = None):
        """Detiene todos los workers del pool de forma ordenada.
        
        Args:
            ctx: Contexto de la operación
        """
        if not self.running:
            logger.warning("El pool de workers ya está detenido")
            return
        
        logger.info("Deteniendo pool de workers...")
        self.running = False
        
        # Detener todos los workers
        for worker in self.workers:
            await worker.stop()
        
        self.workers = []
        logger.info("Pool de workers detenido")
    
    @with_context
    async def status(self, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Obtiene el estado actual del pool de workers.
        
        Args:
            ctx: Contexto de la operación
            
        Returns:
            Dict[str, Any]: Estado del pool
        """
        return {
            "pool_id": self.pool_id,
            "running": self.running,
            "worker_count": len(self.workers),
            "target_worker_count": self.worker_count
        }


# Instancia global del pool de workers
worker_pool = WorkerPool()
