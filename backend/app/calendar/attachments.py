"""Calendar event attachments router."""
from __future__ import annotations

import os
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

logger = logging.getLogger("calendar.attachments")

router = APIRouter(prefix="/api/calendar/events", tags=["calendar-attachments"])

ATTACHMENTS_DIR = Path("/var/lib/maquita-webmail/calendar-attachments")
MAX_SIZE = 25 * 1024 * 1024  # 25 MB


class AttachmentOut(BaseModel):
    id: int
    event_id: str
    filename: str
    content_type: str | None = None
    size: int
    uploaded_by: str
    created_at: str | None = None


def _db(request: Request):
    return request.app.state.db_pool


@router.post("/{event_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    event_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    """Subir un adjunto a un evento de calendario."""
    db = _db(request)

    # Verificar que el evento existe y pertenece al usuario
    ev = await db.fetchrow(
        """SELECT e.id FROM events e
           JOIN calendars c ON c.id = e.calendar_id
           WHERE e.id =  AND c.owner_email = """,
        event_id, user,
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    # Leer contenido y validar tamanio
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="El archivo excede el limite de 25 MB")

    # Guardar archivo
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    event_dir = ATTACHMENTS_DIR / str(event_id)
    event_dir.mkdir(parents=True, exist_ok=True)
    file_path = event_dir / safe_name
    file_path.write_bytes(content)

    # Registrar en BD
    row = await db.fetchrow(
        """INSERT INTO calendar_event_attachments
           (event_id, filename, content_type, size, storage_path, uploaded_by)
           VALUES (, , , , , ) RETURNING *""",
        event_id, file.filename, file.content_type, len(content),
        str(file_path), user,
    )

    return AttachmentOut(
        id=row["id"],
        event_id=str(row["event_id"]),
        filename=row["filename"],
        content_type=row["content_type"],
        size=row["size"],
        uploaded_by=row["uploaded_by"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@router.get("/{event_id}/attachments", response_model=list[AttachmentOut])
async def list_attachments(
    event_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Listar adjuntos de un evento."""
    db = _db(request)
    rows = await db.fetch(
        "SELECT * FROM calendar_event_attachments WHERE event_id =  ORDER BY created_at",
        event_id,
    )
    return [
        AttachmentOut(
            id=r["id"],
            event_id=str(r["event_id"]),
            filename=r["filename"],
            content_type=r["content_type"],
            size=r["size"],
            uploaded_by=r["uploaded_by"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
        )
        for r in rows
    ]


@router.get("/{event_id}/attachments/{att_id}")
async def download_attachment(
    event_id: uuid.UUID,
    att_id: int,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Descargar un adjunto."""
    db = _db(request)
    row = await db.fetchrow(
        "SELECT * FROM calendar_event_attachments WHERE id =  AND event_id = ",
        att_id, event_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")

    file_path = Path(row["storage_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    return FileResponse(
        path=str(file_path),
        filename=row["filename"],
        media_type=row["content_type"] or "application/octet-stream",
    )


@router.delete("/{event_id}/attachments/{att_id}", status_code=204)
async def delete_attachment(
    event_id: uuid.UUID,
    att_id: int,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Eliminar un adjunto."""
    db = _db(request)
    row = await db.fetchrow(
        """SELECT a.* FROM calendar_event_attachments a
           JOIN events e ON e.id = a.event_id
           JOIN calendars c ON c.id = e.calendar_id
           WHERE a.id =  AND a.event_id = 
             AND (a.uploaded_by =  OR c.owner_email = )""",
        att_id, event_id, user,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado o sin permisos")

    # Eliminar archivo fisico
    file_path = Path(row["storage_path"])
    if file_path.exists():
        file_path.unlink()

    await db.execute("DELETE FROM calendar_event_attachments WHERE id = ", att_id)
