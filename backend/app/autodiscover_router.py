"""Autodiscover de Outlook — dinámico, MULTI-DOMINIO, IMAP/SMTP **y ActiveSync**.

Outlook NO soporta placeholders como el autoconfig de Thunderbird, y un autodiscover estático
dejaba `<LoginName>` vacío -> el usuario tecleaba el usuario a mano y metía `user.dominio` en vez
de `user@dominio` (la causa del bloqueo).

Tres respuestas, según lo que pida el cliente (D-9 corregida, 07/09/2026: z-push vuelve porque
dirección trabaja en Outlook, y el NUEVO Outlook no admite configuración manual de ActiveSync,
depende por completo del autodiscover):

- XML, esquema `outlook/responseschema/2006a` (Outlook clásico como IMAP): IMAP 993 + SMTP 465,
  `<LoginName>` = el correo COMPLETO que el cliente envió (cualquier dominio).
- XML, esquema `mobilesync/responseschema/2006` (Outlook clásico como Exchange ActiveSync, Android,
  iOS): `<Type>MobileSync</Type>` con la URL de Z-Push.
- JSON v2 (`/autodiscover/autodiscover.json[/v1.0/<correo>]?Protocol=ActiveSync|AutodiscoverV1`),
  el que usa el nuevo Outlook y Outlook móvil.

`<Server>` = el host canónico del correo (mismo Dovecot que sirve TODOS los dominios virtuales).
Host canónico: env `AUTODISCOVER_MAIL_HOST`, si no `mail.<mail_domain>` del .env.
Anónimo (solo entrega ajustes; el email viene en el POST). Montado sin prefijo; nginx enruta
/autodiscover/autodiscover.xml y .json al backend para CADA dominio.
"""

import html
import os
import re

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings

router = APIRouter()

_EMAIL_RE = re.compile(
    r"<EMailAddress>\s*([^<>\s]+@[^<>\s]+)\s*</EMailAddress>", re.IGNORECASE
)
_VALID = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ESQUEMA_MOBILESYNC = (
    "http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006"
)
ESQUEMA_OUTLOOK = (
    "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a"
)


def _mail_host() -> str:
    h = os.environ.get("AUTODISCOVER_MAIL_HOST")
    if h:
        return h
    md = (get_settings().mail_domain or "").strip()
    return f"mail.{md}" if md and md != "example.com" else "mail.maquita.org"


def url_activesync() -> str:
    return f"https://{_mail_host()}/Microsoft-Server-ActiveSync"


def esquema_pedido(raw: str) -> str:
    """'mobilesync' si el cliente pide ActiveSync; si no, 'outlook' (IMAP/SMTP)."""
    m = re.search(
        r"<AcceptableResponseSchema>\s*([^<\s]+)\s*</AcceptableResponseSchema>",
        raw,
        re.IGNORECASE,
    )
    if m and "mobilesync" in m.group(1).lower():
        return "mobilesync"
    return "outlook"


def _build_xml(email: str) -> str:
    e = html.escape(email)
    host = html.escape(_mail_host())
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="{ESQUEMA_OUTLOOK}">
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


def _build_xml_mobilesync(email: str) -> str:
    e = html.escape(email)
    url = html.escape(url_activesync())
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="{ESQUEMA_MOBILESYNC}">
    <Culture>es:es</Culture>
    <User>
      <DisplayName>{e}</DisplayName>
      <EMailAddress>{e}</EMailAddress>
    </User>
    <Action>
      <Settings>
        <Server>
          <Type>MobileSync</Type>
          <Url>{url}</Url>
          <Name>{url}</Name>
        </Server>
      </Settings>
    </Action>
  </Response>
</Autodiscover>
"""


def _error_xml(mensaje: str, status: int = 400) -> Response:
    return Response(
        content='<?xml version="1.0" encoding="utf-8"?><Autodiscover><Response>'
        f"<Error><Message>{html.escape(mensaje)}</Message></Error></Response></Autodiscover>",
        media_type="application/xml",
        status_code=status,
    )


async def _handle(request: Request) -> Response:
    raw = (await request.body()).decode("utf-8", "ignore")
    m = _EMAIL_RE.search(raw)
    email = m.group(1).strip().lower() if m else ""
    if not _VALID.match(email):
        return _error_xml("Email invalido")
    if esquema_pedido(raw) == "mobilesync":
        return Response(
            content=_build_xml_mobilesync(email), media_type="application/xml"
        )
    return Response(content=_build_xml(email), media_type="application/xml")


@router.post("/autodiscover/autodiscover.xml")
async def autodiscover(request: Request):
    return await _handle(request)


@router.post("/Autodiscover/Autodiscover.xml")
async def autodiscover_capitalized(request: Request):
    return await _handle(request)


def _json_v2(email: str, protocolo: str) -> Response:
    """Autodiscover v2 (JSON): el nuevo Outlook pide `Protocol=ActiveSync` (o `AutodiscoverV1`
    para saber dónde está el XML). `Email` viene en la ruta o en la query."""
    p = (protocolo or "").strip().lower()
    if not _VALID.match(email or ""):
        return JSONResponse(
            {"ErrorCode": "InvalidRequest", "ErrorMessage": "Email invalido"},
            status_code=400,
        )
    if p == "activesync":
        return JSONResponse({"Protocol": "ActiveSync", "Url": url_activesync()})
    if p == "autodiscoverv1":
        return JSONResponse(
            {
                "Protocol": "AutodiscoverV1",
                "Url": f"https://{_mail_host()}/autodiscover/autodiscover.xml",
            }
        )
    return JSONResponse(
        {
            "ErrorCode": "ProtocolNotSupported",
            "ErrorMessage": f"Protocolo no soportado: {protocolo}",
        },
        status_code=400,
    )


@router.get("/autodiscover/autodiscover.json")
@router.get("/Autodiscover/Autodiscover.json")
async def autodiscover_json(request: Request):
    q = request.query_params
    return _json_v2(
        (q.get("Email") or q.get("email") or "").strip().lower(),
        q.get("Protocol") or q.get("protocol") or "",
    )


@router.get("/autodiscover/autodiscover.json/v1.0/{email}")
@router.get("/Autodiscover/Autodiscover.json/v1.0/{email}")
async def autodiscover_json_v1(email: str, request: Request):
    q = request.query_params
    return _json_v2(email.strip().lower(), q.get("Protocol") or q.get("protocol") or "")
