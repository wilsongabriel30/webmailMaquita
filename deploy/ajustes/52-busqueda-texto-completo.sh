#!/usr/bin/env bash
# Búsqueda de texto completo del correo (2026-10-20): Dovecot con fts-flatcurve, índice de los correos
# nuevos al llegar y del correo antiguo de noche, más la caché nocturna para buscar por adjunto.
# Sin índice, buscar en un buzón grande recorre todos los mensajes y pasa de la espera del webmail.
# Todo el trabajo lo hace deploy/dovecot/busqueda/instalar.sh (el mismo que usa el instalador).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$DIR/../dovecot/busqueda/instalar.sh" "$@"
