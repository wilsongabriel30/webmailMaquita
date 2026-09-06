"""Onboarding sin tipeo: datos exactos de configuración + perfil .mobileconfig (iPhone/iPad).

El usuario SIEMPRE es el correo completo con @ (la causa del bloqueo real fue teclear
user.dominio.com en vez de user@dominio.com). El perfil de Apple precarga todo menos la
contraseña, así no hay tecleo del servidor ni del usuario.
"""

import html
import uuid

from fastapi import APIRouter, Depends, Response

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Namespace fijo para UUIDs deterministas (reinstalar el perfil lo ACTUALIZA, no duplica)
_NS = uuid.UUID("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")


def _account(username: str) -> dict:
    domain = username.split("@")[-1].lower()
    host = f"mail.{domain}"
    return {
        "email": username,
        "username": username,  # correo COMPLETO con @
        "host": host,
        "imap": {"host": host, "port": 993, "security": "SSL/TLS"},
        "smtp": {"host": host, "port": 465, "security": "SSL/TLS"},
        "auth": "Contraseña normal",
        "note": "El usuario es tu correo completo con @ (no 'mail.', no solo el nombre).",
    }


@router.get("/settings")
async def onboarding_settings(username: str = Depends(get_current_user)):
    return _account(username)


@router.get("/apple-profile")
async def apple_profile(username: str = Depends(get_current_user)):
    acc = _account(username)
    u = html.escape(username)
    h = html.escape(acc["host"])
    domain = html.escape(username.split("@")[-1].lower())
    ident = f"org.maquita.mail.{domain}"
    prof_uuid = str(uuid.uuid5(_NS, f"profile:{username}")).upper()
    acct_uuid = str(uuid.uuid5(_NS, f"account:{username}")).upper()
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadType</key><string>com.apple.mail.managed</string>
      <key>PayloadVersion</key><integer>1</integer>
      <key>PayloadIdentifier</key><string>{ident}.account</string>
      <key>PayloadUUID</key><string>{acct_uuid}</string>
      <key>PayloadDisplayName</key><string>Correo {u}</string>
      <key>EmailAccountType</key><string>EmailTypeIMAP</string>
      <key>EmailAccountName</key><string>{u}</string>
      <key>EmailAccountDescription</key><string>{u}</string>
      <key>EmailAddress</key><string>{u}</string>
      <key>IncomingMailServerHostName</key><string>{h}</string>
      <key>IncomingMailServerPortNumber</key><integer>993</integer>
      <key>IncomingMailServerUseSSL</key><true/>
      <key>IncomingMailServerAuthentication</key><string>EmailAuthPassword</string>
      <key>IncomingMailServerUsername</key><string>{u}</string>
      <key>OutgoingMailServerHostName</key><string>{h}</string>
      <key>OutgoingMailServerPortNumber</key><integer>465</integer>
      <key>OutgoingMailServerUseSSL</key><true/>
      <key>OutgoingMailServerAuthentication</key><string>EmailAuthPassword</string>
      <key>OutgoingMailServerUsername</key><string>{u}</string>
      <key>OutgoingPasswordSameAsIncomingPassword</key><true/>
      <key>SMIMEEnabled</key><false/>
    </dict>
  </array>
  <key>PayloadDisplayName</key><string>Correo Maquita ({u})</string>
  <key>PayloadIdentifier</key><string>{ident}</string>
  <key>PayloadType</key><string>Configuration</string>
  <key>PayloadUUID</key><string>{prof_uuid}</string>
  <key>PayloadVersion</key><integer>1</integer>
  <key>PayloadOrganization</key><string>Maquita</string>
  <key>PayloadDescription</key><string>Configura tu correo {u} en iPhone/iPad sin escribir nada.</string>
</dict>
</plist>
"""
    return Response(
        content=plist,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": 'attachment; filename="correo-maquita.mobileconfig"'
        },
    )
