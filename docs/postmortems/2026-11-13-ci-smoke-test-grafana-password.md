# Postmortem: smoke test do CI falhando por `GRAFANA_ADMIN_PASSWORD`

- **Data:** 2026-11-13
- **Duração do impacto:** 2 execuções consecutivas do pipeline em `main` falharam
  (pipeline vermelho por cerca de 20 minutos, do primeiro run vermelho até o fix; nenhum impacto em produção: o deploy é manual)
- **Severidade:** baixa (só CI)
- **Estado:** resolvido (commit `09ec129`)

> Sem culpados: o objetivo é entender como o sistema permitiu a falha.

## Resumo
O job "Smoke test da stack" falhava porque a variável `GRAFANA_ADMIN_PASSWORD` era
definida só no comando `docker compose up`, via prefixo inline. Os demais comandos do
mesmo job (`docker compose logs`, `docker compose down -v`) rodavam sem ela.

## Causa raiz
O `docker-compose.yml` exige a variável de propósito (`${GRAFANA_ADMIN_PASSWORD:?...}`,
sem valor padrão, para ninguém subir o Grafana com senha conhecida). O Compose resolve
essa interpolação em **todo** subcomando, não só no `up`. Como a variável estava
presa a um único `run:`, o passo `down -v` (que roda com `if: always()`) encontrava a
variável vazia e falhava, derrubando o job.

Por que não pegamos antes: o ambiente local tem a variável no `.env`, então o problema
só aparece no runner, que não tem `.env`.

## Detecção
Pelo status vermelho do pipeline (`gh run list`). Detecção manual; nenhum alerta
automático (nem faz sentido para CI), mas o ciclo de feedback foi curto.

## Correção
Mover a variável para `env:` no nível do **job**, valendo para todos os steps:

```yaml
smoke-test:
  env:
    GRAFANA_ADMIN_PASSWORD: ci
```

Verificação: execução seguinte verde nos três jobs (testes, smoke test, build).

## O que funcionou
- A exigência de senha explícita no Compose é um bom default de segurança.
- O smoke test faz exatamente o que deve: pegou um problema que os testes unitários
  não pegam, antes de chegar a qualquer ambiente.

## Ações
| Ação | Tipo | Estado |
|---|---|---|
| Variável no nível do job | mitigar/prevenir | feito |
| `.env` ignorado no Git (e conferido que nunca foi versionado) | prevenir | feito |
| Preferir `env:` no nível do job a variáveis inline quando vários comandos do Compose rodam no mesmo job | prevenir | convenção adotada |
| Rodar o Compose sem `.env` localmente antes de abrir PR (`env -u GRAFANA_ADMIN_PASSWORD docker compose config`) | detectar | sugerido |

## Notas de confirmação
O diagnóstico acima é a explicação consistente com o conserto aplicado e com o
comportamento do Compose. Para anexar a evidência exata, rode:
`gh run view --log-failed <id-do-run-vermelho>` e cole a linha de erro aqui.
