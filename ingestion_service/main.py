"""Main entry point for Ingestion Service"""
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from common.utils import init_logging
from common.clients import RedisManager, BaseRedisClient
from common.config import IngestionServiceSettings

from .config import get_settings
from .workers import IngestionWorker
from .api import router
from .dependencies import set_ingestion_service, set_ws_manager
from .services import IngestionService
from .websocket import WebSocketManager

# Global instances
redis_manager: RedisManager = None
redis_client: BaseRedisClient = None
ingestion_worker: IngestionWorker = None
settings: IngestionServiceSettings = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global redis_manager, redis_client, ingestion_worker, settings
    
    # Startup
    settings = get_settings()
    init_logging(settings.log_level, settings.service_name)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting {settings.service_name} v{settings.service_version}")
    
    try:
        # Initialize Redis
        redis_manager = RedisManager(settings)
        redis_conn = await redis_manager.get_client()
        
        redis_client = BaseRedisClient(
            service_name=settings.service_name,
            redis_client=redis_conn,
            settings=settings
        )
        
        # Initialize WebSocket manager
        ws_manager = WebSocketManager()
        set_ws_manager(ws_manager)
        
        # Initialize service
        ingestion_service = IngestionService(
            app_settings=settings,
            service_redis_client=redis_client,
            direct_redis_conn=redis_conn,
            qdrant_url=getattr(settings, 'qdrant_url', 'http://localhost:6333')
        )
        set_ingestion_service(ingestion_service)
        
        # Initialize and start worker
        if settings.auto_start_workers:
            ingestion_worker = IngestionWorker(
                app_settings=settings,
                async_redis_conn=redis_conn,
                redis_client=redis_client,
                qdrant_url=getattr(settings, 'qdrant_url', 'http://localhost:6333')
            )
            await ingestion_worker.initialize()
            await ingestion_worker.start()
            logger.info("Ingestion worker started")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down...")
        
        if ingestion_worker:
            await ingestion_worker.stop()
        
        if redis_manager:
            await redis_manager.close()
        
        logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Ingestion Service",
    description="Document ingestion and processing service with LlamaIndex",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.service_name if settings else "ingestion-service",
        "version": settings.service_version if settings else "1.0.0"
    }


def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating shutdown...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Run the service
    settings = get_settings()
    
    uvicorn.run(
        "ingestion_service.main:app",
        host="0.0.0.0",
        port=8002,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )