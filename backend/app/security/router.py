"""Security sandbox — attachment scanning endpoints."""
import subprocess
import json
import tempfile
import os
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password

logger = logging.getLogger("security.scanner")

router = APIRouter(prefix="/api/security", tags=["security"])

_KW = "keyword"


async def deep_scan_attachment(content: bytes, filename: str, content_type: str) -> dict:
    """Run ClamAV + oletools + file-type analysis on an attachment."""
    threats = []
    details = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 1. ClamAV
        try:
            result = subprocess.run(
                ["clamdscan", "--no-summary", tmp_path],
                capture_output=True, text=True, timeout=60,
            )
            details["clamav"] = result.stdout.strip()
            if "FOUND" in result.stdout:
                parts = result.stdout.split(":")
                threat_name = parts[1].strip() if len(parts) > 1 else "unknown"
                threats.append({"engine": "clamav", "threat": threat_name})
        except FileNotFoundError:
            details["clamav"] = "clamdscan not available"
        except subprocess.TimeoutExpired:
            details["clamav"] = "timeout"

        # 2. oletools for Office documents
        office_exts = [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf"]
        if any(filename.lower().endswith(ext) for ext in office_exts):
            try:
                result = subprocess.run(
                    ["/opt/maquita-webmail/backend/venv/bin/olevba", "--json", tmp_path],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        ole_data = json.loads(result.stdout)
                        details["oletools"] = ole_data
                        if isinstance(ole_data, list):
                            for item in ole_data:
                                if isinstance(item, dict):
                                    if item.get("type") == "AutoExec":
                                        threats.append({
                                            "engine": "oletools",
                                            "threat": f"AutoExec macro: {item.get(_KW, '?')}",
                                        })
                                    if item.get("type") == "Suspicious":
                                        threats.append({
                                            "engine": "oletools",
                                            "threat": f"Suspicious: {item.get(_KW, '?')}",
                                        })
                    except json.JSONDecodeError:
                        details["oletools"] = result.stdout[:500]
                else:
                    details["oletools"] = "no macros detected"
            except FileNotFoundError:
                details["oletools"] = "olevba not available"
            except subprocess.TimeoutExpired:
                details["oletools"] = "timeout"

        # 3. Real MIME type check
        try:
            result = subprocess.run(
                ["file", "--mime-type", tmp_path],
                capture_output=True, text=True, timeout=10,
            )
            real_type = result.stdout.split(":")[1].strip() if ":" in result.stdout else ""
            details["real_mime_type"] = real_type

            dangerous_types = [
                "application/x-executable", "application/x-dosexec",
                "application/x-msdos-program", "application/x-sharedlib",
            ]
            if real_type in dangerous_types:
                threats.append({
                    "engine": "file_analysis",
                    "threat": f"File is actually {real_type} despite extension {os.path.splitext(filename)[1]}",
                })
        except Exception:
            pass

        # Overall result
        if threats:
            scan_result = "malicious" if any(t["engine"] == "clamav" for t in threats) else "suspicious"
        else:
            scan_result = "clean"

    finally:
        os.unlink(tmp_path)

    return {"result": scan_result, "threats": threats, "details": details}


@router.post("/scan")
async def scan_attachment(request: Request, message_id: str, filename: str):
    """Scan attachments of a given message."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    # Fetch attachment via IMAP
    from app.mail.clients.imap_client import get_imap_connection
    password = await get_user_password(request, user)

    imap = await get_imap_connection(user, password)
    try:
        folders_to_search = ["INBOX", "Sent", "Drafts"]
        content = None
        content_type = "application/octet-stream"

        for folder in folders_to_search:
            try:
                await imap.select(folder)
                status, data = await imap.search("HEADER Message-ID " + message_id)
                if status == "OK" and data[0]:
                    uid = data[0].split()[0]
                    status, msg_data = await imap.fetch(
                        uid.decode() if isinstance(uid, bytes) else uid,
                        "(BODY.PEEK[])",
                    )
                    if status == "OK":
                        import email
                        raw = msg_data[1] if len(msg_data) > 1 else msg_data[0]
                        if isinstance(raw, tuple):
                            raw = raw[1]
                        msg = email.message_from_bytes(
                            raw if isinstance(raw, bytes) else raw.encode()
                        )
                        for part in msg.walk():
                            part_filename = part.get_filename()
                            if part_filename == filename:
                                content = part.get_payload(decode=True)
                                content_type = part.get_content_type()
                                break
                    if content:
                        break
            except Exception:
                continue

        if not content:
            raise HTTPException(404, f"Adjunto {filename} no encontrado")

    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    # Run scan
    scan_data = await deep_scan_attachment(content, filename, content_type)

    # Save to DB
    await db.execute(
        """INSERT INTO attachment_scans
           (message_id, filename, content_type, size, scan_result, threats_found, scan_details)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)""",
        message_id, filename, content_type, len(content),
        scan_data["result"], json.dumps(scan_data["threats"]),
        json.dumps(scan_data["details"]),
    )

    return {
        "message_id": message_id,
        "filename": filename,
        "size": len(content),
        "scan_result": scan_data["result"],
        "threats": scan_data["threats"],
        "details": scan_data["details"],
        "scanned_at": datetime.utcnow().isoformat(),
    }


@router.get("/scan/{message_id}")
async def get_scan_results(request: Request, message_id: str):
    """Get scan results for all attachments of a message."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    rows = await db.fetch(
        "SELECT * FROM attachment_scans WHERE message_id = $1 ORDER BY scanned_at DESC",
        message_id,
    )
    return {
        "message_id": message_id,
        "scans": [
            {
                "id": r["id"],
                "filename": r["filename"],
                "content_type": r["content_type"],
                "size": r["size"],
                "scan_result": r["scan_result"],
                "threats": json.loads(r["threats_found"]) if isinstance(r["threats_found"], str) else r["threats_found"],
                "details": json.loads(r["scan_details"]) if isinstance(r["scan_details"], str) else r["scan_details"],
                "scanned_at": r["scanned_at"].isoformat() if r["scanned_at"] else None,
                "scanned_by": r["scanned_by"],
            }
            for r in rows
        ],
    }


@router.get("/stats")
async def scan_stats(request: Request):
    """Scan statistics."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    total = await db.fetchval("SELECT COUNT(*) FROM attachment_scans")
    clean = await db.fetchval("SELECT COUNT(*) FROM attachment_scans WHERE scan_result = 'clean'")
    suspicious = await db.fetchval("SELECT COUNT(*) FROM attachment_scans WHERE scan_result = 'suspicious'")
    malicious = await db.fetchval("SELECT COUNT(*) FROM attachment_scans WHERE scan_result = 'malicious'")

    recent = await db.fetch(
        "SELECT filename, scan_result, scanned_at FROM attachment_scans ORDER BY scanned_at DESC LIMIT 10"
    )

    return {
        "total_scans": total,
        "clean": clean,
        "suspicious": suspicious,
        "malicious": malicious,
        "recent": [
            {
                "filename": r["filename"],
                "result": r["scan_result"],
                "scanned_at": r["scanned_at"].isoformat() if r["scanned_at"] else None,
            }
            for r in recent
        ],
    }
