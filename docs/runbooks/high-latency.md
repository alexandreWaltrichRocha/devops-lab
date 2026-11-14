# Runbook: LatencyBudgetBurn

**Alerta:** mais de 30% das requisições levam mais de 250ms (SLO: 95% abaixo de 250ms).

## Triagem

```
# p95 e p99 agora
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# Por rota
histogram_quantile(0.95, sum by (le, endpoint) (rate(http_request_duration_seconds_bucket[5m])))
```

1. **Todas as rotas ou só uma?** Uma só aponta para o código dessa rota.
2. **CPU no limite?** `docker stats` / `kubectl top pods`. Se está encostando no limite
   (500m), há throttling: escale ou suba o limite.
3. **Redis lento?** `docker compose exec redis redis-cli --latency`.
4. **Carga anormal?** Compare a taxa de requisições com o normal; se foi um teste de
   carga seu (`scripts/loadtest.sh`), é esperado.

## Mitigar

Escalar réplicas; reverter o último deploy; reduzir carga na origem. Se a lentidão for
o Nginx limitando (429), veja `limit_req` em `nginx/default.conf`.
