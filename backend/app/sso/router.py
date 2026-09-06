"""SSO / SAML 2.0 basic integration."""

from __future__ import annotations

import base64
import logging
import uuid
import zlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_admin
from app.auth.jwt import create_access_token, create_refresh_token
from app.config import get_settings

security_logger = logging.getLogger("security")

router = APIRouter(prefix="/api/sso", tags=["sso"])

_s = get_settings()
SP_ENTITY_ID = f"https://{_s.cookie_domain}/api/sso/saml/metadata"
SP_ACS_URL = f"https://{_s.cookie_domain}/api/sso/saml/acs"
SP_SLO_URL = f"https://{_s.cookie_domain}/api/sso/saml/logout"


def _db(request: Request):
    return request.app.state.db_pool


def _redis(request: Request):
    return request.app.state.redis


# ── Schemas ───────────────────────────────────────────────


class SsoConfigOut(BaseModel):
    id: int
    provider: str
    entity_id: Optional[str] = None
    sso_url: Optional[str] = None
    slo_url: Optional[str] = None
    certificate: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SsoConfigUpdate(BaseModel):
    entity_id: Optional[str] = None
    sso_url: Optional[str] = None
    slo_url: Optional[str] = None
    certificate: Optional[str] = None
    is_active: Optional[bool] = None


# ── SP Metadata ───────────────────────────────────────────

METADATA_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{SP_ENTITY_ID}">
  <md:SPSSODescriptor
      AuthnRequestsSigned="false"
      WantAssertionsSigned="true"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:AssertionConsumerService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="{SP_ACS_URL}"
        index="0" isDefault="true"/>
    <md:SingleLogoutService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        Location="{SP_SLO_URL}"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""


@router.get("/saml/metadata", response_class=HTMLResponse)
async def saml_metadata():
    return Response(content=METADATA_XML, media_type="application/xml")


# ── SAML Login (redirect to IdP) ─────────────────────────


@router.get("/saml/login")
async def saml_login(request: Request):
    db = _db(request)
    redis = _redis(request)
    cfg = await db.fetchrow(
        "SELECT sso_url, entity_id FROM sso_config WHERE is_active = true LIMIT 1"
    )
    if not cfg or not cfg["sso_url"]:
        raise HTTPException(400, "SSO no esta configurado o inactivo")

    request_id = f"_maquita_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    authn_request = f"""<samlp:AuthnRequest
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{now}"
    Destination="{cfg['sso_url']}"
    AssertionConsumerServiceURL="{SP_ACS_URL}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
  <saml:Issuer>{SP_ENTITY_ID}</saml:Issuer>
  <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""

    compressed = zlib.compress(authn_request.encode())[2:-4]  # raw deflate
    encoded = base64.b64encode(compressed).decode()

    await redis.setex(f"saml_req:{request_id}", 600, "pending")

    url = cfg["sso_url"] + "?" + urlencode({"SAMLRequest": encoded, "RelayState": ""})
    return RedirectResponse(url=url, status_code=302)


# ── SAML ACS (Assertion Consumer Service) ─────────────────


@router.post("/saml/acs")
async def saml_acs(request: Request):
    """ACS (F-02): firma verificada y TODO lo demás leído del XML verificado, con correlación
    de un solo uso, Destination/Recipient/Audience/tiempos y Assertion ID de un solo uso.
    Ver app/sso/saml_seguridad.py."""
    db = _db(request)
    redis = _redis(request)
    form = await request.form()
    saml_response_b64 = form.get("SAMLResponse")
    if not saml_response_b64:
        raise HTTPException(400, "No SAMLResponse recibido")
    try:
        saml_xml = base64.b64decode(saml_response_b64)
        if len(saml_xml) > 256 * 1024:
            raise ValueError("demasiado grande")
    except Exception:
        raise HTTPException(400, "SAMLResponse inválido")

    cfg = await db.fetchrow(
        "SELECT certificate FROM sso_config WHERE is_active = true LIMIT 1"
    )
    if not cfg or not cfg["certificate"]:
        raise HTTPException(
            500, "SSO: No hay certificado IdP configurado para verificar firma"
        )

    from lxml import etree as lxml_etree
    from signxml import XMLVerifier

    from app.sso import saml_seguridad as ss

    try:
        parser = lxml_etree.XMLParser(
            resolve_entities=False, no_network=True, huge_tree=False
        )
        lxml_root = lxml_etree.fromstring(saml_xml, parser=parser)
        verified = XMLVerifier().verify(lxml_root, x509_cert=cfg["certificate"])
    except Exception:
        security_logger.warning(
            "SAML_FIRMA_INVALIDA ip=%s", request.client.host if request.client else "?"
        )
        raise HTTPException(403, "Firma SAML inválida")

    try:
        response, assertion = ss.extraer_verificado(verified)
        datos = ss.validar(
            response,
            assertion,
            acs_url=SP_ACS_URL,
            entity_id=SP_ENTITY_ID,
            response_sin_firmar=lxml_root,
        )
        await ss.consumir_una_vez(
            redis,
            datos["in_response_to"],
            datos["assertion_id"],
            datos["not_on_or_after"],
        )
    except ss.SAMLRechazada as exc:
        security_logger.warning("SAML_RECHAZADA motivo=%s", str(exc)[:120])
        raise HTTPException(403, "Respuesta SAML rechazada")

    email = datos["name_id"]
    from app.config import get_settings

    settings = get_settings()
    if not email.endswith(f"@{settings.mail_domain}"):
        raise HTTPException(403, "La cuenta no pertenece al dominio del correo")
    if not await db.fetchval(
        "SELECT 1 FROM mailbox WHERE username = $1 AND active = true", email
    ):
        raise HTTPException(403, "La cuenta no tiene un buzón activo")

    # Sesión federada (kind=saml): mismo modelo sid/av que el resto (F-01/F-04).
    from datetime import datetime, timedelta, timezone

    from app.auth.cookies import poner_cookies_sesion
    from app.auth.sesiones import crear_sesion

    sesion = await crear_sesion(
        db,
        redis,
        request,
        email,
        settings.master_password,
        kind="saml",
        abs_exp=datetime.now(timezone.utc) + timedelta(hours=1),
        master="admin",
        user_agent="SSO-SAML",
    )
    await redis.setex(f"sso_session:{email}", 86400, "saml")
    response_http = RedirectResponse(
        url=f"https://{settings.cookie_domain}/", status_code=302
    )
    poner_cookies_sesion(response_http, request, sesion)
    return response_http


# ── SAML Logout ───────────────────────────────────────────


@router.get("/saml/logout")
async def saml_logout(request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    redis = _redis(request)
    cfg = await db.fetchrow(
        "SELECT slo_url FROM sso_config WHERE is_active = true LIMIT 1"
    )
    await redis.delete(f"sso_session:{user}")
    from app.auth.sesiones import cerrar_sid

    await cerrar_sid(db, redis, user, request.state.sid, "saml_logout")

    if cfg and cfg["slo_url"]:
        return RedirectResponse(url=cfg["slo_url"], status_code=302)
    return {"status": "logged_out"}


# ── Admin: get/update SSO config ──────────────────────────


@router.get("/config", response_model=SsoConfigOut)
async def get_sso_config(request: Request, user: str = Depends(require_admin)):
    db = _db(request)
    row = await db.fetchrow("SELECT * FROM sso_config ORDER BY id LIMIT 1")
    if not row:
        await db.execute("INSERT INTO sso_config (provider) VALUES ($1)", "saml")
        row = await db.fetchrow("SELECT * FROM sso_config ORDER BY id LIMIT 1")
    return dict(row)


@router.put("/config", response_model=SsoConfigOut)
async def update_sso_config(
    data: SsoConfigUpdate, request: Request, user: str = Depends(require_admin)
):
    db = _db(request)
    row = await db.fetchrow("SELECT id FROM sso_config ORDER BY id LIMIT 1")
    if not row:
        await db.execute("INSERT INTO sso_config (provider) VALUES ($1)", "saml")
        row = await db.fetchrow("SELECT id FROM sso_config ORDER BY id LIMIT 1")

    fields = []
    values = []
    idx = 1
    for field in ("entity_id", "sso_url", "slo_url", "certificate", "is_active"):
        val = getattr(data, field, None)
        if val is not None:
            fields.append(f"{field} = ${idx}")
            values.append(val)
            idx += 1
    if not fields:
        raise HTTPException(400, "Nada que actualizar")

    fields.append(f"updated_at = ${idx}")
    values.append(datetime.now(timezone.utc))
    idx += 1
    values.append(row["id"])

    await db.execute(
        f"UPDATE sso_config SET {', '.join(fields)} WHERE id = ${idx}",
        *values,
    )
    updated = await db.fetchrow("SELECT * FROM sso_config WHERE id = $1", row["id"])
    return dict(updated)
