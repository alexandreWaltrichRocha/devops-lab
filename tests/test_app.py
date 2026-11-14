import json
import logging
import socket
import time

import pytest
import redis
from fastapi.testclient import TestClient

import main


class FakeRedis:
    """Dublê mínimo do cliente Redis (sem dependência de servidor real)."""

    def __init__(self):
        self.data = {}

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def ping(self):
        return True


class BrokenRedis:
    def incr(self, key):
        raise redis.ConnectionError("down")

    def ping(self):
        raise redis.ConnectionError("down")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "r", FakeRedis())
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def broken_client(monkeypatch):
    monkeypatch.setattr(main, "r", BrokenRedis())
    return TestClient(main.app, raise_server_exceptions=False)


def test_health_nao_depende_do_redis(broken_client):
    resp = broken_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_ready_ok(client):
    assert client.get("/ready").status_code == 200


def test_ready_503_sem_redis(broken_client):
    assert broken_client.get("/ready").status_code == 503


def test_root_incrementa_contador(client):
    assert client.get("/").json()["total_visitors"] == 1
    assert client.get("/").json()["total_visitors"] == 2


def test_root_503_sem_redis(broken_client):
    resp = broken_client.get("/")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_metrics_expoe_prometheus(client):
    client.get("/")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_rota_inexistente_nao_cria_serie_por_url(client):
    for i in range(5):
        client.get(f"/nao-existe-{i}")
    body = client.get("/metrics").text
    assert 'endpoint="unmatched"' in body
    assert "nao-existe-" not in body


def test_excecao_nao_tratada_conta_como_500(client, monkeypatch):
    def boom(_key):
        raise RuntimeError("bug inesperado")

    monkeypatch.setattr(main.r, "incr", boom)
    assert client.get("/").status_code == 500
    body = client.get("/metrics").text
    assert 'http_requests_total{endpoint="/",http_status="500",method="GET"}' in body


def test_requisicao_gera_log_json_estruturado(client, caplog):
    with caplog.at_level(logging.INFO, logger="devops-lab"):
        client.get("/")
    rec = next(r for r in caplog.records if r.getMessage() == "request")
    line = json.loads(main.JsonFormatter().format(rec))
    assert line["level"] == "INFO"
    assert line["method"] == "GET"
    assert line["endpoint"] == "/"
    assert line["status"] == 200
    assert line["duration_ms"] >= 0
    assert line["ts"].endswith("+00:00")


def test_health_e_metrics_nao_geram_log(client, caplog):
    with caplog.at_level(logging.INFO, logger="devops-lab"):
        client.get("/health")
        client.get("/metrics")
    assert not [r for r in caplog.records if r.getMessage() == "request"]


def test_erro_do_redis_loga_excecao_em_json(broken_client, caplog):
    with caplog.at_level(logging.ERROR, logger="devops-lab"):
        broken_client.get("/")
    rec = next(r for r in caplog.records if r.levelno == logging.ERROR)
    line = json.loads(main.JsonFormatter().format(rec))
    assert "Redis" in line["message"]
    assert "ConnectionError" in line["exc_info"]


def test_cliente_redis_real_falha_rapido_sem_retries():
    """Regressão: o redis-py novo reintenta 3x com espera por padrão (~4s por requisição).
    Com Redis inalcançável a falha tem que ser imediata."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]          # porta livre e fechada
    client = main.make_redis("127.0.0.1", port)
    start = time.perf_counter()
    with pytest.raises(redis.ConnectionError):
        client.incr("visitors")
    assert time.perf_counter() - start < 1.0
