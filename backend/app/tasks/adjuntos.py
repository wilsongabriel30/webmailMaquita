"""Archivos adjuntos de las tareas (como en To Do, F3 30/10/2026).

Se validan igual que los adjuntos del correo: las extensiones peligrosas no se aceptan
(`adjuntos_seguros`) y, si SafeAttach está activo, el archivo se analiza; con veredicto malicioso y modo
estricto se rechaza (y lo malicioso o sospechoso queda en `attachment_scans`). Si el analizador falla, el
archivo pasa, como en el correo.

En disco cada archivo se guarda como `<card_id>/<id>`, sin el nombre original: el nombre solo vive en la
base, así que no hay forma de salirse de la carpeta. Al borrar la tarea o la lista se borran sus archivos.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import unicodedata
import uuid
from pathlib import Path

from pydantic import BaseModel

from app.mail.services.adjuntos_seguros import rechazar_peligrosos

logger = logging.getLogger(__name__)

CARPETA = Path(
    os.environ.get("TAREAS_ADJUNTOS_DIR", "/var/lib/maquita-webmail/task-attachments")
)
MAX_TAMANO = 25 * 1024 * 1024  # 25 MB, igual que un adjunto del calendario
MAX_POR_TAREA = 20
_RARO = re.compile(r"[\x00-\x1f\x7f/\\]")


class Adjunto(BaseModel):
    id: uuid.UUID
    card_id: uuid.UUID
    nombre: str
    content_type: str
    tamano: int
    subido_por: str
    creado_en: str


class Rechazado(Exception):
    def __init__(self, status: int, detalle):
        super().__init__(str(detalle))
        self.status = status
        self.detalle = detalle


def nombre_limpio(nombre: str | None) -> str:
    nombre = unicodedata.normalize("NFC", nombre or "")
    nombre = _RARO.sub("_", os.path.basename(nombre.replace("\\", "/"))).strip(" .")
    return nombre[:200] or "archivo"


def _adjunto(row) -> Adjunto:
    d = dict(row)
    d["creado_en"] = d["creado_en"].isoformat()
    return Adjunto(**{k: d[k] for k in Adjunto.model_fields})


async def de_tarea(db, card_id) -> list[Adjunto]:
    rows = await db.fetch(
        "SELECT * FROM task_adjuntos WHERE card_id = $1 ORDER BY creado_en", card_id
    )
    return [_adjunto(r) for r in rows]


async def _analizar(
    db, card_id, user: str, contenido: bytes, nombre: str, tipo: str
) -> None:
    """SafeAttach, con la misma política que el correo saliente."""
    try:
        config = await db.fetchrow(
            "SELECT enabled, enforce FROM safeattach_config WHERE id = 1"
        )
    except Exception:
        return
    if not config or not config["enabled"]:
        return
    try:
        from app.security.router import deep_scan_attachment

        veredicto = await deep_scan_attachment(contenido, nombre, tipo)
    except Exception:
        logger.warning(
            "Adjunto de tarea: SafeAttach no respondió (%s)", nombre, exc_info=True
        )
        return
    if veredicto["result"] in ("malicious", "suspicious"):
        try:
            await db.execute(
                """INSERT INTO attachment_scans
                   (message_id, filename, content_type, size, scan_result, threats_found, scan_details)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)""",
                f"tarea:{card_id}:{user}",
                nombre,
                tipo,
                len(contenido),
                veredicto["result"],
                json.dumps(veredicto["threats"]),
                json.dumps(veredicto["details"]),
            )
        except Exception:
            pass
    if veredicto["result"] == "malicious" and config["enforce"]:
        raise Rechazado(
            422,
            {
                "attachment_blocked": True,
                "filename": nombre,
                "threats": veredicto["threats"],
            },
        )


def _escribir(ruta: Path, contenido: bytes) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)


async def guardar(
    db, user: str, card_id, nombre: str | None, tipo: str | None, contenido: bytes
) -> Adjunto:
    """Valida y guarda un archivo de la tarea (el acceso ya se comprobó)."""
    nombre = nombre_limpio(nombre)
    tipo = (tipo or "application/octet-stream")[:200]
    if not contenido:
        raise Rechazado(400, "El archivo está vacío")
    if len(contenido) > MAX_TAMANO:
        raise Rechazado(413, "El archivo supera el límite de 25 MB")
    rechazar_peligrosos([nombre])
    cuantos = await db.fetchval(
        "SELECT count(*) FROM task_adjuntos WHERE card_id = $1", card_id
    )
    if cuantos >= MAX_POR_TAREA:
        raise Rechazado(400, f"Una tarea admite hasta {MAX_POR_TAREA} archivos")
    await _analizar(db, card_id, user, contenido, nombre, tipo)
    adjunto_id = uuid.uuid4()
    archivo = f"{card_id}/{adjunto_id.hex}"
    await asyncio.to_thread(_escribir, CARPETA / archivo, contenido)
    try:
        row = await db.fetchrow(
            """INSERT INTO task_adjuntos (id, card_id, nombre, content_type, tamano, archivo, subido_por)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *""",
            adjunto_id,
            card_id,
            nombre,
            tipo,
            len(contenido),
            archivo,
            user,
        )
    except Exception:
        (CARPETA / archivo).unlink(missing_ok=True)
        raise
    return _adjunto(row)


async def uno(db, adjunto_id):
    """Fila del adjunto con su tarea (o None)."""
    return await db.fetchrow("SELECT * FROM task_adjuntos WHERE id = $1", adjunto_id)


def ruta_de(row) -> Path:
    return CARPETA / row["archivo"]


async def borrar(db, row) -> None:
    await db.execute("DELETE FROM task_adjuntos WHERE id = $1", row["id"])
    await asyncio.to_thread(lambda: ruta_de(row).unlink(missing_ok=True))


async def con_adjuntos(db, *, card_id=None, list_id=None) -> list[str]:
    """Tareas (de una tarea o de una lista) que tienen archivos, para borrarlos tras borrar la tarea."""
    if card_id is not None:
        rows = await db.fetch(
            "SELECT DISTINCT card_id FROM task_adjuntos WHERE card_id = $1", card_id
        )
    else:
        rows = await db.fetch(
            """SELECT DISTINCT a.card_id FROM task_adjuntos a JOIN task_cards c ON c.id = a.card_id
                WHERE c.list_id = $1""",
            list_id,
        )
    return [str(r["card_id"]) for r in rows]


async def borrar_carpetas(card_ids: list[str]) -> None:
    def _borrar():
        for c in card_ids:
            shutil.rmtree(CARPETA / str(uuid.UUID(c)), ignore_errors=True)

    if card_ids:
        await asyncio.to_thread(_borrar)
