#!/usr/bin/env bash
# Enrutamiento de correo por dominio (2026-10-21, v1.11): MX de respaldo y reenvío a otro servidor,
# configurados en el panel general (Dominios → Enrutamiento) y leídos por Postfix desde la base.
#
# Instala los cuatro mapas pgsql-enrutamiento-*.cf (con la conexión del mapa de dominios que ya
# usa el servidor), excluye de virtual_mailbox_domains los dominios con enrutamiento activo y
# añade relay_domains, relay_recipient_maps, transport_maps y smtp_tls_policy_maps.
#
# No se aplica si el servidor podría quedar como relé abierto: exige reject_unauth_destination o
# defer_unauth_destination en las restricciones y que mynetworks no abarque Internet entera. Con
# relay_recipient_maps siempre puesto, un dominio solo acepta lo que su lista (o «@dominio») admite.
set -euo pipefail
CONF="${POSTFIX_CONF:-/etc/postfix}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLANTILLAS="${REPO}/deploy/webmail/configs/postfix-pgsql"
MARCA="enrutamiento_correo"
pc() { postconf -c "$CONF" "$@" 2>/dev/null; }

dominios_map="$(pc -nh virtual_mailbox_domains | tr ', ' '\n\n' | sed -n 's/^\(proxy:\)\{0,1\}pgsql://p' | head -1)"
if [ -z "$dominios_map" ] || [ ! -f "$dominios_map" ]; then
  echo "Sin cambios: virtual_mailbox_domains no es un mapa pgsql de este servidor; el enrutamiento necesita la base."
  exit 0
fi
DIR_MAPAS="$(dirname "$dominios_map")"

# --- Antes de nada: que no pueda quedar un relé abierto ---
restricciones="$(pc -xh smtpd_relay_restrictions)"
[ -n "$restricciones" ] || restricciones="$(pc -xh smtpd_recipient_restrictions)"
cierre=0; permiso_suelto=0
for r in $(tr ',' ' ' <<<"$restricciones"); do
  case "$r" in
    reject_unauth_destination|defer_unauth_destination) cierre=1; break ;;
    permit) permiso_suelto=1; break ;;
  esac
done
if [ "$cierre" = 0 ] || [ "$permiso_suelto" = 1 ]; then
  echo "No se aplica: smtpd_relay_restrictions no rechaza los destinos no autorizados (falta reject_unauth_destination o hay un «permit» antes). Con relay_domains el servidor sería un relé abierto." >&2
  exit 1
fi
if tr ', ' '\n\n' <<<"$(pc -xh mynetworks)" | grep -qxE '0\.0\.0\.0/0|0/0|\[::\]/0|::/0|\[::/0\]'; then
  echo "No se aplica: mynetworks abarca todas las direcciones; cualquiera podría usar el servidor de relé." >&2
  exit 1
fi

# --- Mapas: conexión del mapa de dominios + consulta de la plantilla ---
mapa_esperado() {
  local plantilla="$PLANTILLAS/$1"
  grep -E '^#' "$plantilla"
  grep -E '^(hosts|user|password|dbname)[[:space:]]*=' "$dominios_map"
  grep -E '^query[[:space:]]*=' "$plantilla"
}
MAPAS=(pgsql-enrutamiento-dominios.cf pgsql-enrutamiento-destinatarios.cf pgsql-enrutamiento-transporte.cf pgsql-enrutamiento-tls.cf)
pendiente=()
for m in "${MAPAS[@]}"; do
  [ "$(mapa_esperado "$m")" = "$(cat "$DIR_MAPAS/$m" 2>/dev/null)" ] || pendiente+=("mapa $DIR_MAPAS/$m")
done

# El mapa de dominios solo se toca si su consulta admite la condición al final (sin GROUP, ORDER…).
CONDICION=" AND NOT EXISTS (SELECT 1 FROM ${MARCA} e WHERE e.dominio = '%s' AND e.activo)"
consulta="$(grep -E '^query[[:space:]]*=' "$dominios_map" | tail -1)"
tocar_dominios=0
if ! grep -q "$MARCA" <<<"$consulta"; then
  if ! grep -qiE '^query[[:space:]]*=[[:space:]]*SELECT .* WHERE ' <<<"$consulta" \
     || grep -qiE 'group by|order by|having|limit|union|;' <<<"$consulta"; then
    echo "No se aplica: la consulta de $dominios_map no tiene la forma esperada. Añada a mano al final de su WHERE:${CONDICION}" >&2
    exit 1
  fi
  tocar_dominios=1; pendiente+=("excluir de virtual_mailbox_domains los dominios con enrutamiento ($dominios_map)")
fi

# --- Parámetros: el mapa propio delante (transporte y TLS) o detrás (dominios y destinatarios) ---
declare -A NUEVO=()
for par in "relay_domains:pgsql-enrutamiento-dominios.cf:detras" "relay_recipient_maps:pgsql-enrutamiento-destinatarios.cf:detras" \
           "transport_maps:pgsql-enrutamiento-transporte.cf:delante" "smtp_tls_policy_maps:pgsql-enrutamiento-tls.cf:delante"; do
  IFS=: read -r nombre archivo lugar <<<"$par"
  propio="pgsql:$DIR_MAPAS/$archivo"
  actual="$(pc -nh "$nombre")"
  grep -qF "$propio" <<<"$actual" && continue
  if [ -z "$actual" ]; then NUEVO[$nombre]="$propio"
  elif [ "$lugar" = delante ]; then NUEVO[$nombre]="$propio, $actual"
  else NUEVO[$nombre]="$actual, $propio"; fi
  pendiente+=("$nombre = ${NUEVO[$nombre]}")
done

if [ "${#pendiente[@]}" -eq 0 ]; then echo "Sin cambios: el enrutamiento de correo ya está configurado."; exit 0; fi
printf 'Pendiente: %s\n' "${pendiente[@]}"
[ "${1:-}" = "--simular" ] && exit 0

# --- Las tablas tienen que existir antes de que Postfix las consulte (si no, difiere TODO el correo) ---
if [ "$CONF" = /etc/postfix ]; then
  valor() { grep -E "^$1[[:space:]]*=" "$dominios_map" | tail -1 | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]*$//'; }
  host="$(valor hosts | awk '{print $1}')"; host="${host#inet:}"; host="${host#unix:}"
  existe="$(PGPASSWORD="$(valor password)" psql -X -At -h "${host:-localhost}" -U "$(valor user)" -d "$(valor dbname)" \
            -c "SELECT to_regclass('public.${MARCA}') IS NOT NULL AND to_regclass('public.enrutamiento_destinatarios') IS NOT NULL" 2>/dev/null || true)"
  if [ "$existe" != t ]; then
    echo "No se aplica todavía: faltan las tablas de enrutamiento en la base. Aplique antes las migraciones (migrations/2026-10-21-enrutamiento-correo.sql)." >&2
    exit 1
  fi
fi

sello="$(date +%Y%m%d_%H%M%S)"
cp -a "$CONF/main.cf" "$CONF/main.cf.bak.$sello"
cp -a "$dominios_map" "$dominios_map.bak.$sello"
deshacer() {
  cp -a "$CONF/main.cf.bak.$sello" "$CONF/main.cf"
  cp -a "$dominios_map.bak.$sello" "$dominios_map"
  echo "Se dejó todo como estaba (copias: *.bak.$sello)." >&2
}
for m in "${MAPAS[@]}"; do
  [ -f "$DIR_MAPAS/$m" ] && cp -a "$DIR_MAPAS/$m" "$DIR_MAPAS/$m.bak.$sello"
  mapa_esperado "$m" > "$DIR_MAPAS/$m.nuevo"
  chmod 640 "$DIR_MAPAS/$m.nuevo"
  chgrp postfix "$DIR_MAPAS/$m.nuevo" 2>/dev/null || true
  mv -f "$DIR_MAPAS/$m.nuevo" "$DIR_MAPAS/$m"
done
if [ "$tocar_dominios" = 1 ]; then
  sed -i -E "/^query[[:space:]]*=/ s/[[:space:]]*\$/${CONDICION//\//\\/}/" "$dominios_map"
fi
for nombre in "${!NUEVO[@]}"; do pc -e "$nombre = ${NUEVO[$nombre]}"; done

if [ "$CONF" = /etc/postfix ]; then
  for m in "${MAPAS[@]}" "$(basename "$dominios_map")"; do
    salida="$(postmap -q "comprobacion.invalid" "pgsql:$DIR_MAPAS/$m" 2>&1 || true)"
    if grep -qiE 'fatal|error|warning' <<<"$salida"; then
      echo "Error: el mapa $m no responde bien (postmap -q)." >&2; deshacer; exit 1
    fi
  done
  if ! postfix check; then echo "Error: postfix check rechaza la configuración." >&2; deshacer; exit 1; fi
  postfix reload
fi
echo "Listo: enrutamiento de correo (MX de respaldo y reenvío) configurado; se gestiona en Dominios → Enrutamiento."
