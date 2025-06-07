"""
Punto de entrada principal para Agent Execution Service.

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
from agent_execution_service.workers.execution_worker import ExecutionWorker
from agent_execution_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Worker global
execution_worker = None
queue_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global execution_worker, queue_manager
    
    logger.info("Iniciando Agent Execution Service")
    
    try:
        # Inicializar Redis y Queue Manager
        redis_client = await get_redis_client()
        queue_manager = DomainQueueManager(redis_client)
        
        # Verificar conexión Redis
        await redis_client.ping()
        logger.info("Conexión a Redis establecida")
        
        # Inicializar worker
        execution_worker = ExecutionWorker(redis_client)
        
        # Iniciar worker en background
        worker_task = asyncio.create_task(execution_worker.start())
        logger.info("ExecutionWorker iniciado")
        
        # Hacer queue_manager disponible para la app
        app.state.queue_manager = queue_manager
        app.state.redis_client = redis_client
        
        yield
        
    finally:
        logger.info("Deteniendo Agent Execution Service")
        
        # Detener worker
        if execution_worker:
            await execution_worker.stop()
        
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
    title="Agent Execution Service",
    description="Servicio de ejecución de agentes con LangChain y colas por tier",
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

# Registrar health routes
register_health_routes(app)

# Health checks específicos del execution service
@app.get("/metrics/overview")
async def get_metrics_overview():
    """Métricas generales del execution service."""
    if execution_worker:
        return await execution_worker.get_execution_stats()
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
init_logging(settings.log_level, service_name="agent-execution-service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8005,
        reload=True,
        log_level="info"
    )