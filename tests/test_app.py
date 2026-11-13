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
