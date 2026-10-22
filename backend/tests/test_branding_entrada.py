"""Pantalla de entrada por dominio: /api/branding según el nombre de servidor pedido.

Regla: `mail.<dominio>` y `webmail.<dominio>` dan los datos de `<dominio>` (sugerencia del
campo de correo, bienvenida, contacto y color) SOLO si ese dominio existe en el servidor.
Un nombre de servidor inventado o mal formado recibe la pantalla general.
"""

from types import SimpleNamespace

import pytest
from fastapi import Response

from app.branding import entrada, router as branding_router
from app.portales import resolucion


class _BaseFalsa:
    """Base de mentira: dominios, portales, marcas y administradores de ejemplo."""

    def __init__(self, sin_pd_admins: bool = False, falla: bool = False):
        self.sin_pd_admins = sin_pd_admins
        self.falla = falla
        self.consultas: list[str] = []

    async def fetch(self, sql, *args):
        self.consultas.append(sql)
        if self.falla:
            raise RuntimeError("la base no responde")
        if "FROM branding_settings" in sql:
            return [
                {"key": "org_name", "value": "Organización General"},
                {"key": "app_name", "value": "Correo General"},
                {"key": "primary_color", "value": "#0078d4"},
            ]
        if "FROM domain WHERE" in sql:
            return [
                {"domain": d}
                for d in ("example.org", "example.com", "agro.example.org", "ALL")
            ]
        if "FROM portal_empresa" in sql:
            return [{"host": "correo.agro.example.org", "dominio": "agro.example.org"}]
        if "FROM branding_empresa" in sql:
            marcas = {
                "example.com": [
                    {"clave": "org_name", "valor": "Empresa Ejemplo"},
                    {"clave": "primary_color", "valor": "#127a3e"},
                ],
                "agro.example.org": [
                    {"clave": "org_name", "valor": "Agro Ejemplo"},
                    {"clave": "primary_color", "valor": "rojo; background:url(x)"},
                    {"clave": "org_email", "valor": "Soporte@Agro.Example.org"},
                ],
            }
            return marcas.get(args[0], []) if args else []
        if "FROM pd_admins" in sql:
            if self.sin_pd_admins:
                raise RuntimeError("permission denied for table pd_admins")
            if args[0] == "example.com":
                return [
                    {"username": "no-es-un-correo"},
                    {"username": "admin@example.com"},
                ]
            return []
        if "FROM domain_admins" in sql:
            if args[0] == "example.com":
                return [{"username": "postmaster@example.com"}]
            return []
        return []


def _peticion(host: str, db) -> SimpleNamespace:
    return SimpleNamespace(
        headers={"host": host},
        app=SimpleNamespace(state=SimpleNamespace(db_pool=db)),
    )


async def _branding(host: str, db=None) -> dict:
    db = db or _BaseFalsa()
    return await branding_router.get_branding(_peticion(host, db), Response())


@pytest.fixture(autouse=True)
def _sin_cache(monkeypatch):
    entrada.olvidar_cache()
    resolucion.olvidar_cache()
    monkeypatch.setattr(
        entrada.organizacion, "dominios_propios", lambda: frozenset({"example.org"})
    )
    monkeypatch.setattr(branding_router, "UPLOAD_DIR", "/nonexistent-branding-pruebas")
    yield
    entrada.olvidar_cache()
    resolucion.olvidar_cache()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host",
    [
        "mail.example.com",
        "webmail.example.com",
        "MAIL.Example.COM:443",
        "mail.example.com.",
    ],
)
async def test_dominio_con_marca_y_administrador(host):
    b = await _branding(host)
    assert b["dominio"] == "example.com"
    assert b["login_placeholder"] == "usuario@example.com"
    assert b["bienvenida"] == "Correo de Empresa Ejemplo"
    assert (
        b["contacto_admin"] == "admin@example.com"
    )  # se salta el usuario que no es un correo
    assert b["primary_color"] == "#127a3e"


@pytest.mark.asyncio
async def test_dominio_de_la_casa_lleva_el_nombre_general():
    b = await _branding("mail.example.org")
    assert b["dominio"] == "example.org"
    assert b["login_placeholder"] == "usuario@example.org"
    assert b["bienvenida"] == "Correo de Organización General"
    assert "contacto_admin" not in b  # sin administrador conocido no se inventa nada
    assert b["primary_color"] == "#0078d4"


@pytest.mark.asyncio
async def test_portal_de_empresa_correo_propio_y_color_invalido():
    b = await _branding("correo.agro.example.org")
    assert b["dominio"] == "agro.example.org"
    assert b["bienvenida"] == "Correo de Agro Ejemplo"
    assert b["contacto_admin"] == "soporte@agro.example.org"
    # Un color mal formado en la marca no se da como color de la pantalla de entrada.
    db = _BaseFalsa()
    datos = await entrada.datos_de_entrada(db, _peticion("correo.agro.example.org", db))
    assert "primary_color" not in datos


@pytest.mark.asyncio
async def test_sin_pd_admins_se_usa_domain_admins():
    b = await _branding("mail.example.com", _BaseFalsa(sin_pd_admins=True))
    assert b["contacto_admin"] == "postmaster@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host",
    [
        "mail.desconocido.example.net",  # dominio que el servidor no atiende
        "mail.example.com/../../etc",
        "mail.<script>.example.com",
        "192.0.2.10",
        "[2001:db8::1]:443",
        "",
        "mail.ALL",
    ],
)
async def test_nombre_no_de_fiar_da_pantalla_general(host):
    b = await _branding(host)
    for campo in ("dominio", "login_placeholder", "bienvenida", "contacto_admin"):
        assert campo not in b
    assert b["org_name"] == "Organización General"


@pytest.mark.asyncio
async def test_resultado_en_cache():
    db = _BaseFalsa()
    for _ in range(5):
        await _branding("mail.example.com", db)
    assert sum("FROM domain WHERE" in c for c in db.consultas) == 1
    assert sum("FROM pd_admins" in c for c in db.consultas) == 1


@pytest.mark.asyncio
async def test_si_la_base_falla_no_hay_datos_de_entrada():
    db = _BaseFalsa(falla=True)
    assert await entrada.datos_de_entrada(db, _peticion("mail.example.com", db)) == {}
