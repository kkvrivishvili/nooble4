"""
Middleware para extraer información del JWT.
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt
import uuid


class JWTMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str):
        super().__init__(app)
        self.secret_key = secret_key
    
    async def dispatch(self, request: Request, call_next):
        # Solo para rutas que requieren JWT
        if request.url.path.startswith("/api/"):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return await call_next(request)
            
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
                
                # Extraer y convertir a UUID
                request.state.tenant_id = uuid.UUID(payload.get("tenant_id"))
                request.state.agent_id = uuid.UUID(payload.get("agent_id"))
                request.state.user_id = uuid.UUID(payload.get("user_id")) if payload.get("user_id") else None
                
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=401, detail="Token inválido")
            except ValueError:
                raise HTTPException(status_code=400, detail="IDs inválidos en token")
        
        response = await call_next(request)
        return response