#!/usr/bin/env bash
# Búsqueda en el texto de los adjuntos (2026-10-21): el índice de texto completo (ajuste 52) pasa a
# incluir PDF, documentos de Office y LibreOffice, RTF, HTML, comprimidos con tope (ZIP, TAR, 7z…) y
# metadatos EXIF; la papelera y el no deseado dejan de indexarse al llegar; el panel muestra el estado
# del índice y permite reindexar un buzón. Lanza, en segundo plano y con prioridad mínima, la
# indexación de los buzones que aún no tienen índice. Respalda dovecot.conf y valida con doveconf -n.
# Todo el trabajo lo hace deploy/dovecot/fts/instalar.sh (el mismo que usa el instalador).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$DIR/../dovecot/fts/instalar.sh" "$@"
