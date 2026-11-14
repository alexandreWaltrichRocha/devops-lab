# Runbook: ErrorBudgetBurnFast / Slow / Steady

**Alerta:** a proporção de respostas 5xx está consumindo o orçamento de erro mais
rápido que o sustentável (SLO de 99,5%; veja `docs/SLO.md`).

- **Fast (14,4x):** emergência. Em ~2 dias o orçamento do mês acaba.
- **Slow (6x):** grave, mas há algumas horas para investigar.
- **Steady (1x por dias):** ticket; algo erra de forma constante e baixa.

## Triagem

1. **Qual rota e qual status?** No Prometheus (`localhost:9090`):
   ```
   sum by (endpoint, http_status) (rate(http_requests_total{http_status=~"5.."}[5m]))
   ```
2. **Foi o Redis?** Se `redis_errors_total` também sobe, siga `redis-errors.md`.
3. **Mudou algo agora há pouco?** `git log --oneline -5` / último deploy
   (`kubectl rollout history deployment/devops-lab-deployment`).
4. **Saturação?** `docker stats` ou `kubectl top pods`; compare com os limites.

## Mitigar (primeiro estancar, depois entender)

- Deploy recente suspeito: `./scripts/deploy.sh --rollback`.
- Falta de capacidade: aumente réplicas (`kubectl scale deploy/devops-lab-deployment --replicas=4`)
  ou confira o HPA.

## Fechar

Quando a razão voltar abaixo do orçamento o alerta se resolve sozinho. Registre o que
consumiu orçamento em `docs/postmortems/` (use o `TEMPLATE.md`).
