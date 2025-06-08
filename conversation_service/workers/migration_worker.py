"""
Worker especializado para migración Redis -> PostgreSQL.
"""

import asyncio
import logging
from datetime import datetime

from conversation_service.services.persistence_manager import PersistenceManager
from conversation_service.services.memory_manager import MemoryManager
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class MigrationWorker:
    """Worker para migración automática a PostgreSQL."""
    
    def __init__(self, redis_client, db_client=None):
        self.persistence = PersistenceManager(redis_client, db_client)
        self.memory_manager = MemoryManager()
        self.running = False
    
    async def start(self):
        """Inicia el worker de migración."""
        self.running = True
        logger.info("MigrationWorker iniciado")
        
        while self.running:
            try:
                await self._process_migrations()
                await asyncio.sleep(settings.persistence_migration_interval)
            except Exception as e:
                logger.error(f"Error en migration worker: {str(e)}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Detiene el worker."""
        self.running = False
        logger.info("MigrationWorker detenido")
    
    async def _process_migrations(self):
        """Procesa conversaciones que necesitan migración."""
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
