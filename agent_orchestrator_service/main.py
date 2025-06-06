"""
Punto de entrada principal para Agent Orchestrator Service.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from routes import chat_router, websocket_router, health_router
from workers.orchestrator_worker import OrchestratorWorker
from config.settings import get_settings

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("orchestrator")

# Configuración
settings = get_settings()

# Worker global
orchestrator_worker = OrchestratorWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    
    Args:
        app: Instancia de FastAPI
    """
    # Iniciar worker en background
    worker_task = asyncio.create_task(orchestrator_worker.start())
    logger.info("OrchestratorWorker iniciado en background")
    
    yield
    
    # Detener worker
    await orchestrator_worker.stop()
    logger.info("OrchestratorWorker detenido")
    
    # Esperar a que termine
    try:
        await asyncio.wait_for(worker_task, timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Timeout esperando a que termine el worker")

# Crear aplicación FastAPI
app = FastAPI(
    title="Agent Orchestrator Service",
    description="Servicio de orquestación de agentes con WebSockets",
    version="0.1.0",
    lifespan=lifespan
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manejadores de errores
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Manejador de errores de validación.
    
    Args:
        request: Solicitud HTTP
        exc: Excepción de validación
        
    Returns:
        JSONResponse: Respuesta con detalles del error
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Manejador general de excepciones.
    
    Args:
        request: Solicitud HTTP
        exc: Excepción
        
    Returns:
        JSONResponse: Respuesta con detalles del error
    """
    logger.error(f"Error no manejado: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Error interno del servidor",
            "message": str(exc)
        }
    )

# Registrar routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(websocket_router)

# Ruta raíz
@app.get("/")
async def root():
    """
    Endpoint raíz.
    
    Returns:
        Dict: Información básica del servicio
    """
    return {
        "service": "Agent Orchestrator Service",
        "version": "0.1.0",
        "status": "running"
    }

# Punto de entrada para ejecución directa
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
