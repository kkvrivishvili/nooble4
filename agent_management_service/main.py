"""
Agent Management Service - Punto de entrada principal.
INTEGRADO: Con sistema de colas por tier y Domain Actions existentes.
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
from agent_management_service.workers.management_worker import ManagementWorker
from agent_management_service.config.settings import get_settings
from agent_management_service.routes import agents, templates, health

settings = get_settings()
logger = logging.getLogger(__name__)

# Worker global
management_worker = None
queue_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global management_worker, queue_manager
    
    logger.info("Iniciando Agent Management Service")
    
    try:
        # Inicializar Redis y Queue Manager
        redis_client = await get_redis_client()
        queue_manager = DomainQueueManager(redis_client)
        
        # Verificar conexión Redis
        await redis_client.ping()
        logger.info("Conexión a Redis establecida")
        
        # Inicializar worker
        management_worker = ManagementWorker(redis_client)
        
        # Iniciar worker en background
        worker_task = asyncio.create_task(management_worker.start())
        logger.info("ManagementWorker iniciado")
        
        # Hacer disponibles para la app
        app.state.queue_manager = queue_manager
        app.state.redis_client = redis_client
        app.state.management_worker = management_worker
        
        yield
        
    finally:
        logger.info("Deteniendo Agent Management Service")
        
        if management_worker:
            await management_worker.stop()
        
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
    title="Agent Management Service",
    description="Servicio de gestión de agentes con sistema de templates y validación por tiers",
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

# Registrar rutas
app.include_router(agents.router)
app.include_router(templates.router)
app.include_router(health.router)

# Registrar health routes base
register_health_routes(app)

# Configurar logging
init_logging(settings.log_level, service_name="agent-management-service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8003,
        reload=True,
        log_level="info"
    )

