"""
Recuperacion de acceso al PANEL ADMIN mediante correo alternativo (Gmail/Hotmail/otro).
Flujo:
  1) El admin registra su correo alternativo -> se le envia un codigo OTP a ese correo.
  2) Ingresa el OTP -> el correo queda verificado y activo como via de recuperacion.
  3) Si pierde el acceso al panel: solicita recuperacion -> se envia un token al correo alternativo.
  4) Con el token define una nueva contrasena del panel.
Limite: 5 recuperaciones por anio. Superado, se desbloquea por consola:
  maquita-admin-recovery reset-counter <admin>
Solo para el panel admin. Autor: Wilson Arguello — Fundacion Maquita.
"""
import re, secrets, hashlib, smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
import bcrypt
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/admin-recovery", tags=["admin-recovery"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_PER_YEAR = 5
FROM_ADDR = "seguridad@maquita.org"


def _db(r: Request):
    return r.app.state.db


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _mask(email: str) -> str:
    try:
        u, d = email.split("@", 1)
        return (u[0] + "***" + u[-1] if len(u) > 2 else u[0] + "***") + "@" + d
    except Exception:
        return "***"


def _send(to: str, subject: str, body: str) -> bool:
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_ADDR
    msg["To"] = to
    try:
        s = smtplib.SMTP("127.0.0.1", 25, timeout=15)
        s.sendmail(FROM_ADDR, [to], msg.as_string())
        s.quit()
        return True
    except Exception:
        return False


# ── Registro del correo alternativo (autenticado) ────────────────
@router.get("/status")
async def status(r: Request, a=Depends(get_current_admin)):
    row = await _db(r).fetchrow(
        "SELECT recovery_email, verified, uses_this_year, counter_year FROM admin_recovery WHERE username=$1",
        a["username"])
    if not row or not row["recovery_email"]:
        return {"configured": False}
    return {"configured": True, "verified": row["verified"],
            "recovery_email": _mask(row["recovery_email"]),
            "uses_this_year": row["uses_this_year"], "max_per_year": MAX_PER_YEAR}


class EmailReq(BaseModel):
    recovery_email: str


@router.post("/register")
async def register(body: EmailReq, r: Request, a=Depends(get_current_admin)):
    email = (body.recovery_email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Correo alternativo invalido")
    otp = f"{secrets.randbelow(1000000):06d}"
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    await _db(r).execute(
        "INSERT INTO admin_recovery (username, recovery_email, verified, otp_hash, otp_expires, otp_attempts, updated_at) "
        "VALUES ($1,$2,false,$3,$4,0,now()) ON CONFLICT (username) DO UPDATE SET "
        "recovery_email=$2, verified=false, otp_hash=$3, otp_expires=$4, otp_attempts=0, updated_at=now()",
        a["username"], email, _h(otp), exp)
    _send(email, "Codigo de verificacion — Panel Maquita",
          f"Tu codigo para activar la recuperacion del panel administrativo es:\n\n    {otp}\n\n"
          f"Vence en 15 minutos. Si no solicitaste esto, ignora este mensaje.\n\n-- Seguridad Maquita")
    return {"ok": True, "sent_to": _mask(email)}


class OtpReq(BaseModel):
    otp: str


@router.post("/verify")
async def verify(body: OtpReq, r: Request, a=Depends(get_current_admin)):
    row = await _db(r).fetchrow(
        "SELECT otp_hash, otp_expires, otp_attempts FROM admin_recovery WHERE username=$1", a["username"])
    if not row or not row["otp_hash"]:
        raise HTTPException(400, "No hay verificacion pendiente")
    if (row["otp_attempts"] or 0) >= 5:
        raise HTTPException(429, "Demasiados intentos. Vuelve a registrar el correo.")
    if not row["otp_expires"] or row["otp_expires"] < datetime.now(timezone.utc):
        raise HTTPException(400, "El codigo expiro. Registra el correo de nuevo.")
    if _h((body.otp or "").strip()) != row["otp_hash"]:
        await _db(r).execute("UPDATE admin_recovery SET otp_attempts=otp_attempts+1 WHERE username=$1", a["username"])
        raise HTTPException(400, "Codigo incorrecto")
    await _db(r).execute(
        "UPDATE admin_recovery SET verified=true, otp_hash=NULL, otp_expires=NULL, otp_attempts=0, updated_at=now() WHERE username=$1",
        a["username"])
    return {"ok": True, "verified": True}


# ── Recuperacion sin sesion (admin bloqueado) ────────────────────
class UserReq(BaseModel):
    username: str


@router.post("/request")
async def request_recovery(body: UserReq, r: Request):
    # Respuesta SIEMPRE generica (no revelar si el usuario existe o tiene recuperacion)
    generic = {"ok": True, "message": "Si la cuenta tiene recuperacion configurada, se envio un enlace al correo alternativo."}
    username = (body.username or "").strip()
    row = await _db(r).fetchrow(
        "SELECT recovery_email, verified, uses_this_year, counter_year FROM admin_recovery WHERE username=$1", username)
    if not row or not row["verified"] or not row["recovery_email"]:
        return generic
    year = datetime.now(timezone.utc).year
    uses = row["uses_this_year"] if row["counter_year"] == year else 0
    if uses >= MAX_PER_YEAR:
        # Agotado: requiere desbloqueo por consola. No revelar; registrar.
        return generic
    token = secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    await _db(r).execute(
        "UPDATE admin_recovery SET token_hash=$1, token_expires=$2, uses_this_year=$3, counter_year=$4, updated_at=now() WHERE username=$5",
        _h(token), exp, uses + 1, year, username)
    _send(row["recovery_email"], "Recuperacion de acceso — Panel Maquita",
          f"Se solicito recuperar el acceso al panel administrativo de: {username}\n\n"
          f"Tu token de recuperacion (valido 30 min, un solo uso):\n\n    {token}\n\n"
          f"Usalo en la pantalla de recuperacion del panel para definir una nueva contrasena.\n"
          f"Llevas {uses + 1}/{MAX_PER_YEAR} recuperaciones este anio.\n"
          f"Si no fuiste tu, contacta a Tecnologia de inmediato.\n\n-- Seguridad Maquita")
    return generic


class ResetReq(BaseModel):
    username: str
    token: str
    new_password: str


@router.post("/reset")
async def reset_password(body: ResetReq, r: Request):
    username = (body.username or "").strip()
    if len(body.new_password or "") < 10:
        raise HTTPException(400, "La contrasena debe tener al menos 10 caracteres")
    row = await _db(r).fetchrow(
        "SELECT token_hash, token_expires FROM admin_recovery WHERE username=$1", username)
    if not row or not row["token_hash"]:
        raise HTTPException(400, "Token invalido")
    if not row["token_expires"] or row["token_expires"] < datetime.now(timezone.utc):
        raise HTTPException(400, "El token expiro")
    if _h((body.token or "").strip()) != row["token_hash"]:
        raise HTTPException(400, "Token invalido")
    ph = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    await _db(r).execute(
        "UPDATE admin_users SET password_hash=$1, failed_attempts=0, locked_until=NULL, active=true WHERE username=$2",
        ph, username)
    await _db(r).execute(
        "UPDATE admin_recovery SET token_hash=NULL, token_expires=NULL, updated_at=now() WHERE username=$1", username)
    return {"ok": True, "message": "Contrasena actualizada. Ya puedes iniciar sesion."}
