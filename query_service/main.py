"""
Punto de entrada del Query Service.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.errors import setup_error_handling
from common.utils.logging import init_logging
from common.helpers.health import register_health_routes
from common.db.supabase import init_supabase

from query_service.workers.query_worker import QueryWorker
from query_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Worker global
query_worker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global query_worker
    
    logger.info("Iniciando Query Service")
    
    # Inicializar conexión a bases de datos
    await init_supabase()
    
    # Inicializar worker
    query_worker = QueryWorker()
    
    # Iniciar worker en background
    worker_task = asyncio.create_task(query_worker.start())
    
    try:
        yield
    finally:
        logger.info("Deteniendo Query Service")
        
        # Detener worker
        if query_worker:
            await query_worker.stop()
        
        # Cancelar task
        worker_task.cancel()
        
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

# Crear aplicación FastAPI (solo para health checks)
app = FastAPI(
    title="Query Service",
    description="Servicio RAG para búsqueda y generación de respuestas con Domain Actions",
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

# Health checks
register_health_routes(app)

# Configurar logging
init_logging(settings.log_level, service_name="query-service")

async def shutdown(signal_type):
    """Manejo de señales para shutdown graceful."""
    logger.info(f"Recibida señal {signal_type.name}, cerrando...")
    
    # Detener worker
    global query_worker
    if query_worker:
        await query_worker.stop()
        
    sys.exit(0)

def handle_exception(loop, context):
    """Maneja excepciones no capturadas en el event loop."""
    msg = context.get("exception", context["message"])
    logger.error(f"Error no capturado: {msg}")
    logger.info("Cerrando servicio...")
    asyncio.create_task(shutdown(signal.SIGTERM))

async def main():
    """Función principal para ejecución independiente."""
    # Configurar logging
    init_logging(settings.log_level, service_name="query-service")
    
    # Manejar señales de sistema
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda sig=sig: asyncio.create_task(shutdown(sig))
        )
    
    # Configurar handler para excepciones no capturadas
    loop.set_exception_handler(handle_exception)
    
    # Inicializar conexión a bases de datos
    await init_supabase()
    
    # Inicializar worker
    global query_worker
    query_worker = QueryWorker()
    
    logger.info("Iniciando Query Service en modo standalone")
    
    try:
        # Iniciar worker y esperar a que termine
        await query_worker.start()
    finally:
        if query_worker:
            await query_worker.stop()
        logger.info("Query Service detenido")

if __name__ == "__main__":
    asyncio.run(main())
