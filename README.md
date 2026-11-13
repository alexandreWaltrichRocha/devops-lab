# DevOps Lab

API FastAPI + Redis, atrás de Nginx, com observabilidade (Prometheus + Grafana),
CI/CD no GitHub Actions e manifests Kubernetes.

```
cliente ─▶ Nginx :80 ─▶ API (FastAPI) :8000 ─▶ Redis
                            ▲
              Prometheus :9090 ──▶ Grafana :3000
```

## Módulos

| Pasta | Conteúdo |
|---|---|
| `modulo-02-docker` | Dockerfile multi-stage, API simples (porta 8000) |
| `modulo-03-compose` | API + Redis com Docker Compose |
| `modulo-04-volumes` | Persistência do Redis com volume nomeado |
| `modulo-05-nginx` | Nginx como reverse proxy |
| **raiz** (módulo 06) | Stack completa com Prometheus, Grafana e alertas |

## Como usar este repositório

```bash
git clone https://github.com/alexandreWaltrichRocha/devops-lab.git
cd devops-lab
cp .env.example .env        # edite e troque GRAFANA_ADMIN_PASSWORD
docker compose up -d --build --wait
```

Só é preciso Docker com Compose v2. A imagem é construída na sua máquina.

**Usando um fork?** O pipeline (`.github/workflows/ci.yml`) publica a imagem em
`alexandrew2033/devops-lab` no Docker Hub, com os secrets `DOCKER_USERNAME` e
`DOCKER_PASSWORD` do repositório original. Secrets não passam para forks, então:

- Os jobs de testes e de smoke test funcionam normalmente.
- O job de build/push só funciona depois que você trocar `IMAGE_NAME` no
  `ci.yml` pelo seu repositório do Docker Hub e criar os seus próprios secrets.
- O `k8s/deployment.yml` também aponta para `alexandrew2033/devops-lab:latest`;
  troque pela sua imagem ou use `./scripts/deploy-local.sh` (build local no Minikube).

Licença: [MIT](LICENSE).

## Subir a stack completa (Docker Compose)

Requisitos: Docker + Docker Compose v2 (no Windows: Docker Desktop com WSL2).

```bash
cp .env.example .env        # edite e troque GRAFANA_ADMIN_PASSWORD
docker compose up -d --build --wait
```

| Serviço | URL | Observação |
|---|---|---|
| API (via Nginx) | http://localhost/ | contador de visitas |
| Health do Nginx | http://localhost/nginx-health | |
| Prometheus | http://localhost:9090 | só localhost; alertas em `/alerts` |
| Grafana | http://localhost:3000 | só localhost; login do `.env` |

O Grafana já sobe com o datasource e o dashboard **"DevOps Lab - API (RED)"**
(taxa de requisições, % de erros 5xx, latência p50/p95/p99, erros de Redis).
`/metrics` não é exposto pelo Nginx; o Prometheus coleta direto da rede interna.

Gerar tráfego para ver os gráficos:

```bash
for i in $(seq 1 200); do curl -s -o /dev/null http://localhost/; done
```

## Endpoints da API

| Rota | Uso |
|---|---|
| `/` | Contador de visitas. `503` se o Redis estiver fora |
| `/health` | Liveness (não consulta o Redis) |
| `/ready` | Readiness (consulta o Redis) |
| `/metrics` | Métricas Prometheus |

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Kubernetes

```bash
kubectl apply -f k8s/
kubectl get pods -w
# acesso (NodePort): http://localhost:30080
```

> **Ordem importa:** as probes usam `/health` e `/ready`. A imagem
> `alexandrew2033/devops-lab:latest` precisa ter sido publicada **depois** desta
> versão do código (via CI no merge em `main`); com a imagem antiga os pods
> nunca ficam `Ready`.
>
> Para atualizar após um novo push: `kubectl rollout restart deployment/devops-lab-deployment`.
> O Redis do cluster usa `emptyDir` (dados somem se o pod for recriado);
> troque por um PVC se precisar persistir.

### Monitoramento no cluster (Prometheus Operator / kube-prometheus-stack)

O `prometheus/prometheus.yml` e o `grafana/provisioning/` são **só da stack Docker
Compose**; não conflitam com o Prometheus do cluster. No Kubernetes, a coleta é
declarada via `ServiceMonitor`, e o operador descobre a app pelos labels:

```bash
# 1) descubra o label `release` que o seu Prometheus exige e ajuste nos 2 arquivos
kubectl -n monitoring get prometheus -o jsonpath='{.items[0].spec.serviceMonitorSelector}'

# 2) aplique (precisa dos CRDs do operador instalados)
kubectl apply -f k8s/monitoring/

# 3) confira em Prometheus > Status > Targets: deve aparecer fastapi-app (2 pods)

# 4) dashboard no Grafana do Helm: o sidecar importa ConfigMaps com este label
kubectl -n monitoring create configmap devops-lab-dashboard --from-file=grafana/dashboards/api-red.json
kubectl -n monitoring label configmap devops-lab-dashboard grafana_dashboard=1
```

O dashboard usa o datasource de uid `prometheus`, que é o padrão do
kube-prometheus-stack; se o seu Grafana usar outro uid, ajuste no JSON.

## CI/CD (`.github/workflows/ci.yml`)

1. **test**: pytest, `promtool check config`, `kubeconform` nos manifests, `docker compose config`.
2. **smoke-test**: sobe a stack inteira e faz requisições reais.
3. **build**: constrói a imagem. O **push só acontece fora de pull request**
   (merge em `main` ou tag `vX.Y.Z`).

Tags geradas: `latest` (só na branch padrão), `sha-<commit>` e, em tags, `1.2.3` / `1.2`.
Secrets necessários: `DOCKER_USERNAME`, `DOCKER_PASSWORD`.
