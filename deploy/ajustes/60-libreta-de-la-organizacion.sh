#!/usr/bin/env bash
# Libreta de la organización en ActiveSync (2026-10-21). Al escribir un destinatario en el teléfono,
# Z-Push buscaba en una colección «GAL» de CardDAV que Radicale no tiene y respondía 403: no aparecía
# nadie. Ahora busca en el directorio de buzones activos del propio dominio (BackendSearchMaquita).
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$APP_DIR/deploy/z-push/directorio/instalar.sh" "$@"
