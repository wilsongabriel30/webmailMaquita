"""S/MIME certificate management and message signing/encryption."""
from __future__ import annotations

import base64
import hashlib
import subprocess
import tempfile
from datetime import datetime
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/smime", tags=["smime"])


def _db(request: Request):
    return request.app.state.db_pool


def _redis(request: Request):
    return request.app.state.redis


# ── Schemas ───────────────────────────────────────────────

class CertificateOut(BaseModel):
    id: int
    user_email: str
    issuer: Optional[str] = None
    subject: Optional[str] = None
    serial_number: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    fingerprint: Optional[str] = None
    is_private: bool = False
    created_at: Optional[datetime] = None


class SmimeStatusOut(BaseModel):
    signed: bool = False
    encrypted: bool = False
    signer: Optional[str] = None
    valid: Optional[bool] = None


# ── Upload certificate ────────────────────────────────────

@router.post("/keys/upload", response_model=CertificateOut, status_code=201)
async def upload_certificate(
    request: Request,
    file: UploadFile = File(...),
    passphrase: Optional[str] = Form(None),
    user: str = Depends(get_current_user),
):
    db = _db(request)
    data = await file.read()
    if len(data) > 100_000:
        raise HTTPException(400, "Archivo demasiado grande (max 100KB)")

    cert_pem = None
    key_pem = None
    cert_obj = None

    fname = (file.filename or "").lower()
    try:
        if fname.endswith(".p12") or fname.endswith(".pfx"):
            pw = passphrase.encode() if passphrase else None
            private_key, certificate, chain = pkcs12.load_key_and_certificates(data, pw)
            cert_obj = certificate
            cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
            if private_key:
                key_pem = private_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.BestAvailableEncryption(b"smime-maquita-key"),
                ).decode()
        else:
            cert_obj = x509.load_pem_x509_certificate(data)
            cert_pem = data.decode()
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el certificado: {exc}")

    fp = hashlib.sha256(cert_obj.public_bytes(serialization.Encoding.DER)).hexdigest()
    issuer = cert_obj.issuer.rfc4514_string()
    subject = cert_obj.subject.rfc4514_string()
    serial = str(cert_obj.serial_number)

    row = await db.fetchrow(
        """INSERT INTO smime_certificates
            (user_email, certificate_pem, private_key_encrypted, issuer, subject,
             serial_number, valid_from, valid_to, fingerprint, is_private)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
           ON CONFLICT (fingerprint) DO UPDATE SET user_email = EXCLUDED.user_email
           RETURNING *""",
        user, cert_pem, key_pem, issuer, subject, serial,
        cert_obj.not_valid_before_utc, cert_obj.not_valid_after_utc,
        fp, key_pem is not None,
    )
    return dict(row)


# ── List certificates ─────────────────────────────────────

@router.get("/keys", response_model=list[CertificateOut])
async def list_certificates(
    request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    rows = await db.fetch(
        "SELECT id, user_email, issuer, subject, serial_number, valid_from, "
        "valid_to, fingerprint, is_private, created_at "
        "FROM smime_certificates WHERE user_email = $1 ORDER BY created_at DESC",
        user,
    )
    return [dict(r) for r in rows]


# ── Delete certificate ────────────────────────────────────

@router.delete("/keys/{cert_id}", status_code=204)
async def delete_certificate(
    cert_id: int, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    result = await db.execute(
        "DELETE FROM smime_certificates WHERE id = $1 AND user_email = $2",
        cert_id, user,
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Certificado no encontrado")


# ── Public key lookup ─────────────────────────────────────

@router.get("/keys/public/{email}")
async def get_public_key(email: str, request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    row = await db.fetchrow(
        "SELECT certificate_pem, issuer, subject, valid_to FROM smime_certificates "
        "WHERE user_email = $1 AND valid_to > NOW() ORDER BY created_at DESC LIMIT 1",
        email,
    )
    if not row:
        raise HTTPException(404, "No se encontro certificado publico para este email")
    return {"email": email, "certificate_pem": row["certificate_pem"],
            "issuer": row["issuer"], "subject": row["subject"], "valid_to": row["valid_to"]}


# ── Sign message ──────────────────────────────────────────

class SignRequest(BaseModel):
    message: str  # raw RFC822 or body text


@router.post("/sign")
async def sign_message(
    body: SignRequest, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    row = await db.fetchrow(
        "SELECT certificate_pem, private_key_encrypted FROM smime_certificates "
        "WHERE user_email = $1 AND is_private = true AND valid_to > NOW() "
        "ORDER BY created_at DESC LIMIT 1",
        user,
    )
    if not row:
        raise HTTPException(400, "No tiene certificado S/MIME con clave privada")

    with tempfile.NamedTemporaryFile(suffix=".pem", mode="w", delete=False) as cf:
        cf.write(row["certificate_pem"])
        cert_path = cf.name
    with tempfile.NamedTemporaryFile(suffix=".key", mode="w", delete=False) as kf:
        kf.write(row["private_key_encrypted"])
        key_path = kf.name
    with tempfile.NamedTemporaryFile(suffix=".eml", mode="w", delete=False) as mf:
        mf.write(body.message)
        msg_path = mf.name

    try:
        result = subprocess.run(
            ["openssl", "smime", "-sign", "-in", msg_path,
             "-signer", cert_path, "-inkey", key_path,
             "-passin", "pass:smime-maquita-key"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise HTTPException(500, f"Error al firmar: {result.stderr[:200]}")
        return {"signed_message": result.stdout}
    finally:
        import os
        for p in (cert_path, key_path, msg_path):
            os.unlink(p)


# ── Encrypt message ───────────────────────────────────────

class EncryptRequest(BaseModel):
    message: str
    recipient_email: str


@router.post("/encrypt")
async def encrypt_message(
    body: EncryptRequest, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    row = await db.fetchrow(
        "SELECT certificate_pem FROM smime_certificates "
        "WHERE user_email = $1 AND valid_to > NOW() ORDER BY created_at DESC LIMIT 1",
        body.recipient_email,
    )
    if not row:
        raise HTTPException(404, f"No hay certificado publico para {body.recipient_email}")

    with tempfile.NamedTemporaryFile(suffix=".pem", mode="w", delete=False) as cf:
        cf.write(row["certificate_pem"])
        cert_path = cf.name
    with tempfile.NamedTemporaryFile(suffix=".eml", mode="w", delete=False) as mf:
        mf.write(body.message)
        msg_path = mf.name

    try:
        result = subprocess.run(
            ["openssl", "smime", "-encrypt", "-aes256",
             "-in", msg_path, cert_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise HTTPException(500, f"Error al encriptar: {result.stderr[:200]}")
        return {"encrypted_message": result.stdout}
    finally:
        import os
        for p in (cert_path, msg_path):
            os.unlink(p)


# ── Verify signature ─────────────────────────────────────

class VerifyRequest(BaseModel):
    message: str


@router.post("/verify")
async def verify_signature(
    body: VerifyRequest, request: Request, user: str = Depends(get_current_user)
):
    with tempfile.NamedTemporaryFile(suffix=".eml", mode="w", delete=False) as mf:
        mf.write(body.message)
        msg_path = mf.name
    try:
        result = subprocess.run(
            ["openssl", "smime", "-verify", "-in", msg_path,
             "-CAfile", "/etc/ssl/certs/ca-certificates.crt"],
            capture_output=True, text=True, timeout=10,
        )
        valid = result.returncode == 0
        signer = None
        for line in result.stderr.split("\n"):
            if "signer" in line.lower() or "subject" in line.lower():
                signer = line.strip()
                break
        return {"valid": valid, "signer": signer, "detail": result.stderr[:300]}
    finally:
        import os
        os.unlink(msg_path)


# ── Message S/MIME status ─────────────────────────────────

@router.get("/status/{message_id}", response_model=SmimeStatusOut)
async def message_smime_status(
    message_id: str,
    request: Request,
    user: str = Depends(get_current_user),
):
    redis = _redis(request)
    password = await redis.get(f"imap_pass:{user}")
    if not password:
        raise HTTPException(401, "Sesion IMAP no disponible")

    from app.mail.clients.imap_client import get_imap_connection
    imap = await get_imap_connection(user, password)
    try:
        await imap.select("INBOX")
        uids = await imap.search(f"HEADER Message-ID {message_id}")
        if not uids:
            raise HTTPException(404, "Mensaje no encontrado")

        uid = uids[0]
        msg_data = await imap.fetch([uid], ["BODY.PEEK[]"])
        if uid not in msg_data:
            raise HTTPException(404, "No se pudo obtener el mensaje")

        raw = msg_data[uid].get(b"BODY[]", b"")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        signed = False
        encrypted = False
        signer_info = None
        valid = None

        if "application/pkcs7-mime" in raw or "application/x-pkcs7-mime" in raw:
            encrypted = True
            if "enveloped-data" in raw:
                encrypted = True
            if "signed-data" in raw:
                signed = True
        if "multipart/signed" in raw:
            signed = True

        if signed:
            with tempfile.NamedTemporaryFile(suffix=".eml", mode="w", delete=False) as f:
                f.write(raw)
                tmp = f.name
            try:
                r = subprocess.run(
                    ["openssl", "smime", "-verify", "-in", tmp,
                     "-CAfile", "/etc/ssl/certs/ca-certificates.crt"],
                    capture_output=True, text=True, timeout=10,
                )
                valid = r.returncode == 0
                for line in r.stderr.split("\n"):
                    if "subject" in line.lower():
                        signer_info = line.strip()
                        break
            finally:
                import os
                os.unlink(tmp)

        return SmimeStatusOut(signed=signed, encrypted=encrypted, signer=signer_info, valid=valid)
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
