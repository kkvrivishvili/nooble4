"""
Punto de entrada principal para el Query Service.

Este módulo configura y ejecuta la aplicación FastAPI,
expone un endpoint de health check y maneja la lógica de
inicio y apagado del servicio.
"""

import logging
import uvicorn
from fastapi import FastAPI, Request, Response

from common.logging import setup_logging
from common.redis import RedisClientManager
from common.services import ServiceManager

from .config import settings
from .services import QueryService

# --- Configuración de Logging ---
setup_logging(service_name=settings.service_name, log_level=settings.log_level)
logger = logging.getLogger(__name__)

# --- Aplicación FastAPI ---
app = FastAPI(
    title="Query Service",
    version="1.0.0",
    description="Servicio para búsqueda vectorial y generación RAG"
)

# --- Gestores de Clientes y Servicios ---
redis_manager = RedisClientManager(settings.redis_url)
service_manager = ServiceManager()

# --- Eventos de Ciclo de Vida --- 
@app.on_event("startup")
async def startup_event():
    """Lógica de inicio del servicio."""
    logger.info("Iniciando Query Service...")
    
    # Conectar a Redis
    await redis_manager.connect()
    logger.info("Conectado a Redis.")
    
    # Registrar el servicio
    query_service = QueryService(
        app_settings=settings,
        service_redis_client=redis_manager.get_client(),
        direct_redis_conn=redis_manager.get_direct_connection()
    )
    service_manager.register_service("query", query_service)
    
    logger.info("Query Service iniciado y listo para recibir acciones.")

@app.on_event("shutdown")
async def shutdown_event():
    """Lógica de apagado del servicio."""
    logger.info("Apagando Query Service...")
    await redis_manager.disconnect()
    logger.info("Desconectado de Redis. Adiós.")

# --- Endpoints de la API ---
@app.get("/health", status_code=200)
async def health_check():
    """Endpoint de Health Check."""
    return {"status": "ok", "service": "Query Service"}

# --- Middleware (opcional) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para loguear cada petición."""
    logger.debug(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.debug(f"Response: {response.status_code}")
    return response

# --- Función para ejecutar con uvicorn ---
def start():
    """Inicia el servidor uvicorn."""
    uvicorn.run(
        "query_service.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True if settings.environment == "development" else False
    )

if __name__ == "__main__":
    start()
