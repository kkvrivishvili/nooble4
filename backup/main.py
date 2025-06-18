"""
Punto de entrada principal para el servicio de ingestión.

Este módulo inicializa la aplicación FastAPI, configura middleware,
registra rutas, maneja eventos de inicio y apagado, y gestiona la inicialización
del pool de workers asíncronos.
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.context import create_context, Context
from common.errors import handle_error, ServiceError
from ingestion_service.config.settings import get_settings
from ingestion_service.routes import documents, tasks, websockets
from ingestion_service.services.queue import queue_service
from ingestion_service.workers.worker_pool import worker_pool

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Obtener configuración
settings = get_settings()

# Crear aplicación FastAPI
app = FastAPI(
    title="Ingestion Service",
    description="Servicio para procesamiento y fragmentación de documentos",
    version="1.0.0",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar manejadores de errores
@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    """Manejador global de errores de servicio."""
    return handle_error(exc)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Manejador general de excepciones no controladas."""
    logger.error(f"Error no controlado: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "internal_server_error",
            "message": "Error interno del servidor",
            "details": str(exc)
        }
    )


# Incluir routers
app.include_router(documents.router)
app.include_router(tasks.router)
app.include_router(websockets.router)

# Endpoint de health check
@app.get("/health")
async def health_check():
    """Endpoint para verificar estado del servicio."""
    # Verificar conexión a Redis
    redis_connected = await queue_service.check_connection()
    
    # Obtener estado del pool de workers
    workers_status = await worker_pool.status()
    
    return {
        "status": "healthy" if redis_connected else "degraded",
        "version": settings.VERSION,
        "redis": "connected" if redis_connected else "disconnected",
        "workers": workers_status
    }


# Eventos de inicio y apagado
@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación."""
    logger.info("Iniciando servicio de ingestión...")
    
    # Contexto para inicio
    ctx = create_context(component="app", operation="startup")
    
    try:
        # Inicializar conexión a Redis
        await queue_service.initialize(ctx)
        
        # Iniciar pool de workers
        if settings.AUTO_START_WORKERS:
            await worker_pool.start(ctx)
        
        logger.info("Servicio de ingestión iniciado correctamente")
        
    except Exception as e:
        logger.error(f"Error al iniciar servicio: {e}")
        # No re-lanzamos la excepción para permitir que la app inicie en modo degradado


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de apagado de la aplicación."""
    logger.info("Deteniendo servicio de ingestión...")
    
    # Contexto para apagado
    ctx = create_context(component="app", operation="shutdown")
    
    try:
        # Detener pool de workers
        await worker_pool.stop(ctx)
        
        # Cerrar conexiones Redis
        await queue_service.shutdown(ctx)
        
        logger.info("Servicio de ingestión detenido correctamente")
        
    except Exception as e:
        logger.error(f"Error durante el apagado del servicio: {e}")


# Ejecutar la aplicación si es el módulo principal
if __name__ == "__main__":
    import uvicorn
    
    # Obtener configuración de puerto y host
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    
    # Iniciar servidor
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=settings.DEBUG
    )
