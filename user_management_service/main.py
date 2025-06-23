"""
Agent Management Service - Punto de entrada principal.
INTEGRADO: Con sistema de colas por tier y Domain Actions existentes.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.clients import RedisManager
from common.errors import setup_error_handling
from common.utils.logging import init_logging
from agent_management_service.workers.management_worker import ManagementWorker
from agent_management_service.config.settings import get_settings
from agent_management_service.routes import agents, templates, health

# Configuración y logger
settings = get_settings()
logger = logging.getLogger(__name__)

# Variables globales para el ciclo de vida
redis_manager: RedisManager = None
workers: List[ManagementWorker] = []
worker_tasks: List[asyncio.Task] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global redis_manager, workers, worker_tasks
    
    init_logging(settings.log_level, settings.service_name)
    logger.info(f"Iniciando {settings.service_name} v{settings.service_version}")
    
    try:
        # Inicializar Redis Manager
        redis_manager = RedisManager(settings=settings)
        redis_conn = await redis_manager.get_client()
        logger.info("Redis Manager inicializado")
        
        # Crear workers
        for i in range(settings.worker_count):
            worker = ManagementWorker(
                app_settings=settings,
                async_redis_conn=redis_conn,
                consumer_id_suffix=f"worker-{i}"
            )
            workers.append(worker)
            
            await worker.initialize()
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
            
        logger.info(f"{len(workers)} ManagementWorkers iniciados")
        
        # Hacer disponibles para la app
        app.state.redis_manager = redis_manager
        
        yield
        
    finally:
        logger.info(f"Deteniendo {settings.service_name}...")
        
        for worker in workers:
            await worker.stop()
        
        for task in worker_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if redis_manager:
            await redis_manager.close()
        
        logger.info(f"{settings.service_name} detenido completamente")

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

