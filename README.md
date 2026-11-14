# DevOps Lab

API FastAPI + Redis, atrás de Nginx, com observabilidade (Prometheus + Grafana),
CI/CD no GitHub Actions e manifests Kubernetes.

```
cliente ─▶ Nginx :80 ─▶ API (FastAPI) :8000 ─▶ Redis
                            ▲
              Prometheus :9090 ──▶ Grafana :3000
                   │
                   └──▶ Alertmanager :9093
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
- Para usar a sua imagem no Kubernetes, troque `alexandrew2033/devops-lab` no
  `k8s/deployment.yml` e a variável `BASE_IMAGE` em `scripts/deploy.sh` e `scripts/deploy-local.sh`.
  Sem Docker Hub, `./scripts/deploy-local.sh` faz o build local e carrega a imagem no Minikube.

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
| Alertmanager | http://localhost:9093 | só localhost; recebe os alertas do Prometheus |
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

## Confiabilidade (SRE)

**SLOs** (detalhes em [`docs/SLO.md`](docs/SLO.md)): disponibilidade de **99,5%** (sem 5xx) e
latência com **95%** das requisições abaixo de **250ms**, em 30 dias.

Os alertas seguem o modelo de **burn rate** do Google SRE Workbook: em vez de "erro acima
de X%", avisam quando o orçamento de erro está sendo consumido rápido demais, com duas
janelas (longa e curta) para reagir rápido e parar de alertar logo após a correção.

| Alerta | O que significa | Runbook |
|---|---|---|
| `AppDown` | Prometheus não coleta a API | [app-down](docs/runbooks/app-down.md) |
| `RedisErrors` | A API falha ao acessar o Redis | [redis-errors](docs/runbooks/redis-errors.md) |
| `ErrorBudgetBurnFast/Slow/Steady` | Orçamento de erro queimando 14x / 6x / 1x | [error-budget-burn](docs/runbooks/error-budget-burn.md) |
| `LatencyBudgetBurn` | Mais de 30% das requisições acima de 250ms | [high-latency](docs/runbooks/high-latency.md) |

`prometheus/alerts.yml` é a fonte da verdade. O `k8s/monitoring/prometheusrule.yml` é
**gerado** (`python scripts/sync_rules.py`) e o CI falha se divergir.

### Notificações (Discord)

Por padrão o Alertmanager só mostra os alertas em http://localhost:9093. Para receber no
Discord, siga [`alertmanager/alertmanager.discord.yml.example`](alertmanager/alertmanager.discord.yml.example)
(a URL do webhook fica num arquivo ignorado pelo Git, nunca no repositório).

### Logs estruturados

A API escreve **uma linha JSON por requisição** (rota, status, duração; `/health` e
`/metrics` ficam de fora):

```bash
docker compose logs -f web | grep '^{' | jq -c 'select(.status >= 500)'
```

`LOG_FORMAT=text` volta ao formato legível; `LOG_LEVEL` controla o nível.

### Teste de carga e experimentos de falha

```bash
./scripts/loadtest.sh                       # k6: 60 req/s por 60s; thresholds = SLOs
RATE=90 DURATION=2m ./scripts/loadtest.sh

./scripts/chaos.sh redis-down 20            # derruba o Redis; espere 503 e o alerta RedisErrors
./scripts/chaos.sh app-restart              # reinicia a API; veja o que o Nginx devolve
./scripts/chaos.sh kill-pod                 # Kubernetes: mata 1 pod; com 2+ réplicas deve seguir 200
```

Registre o que observar em [`docs/postmortems/`](docs/postmortems/) (há um
[template](docs/postmortems/TEMPLATE.md) e um exemplo real).

## Testes

```bash
pip install -r requirements-dev.txt
pytest                                      # testes da API
python scripts/sync_rules.py --check        # PrometheusRule em sincronia com alerts.yml

# testes unitários das regras de alerta (precisa do promtool, ou via Docker):
docker run --rm --entrypoint promtool -v "$PWD/prometheus:/etc/prometheus:ro" \
  prom/prometheus:v2.51.0 test rules /etc/prometheus/tests/alerts_test.yml
```

## Kubernetes

```bash
./scripts/deploy-local.sh                   # Minikube: build local com tag única + deploy
./scripts/deploy.sh                         # imagem já publicada pelo CI (tag sha-<commit>)
./scripts/deploy.sh sha-<40 hex>            # uma versão específica
./scripts/deploy.sh --rollback              # volta para a revisão anterior
kubectl get pods -w                         # acesso (NodePort): http://localhost:30080
```

**Nunca `:latest` no cluster.** O `k8s/deployment.yml` traz `:latest` só como valor padrão;
os scripts trocam por uma tag imutável (`sha-<commit>` ou `local-<data>`) **antes** do
`kubectl apply`, então cada deploy é rastreável e tem rollback. O `deploy.sh` reverte
sozinho se o rollout não completar e recusa fazer deploy de `latest`.

> **Ordem importa:** as probes usam `/health` e `/ready`. O `deploy.sh` usa a imagem que o
> CI publicou para o commit atual, então rode-o **depois** do pipeline ficar verde.

O que há em `k8s/`:

| Manifesto | Para quê |
|---|---|
| `deployment.yml` | API: rolling update sem indisponibilidade, probes startup/liveness/readiness, contexto de segurança restrito |
| `hpa.yml` | Autoescala 2 a 5 réplicas por CPU (precisa de `minikube addons enable metrics-server`) |
| `pdb.yml` | Mantém ao menos 1 pod durante manutenção do nó (`kubectl drain`) |
| `redis-pvc.yml` + `redis-deployment.yml` | Redis com volume persistente (AOF): o contador sobrevive à recriação do pod |
| `networkpolicy.yml` | Só os pods da API falam com o Redis (efeito só com CNI que aplique, ex.: `minikube start --cni=calico`) |

O workflow `k8s-e2e.yml` valida tudo isso num cluster **kind** efêmero a cada PR,
inclusive que derrubar o Redis **não reinicia** os pods da API.

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

## CI/CD

**`ci.yml`** (push em `main`, tags `v*.*.*` e PRs):

1. **test**: pytest, testes unitários dos alertas (`promtool test rules`), `promtool check config`,
   `amtool check-config`, PrometheusRule em sincronia, `shellcheck`, `kubeconform` nos manifests,
   `docker compose config`.
2. **smoke-test**: sobe a stack inteira e confere requisições reais, `/metrics` fechado no Nginx,
   Prometheus coletando a API, Alertmanager conectado, regras de SLO carregadas e logs JSON.
3. **build**: constrói a imagem com **SBOM e provenance**. O **push só acontece fora de pull request**
   (merge em `main` ou tag `vX.Y.Z`).

**`security.yml`** (PR, push, e toda segunda-feira): `pip-audit` nas dependências (falha se achar
vulnerabilidade) e Trivy na imagem e nas configs (só relatório por enquanto). Roda sem secrets.
O Trivy é usado via container na **0.69.3**, versão segura pelo aviso GHSA-69fq-xp46-6x23
(releases 0.69.4 a 0.69.6 e as tags antigas da `trivy-action` foram comprometidas em março de 2026).

**`k8s-e2e.yml`** (PRs que mexem em `k8s/`, `app/` ou `Dockerfile`): cluster kind efêmero.

**Dependabot** abre PRs semanais para actions, dependências Python, Dockerfile e Compose.

Tags geradas: `latest` (só na branch padrão), `sha-<commit>` e, em tags, `1.2.3` / `1.2`.
Secrets necessários: `DOCKER_USERNAME`, `DOCKER_PASSWORD`.

## Fora do escopo (por enquanto)

Ideias que fazem sentido, mas que exigem infraestrutura que este lab não tem:
GitOps com Argo CD/Flux (precisa de um cluster alcançável), Terraform (precisa de uma nuvem),
tracing com OpenTelemetry e agregação de logs com Loki (mais serviços na stack, e o WSL2 tem
pouca RAM), Helm/Kustomize e assinatura de imagem com cosign.
