# Runbook: RedisErrors

**Alerta:** `rate(redis_errors_total[1m]) > 0` por 30s. A API não consegue falar com o
Redis. `/` e `/ready` respondem **503** (de propósito: melhor falhar explícito que
mostrar um contador falso). `/health` continua 200, então os pods **não** são
reiniciados em cascata; eles saem do balanceamento via `/ready`.

## Verificar

```bash
docker compose ps redis
docker compose logs --tail=50 redis
docker compose exec redis redis-cli ping          # esperado: PONG
```

Kubernetes:

```bash
kubectl get pods -l app=redis
kubectl logs deploy/redis --tail=50
kubectl get pvc                                    # PVC do Redis Bound?
```

## Causas comuns

- Redis parado ou reiniciando: `docker compose start redis` / `kubectl rollout restart deploy/redis`.
- Disco cheio no volume (AOF ligado): veja `docker system df` / uso do PVC.
- Nome do host errado (`REDIS_HOST`): confira o ConfigMap `devops-lab-config`.

## Depois de resolver

A API se recupera sozinha; confirme `curl http://localhost/` com 200 e o alerta
saindo de *firing*. Se o contador voltou a zero, o volume foi perdido: registre.
