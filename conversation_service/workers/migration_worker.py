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
    Worker mejorado para migración automática a PostgreSQL con patrón BaseWorker 4.0.
    
    Características:
    - Implementa completamente el patrón BaseWorker 4.0 con _handle_action
    - Mantiene un ciclo de migración propio y autónomo
    - Soporta acciones explícitas de migración vía Domain Actions
    - Combina procesamiento reactivo (Domain Actions) con proactivo (ciclo de migración)
    
    Este worker es un híbrido que cumple con el patrón estándar mientras 
    mantiene su funcionalidad especializada de migración automática programada.
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
            
        logger.info("MigrationWorker detenido")
    
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
