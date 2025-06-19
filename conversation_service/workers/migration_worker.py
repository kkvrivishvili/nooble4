"""
Worker especializado para migración Redis -> PostgreSQL.

Implementación con patrón BaseWorker 4.0 que mantiene un ciclo de ejecución
propio para tareas de migración automática.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con handle_action
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

import time
import redis.asyncio as redis_async

from common.config import CommonAppSettings
from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from conversation_service.services.persistence_manager import PersistenceManager
from conversation_service.services.memory_manager import MemoryManager
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class MigrationWorker(BaseWorker):
    """
    Worker mejorado para migración automática a PostgreSQL con patrón BaseWorker 4.0.
    
    Características:
    - Implementa completamente el patrón BaseWorker 4.0 con _handle_action
    - Mantiene un ciclo de migración propio y autónomo
    - Soporta acciones explícitas de migración vía Domain Actions
    - Combina procesamiento reactivo (Domain Actions) con proactivo (ciclo de migración)
    
    Este worker es un híbrido que cumple con el patrón estándar mientras 
    mantiene su funcionalidad especializada de migración automática programada.
    """
    
    def __init__(
        self,
        app_settings: CommonAppSettings,
        async_redis_conn: redis_async.Redis,
        consumer_id_suffix: Optional[str] = None,
        db_client: Optional[Any] = None
    ):
        """
        Inicializa el MigrationWorker.
        
        Args:
            app_settings: Configuración de la aplicación.
            async_redis_conn: Conexión Redis asíncrona.
            consumer_id_suffix: Sufijo para el ID del consumidor.
            db_client: Cliente de base de datos opcional.
        """
        super().__init__(app_settings, async_redis_conn, consumer_id_suffix)
        
        self.db_client = db_client
        self.persistence: Optional[PersistenceManager] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.logger = logging.getLogger(f"{__name__}.{self.consumer_name}")

    async def initialize(self):
        """Inicializa el worker y sus dependencias de forma asíncrona."""
        if self.initialized:
            return
        
        await super().initialize()
        
        self.persistence = PersistenceManager(self.async_redis_conn, self.db_client)
        self.memory_manager = MemoryManager()
        
        self.initialized = True
        self.logger.info(f"MigrationWorker ({self.consumer_name}) inicializado correctamente")

    async def run(self):
        """
        Ejecuta el worker, combinando el ciclo de migración proactivo con
        el procesamiento de acciones reactivo del BaseWorker.
        """
        await self.initialize()
        
        self.running = True
        self.logger.info(f"Iniciando MigrationWorker ({self.consumer_name}) con procesador dual")
        
        migration_task = asyncio.create_task(self._migration_loop())
        
        try:
            # Llama al run() de BaseWorker para el procesamiento de acciones
            await super().run()
        finally:
            self.logger.info(f"Deteniendo ciclo de migración para worker {self.consumer_name}")
            if not migration_task.done():
                migration_task.cancel()
                try:
                    await migration_task
                except asyncio.CancelledError:
                    pass # Esperado al cancelar
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Maneja Domain Actions para migración explícita y consulta de estado.
        
        Este método cumple con la interfaz estándar del BaseWorker 4.0 permitiendo
        que el worker procese acciones explícitas adicionalmente a su ciclo de migración
        automática.
        
        Args:
            action: Acción de dominio a procesar
            context: Contexto de ejecución opcional
            
        Returns:
            Resultado del procesamiento de la acción
            
        Raises:
            ValueError: Si la acción no está soportada
        """
        start_time = time.time()
        action_type = action.action_type
        
        try:
            if action_type == "migration.start":
                # Solicitud manual para iniciar migración
                if not self.running:
                    await self.start()
                return {
                    "success": True,
                    "message": "Migración iniciada exitosamente",
                    "execution_time": time.time() - start_time
                }
                
            elif action_type == "migration.stop":
                # Solicitud manual para detener migración
                if self.running:
                    await self.stop()
                return {
                    "success": True,
                    "message": "Migración detenida exitosamente",
                    "execution_time": time.time() - start_time
                }
                
            elif action_type == "migration.migrate_conversation":
                # Solicitud para migrar una conversación específica
                conversation_id = action.data.get("conversation_id")
                if not conversation_id:
                    raise ValueError("Se requiere conversation_id")
                    
                success = await self.persistence.migrate_conversation_to_postgresql(conversation_id)
                
                if success and action.data.get("cleanup_memory", True):
                    self.memory_manager.cleanup_conversation_memory(conversation_id)
                    
                return {
                    "success": success,
                    "conversation_id": conversation_id,
                    "message": "Migración completada" if success else "Error en migración",
                    "execution_time": time.time() - start_time
                }
                
            elif action_type == "migration.get_stats":
                # Obtener estadísticas de migración
                stats = await self.get_migration_stats()
                return {
                    "success": True,
                    "stats": stats,
                    "execution_time": time.time() - start_time
                }
            else:
                error_msg = f"No hay handler implementado para la acción: {action_type}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"Error procesando acción {action_type}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
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
