from fastapi import FastAPI, Request, Response
import jwt, os, aioredis

app = FastAPI()
redis = None
SECRET = os.getenv("JWT_SECRET")

@app.on_event("startup")
async def startup():
    global redis
    redis = await aioredis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

@app.get("/auth")
async def auth(request: Request):
    token = request.headers.get("Authorization", "").split("Bearer ")[-1]
    if not token:
        return Response(status_code=401)
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        sub = payload.get("sub")
        used = int(await redis.get(f"quota:{sub}") or 0)
        limit = int(os.getenv("QUOTA_LIMIT", "1000"))
        if used >= limit:
            return Response(status_code=403)
        await redis.incr(f"quota:{sub}")
        return Response(status_code=200)
    except Exception as e:
        return Response(content=str(e), status_code=403)
