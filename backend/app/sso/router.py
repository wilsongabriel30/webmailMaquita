"""SSO / SAML 2.0 basic integration."""
from __future__ import annotations

import base64
import uuid
import zlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_admin
from app.auth.jwt import create_access_token, create_refresh_token
from app.config import get_settings

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
    db = _db(request)
    redis = _redis(request)
    form = await request.form()
    saml_response_b64 = form.get("SAMLResponse")
    if not saml_response_b64:
        raise HTTPException(400, "No SAMLResponse recibido")

    try:
        saml_xml = base64.b64decode(saml_response_b64)
        root = ET.fromstring(saml_xml)
    except Exception as exc:
        raise HTTPException(400, f"SAMLResponse inválido: {exc}")

    # ── Verify SAML XML signature (critical: prevents auth bypass) ──
    cfg = await db.fetchrow(
        "SELECT certificate FROM sso_config WHERE is_active = true LIMIT 1"
    )
    if not cfg or not cfg["certificate"]:
        raise HTTPException(500, "SSO: No hay certificado IdP configurado para verificar firma")

    try:
        from signxml import XMLVerifier
        from lxml import etree as lxml_etree

        idp_cert_pem = cfg["certificate"]
        lxml_root = lxml_etree.fromstring(saml_xml)
        XMLVerifier().verify(lxml_root, x509_cert=idp_cert_pem)
    except Exception as sig_exc:
        raise HTTPException(403, f"Firma SAML inválida: {sig_exc}")

    # Extract NameID (email)
    ns = {
        "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    }

    status_el = root.find(".//samlp:Status/samlp:StatusCode", ns)
    if status_el is not None:
        status_value = status_el.get("Value", "")
        if "Success" not in status_value:
            raise HTTPException(403, f"SAML auth fallida: {status_value}")

    name_id_el = root.find(".//saml:Assertion/saml:Subject/saml:NameID", ns)
    if name_id_el is None:
        name_id_el = root.find(".//saml:NameID", ns)
    if name_id_el is None or not name_id_el.text:
        raise HTTPException(400, "No se encontró NameID en la respuesta SAML")

    email = name_id_el.text.strip().lower()

    # Verify domain
    from app.config import get_settings
    settings = get_settings()
    if not email.endswith(f"@{settings.mail_domain}"):
        raise HTTPException(403, f"Email {email} no pertenece al dominio {settings.mail_domain}")

    # Create JWT session
    access_token = create_access_token(email)
    refresh_raw, refresh_hash = create_refresh_token()
    await db.execute(
        "INSERT INTO refresh_tokens (username, token_hash, expires_at) "
        "VALUES ($1, $2, NOW() + interval '7 days')",
        email, refresh_hash,
    )

    # Set flag so frontend knows this is SSO session
    await redis.setex(f"sso_session:{email}", 86400, "saml")

    # Redirect to frontend with cookies
    response = RedirectResponse(url=f"https://{settings.cookie_domain}/", status_code=302)
    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=True, samesite="lax",
        domain=settings.cookie_domain, max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        "refresh_token", refresh_raw,
        httponly=True, secure=True, samesite="lax",
        domain=settings.cookie_domain, path="/api/auth/refresh",
        max_age=settings.refresh_token_expire_days * 86400,
    )
    return response


# ── SAML Logout ───────────────────────────────────────────

@router.get("/saml/logout")
async def saml_logout(request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    redis = _redis(request)
    cfg = await db.fetchrow(
        "SELECT slo_url FROM sso_config WHERE is_active = true LIMIT 1"
    )
    await redis.delete(f"sso_session:{user}")
    await redis.delete(f"imap_pass:{user}")

    if cfg and cfg["slo_url"]:
        return RedirectResponse(url=cfg["slo_url"], status_code=302)
    return {"status": "logged_out"}


# ── Admin: get/update SSO config ──────────────────────────

@router.get("/config", response_model=SsoConfigOut)
async def get_sso_config(request: Request, user: str = Depends(require_admin)):
    db = _db(request)
    row = await db.fetchrow("SELECT * FROM sso_config ORDER BY id LIMIT 1")
    if not row:
        await db.execute(
            "INSERT INTO sso_config (provider) VALUES ($1)", "saml"
        )
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
