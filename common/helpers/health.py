"""
Health checks comunes para todos los servicios.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

def register_health_routes(app: FastAPI):
    """Registra rutas de health check estándar."""
    
    @app.get("/health")
    async def health_check():
        """Health check básico."""
        return JSONResponse(content={
            "status": "ok",
            "service": app.title,
            "version": getattr(app, "version", "unknown")
        })
    
    @app.get("/ready")
    async def readiness_check():
        """Readiness check básico."""
        return JSONResponse(content={
            "status": "ready",
            "service": app.title
        })
