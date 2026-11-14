"""API do DevOps Lab: FastAPI + Redis + métricas Prometheus.

Endpoints:
  /         contador de visitas (depende do Redis)
  /health   liveness  -> processo está vivo (NÃO depende de nada externo)
  /ready    readiness -> pronto para receber tráfego (checa o Redis)
  /metrics  métricas Prometheus

Logs: JSON por padrão (uma linha por requisição; /health e /metrics ficam de fora).
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)



# --- Logs estruturados -------------------------------------------------------
# Uma linha JSON por evento: fácil de filtrar com `jq` e de ingerir em Loki/ELK.
# LOG_FORMAT=text volta ao formato legível para depuração local.
_LOG_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Campos passados via `extra={...}` entram no JSON.
        payload.update({k: v for k, v in record.__dict__.items() if k not in _LOG_ATTRS})
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("devops-lab")
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    if not logger.handlers:
        handler = logging.StreamHandler()
        if os.getenv("LOG_FORMAT", "json") == "json":
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


log = _setup_logging()

app = FastAPI(title="DevOps Lab")

# --- Redis -----------------------------------------------------------------
# Timeouts curtos: sem eles, um Redis "sumido" (IP sem resposta) trava a
# requisição indefinidamente e esgota o threadpool do servidor.
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


def make_redis(host: str, port: int) -> redis.Redis:
    # Retry(NoBackoff(), 0): sem retentativas. As versões recentes do redis-py fazem 3
    # tentativas com espera crescente por padrão, e uma requisição com o Redis fora
    # demoraria ~4s em vez de falhar rápido (travando threads e queimando o SLO de
    # latência). Aqui queremos o 503 imediato; quem reintenta é o cliente HTTP.
    return redis.Redis(
        host=host,
        port=port,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
        retry=Retry(NoBackoff(), 0),
    )


r = make_redis(REDIS_HOST, REDIS_PORT)

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
        elapsed = time.perf_counter() - start
        REQUEST_COUNT.labels(request.method, endpoint, str(status)).inc()
        REQUEST_LATENCY.labels(endpoint).observe(elapsed)
        log.info(
            "request",
            extra={
                "method": request.method,
                "endpoint": endpoint,
                "status": status,
                "duration_ms": round(elapsed * 1000, 2),
            },
        )


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
