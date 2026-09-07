"""N-19: autenticación DAV para Z-Push delante de Radicale."""

import base64

import pytest

from app.auth import dav_auth
from app.calendar.service import _user_prefix


def _basic(u, p):
    return "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()


def test_basic_valida_y_normaliza():
    assert dav_auth.credenciales_basic(_basic("Ana@Ejemplo.org", "abcd")) == (
        "ana@ejemplo.org",
        "abcd",
    )
    assert dav_auth.credenciales_basic(None) is None
    assert dav_auth.credenciales_basic("Bearer x") is None
    assert dav_auth.credenciales_basic("Basic ???") is None
    assert dav_auth.credenciales_basic(_basic("sinarroba", "x")) is None
    assert dav_auth.credenciales_basic(_basic("a@b.org", "")) is None


class _DB:
    def __init__(self, acepta_app, politica):
        self.acepta_app, self.politica, self.llamadas = acepta_app, politica, []

    async def fetchrow(self, sql, *args):
        self.llamadas.append(("fetchrow", args))
        assert "verificar_contrasena_aplicacion" in sql
        assert (
            args[2] == dav_auth.MARCA_ORIGEN
        )  # nunca «127.0.0.1»: la función rechazaría
        return {"user": args[0]} if self.acepta_app else None

    async def fetchval(self, sql, *args):
        return "true" if self.politica else "false"


class _Redis:
    def __init__(self):
        self.d = {}

    async def get(self, k):
        return self.d.get(k)

    async def set(self, k, v, ex=None):
        self.d[k] = v


@pytest.mark.asyncio
async def test_clave_de_aplicacion_entra_y_se_recuerda():
    db, r = _DB(acepta_app=True, politica=True), _Redis()
    assert (
        await dav_auth.verificar(db, r, "ana@ejemplo.org", "abcd-efgh-jkmn-pqrs")
        is True
    )
    assert (
        await dav_auth.verificar(db, r, "ana@ejemplo.org", "abcd-efgh-jkmn-pqrs")
        is True
    )
    assert len(db.llamadas) == 1  # la segunda salió de la caché
    assert not any("abcd" in k for k in r.d)  # en Redis solo va el hash


@pytest.mark.asyncio
async def test_principal_solo_si_la_politica_no_es_obligatoria(monkeypatch):
    import app.auth.password as pw

    monkeypatch.setattr(pw, "verify_imap", lambda u, c: c == "principal")
    assert (
        await dav_auth.verificar(
            _DB(False, politica=False), None, "ana@ejemplo.org", "principal"
        )
        is True
    )
    assert (
        await dav_auth.verificar(
            _DB(False, politica=True), None, "ana@ejemplo.org", "principal"
        )
        is False
    )
    assert (
        await dav_auth.verificar(
            _DB(False, politica=False), None, "ana@ejemplo.org", "mala"
        )
        is False
    )


def test_prefijo_de_colecciones_es_el_correo_completo():
    """Z-Push usa /<correo>/ (CALDAV_PATH '/%u/'); el webmail tiene que escribir en el MISMO árbol."""
    assert _user_prefix("Ana@Ejemplo.org") == "ana@ejemplo.org"


@pytest.mark.asyncio
async def test_activar_la_politica_corta_la_principal_en_el_acto(monkeypatch):
    """Informe de Andes (07/09): la principal aceptada ANTES de activar la política no puede seguir
    valiendo por la caché. Solo se recuerdan los aciertos de contraseña de aplicación.
    """
    import app.auth.password as pw

    monkeypatch.setattr(pw, "verify_imap", lambda u, c: c == "principal")
    r = _Redis()
    db = _DB(False, politica=False)
    assert await dav_auth.verificar(db, r, "ana@ejemplo.org", "principal") is True
    assert not r.d  # la principal no se recuerda
    db.politica = True
    assert await dav_auth.verificar(db, r, "ana@ejemplo.org", "principal") is False
