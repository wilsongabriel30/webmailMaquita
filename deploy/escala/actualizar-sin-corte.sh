#!/bin/bash
# =============================================================================
# Reinicio escalonado («rolling») de las réplicas del webmail, sin corte.
#
# Para cada réplica, UNA A UNA:
#   1. la «drena»: crea su archivo de drenaje → /api/listo responde 503 y el
#      balanceador deja de mandarle peticiones nuevas;
#   2. espera ESPERA_DRENAJE segundos a que terminen las que tenía en curso;
#   3. (opcional) ejecuta PASO_PREVIO en esa réplica (p. ej. instalar dependencias);
#   4. reinicia su servicio de systemd;
#   5. espera a que /api/salud responda, quita el drenaje y espera /api/listo = 200;
#   6. solo entonces pasa a la siguiente. Si una réplica no vuelve, SE DETIENE y
#      deja las demás como estaban (siguen sirviendo con la versión anterior).
#
# Réplicas: REPLICAS="destino1 destino2 ..." donde cada destino es
#     host[:puerto[:servicio[:archivo_drenaje]]]
#   host = «local» para esta máquina; cualquier otro nombre se usa por SSH (root,
#   con clave pública). Valores por defecto: puerto 8000, servicio maquita-webmail,
#   drenaje /run/maquita-webmail/drenar.
#
# Ejemplos:
#   # Dos nodos de aplicación detrás de HAProxy:
#   REPLICAS="app1.example.org app2.example.org" deploy/escala/actualizar-sin-corte.sh
#   # Dos instancias en la misma máquina (unidad plantilla maquita-webmail@.service):
#   REPLICAS="local:8001:maquita-webmail@8001:/run/maquita-webmail/drenar-8001 \
#             local:8002:maquita-webmail@8002:/run/maquita-webmail/drenar-8002" \
#     deploy/escala/actualizar-sin-corte.sh
#   # Ver qué haría sin tocar nada:
#   deploy/escala/actualizar-sin-corte.sh --simular
#
# Con UNA sola réplica (la instalación de serie) no hay a quién pasar el tráfico:
# el script reinicia igual, pero avisa de que habrá un corte de unos segundos.
# Detalle y topología: docs/GRAN-ESCALA.md
# =============================================================================
set -u

REPLICAS="${REPLICAS:-local}"
ESPERA_DRENAJE="${ESPERA_DRENAJE:-10}"   # segundos para vaciar peticiones en curso
TIEMPO_MAX="${TIEMPO_MAX:-120}"          # segundos máximos para que una réplica vuelva
PASO_PREVIO="${PASO_PREVIO:-}"           # comando a ejecutar en la réplica antes de reiniciar
SIMULAR=0
[ "${1:-}" = "--simular" ] && SIMULAR=1

ROJO='\033[0;31m'; VERDE='\033[0;32m'; AMARILLO='\033[1;33m'; NC='\033[0m'
info() { echo -e "${VERDE}▶${NC} $*"; }
aviso() { echo -e "${AMARILLO}!${NC} $*"; }
error() { echo -e "${ROJO}✗${NC} $*" >&2; }

# Ejecuta un comando en la réplica (local o por SSH).
en_replica() {
    local host="$1"; shift
    if [ "$SIMULAR" = 1 ]; then
        echo "    [simulación] ($host) $*"
        return 0
    fi
    if [ "$host" = "local" ]; then
        bash -c "$*"
    else
        ssh -o BatchMode=yes -o ConnectTimeout=10 "root@$host" "$*"
    fi
}

# Código HTTP de una ruta de la réplica, consultada DESDE la propia réplica
# (el puerto de la aplicación solo escucha en 127.0.0.1).
codigo_http() {
    local host="$1" puerto="$2" ruta="$3"
    if [ "$SIMULAR" = 1 ]; then echo 200; return; fi
    en_replica "$host" "curl -s -o /dev/null -m 5 -w '%{http_code}' http://127.0.0.1:${puerto}${ruta}" 2>/dev/null || echo 000
}

esperar_codigo() {
    local host="$1" puerto="$2" ruta="$3" deseado="$4" limite=$((SECONDS + TIEMPO_MAX))
    while [ $SECONDS -lt $limite ]; do
        [ "$(codigo_http "$host" "$puerto" "$ruta")" = "$deseado" ] && return 0
        sleep 2
    done
    return 1
}

total=$(echo "$REPLICAS" | wc -w)
if [ "$total" -lt 2 ]; then
    aviso "Solo hay una réplica: mientras se reinicia el servicio no hay otra que atienda (corte de unos segundos)."
    aviso "Para actualizar sin corte hacen falta 2+ réplicas detrás del balanceador (docs/GRAN-ESCALA.md)."
fi

# Antes de tocar nada: todas tienen que estar listas. Reiniciar una cuando otra ya
# está caída dejaría el servicio sin nadie.
for destino in $REPLICAS; do
    IFS=: read -r host puerto servicio drenaje <<< "$destino"
    puerto="${puerto:-8000}"
    if [ "$(codigo_http "$host" "$puerto" /api/listo)" != 200 ]; then
        error "La réplica $destino no está lista (/api/listo ≠ 200). Arréglala antes de actualizar."
        exit 1
    fi
done

n=0
for destino in $REPLICAS; do
    n=$((n + 1))
    IFS=: read -r host puerto servicio drenaje <<< "$destino"
    puerto="${puerto:-8000}"
    servicio="${servicio:-maquita-webmail}"
    drenaje="${drenaje:-/run/maquita-webmail/drenar}"
    info "[$n/$total] $host · puerto $puerto · servicio $servicio"

    en_replica "$host" "mkdir -p '$(dirname "$drenaje")' && touch '$drenaje'" || { error "No se pudo drenar $destino"; exit 1; }
    if [ "$total" -ge 2 ]; then
        echo "    drenando ${ESPERA_DRENAJE}s (el balanceador deja de enviarle tráfico)…"
        [ "$SIMULAR" = 1 ] || sleep "$ESPERA_DRENAJE"
    fi

    if [ -n "$PASO_PREVIO" ]; then
        echo "    paso previo: $PASO_PREVIO"
        if ! en_replica "$host" "$PASO_PREVIO"; then
            error "Falló el paso previo en $destino. La réplica sigue drenada y con la versión anterior."
            en_replica "$host" "rm -f '$drenaje'"
            exit 1
        fi
    fi

    echo "    reiniciando $servicio…"
    en_replica "$host" "systemctl restart '$servicio'" || { error "systemctl restart falló en $destino"; exit 1; }

    if ! esperar_codigo "$host" "$puerto" /api/salud 200; then
        error "$destino no responde en /api/salud tras ${TIEMPO_MAX}s. Se detiene la actualización (las demás réplicas no se tocan)."
        en_replica "$host" "journalctl -u '$servicio' -n 30 --no-pager" || true
        exit 1
    fi
    en_replica "$host" "rm -f '$drenaje'"
    if ! esperar_codigo "$host" "$puerto" /api/listo 200; then
        error "$destino arrancó pero no está lista (base o Redis). Se detiene la actualización."
        exit 1
    fi
    echo -e "    ${VERDE}lista${NC}"
done

info "Actualización escalonada terminada: $total réplica(s) reiniciada(s) sin perder ninguna a la vez."
