"""Prueba rápida del «Correo marcado» de Tareas tras la corrección del 05/11/2026.

1) Dos correos marcados con el MISMO Message-ID (copias del mismo mensaje) y un correo cuyo
   Message-ID ya tiene tarea: `aplicar` no debe fallar y debe crear una sola tarea nueva.
   Todo se hace dentro de una transacción que se deshace: la BD queda como estaba.
2) GET /api/tasks/views/flagged/count con la sesión de pruebas debe responder 200.

Uso (en VM 130, como root):
  cd /opt/maquita-webmail/backend && venv/bin/python tests/prueba_rapida_flagged_count.py
"""

import asyncio
import json
import os
import subprocess
import sys
import urllib.request
import uuid

sys.path.insert(0, "/opt/maquita-webmail/backend")

import asyncpg  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.tasks import correo_marcado  # noqa: E402

CUENTA = os.environ.get("PRUEBA_CUENTA", "test@example.org")


async def prueba_bd() -> None:
    con = await asyncpg.connect(get_settings().database_url)
    try:
        tr = con.transaction()
        await tr.start()
        try:
            mid = f"<prueba-{uuid.uuid4()}@example.org>"
            # Tarea ya existente para `mid` pero en OTRA carpeta: la sincronización (solo INBOX) no la ve.
            list_id, _ = await correo_marcado.asegurar_lista(con, CUENTA)
            card = await con.fetchval(
                "INSERT INTO task_cards (list_id, title, description, created_by, position) "
                "VALUES ($1, 'prueba previa', '', $2, 0) RETURNING id",
                list_id,
                CUENTA,
            )
            await con.execute(
                "INSERT INTO task_correo (card_id, user_email, carpeta, uid, message_id) "
                "VALUES ($1, $2, 'Archive', 999901, $3)",
                card,
                CUENTA,
                mid,
            )
            antes = await con.fetchval(
                "SELECT count(*) FROM task_correo WHERE user_email = $1", CUENTA
            )
            mid2 = f"<prueba-{uuid.uuid4()}@example.org>"
            marcados = [
                {"uid": 999902, "message_id": mid2, "subject": "Copia 1", "from": "a@b.c"},
                {"uid": 999903, "message_id": mid2, "subject": "Copia 2", "from": "a@b.c"},
                {"uid": 999904, "message_id": mid, "subject": "Ya con tarea", "from": "a@b.c"},
            ]
            cambios = await correo_marcado.aplicar(con, CUENTA, marcados, completo=False)
            despues = await con.fetchval(
                "SELECT count(*) FROM task_correo WHERE user_email = $1", CUENTA
            )
            huerfanas = await con.fetchval(
                "SELECT count(*) FROM task_cards tc WHERE tc.list_id = $1 AND tc.title IN ('Copia 2', 'Ya con tarea')",
                list_id,
            )
            assert cambios["creadas"] == 1, cambios
            assert despues - antes == 1, (antes, despues)
            assert huerfanas == 0, "quedó una tarjeta sin su enlace al correo"
            print("OK  aplicar(): 3 marcados conflictivos -> 1 tarea nueva, sin error ni tarjetas huérfanas")
        finally:
            await tr.rollback()
    finally:
        await con.close()


def prueba_http() -> None:
    token = subprocess.run(
        ["/usr/local/bin/sesion-prueba", CUENTA], capture_output=True, text=True, check=True
    ).stdout.strip().splitlines()[-1]
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/tasks/views/flagged/count",
        headers={"Cookie": f"access_token={token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        cuerpo = json.loads(r.read().decode())
        assert r.status == 200 and "flagged" in cuerpo, (r.status, cuerpo)
        print(f"OK  GET /api/tasks/views/flagged/count -> 200 {cuerpo}")


if __name__ == "__main__":
    asyncio.run(prueba_bd())
    prueba_http()
