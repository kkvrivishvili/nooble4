from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
import jwt
import os
import aioredis
import httpx
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales
redis = None
http_client = None

# Configuración
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-here")
JWT_ALGORITHM = "HS256"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis_database:6379/0")
AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://authentik:9000")
QUOTA_LIMIT = int(os.getenv("QUOTA_LIMIT", "1000"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hora
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la aplicación"""
    global redis, http_client
    
    # Startup
    logger.info("Starting Forward Auth Service...")
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    http_client = httpx.AsyncClient()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Forward Auth Service...")
    await redis.close()
    await http_client.aclose()

app = FastAPI(
    title="Forward Auth Service",
    description="Servicio de autenticación y autorización para Nooble Platform",
    version="1.0.0",
    lifespan=lifespan
)

class AuthValidator:
    """Clase para validar tokens y permisos"""
    
    @staticmethod
    async def validate_jwt_token(token: str) -> Dict[str, Any]:
        """Valida un token JWT y retorna el payload"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            # Verificar expiración
            if "exp" in payload:
                exp_timestamp = payload["exp"]
                if datetime.utcnow().timestamp() > exp_timestamp:
                    raise jwt.ExpiredSignatureError("Token has expired")
            
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token")
    
    @staticmethod
    async def validate_with_authentik(token: str) -> Optional[Dict[str, Any]]:
        """Valida el token con Authentik"""
        try:
            # Verificar en caché primero
            cached_result = await redis.get(f"auth:token:{token[:20]}")
            if cached_result:
                return json.loads(cached_result)
            
            # Validar con Authentik
            response = await http_client.get(
                f"{AUTHENTIK_URL}/api/v3/core/tokens/view_key/",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                user_data = response.json()
                # Cachear el resultado
                await redis.setex(
                    f"auth:token:{token[:20]}", 
                    CACHE_TTL, 
                    json.dumps(user_data)
                )
                return user_data
            
            return None
        except Exception as e:
            logger.error(f"Error validating with Authentik: {str(e)}")
            return None

class RateLimiter:
    """Clase para manejar rate limiting"""
    
    @staticmethod
    async def check_rate_limit(identifier: str, limit: int = QUOTA_LIMIT) -> bool:
        """Verifica si el usuario ha excedido el límite de requests"""
        key = f"rate_limit:{identifier}"
        
        # Incrementar contador
        current = await redis.incr(key)
        
        # Establecer TTL si es el primer request
        if current == 1:
            await redis.expire(key, RATE_LIMIT_WINDOW)
        
        return current <= limit
    
    @staticmethod
    async def get_remaining_quota(identifier: str, limit: int = QUOTA_LIMIT) -> Dict[str, int]:
        """Obtiene la cuota restante para un usuario"""
        key = f"rate_limit:{identifier}"
        used = int(await redis.get(key) or 0)
        ttl = await redis.ttl(key)
        
        return {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "reset_in": ttl if ttl > 0 else RATE_LIMIT_WINDOW
        }

@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    try:
        # Verificar conexión a Redis
        await redis.ping()
        return {"status": "healthy", "service": "forward-auth"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/auth")
async def authenticate(request: Request):
    """Endpoint principal de autenticación"""
    # Extraer token del header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        return Response(status_code=401, headers={"X-Auth-Error": "Missing token"})
    
    token = auth_header.split("Bearer ", 1)[1]
    if not token:
        return Response(status_code=401, headers={"X-Auth-Error": "Invalid token format"})
    
    try:
        # Intentar validación local primero (más rápida)
        payload = await AuthValidator.validate_jwt_token(token)
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id", "default")
        
    except HTTPException:
        # Si falla la validación local, intentar con Authentik
        user_data = await AuthValidator.validate_with_authentik(token)
        if not user_data:
            return Response(status_code=401, headers={"X-Auth-Error": "Invalid token"})
        
        user_id = user_data.get("pk") or user_data.get("user_id")
        tenant_id = user_data.get("tenant_id", "default")
        payload = user_data
    
    if not user_id:
        return Response(status_code=401, headers={"X-Auth-Error": "User ID not found"})
    
    # Verificar rate limiting
    rate_limit_key = f"{tenant_id}:{user_id}"
    if not await RateLimiter.check_rate_limit(rate_limit_key):
        quota_info = await RateLimiter.get_remaining_quota(rate_limit_key)
        return Response(
            status_code=429,
            headers={
                "X-RateLimit-Limit": str(quota_info["limit"]),
                "X-RateLimit-Remaining": str(quota_info["remaining"]),
                "X-RateLimit-Reset": str(quota_info["reset_in"]),
                "X-Auth-Error": "Rate limit exceeded"
            }
        )
    
    # Obtener información de cuota
    quota_info = await RateLimiter.get_remaining_quota(rate_limit_key)
    
    # Headers de respuesta exitosa
    response_headers = {
        "X-User-ID": str(user_id),
        "X-Tenant-ID": str(tenant_id),
        "X-Forwarded-User": str(user_id),
        "X-Auth-Status": "valid",
        "X-RateLimit-Limit": str(quota_info["limit"]),
        "X-RateLimit-Remaining": str(quota_info["remaining"]),
        "X-RateLimit-Reset": str(quota_info["reset_in"])
    }
    
    # Agregar roles si están disponibles
    if "roles" in payload:
        response_headers["X-User-Roles"] = ",".join(payload["roles"])
    
    # Agregar información adicional del usuario si está disponible
    if "email" in payload:
        response_headers["X-User-Email"] = payload["email"]
    
    if "groups" in payload:
        response_headers["X-User-Groups"] = ",".join(payload["groups"])
    
    # Log de autenticación exitosa
    logger.info(f"Authentication successful for user {user_id} in tenant {tenant_id}")
    
    return Response(status_code=200, headers=response_headers)

@app.post("/auth/validate")
async def validate_token(request: Request):
    """Endpoint para validar tokens (útil para debugging)"""
    try:
        body = await request.json()
        token = body.get("token")
        
        if not token:
            raise HTTPException(status_code=400, detail="Token required")
        
        # Validar token
        payload = await AuthValidator.validate_jwt_token(token)
        
        # Verificar con Authentik si está configurado
        authentik_data = await AuthValidator.validate_with_authentik(token)
        
        return {
            "valid": True,
            "payload": payload,
            "authentik_data": authentik_data,
            "expires_at": datetime.fromtimestamp(payload.get("exp", 0)).isoformat() if "exp" in payload else None
        }
    
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"valid": False, "error": e.detail}
        )
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"valid": False, "error": "Internal server error"}
        )

@app.get("/auth/quota/{user_id}")
async def get_user_quota(user_id: str, tenant_id: str = "default"):
    """Obtiene la información de cuota para un usuario"""
    rate_limit_key = f"{tenant_id}:{user_id}"
    quota_info = await RateLimiter.get_remaining_quota(rate_limit_key)
    
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "quota": quota_info
    }

@app.post("/auth/reset-quota/{user_id}")
async def reset_user_quota(user_id: str, tenant_id: str = "default"):
    """Resetea la cuota de un usuario (solo para admins)"""
    # TODO: Agregar validación de permisos de admin
    rate_limit_key = f"{tenant_id}:{user_id}"
    await redis.delete(f"rate_limit:{rate_limit_key}")
    
    return {
        "message": f"Quota reset for user {user_id} in tenant {tenant_id}",
        "success": True
    }

@app.get("/metrics")
async def get_metrics():
    """Endpoint de métricas para monitoreo"""
    try:
        # Obtener estadísticas de Redis
        info = await redis.info()
        
        # Contar tokens activos en caché
        token_keys = await redis.keys("auth:token:*")
        
        # Contar usuarios con rate limiting activo
        rate_limit_keys = await redis.keys("rate_limit:*")
        
        return {
            "service": "forward-auth",
            "status": "healthy",
            "redis": {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            },
            "cache": {
                "cached_tokens": len(token_keys),
                "active_rate_limits": len(rate_limit_keys)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get metrics"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)