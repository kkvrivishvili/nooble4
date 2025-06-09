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
from common.redis_pool import get_redis_client
from common.services.domain_queue_manager import DomainQueueManager
from agent_orchestrator_service.workers.orchestrator_worker import OrchestratorWorker
from agent_orchestrator_service.routes import chat_router, websocket_router, health_router
from agent_orchestrator_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Worker global
orchestrator_worker = None
queue_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global orchestrator_worker, queue_manager
    
    logger.info("Iniciando Agent Orchestrator Service")
    
    try:
        # Inicializar Redis y Queue Manager
        redis_client = await get_redis_client()
        queue_manager = DomainQueueManager(redis_client)
        
        # Verificar conexión Redis
        await redis_client.ping()
        logger.info("Conexión a Redis establecida")
        
        # Inicializar worker pasando explícitamente el queue_manager
        orchestrator_worker = OrchestratorWorker(redis_client, queue_manager)
        
        # Iniciar worker en background
        worker_task = asyncio.create_task(orchestrator_worker.start())
        logger.info("OrchestratorWorker iniciado")
        
        # Hacer queue_manager disponible para la app
        app.state.queue_manager = queue_manager
        app.state.redis_client = redis_client
        
        yield
        
    finally:
        logger.info("Deteniendo Agent Orchestrator Service")
        
        # Detener worker
        if orchestrator_worker:
            await orchestrator_worker.stop()
        
        # Cancelar task
        if 'worker_task' in locals():
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        
        # Cerrar conexiones Redis
        if queue_manager and hasattr(queue_manager, 'redis'):
            await queue_manager.redis.close()

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
@app.get("/metrics/overview")
async def get_metrics_overview():
    """Métricas generales del orchestrator."""
    if orchestrator_worker:
        return await orchestrator_worker.get_orchestrator_stats()
    else:
        return {"error": "Worker no inicializado"}

@app.get("/metrics/queues")
async def get_queue_metrics():
    """Métricas específicas de colas."""
    if queue_manager:
        return await queue_manager.get_queue_stats(settings.domain_name)
    else:
        return {"error": "Queue manager no inicializado"}

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