"""API do DevOps Lab: FastAPI + Redis + métricas Prometheus.

Endpoints:
  /         contador de visitas (depende do Redis)
  /health   liveness  -> processo está vivo (NÃO depende de nada externo)
  /ready    readiness -> pronto para receber tráfego (checa o Redis)
  /metrics  métricas Prometheus
"""
import logging
import os
import time

import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("devops-lab")

app = FastAPI(title="DevOps Lab")

# --- Redis -----------------------------------------------------------------
# Timeouts curtos: sem eles, um Redis "sumido" (IP sem resposta) trava a
# requisição indefinidamente e esgota o threadpool do servidor.
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)

# --- Métricas --------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requisições HTTP",
    ["method", "endpoint", "http_status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latência das requisições HTTP em segundos",
    ["endpoint"],
)
REDIS_ERRORS = Counter("redis_errors_total", "Falhas ao acessar o Redis")

# Rotas que não entram nas métricas (evita poluir com probes/scrapes).
EXCLUDED_PATHS = {"/metrics", "/health"}


def _endpoint_label(request: Request) -> str:
    """Usa o *template* da rota (ex.: /items/{id}) e não o path cru.

    Com o path cru, qualquer scanner batendo em /a, /b, /c... cria uma série
    nova por URL (explosão de cardinalidade no Prometheus).
    """
    route = request.scope.get("route")
    return route.path if route is not None else "unmatched"


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)

    start = time.perf_counter()
    status = 500  # se call_next levantar exceção, contabiliza como 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        endpoint = _endpoint_label(request)
        REQUEST_COUNT.labels(request.method, endpoint, str(status)).inc()
        REQUEST_LATENCY.labels(endpoint).observe(time.perf_counter() - start)


# --- Rotas -----------------------------------------------------------------
@app.get("/")
def read_root():
    try:
        count = r.incr("visitors")
    except redis.RedisError:
        REDIS_ERRORS.inc()
        log.exception("Falha ao acessar o Redis")
        # 503 explícito em vez de "total_visitors: 0": o erro aparece nas
        # métricas/SLO em vez de ser engolido silenciosamente.
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "message": "Redis indisponível"},
        )
    return {
        "status": "online",
        "message": "API integrada com Redis, Nginx e Prometheus!",
        "total_visitors": count,
    }


@app.get("/health")
def health():
    """Liveness: só diz que o processo responde. Não consulta o Redis, senão
    uma queda do Redis faria o Kubernetes reiniciar todos os pods em cascata."""
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    """Readiness: só recebe tráfego se o Redis responde."""
    try:
        r.ping()
    except redis.RedisError:
        return JSONResponse(status_code=503, content={"status": "not ready"})
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
