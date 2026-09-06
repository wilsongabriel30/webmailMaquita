#!/usr/bin/env python3
"""Purga de una sola vez: claves imap_pass:* de Redis que NO descifran con la clave actual
(valores en claro de antes del cifrado, o cifrados con otro SECRET_KEY).

El código dejó de aceptarlas (R-1, 2026-09-06): antes un fallback las usaba tal cual, lo
que las mantenía vivas indefinidamente. Sin --aplicar solo cuenta.

    cd /opt/maquita-webmail/backend && venv/bin/python ../deploy/tools/purgar-imap-pass-legacy.py [--aplicar]
"""

import os
import sys

import redis

sys.path.insert(0, os.getcwd())
from app.config import get_settings  # noqa: E402
from app.core.session import decrypt_password  # noqa: E402

aplicar = "--aplicar" in sys.argv
r = redis.from_url(get_settings().redis_url)
claves = list(r.scan_iter("imap_pass:*"))
malas = []
for k in claves:
    try:
        decrypt_password(r.get(k).decode())
    except Exception:
        malas.append(k)
print(f"antes: {len(claves)} claves imap_pass:*, {len(malas)} no descifran")
if aplicar and malas:
    r.delete(*malas)
    quedan = sum(1 for _ in r.scan_iter("imap_pass:*"))
    print(f"despues: {quedan} claves imap_pass:*, {len(malas)} eliminadas")
elif malas:
    print("(sin --aplicar no se borra nada)")
