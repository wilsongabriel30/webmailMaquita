#!/usr/bin/env bash
# Pruebas de humo del correo: corre todas (o las indicadas) y dice OK / FALLO / OMITIDA de cada una.
#
# Uso:  HUMO_URL=https://mail.example.org bash deploy/pruebas-humo/ejecutar.sh [opciones] [prueba ...]
#   --token T       usar este access_token (si no, se abre la sesión de pruebas con sesion_prueba.py,
#                   lo que solo funciona en el propio servidor del correo)
#   --navegador     solo las pruebas con navegador (necesitan Python con Playwright y Chromium)
#   --servidor      solo las pruebas de API que corren en el servidor (calendario, reuniones, tareas)
#   --listar        muestra las pruebas disponibles
# Ejemplo: bash ejecutar.sh offline secciones      → solo humo_offline.py y humo_secciones.py
# Variables: ver comun.py (también se leen de /etc/maquita-humo.env). Detalle: README.md
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="${HUMO_BACKEND:-/opt/maquita-webmail/backend}"
PY_SERVIDOR="$BACKEND/venv/bin/python"; [ -x "$PY_SERVIDOR" ] || PY_SERVIDOR=python3
PY_NAVEGADOR="${HUMO_PYTHON:-python3}"
TIEMPO="${HUMO_TIEMPO:-240}"
TOKEN="${HUMO_TOKEN:-}"; GRUPOS="navegador servidor"; ELEGIDAS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --token) TOKEN="${2:-}"; shift 2 ;;
    --navegador) GRUPOS="navegador"; shift ;;
    --servidor) GRUPOS="servidor"; shift ;;
    --listar) for g in navegador servidor; do for f in "$DIR/$g"/humo_*.py; do
                n="$(basename "$f" .py)"; echo "$g  ${n#humo_}"; done; done; exit 0 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) ELEGIDAS+=("$1"); shift ;;
  esac
done

elegida() {  # ¿hay que correr esta prueba?
  [ "${#ELEGIDAS[@]}" -eq 0 ] && return 0
  local e; for e in "${ELEGIDAS[@]}"; do [ "$e" = "$1" ] && return 0; done; return 1
}

if [ -z "$TOKEN" ] && [[ "$GRUPOS" == *navegador* ]]; then
  TOKEN="$("$PY_SERVIDOR" "$DIR/sesion_prueba.py" 2>/dev/null | tail -1)"
  [ -n "$TOKEN" ] || echo "Aviso: no se pudo abrir la sesión de pruebas (pase --token o corra en el servidor)."
fi
navegador_ok=1; "$PY_NAVEGADOR" -c "import playwright" 2>/dev/null || navegador_ok=0

ok=0; fallo=0; omitida=0; resumen=()
for g in $GRUPOS; do
  for f in "$DIR/$g"/humo_*.py; do
    n="$(basename "$f" .py)"; n="${n#humo_}"
    elegida "$n" || continue
    if [ "$g" = navegador ] && { [ "$navegador_ok" = 0 ] || [ -z "$TOKEN" ]; }; then
      omitida=$((omitida+1)); resumen+=("OMITIDA  $n (sin Playwright o sin sesión)"); continue
    fi
    printf '\n\033[1m== %s ==\033[0m\n' "$n"
    if [ "$g" = navegador ]; then timeout "$TIEMPO" "$PY_NAVEGADOR" "$f" "$TOKEN"; rc=$?
    else (cd "$BACKEND" 2>/dev/null || true; timeout "$TIEMPO" "$PY_SERVIDOR" "$f"); rc=$?; fi
    if [ "$rc" -eq 0 ]; then ok=$((ok+1)); resumen+=("OK       $n")
    else fallo=$((fallo+1)); resumen+=("FALLO    $n (código $rc)"); fi
  done
done

printf '\n\033[1m== Resumen ==\033[0m\n'; printf '%s\n' "${resumen[@]}"
echo "OK: $ok · FALLO: $fallo · OMITIDA: $omitida"
[ "$fallo" -eq 0 ]
