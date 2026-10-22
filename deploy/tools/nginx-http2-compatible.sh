#!/usr/bin/env bash
# «http2 on;» existe desde nginx 1.25.1. En uno anterior (Debian 12 trae 1.22, Ubuntu 22.04 la 1.18) nginx -t
# lo rechaza: aquí se pasa a la forma antigua («listen 443 ssl http2;»). Con nginx 1.25.1 o posterior no toca nada.
# Uso: nginx-http2-compatible.sh ARCHIVO…
set -euo pipefail
version="$(nginx -v 2>&1 | sed -nE 's#.*nginx/([0-9]+\.[0-9]+\.[0-9]+).*#\1#p')"
[ -n "$version" ] || exit 0
[ "$(printf '%s\n1.25.1\n' "$version" | sort -V | head -1)" = "1.25.1" ] && exit 0
for archivo in "$@"; do
  [ -f "$archivo" ] || continue
  grep -Eq '^[[:space:]]*http2[[:space:]]+on;' "$archivo" || continue
  sed -E -i '/^[[:space:]]*http2[[:space:]]+on;/d; s/^([[:space:]]*listen[[:space:]]+(\[::\]:)?443[[:space:]]+ssl);/\1 http2;/' "$archivo"
done
