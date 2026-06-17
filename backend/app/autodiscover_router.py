"""Autodiscover de Outlook (IMAP/SMTP) — dinámico y MULTI-DOMINIO.

Outlook NO soporta placeholders como el autoconfig de Thunderbird, y un autodiscover estático
dejaba `<LoginName>` vacío -> el usuario tecleaba el usuario a mano y metía `user.dominio` en vez
de `user@dominio` (la causa del bloqueo).

Aquí:
- `<LoginName>` = el correo COMPLETO que el cliente envió (cualquier dominio).
- `<Server>` = el host canónico del correo (mismo Dovecot que sirve TODOS los dominios virtuales:
  maquita.org, maquita.com.ec, maquitaturismo.com, etc.). Por eso un usuario de cualquier dominio
  se conecta al mismo servidor con su correo completo como usuario.

Host canónico: env `AUTODISCOVER_MAIL_HOST`, si no `mail.<mail_domain>` del .env.
Anónimo (solo entrega ajustes; el email viene en el POST). Montado sin prefijo; nginx enruta
/autodiscover/autodiscover.xml al backend para CADA dominio (ver doc: DNS SRV/CNAME por dominio).
"""
import html
import os
import re

from fastapi import APIRouter, Request, Response

from app.config import get_settings

router = APIRouter()

_EMAIL_RE = re.compile(r"<EMailAddress>\s*([^<>\s]+@[^<>\s]+)\s*</EMailAddress>", re.IGNORECASE)
_VALID = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _mail_host() -> str:
    h = os.environ.get("AUTODISCOVER_MAIL_HOST")
    if h:
        return h
    md = (get_settings().mail_domain or "").strip()
    return f"mail.{md}" if md and md != "example.com" else "mail.maquita.org"


def _build_xml(email: str) -> str:
    e = html.escape(email)
    host = html.escape(_mail_host())
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a">
    <Account>
      <AccountType>email</AccountType>
      <Action>settings</Action>
      <Protocol>
        <Type>IMAP</Type>
        <Server>{host}</Server>
        <Port>993</Port>
        <DomainRequired>off</DomainRequired>
        <LoginName>{e}</LoginName>
        <SPA>off</SPA>
        <SSL>on</SSL>
        <AuthRequired>on</AuthRequired>
      </Protocol>
      <Protocol>
        <Type>SMTP</Type>
        <Server>{host}</Server>
        <Port>465</Port>
        <DomainRequired>off</DomainRequired>
        <LoginName>{e}</LoginName>
        <SPA>off</SPA>
        <SSL>on</SSL>
        <Encryption>SSL</Encryption>
        <AuthRequired>on</AuthRequired>
        <UsePOPAuth>off</UsePOPAuth>
        <SMTPLast>off</SMTPLast>
      </Protocol>
    </Account>
  </Response>
</Autodiscover>
"""


async def _handle(request: Request) -> Response:
    raw = (await request.body()).decode("utf-8", "ignore")
    m = _EMAIL_RE.search(raw)
    email = m.group(1).strip().lower() if m else ""
    if not _VALID.match(email):
        return Response(
            content='<?xml version="1.0" encoding="utf-8"?><Autodiscover><Response>'
            "<Error><Message>Email invalido</Message></Error></Response></Autodiscover>",
            media_type="application/xml",
            status_code=400,
        )
    return Response(content=_build_xml(email), media_type="application/xml")


@router.post("/autodiscover/autodiscover.xml")
async def autodiscover(request: Request):
    return await _handle(request)


@router.post("/Autodiscover/Autodiscover.xml")
async def autodiscover_capitalized(request: Request):
    return await _handle(request)
