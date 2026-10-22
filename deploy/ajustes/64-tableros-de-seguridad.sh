#!/usr/bin/env bash
# Tableros de seguridad del panel general (2026-10-21, v1.11: Seguridad → Tableros). Los servidores ya
# instalados no tienen el recolector que agrega cada 5 minutos el flujo de correo, los inicios de
# sesión y las anomalías en tablas propias (sin él, los tableros salen vacíos). Aquí se crean las
# tablas si faltan, se instala maxminddb en el entorno del panel y se activa el temporizador.
# Lo hace deploy/seguridad/instalar.sh, que es el mismo que usa el instalador.
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
exec bash "$APP_DIR/deploy/seguridad/instalar.sh" "$@"
