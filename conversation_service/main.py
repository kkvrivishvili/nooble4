"""
Punto de entrada principal para Conversation Service.
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
from conversation_service.config.settings import get_settings
from conversation_service.routes import conversations, analytics, health

settings = get_settings()
logger = logging.getLogger(__name__)

# Worker global
conversation_worker = None
queue_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global conversation_worker, queue_manager
    
    logger.info("Iniciando Conversation Service")
    
    try:
        # Inicializar Redis y Queue Manager
        redis_client = await get_redis_client()
        queue_manager = DomainQueueManager(redis_client)
        
        # Verificar conexión Redis
        await redis_client.ping()
        logger.info("Conexión a Redis establecida")
        
        # Inicializar worker
        conversation_worker = ConversationWorker(redis_client)
        
        # Iniciar worker en background
        worker_task = asyncio.create_task(conversation_worker.start())
        logger.info("ConversationWorker iniciado")
        
        # Hacer disponibles para la app
        app.state.queue_manager = queue_manager
        app.state.redis_client = redis_client
        app.state.conversation_worker = conversation_worker
        
        yield
        
    finally:
        logger.info("Deteniendo Conversation Service")
        
        if conversation_worker:
            await conversation_worker.stop()
        
        if 'worker_task' in locals():
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        
        if queue_manager and hasattr(queue_manager, 'redis'):
            await queue_manager.redis.close()

# Crear aplicación
app = FastAPI(
    title="Conversation Service",
    description="Servicio de gestión de conversaciones y memoria del sistema",
    version=settings.service_version,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar manejo de errores
setup_error_handling(app)

# Registrar routers
app.include_router(conversations.router)
app.include_router(analytics.router)
app.include_router(health.router)

# Registrar health routes base
register_health_routes(app)

# Configurar logging
init_logging(settings.log_level, service_name="conversation-service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8004,
        reload=True,
        log_level="info"
    )

