"""
Manejo de errores común para todos los servicios.
"""

import logging
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.applications import FastAPI

logger = logging.getLogger(__name__)

def setup_error_handling(app: FastAPI):
    """Configura manejo de errores para FastAPI."""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "type": "HTTPException",
                    "message": exc.detail,
                    "status_code": exc.status_code
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Error no manejado: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "type": "InternalError",
                    "message": "Error interno del servidor"
                }
            }
        )

def handle_errors(error_type: str = "simple", log_traceback: bool = False):
    """Decorator para manejo de errores en endpoints."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_traceback:
                    logger.exception(f"Error en {func.__name__}: {str(e)}")
                else:
                    logger.error(f"Error en {func.__name__}: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        return wrapper
    return decorator
