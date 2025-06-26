"""
Punto de entrada principal del Query Service.

Configura y ejecuta el servicio con FastAPI y el QueryWorker.
"""

import asyncio
from common.utils.logging import init_logging
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from common.clients import RedisManager
from common.utils import init_logging

from common.config import QueryServiceSettings
from .workers.query_worker import QueryWorker


# Variables globales para el ciclo de vida
redis_manager: Optional[RedisManager] = None
query_workers: List[QueryWorker] = []
worker_tasks: List[asyncio.Task] = []

# Configuración
settings = QueryServiceSettings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    
    Inicializa recursos al inicio y los limpia al finalizar.
    """
    global redis_manager, query_workers, worker_tasks
    
    try:
        # Inicializar logging
        init_logging(
            log_level=settings.log_level,
            service_name=settings.service_name
        )
        
        logger.info(f"Iniciando {settings.service_name} v{settings.service_version}")
        
        # Inicializar Redis Manager
        redis_manager = RedisManager(settings=settings)
        redis_conn = await redis_manager.get_client()
        logger.info("Redis Manager inicializado")
        
        # Crear workers según configuración
        num_workers = getattr(settings, 'worker_count', 2)
        
        for i in range(num_workers):
            worker = QueryWorker(
                app_settings=settings,
                async_redis_conn=redis_conn,
                consumer_id_suffix=f"worker-{i}"
            )
            query_workers.append(worker)
            
            # Inicializar y ejecutar worker
            await worker.initialize()
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        
        logger.info(f"{num_workers} QueryWorkers iniciados")
        
        # Hacer disponibles las referencias en app.state
        app.state.redis_manager = redis_manager
        app.state.query_workers = query_workers
        
        yield
        
    finally:
        logger.info("Deteniendo Query Service...")
        
        # Detener workers
        for worker in query_workers:
            await worker.stop()
        
        # Cancelar tareas
        for task in worker_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Cerrar Redis Manager
        if redis_manager:
            await redis_manager.close()
        
        logger.info("Query Service detenido completamente")


# Crear aplicación FastAPI
app = FastAPI(
    title=settings.service_name,
    description="Servicio de búsqueda vectorial y generación RAG",
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


# --- Health Check Endpoints ---

@app.get("/health")
async def health_check():
    """
    Health check básico del servicio.
    """
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Health check detallado con estado de componentes.
    """
    health_status = {
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "components": {}
    }
    
    # Verificar Redis
    try:
        if redis_manager:
            client = await redis_manager.get_client()
            await client.ping()
            health_status["components"]["redis"] = {"status": "healthy"}
        else:
            health_status["components"]["redis"] = {"status": "unhealthy", "error": "Not initialized"}
    except Exception as e:
        health_status["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
    
    # Verificar Workers
    workers_status = []
    for i, worker in enumerate(query_workers):
        worker_status = {
            "id": i,
            "running": worker._running,
            "initialized": worker.initialized
        }
        workers_status.append(worker_status)
    
    health_status["components"]["workers"] = {
        "status": "healthy" if all(w["running"] for w in workers_status) else "degraded",
        "details": workers_status
    }
    
    # Estado general
    all_healthy = all(
        comp.get("status") == "healthy" 
        for comp in health_status["components"].values()
    )
    health_status["status"] = "healthy" if all_healthy else "degraded"
    
    return health_status


# --- Metrics Endpoints ---

@app.get("/metrics")
async def get_metrics():
    """
    Obtiene métricas del servicio.
    """
    metrics = {
        "service": settings.service_name,
        "workers": []
    }
    
    # Por ahora no tenemos métricas específicas implementadas
    # pero podríamos agregar contadores de acciones procesadas, etc.
    
    return metrics


# --- API Info ---

@app.get("/")
async def root():
    """
    Información básica del servicio.
    """
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Query Service - Búsqueda vectorial y generación RAG",
        "endpoints": {
            "health": "/health",
            "health_detailed": "/health/detailed",
            "metrics": "/metrics",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


if __name__ == "__main__":
    init_logging(settings.log_level, settings.service_name)
    uvicorn.run(
        "query_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # En producción debe ser False
        log_level=settings.log_level.lower()
    )