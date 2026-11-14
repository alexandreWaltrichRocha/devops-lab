# Runbook: AppDown

**Alerta:** `up{job="fastapi-app"} == 0` por 30s. O Prometheus não consegue coletar
`/metrics` da API.

## Verificar (2 minutos)

```bash
docker compose ps                      # web está Up/healthy?
docker compose logs --tail=50 web      # erro de boot, falta de dependência?
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/nginx-health   # Nginx vivo?
```

Kubernetes:

```bash
kubectl get pods -l app=devops-lab
kubectl describe pod -l app=devops-lab | tail -30    # eventos: probe falhando? OOMKilled?
kubectl logs -l app=devops-lab --tail=50
```

## Causas comuns

| Sintoma | Causa provável | Ação |
|---|---|---|
| Container reiniciando em loop | erro no código / dependência | `logs`; reverter para a imagem anterior |
| `OOMKilled` | limite de memória (192Mi) baixo | subir o limite ou achar o vazamento |
| `web` saudável mas alvo `down` | rede do Compose / nome do serviço | `docker compose down && up -d` |
| Tudo parado | Docker/Minikube parou | subir o Docker; `minikube start` |

## Mitigar

Reverter para a versão anterior: `./scripts/deploy.sh --rollback` (Kubernetes) ou
`git revert` + novo deploy. Depois, registre o incidente em `docs/postmortems/`.
