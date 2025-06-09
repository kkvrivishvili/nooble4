"""
Worker especializado para migración Redis -> PostgreSQL.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from conversation_service.services.persistence_manager import PersistenceManager
from conversation_service.services.memory_manager import MemoryManager
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class MigrationWorker(BaseWorker):
    """
    Worker mejorado para migración automática a PostgreSQL.
    
    A diferencia de otros workers basados en Domain Actions, este worker
    mantiene un ciclo de ejecución propio mientras implementa la interfaz
    de inicialización asíncrona del BaseWorker.
    """
    
    def __init__(self, redis_client, queue_manager=None, db_client=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            queue_manager: Gestor de colas por dominio (opcional)
            db_client: Cliente de base de datos PostgreSQL (opcional)
        """
        queue_manager = queue_manager or DomainQueueManager(redis_client)
        super().__init__(redis_client, queue_manager)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "conversation"
        
        # Almacenar db_client para usar en la inicialización
        self.db_client = db_client
        
        # Variables que se inicializarán de forma asíncrona
        self.persistence = None
        self.memory_manager = None
        self.migration_task = None
        self.initialized = False
        self.running = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        # Inicializar componentes
        await self._initialize_components()
        
        self.initialized = True
        logger.info("ImprovedMigrationWorker inicializado")
    
    async def _initialize_components(self):
        """Inicializa los componentes necesarios para la migración."""
        # Inicializar servicios
        self.persistence = PersistenceManager(self.redis_client, self.db_client)
        self.memory_manager = MemoryManager()
    
    async def start(self):
        """Inicia el worker de migración en un task separado."""
        if not self.initialized:
            await self.initialize()
            
        if self.running:
            logger.warning("Worker de migración ya está en ejecución")
            return
            
        self.running = True
        self.migration_task = asyncio.create_task(self._migration_loop())
        logger.info("ImprovedMigrationWorker iniciado")
    
    async def stop(self):
        """Detiene el worker."""
        if not self.running:
            return
            
        self.running = False
        
        if self.migration_task:
            try:
                # Esperar a que termine la tarea actual
                await asyncio.wait_for(self.migration_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout al esperar finalización de migración, forzando cierre")
            except Exception as e:
                logger.error(f"Error al detener worker de migración: {str(e)}")
            
            self.migration_task = None
            
        logger.info("ImprovedMigrationWorker detenido")
    
    async def _migration_loop(self):
        """Bucle principal de migración."""
        while self.running:
            try:
                await self._process_migrations()
                await asyncio.sleep(settings.persistence_migration_interval)
            except Exception as e:
                logger.error(f"Error en ciclo de migración: {str(e)}")
                await asyncio.sleep(10)
    
    async def _process_migrations(self):
        """Procesa conversaciones que necesitan migración."""
        if not self.initialized:
            await self.initialize()
            
        candidates = await self.persistence.get_conversations_needing_migration()
        
        if not candidates:
            return
        
        logger.info(f"Procesando {len(candidates)} conversaciones para migración")
        
        for conversation_id in candidates:
            try:
                # Migrar a PostgreSQL
                success = await self.persistence.migrate_conversation_to_postgresql(conversation_id)
                
                if success:
                    # Limpiar memoria LangChain
                    self.memory_manager.cleanup_conversation_memory(conversation_id)
                    logger.info(f"Conversación migrada exitosamente: {conversation_id}")
                else:
                    logger.warning(f"Falló migración de conversación: {conversation_id}")
                    
            except Exception as e:
                logger.error(f"Error migrando conversación {conversation_id}: {str(e)}")
    
    async def get_migration_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas sobre el estado de migración.
        
        Returns:
            Diccionario con estadísticas del proceso de migración
        """
        if not self.initialized:
            await self.initialize()
            
        pending = await self.persistence.get_pending_migration_count()
        completed = await self.persistence.get_completed_migration_count()
        failed = await self.persistence.get_failed_migration_count()
        
        return {
            "status": "running" if self.running else "stopped",
            "migrations": {
                "pending": pending,
                "completed": completed,
                "failed": failed,
                "total": pending + completed + failed
            },
            "last_run": datetime.now().isoformat(),
            "interval_seconds": settings.persistence_migration_interval
        }
