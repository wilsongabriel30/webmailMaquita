#!/usr/bin/env bash
# probar-ia.sh — prueba la IA configurada. Imprime "IA OK" o el error + causa + solucion.
# Uso: bash deploy/webmail/probar-ia.sh [ruta-al-.env]
set -uo pipefail
ENV_FILE="${1:-/opt/maquita-webmail/backend/.env}"
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a
PROV="${IA_PROVIDER:-}"; BASE="${IA_BASE_URL:-${OLLAMA_URL:-}}"; MODEL="${IA_MODEL:-}"; KEY="${IA_API_KEY:-}"
if [ -z "$PROV" ] && [ -z "$BASE" ]; then
  echo "IA no configurada (opcional) — la app funciona igual (fail-open)."
  echo "Para activarla: descomenta un preset en backend/.env y vuelve a correr este script."
  exit 0
fi
echo "Probando IA -> provider=$PROV base=$BASE model=$MODEL"
case "$PROV" in
  ollama)    R=$(curl -s -m 30 "$BASE/api/generate" -H "content-type: application/json" -d "{\"model\":\"$MODEL\",\"prompt\":\"responde solo: OK\",\"stream\":false}") ;;
  anthropic) R=$(curl -s -m 30 "$BASE/v1/messages" -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d "{\"model\":\"$MODEL\",\"max_tokens\":10,\"messages\":[{\"role\":\"user\",\"content\":\"responde solo: OK\"}]}") ;;
  gateway|custom) R=$(curl -s -m 30 "$BASE/api/v1/ia/generate" -H "X-API-Key: $KEY" -H "content-type: application/json" -d "{\"prompt\":\"responde solo: OK\",\"model\":\"$MODEL\",\"max_tokens\":10}") ;;
  *)         R=$(curl -s -m 30 "$BASE/v1/chat/completions" -H "Authorization: Bearer $KEY" -H "content-type: application/json" -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"responde solo: OK\"}],\"max_tokens\":10}") ;;
esac
if echo "$R" | grep -qiE "respuesta|response|\"content\"|choices|\"text\""; then
  echo "IA OK"
  exit 0
fi
echo "IA ERROR. Respuesta: ${R:0:200}"
echo "  Causa probable: endpoint/modelo/clave incorrectos o servicio de IA caido."
echo "  Solucion: 1) curl $BASE debe responder  2) el modelo '$MODEL' debe existir  3) revisa IA_API_KEY."
exit 1
