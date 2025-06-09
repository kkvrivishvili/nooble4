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
from common.redis_pool import get_redis_client
from common.services.domain_queue_manager import DomainQueueManager
from conversation_service.workers.conversation_worker import ConversationWorker
from conversation_service.workers.migration_worker import MigrationWorker
from conversation_service.routes.crm_routes import router as crm_router
from conversation_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

conversation_worker = None
migration_worker = None
queue_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global conversation_worker, migration_worker, queue_manager
    
    logger.info("Iniciando Conversation Service")
    
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        logger.info("Redis conectado")
        
        # Inicializar DomainQueueManager
        queue_manager = DomainQueueManager(redis_client)
        logger.info("DomainQueueManager inicializado")
        
        # Inicializar workers con queue_manager
        conversation_worker = ConversationWorker(redis_client, queue_manager)
        migration_worker = MigrationWorker(redis_client, queue_manager)
        
        # Iniciar workers
        worker_tasks = [
            asyncio.create_task(conversation_worker.start()),
            asyncio.create_task(migration_worker.start())
        ]
        
        logger.info("Workers iniciados con DomainQueueManager")
        
        app.state.redis_client = redis_client
        app.state.queue_manager = queue_manager
        yield
        
    finally:
        logger.info("Deteniendo Conversation Service")
        
        if conversation_worker:
            await conversation_worker.stop()
        if migration_worker:
            await migration_worker.stop()
        
        for task in worker_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

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

