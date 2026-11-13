import logging
import os

import redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse

log = logging.getLogger("devops-lab")
app = FastAPI()

# O Docker Compose resolve o nome do serviço ("redis") via DNS interno.
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


@app.get("/")
def read_root():
    try:
        count = r.incr("hits")
    except redis.RedisError:
        # Loga o detalhe no servidor, mas não vaza a mensagem de erro interna
        # (host/porta do Redis) para quem chamou a API.
        log.exception("Falha ao acessar o Redis")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "message": "Redis indisponível"},
        )
    return {
        "status": "online",
        "message": "API integrada com Redis via Docker Compose!",
        "total_visitors": count,
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
