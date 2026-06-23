#!/usr/bin/env bash
# calc-storage.sh — Calcula el almacenamiento por dominio para el dashboard del panel.
# Usa la quota CACHEADA de Dovecot (rapido) en vez de caminar /var/vmail (lento, 2TB).
# Se ejecuta por cron (cada hora). El endpoint /api/dashboard/storage lee el resultado al instante.
set -uo pipefail

sudo -u postgres psql -d maildb -q -c \
  "CREATE TABLE IF NOT EXISTS dashboard_cache (key text PRIMARY KEY, data jsonb, updated_at timestamptz DEFAULT now())" >/dev/null 2>&1

# El backend (usuario mailserver) lee esta tabla; sin este GRANT el SELECT falla
# con "permission denied" y el endpoint /api/dashboard/storage devuelve {} (el
# panel muestra "No se pudo obtener datos de almacenamiento"). Idempotente.
sudo -u postgres psql -d maildb -q -c \
  "GRANT SELECT ON dashboard_cache TO mailserver" >/dev/null 2>&1 || true

JSON=$(doveadm quota get -A 2>/dev/null | python3 -c '
import sys, json
from collections import defaultdict
agg = defaultdict(lambda: {"total_bytes": 0, "users": {}})
for line in sys.stdin:
    p = line.split()
    if "STORAGE" in p:
        try:
            i = p.index("STORAGE"); used = int(p[i + 1]); user = p[0]
        except Exception:
            continue
        dom = user.split("@")[1] if "@" in user else "?"
        b = used * 1024
        agg[dom]["users"][user] = b
        agg[dom]["total_bytes"] += b
print(json.dumps({k: v for k, v in agg.items()}))
')

[ -z "$JSON" ] && { echo "calc-storage: sin datos de doveadm"; exit 1; }

sudo -u postgres psql -d maildb -q -c \
  "INSERT INTO dashboard_cache (key, data, updated_at) VALUES ('storage', \$j\$${JSON}\$j\$::jsonb, now()) \
   ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, updated_at = now()" >/dev/null

echo "calc-storage OK: $(echo "$JSON" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))') dominios"
