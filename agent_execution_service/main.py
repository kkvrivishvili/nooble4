"""
Punto de entrada del Agent Execution Service.
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.errors import setup_error_handling
from common.utils.logging import init_logging
from common.helpers.health import register_health_routes
from config.settings import get_settings
from workers.execution_worker import ExecutionWorker

settings = get_settings()
logger = logging.getLogger(__name__)

# Worker global
execution_worker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global execution_worker
    
    logger.info("Iniciando Agent Execution Service")
    
    # Inicializar worker
    execution_worker = ExecutionWorker()
    
    # Iniciar worker en background
    worker_task = asyncio.create_task(execution_worker.start())
    
    try:
        yield
    finally:
        logger.info("Deteniendo Agent Execution Service")
        
        # Detener worker
        if execution_worker:
            await execution_worker.stop()
        
        # Cancelar task
        worker_task.cancel()
        
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

# Crear aplicación
app = FastAPI(
    title="Agent Execution Service",
    description="Motor de ejecución de agentes con LangChain",
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

# Health checks (no necesitamos rutas REST, solo health)
register_health_routes(app)

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
