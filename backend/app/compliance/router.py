"""Compliance Router — eDiscovery, User Activity, Legal Holds, Fraud Alerts.

Endpoints para módulo de compliance tipo Microsoft Purview.
Solo accesible por rol admin/compliance.
"""
import asyncio
import email
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.compliance.auth import (
    require_compliance_admin as require_admin,
    require_compliance_read,
    require_compliance_write,
    require_compliance_export,
    require_compliance_security,
)
from app.compliance.content_extractor import search_maildir
from app.compliance.evidence_signer import sign_export, ensure_gpg_key
from app.compliance.activity_logger import (
    get_activity_stats,
    get_user_activities,
    log_user_activity,
)

logger = logging.getLogger("compliance")

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


def _get_db(request: Request):
    return request.app.state.db_pool


# =====================================================
# ACTIVITY LOG — Auditoría de actividad de usuarios
# =====================================================

@router.get("/activity")
async def list_activities(
    request: Request,
    username: Optional[str] = None,
    action: Optional[str] = None,
    category: Optional[str] = None,
    risk_level: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin: str = Depends(require_compliance_read),
):
    """Listar actividad de usuarios con filtros."""
    db = _get_db(request)
    return await get_user_activities(
        db, username=username, action=action, category=category,
        risk_level=risk_level, date_from=date_from, date_to=date_to,
        page=page, per_page=per_page,
    )


@router.get("/activity/stats")
async def activity_stats(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    admin: str = Depends(require_compliance_read),
):
    """Estadísticas de actividad para dashboard compliance."""
    db = _get_db(request)
    return await get_activity_stats(db, days)


@router.get("/activity/export")
async def export_activities(
    request: Request,
    username: Optional[str] = None,
    action: Optional[str] = None,
    category: Optional[str] = None,
    risk_level: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    admin: str = Depends(require_compliance_export),
):
    """Exportar actividades en formato JSON (máx 10000)."""
    db = _get_db(request)
    ip = request.headers.get("x-real-ip", request.client.host if request.client else "")
    await log_user_activity(db, admin, "email_export", ip_address=ip,
                            details={"type": "activity_export"})

    result = await get_user_activities(
        db, username=username, action=action, category=category,
        risk_level=risk_level, date_from=date_from, date_to=date_to,
        page=1, per_page=10000,
    )
    return result


# =====================================================
# COMPLIANCE CASES — Casos de investigación
# =====================================================

class CaseCreate(BaseModel):
    title: str
    description: str = ""
    reason: str
    case_type: str = "investigation"
    priority: str = "normal"
    assigned_to: str = ""


class CaseUpdate(BaseModel):
    title: str = None
    description: str = None
    status: str = None
    priority: str = None
    assigned_to: str = None
    close_reason: str = None


@router.get("/cases")
async def list_cases(
    request: Request,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: str = Depends(require_compliance_read),
):
    """Listar casos de compliance."""
    db = _get_db(request)
    conditions = []
    params = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = await db.fetchval(f"SELECT count(*) FROM compliance_cases {where}", *params)

    offset = (page - 1) * per_page
    rows = await db.fetch(
        f"""SELECT * FROM compliance_cases {where}
            ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}""",
        *params, per_page, offset,
    )

    return {
        "cases": [
            {**dict(r),
             "created_at": r["created_at"].isoformat() if r["created_at"] else None,
             "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
             "approved_at": r["approved_at"].isoformat() if r["approved_at"] else None,
             "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None}
            for r in rows
        ],
        "total": total, "page": page, "per_page": per_page,
    }


@router.post("/cases", status_code=201)
async def create_case(
    body: CaseCreate,
    request: Request,
    admin: str = Depends(require_compliance_write),
):
    """Crear nuevo caso de compliance/eDiscovery."""
    db = _get_db(request)
    ip = request.headers.get("x-real-ip", "")

    row = await db.fetchrow(
        """INSERT INTO compliance_cases
           (title, description, reason, case_type, priority, created_by, assigned_to)
           VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *""",
        body.title, body.description, body.reason, body.case_type,
        body.priority, admin, body.assigned_to or admin,
    )

    await log_user_activity(
        db, admin, "ediscovery_search", ip_address=ip,
        target=f"case:{row['id']}", details={"case_title": body.title, "action": "case_created"},
    )

    return {**dict(row),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat()}


@router.get("/cases/{case_id}")
async def get_case(case_id: int, request: Request, admin: str = Depends(require_compliance_read)):
    """Detalle de un caso."""
    db = _get_db(request)
    row = await db.fetchrow("SELECT * FROM compliance_cases WHERE id = $1", case_id)
    if not row:
        raise HTTPException(404, "Caso no encontrado")

    # Contar búsquedas, resultados, holds y exports
    searches = await db.fetchval("SELECT count(*) FROM ediscovery_searches WHERE case_id = $1", case_id)
    results = await db.fetchval(
        "SELECT count(*) FROM ediscovery_results WHERE search_id IN (SELECT id FROM ediscovery_searches WHERE case_id = $1)",
        case_id,
    )
    holds = await db.fetchval("SELECT count(*) FROM legal_holds WHERE case_id = $1 AND is_active", case_id)
    exports = await db.fetchval("SELECT count(*) FROM ediscovery_exports WHERE case_id = $1", case_id)

    return {
        **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(row).items()},
        "searches_count": searches, "results_count": results,
        "active_holds": holds, "exports_count": exports,
    }


@router.put("/cases/{case_id}")
async def update_case(case_id: int, body: CaseUpdate, request: Request, admin: str = Depends(require_compliance_write)):
    """Actualizar caso."""
    db = _get_db(request)

    existing = await db.fetchrow("SELECT * FROM compliance_cases WHERE id = $1", case_id)
    if not existing:
        raise HTTPException(404, "Caso no encontrado")

    fields = []
    values = []
    idx = 1
    for key in ["title", "description", "status", "priority", "assigned_to"]:
        val = getattr(body, key, None)
        if val is not None:
            fields.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1

    if body.status == "closed":
        fields.append(f"closed_by = ${idx}")
        values.append(admin)
        idx += 1
        fields.append(f"closed_at = NOW()")
        if body.close_reason:
            fields.append(f"close_reason = ${idx}")
            values.append(body.close_reason)
            idx += 1

    if body.status == "approved":
        fields.append(f"approved_by = ${idx}")
        values.append(admin)
        idx += 1
        fields.append(f"approved_at = NOW()")

    fields.append("updated_at = NOW()")

    if not fields:
        raise HTTPException(400, "Sin cambios")

    values.append(case_id)
    row = await db.fetchrow(
        f"UPDATE compliance_cases SET {', '.join(fields)} WHERE id = ${idx} RETURNING *",
        *values,
    )

    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(row).items()}


# =====================================================
# eDISCOVERY SEARCHES — Búsquedas forenses
# =====================================================

class SearchCreate(BaseModel):
    case_id: int
    mailboxes_scope: list[str] = []
    folders_scope: list[str] = ["INBOX", "Sent", "Drafts", "Trash", "Junk"]
    senders_filter: list[str] = []
    recipients_filter: list[str] = []
    keywords: list[str] = []
    date_from: str = ""
    date_to: str = ""
    has_attachments: bool = None
    min_size: int = None
    max_size: int = None


@router.post("/ediscovery/search", status_code=201)
async def execute_search(
    body: SearchCreate,
    request: Request,
    admin: str = Depends(require_compliance_export),
):
    """Ejecutar búsqueda eDiscovery en buzones vía IMAP master user."""
    db = _get_db(request)
    ip = request.headers.get("x-real-ip", "")

    # Verificar caso existe y está aprobado o abierto
    case = await db.fetchrow("SELECT * FROM compliance_cases WHERE id = $1", body.case_id)
    if not case:
        raise HTTPException(404, "Caso no encontrado")
    if case["status"] not in ("open", "approved", "in_progress"):
        raise HTTPException(400, f"Caso en estado '{case['status']}' — no permite búsquedas")

    # Registrar búsqueda
    search_row = await db.fetchrow(
        """INSERT INTO ediscovery_searches
           (case_id, query_text, mailboxes_scope, folders_scope, senders_filter,
            recipients_filter, date_from, date_to, keywords, has_attachments,
            min_size, max_size, executed_by, status)
           VALUES ($1, $2, $3, $4, $5, $6,
                   NULLIF($7, '')::timestamptz, NULLIF($8, '')::timestamptz,
                   $9, $10, $11, $12, $13, 'running')
           RETURNING *""",
        body.case_id,
        " ".join(body.keywords) if body.keywords else None,
        body.mailboxes_scope or None,
        body.folders_scope or None,
        body.senders_filter or None,
        body.recipients_filter or None,
        body.date_from, body.date_to,
        body.keywords or None,
        body.has_attachments,
        body.min_size, body.max_size,
        admin,
    )
    search_id = search_row["id"]

    await log_user_activity(
        db, admin, "ediscovery_search", ip_address=ip,
        target=f"case:{body.case_id}/search:{search_id}",
        details={"mailboxes": body.mailboxes_scope, "keywords": body.keywords},
    )

    # Ejecutar búsqueda IMAP en background
    start_time = time.time()
    total_results = 0

    try:
        mailboxes = body.mailboxes_scope
        if not mailboxes:
            # Obtener todos los buzones
            rows = await db.fetch("SELECT username FROM mailbox WHERE active = TRUE")
            mailboxes = [r["username"] for r in rows]

        for mailbox_user in mailboxes:
            for folder in (body.folders_scope or ["INBOX"]):
                try:
                    results = await _search_mailbox_imap(
                        mailbox_user, folder, body, db, search_id
                    )
                    total_results += results
                except Exception as exc:
                    logger.warning("Error buscando %s/%s: %s", mailbox_user, folder, exc)

        duration_ms = int((time.time() - start_time) * 1000)
        await db.execute(
            """UPDATE ediscovery_searches
               SET status = 'completed', result_count = $1, duration_ms = $2
               WHERE id = $3""",
            total_results, duration_ms, search_id,
        )

    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        await db.execute(
            """UPDATE ediscovery_searches
               SET status = 'error', error_message = $1, duration_ms = $2
               WHERE id = $3""",
            str(exc)[:500], duration_ms, search_id,
        )
        raise HTTPException(500, f"Error en búsqueda: {str(exc)[:200]}")

    return {
        "search_id": search_id,
        "case_id": body.case_id,
        "status": "completed",
        "result_count": total_results,
        "duration_ms": duration_ms,
    }


async def _search_mailbox_imap(
    mailbox_user: str,
    folder: str,
    criteria: SearchCreate,
    db,
    search_id: int,
) -> int:
    """Busca en un buzón vía doveadm search (master user) y guarda resultados."""
    count = 0

    # Construir criterio doveadm search
    search_args = ["sudo", "doveadm", "search", "-u", mailbox_user, "mailbox", folder]

    if criteria.date_from:
        search_args += ["since", criteria.date_from[:10]]
    if criteria.date_to:
        search_args += ["before", criteria.date_to[:10]]

    loop = asyncio.get_event_loop()

    def _do_search():
        try:
            result = subprocess.run(
                search_args, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                return []
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            return lines
        except Exception:
            return []

    uid_lines = await loop.run_in_executor(None, _do_search)
    if not uid_lines:
        return 0

    # Obtener headers de cada mensaje via doveadm fetch
    for line in uid_lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        mailbox_guid, uid = parts[0], parts[1]

        try:
            msg_data = await _fetch_message_headers(mailbox_user, uid, folder, loop)
            if not msg_data:
                continue

            # Filtrar por keywords si hay
            if criteria.keywords:
                text_content = (
                    (msg_data.get("subject", "") or "") + " " +
                    (msg_data.get("from", "") or "") + " " +
                    (msg_data.get("to", "") or "")
                ).lower()
                if not any(kw.lower() in text_content for kw in criteria.keywords):
                    # Si hay keywords, también buscar en body
                    body_text = await _fetch_message_body_text(mailbox_user, uid, folder, loop)
                    full_text = text_content + " " + (body_text or "").lower()
                    if not any(kw.lower() in full_text for kw in criteria.keywords):
                        continue

            # Filtrar por remitente/destinatario
            if criteria.senders_filter:
                sender = (msg_data.get("from", "") or "").lower()
                if not any(s.lower() in sender for s in criteria.senders_filter):
                    continue
            if criteria.recipients_filter:
                recipients = (msg_data.get("to", "") or "").lower()
                if not any(r.lower() in recipients for r in criteria.recipients_filter):
                    continue

            # Calcular hash del mensaje
            raw = msg_data.get("raw_header", "")
            msg_hash = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

            # Guardar resultado
            sent_date = msg_data.get("date", "")
            msg_size = msg_data.get("size", 0)
            if isinstance(msg_size, str):
                msg_size = int(msg_size) if msg_size.isdigit() else 0
            await db.execute(
                """INSERT INTO ediscovery_results
                   (search_id, mailbox, folder, uid, message_id, subject, sender,
                    recipients, sent_at, size_bytes, has_attachments, hash_sha256)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                           NULLIF($9, '')::timestamptz, $10, $11, $12)""",
                search_id, mailbox_user, folder, int(uid),
                msg_data.get("message_id"), msg_data.get("subject"),
                msg_data.get("from"), msg_data.get("to"),
                sent_date, msg_size,
                msg_data.get("has_attachments", False), msg_hash,
            )
            count += 1

        except Exception as exc:
            logger.debug("Error procesando %s uid %s: %s", mailbox_user, uid, exc)

    return count


async def _fetch_message_headers(user: str, uid: str, folder: str, loop) -> dict:
    """Obtiene headers de un mensaje vía doveadm fetch."""
    def _do():
        try:
            result = subprocess.run(
                ["sudo", "doveadm", "fetch", "-u", user, "hdr.subject hdr.from hdr.to hdr.message-id hdr.date hdr.content-type date.sent size.physical",
                 "mailbox", folder, "uid", uid],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return None

            data = {"raw_header": result.stdout}
            for line in result.stdout.split("\n"):
                if line.startswith("hdr.subject:"):
                    data["subject"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif line.startswith("hdr.from:"):
                    data["from"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif line.startswith("hdr.to:"):
                    data["to"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif line.startswith("hdr.message-id:"):
                    data["message_id"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif line.startswith("hdr.date:"):
                    data["date"] = line.split(":", 1)[1].strip() if ":" in line else ""
                elif line.startswith("hdr.content-type:"):
                    ct = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                    data["has_attachments"] = "multipart/mixed" in ct
                elif line.startswith("date.sent:"):
                    raw_date = line.split(":", 1)[1].strip() if ":" in line else ""
                    # Dovecot 2.4 uses (+0000) format — strip parens for PostgreSQL
                    data["date"] = raw_date.replace("(", "").replace(")", "").strip()
                elif line.startswith("size.physical:") or line.startswith("size:"):
                    try:
                        size_str = line.split(":", 1)[1].strip()
                        data["size"] = int(size_str) if size_str.isdigit() else 0
                    except (ValueError, IndexError):
                        data["size"] = 0
            return data
        except Exception:
            return None

    return await loop.run_in_executor(None, _do)


async def _fetch_message_body_text(user: str, uid: str, folder: str, loop) -> str:
    """Obtiene texto del body para búsqueda por keywords."""
    def _do():
        try:
            result = subprocess.run(
                ["sudo", "doveadm", "fetch", "-u", user, "body.preview",
                 "mailbox", folder, "uid", uid],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout[:5000] if result.returncode == 0 else ""
        except Exception:
            return ""

    return await loop.run_in_executor(None, _do)


@router.get("/ediscovery/searches")
async def list_searches(
    request: Request,
    case_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: str = Depends(require_compliance_read),
):
    """Listar búsquedas eDiscovery."""
    db = _get_db(request)
    if case_id:
        rows = await db.fetch(
            """SELECT * FROM ediscovery_searches WHERE case_id = $1
               ORDER BY executed_at DESC LIMIT $2 OFFSET $3""",
            case_id, per_page, (page - 1) * per_page,
        )
        total = await db.fetchval("SELECT count(*) FROM ediscovery_searches WHERE case_id = $1", case_id)
    else:
        rows = await db.fetch(
            "SELECT * FROM ediscovery_searches ORDER BY executed_at DESC LIMIT $1 OFFSET $2",
            per_page, (page - 1) * per_page,
        )
        total = await db.fetchval("SELECT count(*) FROM ediscovery_searches")

    return {
        "searches": [
            {k: (v.isoformat() if isinstance(v, datetime) else (list(v) if isinstance(v, (list, tuple)) else v))
             for k, v in dict(r).items()}
            for r in rows
        ],
        "total": total,
    }


@router.get("/ediscovery/results/{search_id}")
async def get_search_results(
    search_id: int,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin: str = Depends(require_compliance_read),
):
    """Obtener resultados de una búsqueda eDiscovery."""
    db = _get_db(request)

    search = await db.fetchrow("SELECT * FROM ediscovery_searches WHERE id = $1", search_id)
    if not search:
        raise HTTPException(404, "Búsqueda no encontrada")

    total = await db.fetchval("SELECT count(*) FROM ediscovery_results WHERE search_id = $1", search_id)
    rows = await db.fetch(
        """SELECT * FROM ediscovery_results WHERE search_id = $1
           ORDER BY sent_at DESC NULLS LAST LIMIT $2 OFFSET $3""",
        search_id, per_page, (page - 1) * per_page,
    )

    ip = request.headers.get("x-real-ip", "")
    await log_user_activity(
        db, admin, "ediscovery_preview", ip_address=ip,
        target=f"search:{search_id}", details={"results_viewed": len(rows)},
    )

    return {
        "search_id": search_id,
        "case_id": search["case_id"],
        "results": [
            {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(r).items()}
            for r in rows
        ],
        "total": total, "page": page, "per_page": per_page,
    }


# =====================================================
# eDISCOVERY EXPORT — Exportación con cadena de custodia
# =====================================================

class ExportRequest(BaseModel):
    case_id: int
    search_id: int
    result_ids: list[int] = []
    export_format: str = "eml"
    reason: str = ""


@router.post("/ediscovery/export")
async def export_evidence(
    body: ExportRequest,
    request: Request,
    admin: str = Depends(require_compliance_export),
):
    """Exportar evidencia con hash SHA256 y cadena de custodia."""
    db = _get_db(request)
    ip = request.headers.get("x-real-ip", "")

    case = await db.fetchrow("SELECT * FROM compliance_cases WHERE id = $1", body.case_id)
    if not case:
        raise HTTPException(404, "Caso no encontrado")

    # Obtener resultados a exportar
    if body.result_ids:
        results = await db.fetch(
            "SELECT * FROM ediscovery_results WHERE id = ANY($1) AND search_id = $2",
            body.result_ids, body.search_id,
        )
    else:
        results = await db.fetch(
            "SELECT * FROM ediscovery_results WHERE search_id = $1", body.search_id,
        )

    if not results:
        raise HTTPException(404, "Sin resultados para exportar")

    # Crear directorio de exportación
    export_dir = f"/opt/maquita-webmail/exports/case-{body.case_id}"
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    export_name = f"export_{body.search_id}_{timestamp}"
    export_path = os.path.join(export_dir, export_name)
    os.makedirs(export_path, exist_ok=True)

    loop = asyncio.get_event_loop()
    exported = []
    manifest = []

    for r in results:
        try:
            # Exportar mensaje vía doveadm
            mailbox = r["mailbox"]
            uid = r["uid"]
            folder = r["folder"] or "INBOX"

            def _export_msg(m=mailbox, u=str(uid), f=folder):
                try:
                    result = subprocess.run(
                        ["sudo", "doveadm", "fetch", "-u", m, "text", "mailbox", f, "uid", u],
                        capture_output=True, timeout=30,
                    )
                    return result.stdout if result.returncode == 0 else None
                except Exception:
                    return None

            raw_msg = await loop.run_in_executor(None, _export_msg)
            if not raw_msg:
                continue

            # Hash SHA256
            msg_hash = hashlib.sha256(raw_msg).hexdigest()

            # Guardar archivo
            safe_id = str(r["id"])
            if body.export_format == "eml":
                filename = f"msg_{safe_id}.eml"
                filepath = os.path.join(export_path, filename)
                with open(filepath, "wb") as f:
                    f.write(raw_msg)
            else:
                filename = f"msg_{safe_id}.eml"
                filepath = os.path.join(export_path, filename)
                with open(filepath, "wb") as f:
                    f.write(raw_msg)

            manifest.append({
                "result_id": r["id"],
                "mailbox": mailbox,
                "folder": folder,
                "uid": uid,
                "message_id": r["message_id"],
                "subject": r["subject"],
                "sender": r["sender"],
                "sha256": msg_hash,
                "filename": filename,
                "size": len(raw_msg),
            })
            exported.append(r["id"])

        except Exception as exc:
            logger.warning("Error exportando result %s: %s", r["id"], exc)

    # Escribir manifiesto CSV
    manifest_path = os.path.join(export_path, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({
            "case_id": body.case_id,
            "case_title": case["title"],
            "search_id": body.search_id,
            "exported_by": admin,
            "exported_at": datetime.utcnow().isoformat(),
            "reason": body.reason,
            "total_messages": len(exported),
            "messages": manifest,
        }, f, indent=2, ensure_ascii=False)

    # Hash del manifiesto
    with open(manifest_path, "rb") as f:
        manifest_hash = hashlib.sha256(f.read()).hexdigest()

    # Registrar exportación
    total_size = sum(m["size"] for m in manifest)
    await db.execute(
        """INSERT INTO ediscovery_exports
           (case_id, search_id, export_format, result_ids, total_messages,
            file_path, file_hash_sha256, file_size, exported_by, reason)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
        body.case_id, body.search_id, body.export_format,
        exported, len(exported),
        export_path, manifest_hash, total_size,
        admin, body.reason,
    )

    await log_user_activity(
        db, admin, "ediscovery_export", ip_address=ip,
        target=f"case:{body.case_id}/search:{body.search_id}",
        details={"total_exported": len(exported), "format": body.export_format},
    )

    # Sign with GPG
    try:
        sign_result = await sign_export(
            export_path=export_path,
            manifest_path=manifest_path,
            export_id=0,  # Will be updated
            exported_by=admin,
            db_pool=db,
        )
        gpg_sig = sign_result.get("gpg_signature_path", "")
        timestamp = sign_result.get("timestamp_seal", {})
    except Exception as sign_err:
        logger.warning("GPG signing failed: %s", sign_err)
        gpg_sig = ""
        timestamp = {}

    return {
        "case_id": body.case_id,
        "search_id": body.search_id,
        "exported": len(exported),
        "export_path": export_path,
        "manifest_hash": manifest_hash,
        "total_size": total_size,
        "gpg_signature": gpg_sig,
        "timestamp_seal": timestamp,
    }


@router.get("/ediscovery/exports")
async def list_exports(
    request: Request,
    case_id: Optional[int] = None,
    admin: str = Depends(require_compliance_read),
):
    """Listar exportaciones (cadena de custodia)."""
    db = _get_db(request)
    if case_id:
        rows = await db.fetch(
            "SELECT * FROM ediscovery_exports WHERE case_id = $1 ORDER BY exported_at DESC", case_id
        )
    else:
        rows = await db.fetch("SELECT * FROM ediscovery_exports ORDER BY exported_at DESC LIMIT 100")

    return [
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(r).items()}
        for r in rows
    ]


# =====================================================
# LEGAL HOLDS — Retención legal
# =====================================================

class HoldCreate(BaseModel):
    case_id: int
    mailbox: str
    scope: str = "all"
    folder_pattern: str = ""
    date_from: str = ""
    date_to: str = ""
    reason: str


@router.get("/holds")
async def list_holds(
    request: Request,
    active_only: bool = True,
    admin: str = Depends(require_compliance_read),
):
    """Listar retenciones legales."""
    db = _get_db(request)
    if active_only:
        rows = await db.fetch("SELECT * FROM legal_holds WHERE is_active = TRUE ORDER BY enabled_at DESC")
    else:
        rows = await db.fetch("SELECT * FROM legal_holds ORDER BY enabled_at DESC LIMIT 100")

    return [
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(r).items()}
        for r in rows
    ]


@router.post("/holds", status_code=201)
async def create_hold(
    body: HoldCreate,
    request: Request,
    admin: str = Depends(require_compliance_write),
):
    """Crear retención legal sobre un buzón."""
    db = _get_db(request)
    ip = request.headers.get("x-real-ip", "")

    case = await db.fetchrow("SELECT * FROM compliance_cases WHERE id = $1", body.case_id)
    if not case:
        raise HTTPException(404, "Caso no encontrado")

    # Verificar buzón existe
    mb = await db.fetchrow("SELECT username FROM mailbox WHERE username = $1", body.mailbox)
    if not mb:
        raise HTTPException(404, f"Buzón {body.mailbox} no encontrado")

    row = await db.fetchrow(
        """INSERT INTO legal_holds
           (case_id, mailbox, scope, folder_pattern, date_from, date_to, reason, enabled_by)
           VALUES ($1, $2, $3, $4, NULLIF($5,'')::timestamptz, NULLIF($6,'')::timestamptz, $7, $8)
           RETURNING *""",
        body.case_id, body.mailbox, body.scope, body.folder_pattern,
        body.date_from, body.date_to, body.reason, admin,
    )

    await log_user_activity(
        db, admin, "legal_hold_enable", ip_address=ip,
        mailbox=body.mailbox, target=f"case:{body.case_id}",
        details={"scope": body.scope, "reason": body.reason},
    )

    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in dict(row).items()}


@router.delete("/holds/{hold_id}")
async def release_hold(
    hold_id: int,
    request: Request,
    admin: str = Depends(require_compliance_write),
):
    """Liberar retención legal."""
    db = _get_db(request)
    ip = request.headers.get("x-real-ip", "")

    hold = await db.fetchrow("SELECT * FROM legal_holds WHERE id = $1", hold_id)
    if not hold:
        raise HTTPException(404, "Retención no encontrada")

    await db.execute(
        """UPDATE legal_holds SET is_active = FALSE, released_by = $1, released_at = NOW()
           WHERE id = $2""",
        admin, hold_id,
    )

    await log_user_activity(
        db, admin, "legal_hold_release", ip_address=ip,
        mailbox=hold["mailbox"], target=f"case:{hold['case_id']}/hold:{hold_id}",
    )

    return {"ok": True, "hold_id": hold_id, "released_by": admin}


# =====================================================
# FRAUD ALERTS — Alertas antifraude
# =====================================================

@router.get("/alerts")
async def list_alerts(
    request: Request,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin: str = Depends(require_compliance_read),
):
    """Listar alertas antifraude."""
    db = _get_db(request)
    conditions = []
    params = []
    idx = 1

    if alert_type:
        conditions.append(f"alert_type = ${idx}")
        params.append(alert_type)
        idx += 1
    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1
    if acknowledged is not None:
        conditions.append(f"is_acknowledged = ${idx}")
        params.append(acknowledged)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = await db.fetchval(f"SELECT count(*) FROM fraud_alerts {where}", *params)

    rows = await db.fetch(
        f"""SELECT * FROM fraud_alerts {where}
            ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}""",
        *params, per_page, (page - 1) * per_page,
    )

    return {
        "alerts": [
            {k: (v.isoformat() if isinstance(v, datetime) else (str(v) if k == "source_ip" and v else v))
             for k, v in dict(r).items()}
            for r in rows
        ],
        "total": total,
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    request: Request,
    admin: str = Depends(require_compliance_write),
):
    """Marcar alerta como revisada."""
    db = _get_db(request)
    await db.execute(
        """UPDATE fraud_alerts SET is_acknowledged = TRUE,
           acknowledged_by = $1, acknowledged_at = NOW()
           WHERE id = $2""",
        admin, alert_id,
    )
    return {"ok": True}


@router.post("/alerts/{alert_id}/link-case")
async def link_alert_to_case(
    alert_id: int,
    request: Request,
    case_id: int = Query(...),
    admin: str = Depends(require_compliance_write),
):
    """Vincular alerta a un caso de compliance."""
    db = _get_db(request)
    await db.execute("UPDATE fraud_alerts SET case_id = $1 WHERE id = $2", case_id, alert_id)
    return {"ok": True, "alert_id": alert_id, "case_id": case_id}


@router.get("/alerts/stats")
async def alert_stats(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    admin: str = Depends(require_compliance_read),
):
    """Estadísticas de alertas antifraude."""
    db = _get_db(request)

    total = await db.fetchval(
        "SELECT count(*) FROM fraud_alerts WHERE created_at >= NOW() - make_interval(days => $1)", days
    )
    unack = await db.fetchval(
        "SELECT count(*) FROM fraud_alerts WHERE is_acknowledged = FALSE AND created_at >= NOW() - make_interval(days => $1)",
        days,
    )
    by_type = await db.fetch(
        """SELECT alert_type, count(*) as total FROM fraud_alerts
           WHERE created_at >= NOW() - make_interval(days => $1)
           GROUP BY alert_type ORDER BY total DESC""", days
    )
    by_severity = await db.fetch(
        """SELECT severity, count(*) as total FROM fraud_alerts
           WHERE created_at >= NOW() - make_interval(days => $1)
           GROUP BY severity ORDER BY total DESC""", days
    )

    return {
        "period_days": days,
        "total": total,
        "unacknowledged": unack,
        "by_type": {r["alert_type"]: r["total"] for r in by_type},
        "by_severity": {r["severity"]: r["total"] for r in by_severity},
    }


# =====================================================
# MAIL TRACE — Message Tracking mejorado (P7)
# =====================================================

@router.get("/mail-trace")
async def mail_trace(
    request: Request,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    message_id: Optional[str] = None,
    queue_id: Optional[str] = None,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    source_ip: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin: str = Depends(require_admin),
):
    """Message Trace mejorado — consulta tabla mail_trace con filtros completos."""
    db = _get_db(request)
    conditions = []
    params = []
    idx = 1

    if sender:
        conditions.append(f"sender ILIKE ${idx}")
        params.append(f"%{sender}%")
        idx += 1
    if recipient:
        conditions.append(f"recipient ILIKE ${idx}")
        params.append(f"%{recipient}%")
        idx += 1
    if message_id:
        conditions.append(f"message_id ILIKE ${idx}")
        params.append(f"%{message_id}%")
        idx += 1
    if queue_id:
        conditions.append(f"queue_id = ${idx}")
        params.append(queue_id)
        idx += 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if direction:
        conditions.append(f"direction = ${idx}")
        params.append(direction)
        idx += 1
    if source_ip:
        conditions.append(f"source_ip = ${idx}::inet")
        params.append(source_ip)
        idx += 1
    if date_from:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(date_to)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = await db.fetchval(f"SELECT count(*) FROM mail_trace {where}", *params)

    rows = await db.fetch(
        f"""SELECT id, queue_id, message_id, direction, sender, recipient,
                   source_ip, spf_result, dkim_result, dmarc_result, rspamd_score,
                   rspamd_action, status, dsn, delay_seconds, relay, tls_version,
                   size_bytes, created_at
            FROM mail_trace {where}
            ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}""",
        *params, per_page, (page - 1) * per_page,
    )

    return {
        "entries": [
            {k: (v.isoformat() if isinstance(v, datetime) else (str(v) if k == "source_ip" and v else v))
             for k, v in dict(r).items()}
            for r in rows
        ],
        "total": total, "page": page, "per_page": per_page,
    }


@router.get("/mail-trace/stats")
async def mail_trace_stats(
    request: Request,
    hours: int = Query(24, ge=1, le=720),
    admin: str = Depends(require_admin),
):
    """Estadísticas de mail trace."""
    db = _get_db(request)

    total = await db.fetchval(
        "SELECT count(*) FROM mail_trace WHERE created_at >= NOW() - make_interval(hours => $1)", hours
    )
    by_status = await db.fetch(
        """SELECT status, count(*) as total FROM mail_trace
           WHERE created_at >= NOW() - make_interval(hours => $1)
           GROUP BY status ORDER BY total DESC""", hours
    )
    by_direction = await db.fetch(
        """SELECT direction, count(*) as total FROM mail_trace
           WHERE created_at >= NOW() - make_interval(hours => $1)
           GROUP BY direction ORDER BY total DESC""", hours
    )

    return {
        "period_hours": hours,
        "total": total,
        "by_status": {r["status"]: r["total"] for r in by_status},
        "by_direction": {r["direction"]: r["total"] for r in by_direction},
    }


# =====================================================
# HEALTHCHECK — Estado del módulo compliance
# =====================================================

@router.get("/health")
async def compliance_health(
    request: Request,
    admin: str = Depends(require_compliance_read),
):
    """Healthcheck del módulo compliance — estado de tablas, servicios, conteos."""
    from app.compliance.compliance_health import get_compliance_health
    db = _get_db(request)
    return await get_compliance_health(db)