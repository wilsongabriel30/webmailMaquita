"""El visor de OnlyOffice descarga el adjunto con la sesión de quien lo abrió.

Antecedente (12/10/2026): OnlyOffice pide el archivo a `/api/mail/oo-download` desde su
servidor, sin la cookie del navegador. Desde que la credencial IMAP en Redis va por sesión
(`imap_pass:{u}:{sid}`), la descarga respondía siempre 401 y ningún documento de Office se
veía. Ahora el vale de descarga lleva el `sid` (y la cuenta activa) y la descarga los restaura.
También: nombres con apóstrofo curvo o raya ya no rompen la cabecera (RFC 5987).
"""

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import jwt

from app.mail.routers import onlyoffice

SECRETO = "secreto-de-prueba-de-descarga-0123456789"
NOMBRE = "Informe dirección – ’24.docx"


class _Pool:
    async def fetchrow(self, *a, **k):
        return None


def _peticion(**estado):
    return SimpleNamespace(
        state=SimpleNamespace(**estado),
        app=SimpleNamespace(state=SimpleNamespace(db_pool=_Pool())),
    )


def _vale(monkeypatch, **estado):
    monkeypatch.setattr(onlyoffice, "_DOWNLOAD_SECRET", SECRETO)
    monkeypatch.setattr(
        onlyoffice, "_OO_SECRET", "secreto-de-prueba-del-servidor-0123456789"
    )
    cuerpo = onlyoffice.OfficeEditorRequest(
        folder="INBOX", uid=7, part_number="2", filename=NOMBRE
    )
    config = asyncio.run(
        onlyoffice.office_editor_config(cuerpo, _peticion(**estado), "ana@example.com")
    )
    return parse_qs(urlparse(config["document"]["url"]).query)["token"][0]


def test_el_vale_lleva_la_sesion_de_quien_abre(monkeypatch):
    datos = jwt.decode(
        _vale(monkeypatch, sid="s-123", cuenta_activa="otra@example.com"),
        SECRETO,
        algorithms=["HS256"],
    )
    assert datos["sid"] == "s-123"
    assert datos["cuenta_activa"] == "otra@example.com"


def test_la_descarga_usa_esa_sesion_y_soporta_nombres_raros(monkeypatch):
    vale = _vale(monkeypatch, sid="s-123")
    vistos = {}

    async def _clave(request, usuario):
        vistos["sid"] = request.state.sid
        return "clave"

    async def _login(request, usuario):
        return usuario

    class _Imap:
        async def logout(self):
            pass

    async def _conexion(usuario, clave):
        return _Imap()

    async def _adjunto(imap, carpeta, uid, parte):
        return b"PK\x03\x04"

    monkeypatch.setattr(onlyoffice, "get_user_password", _clave)
    monkeypatch.setattr(onlyoffice, "get_imap_login_user", _login)
    monkeypatch.setattr(onlyoffice, "get_imap_connection", _conexion)
    monkeypatch.setattr(onlyoffice, "fetch_attachment", _adjunto)

    # La petición de OnlyOffice no trae cookie: el estado llega vacío.
    resp = asyncio.run(onlyoffice.onlyoffice_download(token=vale, request=_peticion()))
    assert vistos["sid"] == "s-123"
    assert resp.body == b"PK\x03\x04"
    cabecera = resp.headers["content-disposition"]
    cabecera.encode("latin-1")
    assert "filename*=UTF-8''" in cabecera
