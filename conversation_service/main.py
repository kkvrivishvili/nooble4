"""
Punto de entrada principal.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.errors import setup_error_handling
from common.utils.logging import init_logging
from common.helpers.health import register_health_routes
from common.clients.redis_client import RedisManager
from conversation_service.workers.conversation_worker import ConversationWorker
from conversation_service.workers.migration_worker import MigrationWorker
from conversation_service.routes.crm_routes import router as crm_router
from common.config import ConversationSettings

settings = ConversationSettings()
logger = logging.getLogger(__name__)

# Lista global de workers y gestor de Redis
worker_tasks = []
redis_manager: RedisManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_tasks, redis_manager
    
    logger.info("Iniciando Conversation Service")
    
    try:
        # Inicializar RedisManager
        redis_manager = RedisManager(settings.redis_url)
        await redis_manager.initialize()
        logger.info("Redis Manager inicializado y conexión establecida")
        
        app.state.redis_manager = redis_manager

        # Crear e iniciar ConversationWorkers
        conversation_worker_count = settings.get("conversation_workers", 1)
        for i in range(conversation_worker_count):
            worker = ConversationWorker(
                app_settings=settings,
                async_redis_conn=redis_manager.get_connection(),
                consumer_id_suffix=f"conv-{i+1}"
            )
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        logger.info(f"{conversation_worker_count} ConversationWorkers iniciados")

        # Crear e iniciar MigrationWorkers
        migration_worker_count = settings.get("migration_workers", 1)
        for i in range(migration_worker_count):
            worker = MigrationWorker(
                app_settings=settings,
                async_redis_conn=redis_manager.get_connection(),
                consumer_id_suffix=f"mig-{i+1}"
            )
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        logger.info(f"{migration_worker_count} MigrationWorkers iniciados")
        
        yield
        
    finally:
        logger.info("Deteniendo Conversation Service")
        
        # Detener todos los workers
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        logger.info("Todos los workers han sido detenidos")
        
        # Cerrar conexiones Redis
        if redis_manager:
            await redis_manager.close()
            logger.info("Conexiones Redis cerradas")

app = FastAPI(
    title="Conversation Service", 
    description="Servicio de gestión de conversaciones con LangChain",
    version=settings.service_version,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_error_handling(app)
register_health_routes(app)

app.include_router(crm_router)

init_logging(settings.log_level, service_name="conversation-service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)

