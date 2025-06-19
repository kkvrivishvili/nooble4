"""
Punto de entrada principal para Agent Orchestrator Service.

MODIFICADO: Integración completa con sistema de colas por tier.
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
from agent_orchestrator_service.workers.orchestrator_worker import OrchestratorWorker
from agent_orchestrator_service.routes import chat_router, websocket_router, health_router
from agent_orchestrator_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Lista global de workers y gestor de Redis
worker_tasks = []
redis_manager: RedisManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global worker_tasks, redis_manager
    
    logger.info("Iniciando Agent Orchestrator Service")
    
    try:
        # Inicializar RedisManager
        redis_manager = RedisManager(settings.redis_url)
        await redis_manager.initialize()
        logger.info("Redis Manager inicializado y conexión establecida")
        
        app.state.redis_manager = redis_manager

        # Crear e iniciar workers
        worker_count = settings.workers_per_service
        for i in range(worker_count):
            worker = OrchestratorWorker(
                app_settings=settings,
                async_redis_conn=redis_manager.get_connection(),
                consumer_id_suffix=f"{i+1}"
            )
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        
        logger.info(f"{worker_count} OrchestratorWorkers iniciados")
        
        yield
        
    finally:
        logger.info("Deteniendo Agent Orchestrator Service")
        
        # Detener workers
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        logger.info("Todos los workers han sido detenidos")
        
        # Cerrar conexiones Redis
        if redis_manager:
            await redis_manager.close()
            logger.info("Conexiones Redis cerradas")

# Crear aplicación
app = FastAPI(
    title="Agent Orchestrator Service",
    description="Servicio de orquestación de agentes con WebSockets y colas por tier",
    version=settings.service_version,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar manejo de errores
setup_error_handling(app)

# Registrar routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(websocket_router)

# Health checks específicos del orchestrator


# Configurar logging
init_logging(settings.log_level, service_name="agent-orchestrator-service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8001,  # CORREGIDO: Puerto no conflictivo
        reload=True,
        log_level="info"
    )