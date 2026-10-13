#!/usr/bin/env bash
# Envíos autenticados (587/465) con la fecha del servidor, no la del equipo de quien envía (2026-10-13).
exec bash "$(cd "$(dirname "$0")/.." && pwd)/postfix/aplicar-fecha-servidor.sh" "$@"
