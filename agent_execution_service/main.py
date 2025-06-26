"""
Punto de entrada principal para Agent Execution Service.
"""
import asyncio
from common.utils.logging import init_logging
import logging
import signal
from contextlib import asynccontextmanager
from typing import List
import uvicorn
from fastapi import FastAPI

from common.clients.redis.redis_manager import RedisManager
from common.utils.logging import init_logging
from common.config.service_settings import ExecutionServiceSettings
from .workers.execution_worker import ExecutionWorker

# Variables globales para gestión de recursos
redis_manager: RedisManager = None
workers: List[ExecutionWorker] = []
settings: ExecutionServiceSettings = None
worker_tasks: List[asyncio.Task] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor del ciclo de vida de la aplicación."""
    global redis_manager, workers, settings, worker_tasks
    
    # Inicializar logging primero con valores por defecto o desde una config básica
    # para asegurar que el logger esté disponible incluso si la carga de settings falla.
    init_logging() # Llama con valores por defecto
    logger = logging.getLogger(__name__)

    try:
        # Cargar configuración
        settings = ExecutionServiceSettings()
        
        # Re-inicializar logging con la configuración cargada
        init_logging(
            log_level=settings.log_level,
            service_name=settings.service_name
        )
        logger.info(f"Iniciando {settings.service_name} v{settings.service_version}")
        
        # Validar configuración crítica
        if not settings.redis_url:
            logger.error("REDIS_URL no configurado")
            raise ValueError("REDIS_URL es requerido")
        
        # Inicializar Redis Manager
        redis_manager = RedisManager(settings)
        redis_client = await redis_manager.get_client()
        logger.info("Conexión Redis establecida")
        
        # Crear workers
        workers = []
        for i in range(settings.worker_count):
            worker = ExecutionWorker(
                app_settings=settings,
                async_redis_conn=redis_client,
                consumer_id_suffix=f"worker-{i}"
            )
            workers.append(worker)
        
        # Inicializar workers
        for worker in workers:
            await worker.initialize()
        
        # Iniciar workers como tareas
        worker_tasks = []
        for worker in workers:
            task = asyncio.create_task(
                worker.run(),
                name=f"worker-{worker.consumer_name}"
            )
            worker_tasks.append(task)
        
        logger.info(f"Servicio {settings.service_name} iniciado con {len(workers)} workers")
        
        yield
        
    except Exception as e:
        logger.error(f"Error durante el startup: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Iniciando shutdown del servicio...")
        
        try:
            # Detener workers
            for worker in workers:
                try:
                    await worker.stop()
                except Exception as e:
                    logger.error(f"Error deteniendo worker: {e}")
            
            # Cancelar tareas de workers
            for task in worker_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Cerrar Redis
            if redis_manager:
                await redis_manager.close()
            
            logger.info("Servicio detenido correctamente")
            
        except Exception as e:
            logger.error(f"Error durante shutdown: {e}")

# Crear aplicación FastAPI
app = FastAPI(
    title="Agent Execution Service",
    description="Servicio de ejecución de agentes con modos simple (Chat+RAG) y avanzado (ReAct)",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "service": "agent_execution_service",
        "version": "2.0.0",
        "status": "running",
        "modes": ["simple", "advance"]
    }

@app.get("/health")
async def health_check():
    """Health check básico."""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def detailed_health_check():
    """Health check detallado."""
    global redis_manager, workers, settings
    
    health_status = {
        "service": "agent_execution_service",
        "status": "healthy",
        "workers": {
            "configured": len(workers),
            "running": 0
        },
        "redis_connected": False
    }
    
    # Verificar workers
    try:
        running_workers = sum(1 for w in workers if w._running)
        health_status["workers"]["running"] = running_workers
        
        if running_workers == 0 and len(workers) > 0:
            health_status["status"] = "degraded"
            
    except Exception as e:
        health_status["workers"]["error"] = str(e)
    
    # Verificar Redis
    try:
        if redis_manager:
            redis_client = await redis_manager.get_client()
            await redis_client.ping()
            health_status["redis_connected"] = True
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["redis_error"] = str(e)
    
    return health_status

@app.get("/metrics")
async def metrics():
    """Métricas básicas del servicio."""
    global workers
    
    metrics_data = {
        "workers_total": len(workers),
        "workers_running": sum(1 for w in workers if getattr(w, '_running', False)),
        "service_version": "1.0.0"
    }
    
    return metrics_data

async def shutdown_handler():
    """Handler para shutdown graceful."""
    logger = logging.getLogger(__name__)
    logger.info("Recibida señal de shutdown...")
    
    # FastAPI se encarga del shutdown via lifespan

def setup_signal_handlers():
    """Configura handlers para señales del sistema."""
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(shutdown_handler()))
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(shutdown_handler()))

if __name__ == "__main__":
    init_logging(settings.log_level, settings.service_name)
    # Configurar signal handlers
    setup_signal_handlers()
    
    # Cargar configuración para desarrollo
    dev_settings = ExecutionServiceSettings()
    
    uvicorn.run(
        "agent_execution_service.main:app",
        host="0.0.0.0",
        port=8005,  # Puerto específico para este servicio
        reload=False,  # Cambiar a False para producción
        log_level=dev_settings.log_level.lower(),
        access_log=True
    )