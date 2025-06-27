"""
Punto de entrada principal para Agent Orchestrator Service.

Refactorizado para usar la nueva estructura.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.utils.logging import init_logging
from common.clients.redis.redis_manager import RedisManager
from common.clients.base_redis_client import BaseRedisClient
from agent_orchestrator_service.workers.orchestrator_worker import OrchestratorWorker
from agent_orchestrator_service.routes import chat_router, websocket_router, health_router
from agent_orchestrator_service.routes.chat_routes import set_orchestration_service as set_chat_service
from agent_orchestrator_service.routes.websocket_routes import set_orchestration_service as set_ws_service
from agent_orchestrator_service.services.orchestration_service import OrchestrationService
from agent_orchestrator_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Variables globales
worker_tasks = []
redis_manager: RedisManager = None
orchestration_service: OrchestrationService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global worker_tasks, redis_manager, orchestration_service
    
    logger.info("Iniciando Agent Orchestrator Service")
    
    try:
        # Inicializar RedisManager
        redis_manager = RedisManager(settings)
        redis_conn = await redis_manager.get_client()
        logger.info("Redis Manager inicializado")
        
        # Crear Redis client
        redis_client = BaseRedisClient(
            service_name=settings.service_name,
            redis_client=redis_conn,
            settings=settings
        )
        
        # Inicializar servicio de orquestación
        orchestration_service = OrchestrationService(
            app_settings=settings,
            service_redis_client=redis_client,
            direct_redis_conn=redis_conn
        )
        
        # Establecer servicio en routers
        set_chat_service(orchestration_service)
        set_ws_service(orchestration_service)
        
        # Crear e iniciar workers (solo para acciones especiales)
        worker_count = 1  # Solo necesitamos un worker mínimo
        for i in range(worker_count):
            worker = OrchestratorWorker(
                app_settings=settings,
                async_redis_conn=redis_conn,
                consumer_id_suffix=f"{i+1}"
            )
            await worker.initialize()
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        
        logger.info(f"{worker_count} OrchestratorWorkers iniciados")
        
        # Tarea de limpieza de sesiones inactivas
        cleanup_task = asyncio.create_task(_cleanup_inactive_sessions())
        worker_tasks.append(cleanup_task)
        
        yield
        
    finally:
        logger.info("Deteniendo Agent Orchestrator Service")
        
        # Detener workers
        for task in worker_tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        logger.info("Todos los workers detenidos")
        
        # Cerrar Redis
        if redis_manager:
            await redis_manager.close()
            logger.info("Conexiones Redis cerradas")


async def _cleanup_inactive_sessions():
    """Tarea periódica para limpiar sesiones inactivas."""
    while True:
        try:
            await asyncio.sleep(300)  # Cada 5 minutos
            if orchestration_service:
                websocket_manager = orchestration_service.get_websocket_manager()
                await websocket_manager.cleanup_inactive_sessions(inactive_minutes=30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error en limpieza de sesiones: {e}")


# Crear aplicación
app = FastAPI(
    title="Agent Orchestrator Service",
    description="Servicio de orquestación de agentes con WebSocket para chat en tiempo real",
    version=settings.service_version,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(websocket_router)

# Configurar logging
init_logging(settings.log_level, service_name=settings.service_name)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent_orchestrator_service.main:app",
        host="0.0.0.0",
        port=settings.agent_orchestrator_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )