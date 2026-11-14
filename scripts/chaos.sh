#!/usr/bin/env bash
# Experimentos de falha controlada. Cada um gera tráfego, provoca a falha, restaura e
# mostra a distribuição de status HTTP. Anote o que observou em docs/postmortems/.
#
# Uso:
#   ./scripts/chaos.sh redis-down [segundos]   # Compose: derruba o Redis
#   ./scripts/chaos.sh app-restart             # Compose: reinicia a API
#   ./scripts/chaos.sh kill-pod                # Kubernetes: mata 1 pod da API (precisa de 2+)
set -euo pipefail
cd "$(dirname "$0")/.."

URL="${URL:-http://localhost}"

# Manda requisições por $1 segundos e imprime a contagem por status HTTP.
traffic() {
  local secs="$1" end=$((SECONDS + $1))
  while (( SECONDS < end )); do
    curl -s -o /dev/null -m 2 -w '%{http_code}\n' "$URL/" || echo "ERR"
    sleep 0.1
  done | sort | uniq -c | sort -rn
}

case "${1:-}" in
  redis-down)
    secs="${2:-20}"
    echo ">> Derrubando o Redis por ${secs}s (esperado: 503 enquanto estiver fora)"
    docker compose stop redis
    traffic "$secs"
    docker compose start redis
    echo ">> Redis de volta. Aguardando recuperação..."
    sleep 5
    echo "Status final de /:"; curl -s -o /dev/null -w '%{http_code}\n' "$URL/"
    echo "Veja o alerta RedisErrors em http://localhost:9090/alerts"
    ;;
  app-restart)
    echo ">> Reiniciando a API (esperado: alguns 502 do Nginx durante o restart)"
    ( sleep 2; docker compose restart web >/dev/null ) &
    traffic 20
    wait
    ;;
  kill-pod)
    command -v kubectl >/dev/null || { echo "kubectl não encontrado" >&2; exit 1; }
    kubectl port-forward svc/devops-lab-service 8080:80 >/dev/null 2>&1 &
    PF=$!
    trap 'kill $PF 2>/dev/null || true' EXIT
    sleep 3
    URL="http://localhost:8080"
    POD="$(kubectl get pods -l app=devops-lab -o jsonpath='{.items[0].metadata.name}')"
    echo ">> Matando o pod $POD. Com 2+ réplicas o esperado é 100% de 200 (a conexão do"
    echo "   port-forward pode cair se ela estava presa justamente nesse pod)."
    ( sleep 3; kubectl delete pod "$POD" --wait=false >/dev/null ) &
    traffic 25
    wait
    kubectl get pods -l app=devops-lab
    ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
