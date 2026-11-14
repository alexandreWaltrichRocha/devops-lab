# SLOs do devops-lab

Objetivos de confiabilidade da API, as métricas que os medem (SLIs) e como os
alertas se ligam a eles. Os números são de um laboratório: o importante é o método.

## Definições

| | SLI (o que medimos) | SLO (a meta) | Janela |
|---|---|---|---|
| **Disponibilidade** | Requisições sem status 5xx ÷ total de requisições | **99,5%** | 30 dias |
| **Latência** | Requisições respondidas em até 250ms ÷ total | **95%** | 30 dias |

Fonte dos dados: `http_requests_total` e `http_request_duration_seconds` (veja
`app/main.py`). Requisições a `/health` e `/metrics` não são contadas, então
probes e scrapes não distorcem o SLI. `/ready` é contada.

Respostas 4xx **não** consomem o orçamento: são erro do cliente, não da API.

## Orçamento de erro

Com 99,5% em 30 dias, o orçamento é **0,5%** das requisições (≈ 3h36min de
indisponibilidade total equivalente por mês). Para a latência, 5%.

Enquanto houver orçamento, pode-se lançar mudanças. Se acabar, o foco passa a ser
confiabilidade (congelar features de risco, corrigir a causa dos erros).

## Alertas (burn rate)

Em vez de "erro acima de X% por 1 minuto", alertamos pela **velocidade** com que o
orçamento é consumido (*burn rate*: 1x = gasta o orçamento exatamente em 30 dias).
Cada alerta exige duas janelas, uma longa (confirma que é sério) e uma curta
(confirma que ainda está acontecendo e para de alertar logo após a correção).

| Alerta | Burn | Janelas | Esgota o orçamento em | Severidade |
|---|---|---|---|---|
| `ErrorBudgetBurnFast` | 14,4x | 1h e 5m | ~2 dias | critical (acordar) |
| `ErrorBudgetBurnSlow` | 6x | 6h e 30m | ~5 dias | critical |
| `ErrorBudgetBurnSteady` | 1x | 3d e 6h | 30 dias | warning (ticket) |
| `LatencyBudgetBurn` | 6x | 1h e 5m | ~5 dias | warning |
| `AppDown` | – | scrape falhou 30s | – | critical |
| `RedisErrors` | – | qualquer erro por 30s | – | critical |

Todos (menos `AppDown` e `RedisErrors`) só disparam com tráfego mínimo de
~36 req/h, para uma única requisição com erro não gerar um *page*.

Referência: Google SRE Workbook, capítulo 5 ("Alerting on SLOs").

## Onde está cada coisa

- Regras e alertas: `prometheus/alerts.yml` (fonte da verdade).
- Testes unitários dos alertas: `prometheus/tests/alerts_test.yml`
  (`promtool test rules`, roda no CI).
- Versão para Kubernetes/Operator: `k8s/monitoring/prometheusrule.yml`, **gerada** por
  `python scripts/sync_rules.py` (o CI falha se divergir).
- Roteamento/notificação: `alertmanager/alertmanager.yml`.
- O que fazer quando dispara: `docs/runbooks/`.

## Limitações conhecidas

- Com tráfego de laboratório (poucas requisições) a guarda de volume mantém os
  alertas de burn rate quietos; para vê-los disparar use `scripts/loadtest.sh` e
  `scripts/chaos.sh`.
- O orçamento de 30 dias depende do Prometheus reter dados por 30 dias; o Compose
  retém 15. Os alertas usam no máximo janelas de 3 dias, então funcionam, mas um
  painel de "orçamento restante em 30 dias" exigiria aumentar a retenção.
