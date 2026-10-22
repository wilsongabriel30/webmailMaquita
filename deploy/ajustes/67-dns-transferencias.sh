#!/usr/bin/env bash
# Transferencias de zona a secundarios en la configuración (2026-10-21). Desde ahora allow-transfer y
# also-notify de las zonas del panel salen de /etc/maquita-dns/servidor.json («maquita-dns servidor
# --transferir-a …»), que las actualizaciones no tocan. Quien parcheaba zona.py a mano tiene esos valores
# solo en /etc/bind/maquita-zonas.conf, y la siguiente zona nueva los borraría: aquí se pasan a la
# configuración (lo más repetido como global; las zonas distintas, con ajuste propio) y se comprueba con
# named-checkconf. Con claves TSIG o listas de control con nombre no se toca nada: se pide revisarlo.
# Sin secundarios declarados no hace falta nada (sin configuración = comportamiento de siempre).
set -euo pipefail
DNS="$(cd "$(dirname "$0")/../dns" && pwd)/maquita-dns"
[ -f /etc/bind/maquita-zonas.conf ] && [ -d /etc/maquita-dns ] || { echo "Sin cambios: este servidor no usa las Zonas DNS del panel."; exit 0; }
command -v python3 >/dev/null || { echo "Error: falta python3." >&2; exit 1; }

campo() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1]) or "")' "$1"; }

salida="$(python3 "$DNS" transferencias-importar --simular)" || { echo "Error: $(campo error <<<"$salida")" >&2; exit 1; }
estado="$(campo estado <<<"$salida")"
case "$estado" in
  sin-cambios) echo "Sin cambios: $(campo motivo <<<"$salida")."; exit 0 ;;
  revisar)
    echo "Sin cambios: $(campo motivo <<<"$salida"). Configúrelo con «maquita-dns servidor --transferir-a … --notificar-a … [--tsig generar]» (docs/CONFIGURAR-DNS.md)."
    exit 0 ;;
  pendiente) ;;
  *) echo "Error: respuesta inesperada: $salida" >&2; exit 1 ;;
esac
echo "Pendiente: pasar a la configuración las transferencias que ya declara BIND ($(python3 -c 'import json,sys; d=json.load(sys.stdin); g=d["global"]; print("transferir a: " + (", ".join(g["transferir_a"]) or "nadie") + "; avisar a: " + (", ".join(g["notificar_a"]) or "nadie") + ("; zonas con ajuste propio: " + ", ".join(d["zonas_con_ajuste_propio"]) if d["zonas_con_ajuste_propio"] else ""))' <<<"$salida"))."
[ "${1:-}" = "--simular" ] && exit 0

cp -a /etc/bind/maquita-zonas.conf "/etc/bind/maquita-zonas.conf.antes-67-$(date +%Y%m%d%H%M%S)"
salida="$(python3 "$DNS" transferencias-importar)" || { echo "Error: $(campo error <<<"$salida") (BIND sigue con lo anterior)." >&2; exit 1; }
[ "$(campo estado <<<"$salida")" = "listo" ] || { echo "Error: $salida" >&2; exit 1; }
echo "Listo: transferencias en /etc/maquita-dns/servidor.json; «maquita-dns servidor» las muestra."
