"""A cada cuenta, el servidor de su empresa; a las demás, el general."""

import pytest

from app.portales import direcciones as d

pytestmark = pytest.mark.asyncio


class _Db:
    def __init__(self, filas=None, falla=False):
        self.filas = filas or []
        self.falla = falla
        self.consultas = 0

    async def fetch(self, *_):
        self.consultas += 1
        if self.falla:
            raise RuntimeError("sin base de datos")
        return self.filas


class _Peticion:
    def __init__(self, host):
        self.headers = {"host": host}


PORTALES = [
    {"host": "mail.uno.example", "dominio": "uno.example"},
    {"host": "correo.uno.example", "dominio": "uno.example"},
    {"host": "Mail.Dos.Example", "dominio": "Dos.Example"},
]


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://mail.casa.example")
    monkeypatch.delenv("DIRECCIONES_POR_DOMINIO", raising=False)
    d.olvidar_cache()
    yield
    d.olvidar_cache()


async def test_cuenta_con_portal_recibe_el_servidor_de_su_empresa():
    db = _Db(PORTALES)
    assert await d.servidor_de_cuenta(db, "ana@uno.example") == "mail.uno.example"
    assert await d.url_de_cuenta(db, "Luis@DOS.example") == "https://mail.dos.example"


async def test_con_varios_nombres_vale_el_primero():
    assert await d.servidor_de_dominio(_Db(PORTALES), "uno.example") == "mail.uno.example"


async def test_cuenta_sin_portal_va_al_servidor_general():
    db = _Db(PORTALES)
    assert await d.servidor_de_cuenta(db, "eva@tres.example") == "mail.casa.example"
    assert await d.url_de_cuenta(db, "eva@tres.example") == "https://mail.casa.example"
    assert await d.servidor_de_cuenta(db, "eva@tres.example", general="otro.example") == "otro.example"


async def test_un_subdominio_parecido_no_hereda_el_portal():
    db = _Db(PORTALES)
    assert await d.servidor_de_dominio(db, "sub.uno.example") is None
    assert await d.servidor_de_dominio(db, "uno.example.atacante.example") is None


async def test_sin_base_o_con_la_base_caida_todo_va_al_general():
    assert await d.servidor_de_cuenta(None, "ana@uno.example") == "mail.casa.example"
    assert await d.url_de_cuenta(_Db(falla=True), "ana@uno.example") == "https://mail.casa.example"


async def test_se_puede_apagar(monkeypatch):
    monkeypatch.setenv("DIRECCIONES_POR_DOMINIO", "0")
    assert await d.url_de_cuenta(_Db(PORTALES), "ana@uno.example") == "https://mail.casa.example"


async def test_la_tabla_se_consulta_una_vez_por_minuto():
    db = _Db(PORTALES)
    for _ in range(5):
        await d.url_de_cuenta(db, "ana@uno.example")
    assert db.consultas == 1


async def test_la_cabecera_host_solo_vale_si_es_un_portal_conocido():
    db = _Db(PORTALES)
    assert await d.url_de_peticion(db, _Peticion("mail.uno.example:443")) == "https://mail.uno.example"
    assert await d.url_de_peticion(db, _Peticion("atacante.example")) == "https://mail.casa.example"
    assert await d.url_de_peticion(db, _Peticion("mail.uno.example.atacante.example")) == "https://mail.casa.example"
    assert await d.url_de_peticion(db, _Peticion("")) == "https://mail.casa.example"


async def test_cambiar_base_solo_toca_enlaces_de_la_direccion_general():
    assert d.cambiar_base("https://mail.casa.example/webmail/tasks?x=1", "https://mail.uno.example") == "https://mail.uno.example/webmail/tasks?x=1"
    assert d.cambiar_base("https://otro.example/x", "https://mail.uno.example") == "https://otro.example/x"
    assert d.cambiar_base("https://mail.casa.example.atacante.example/x", "https://mail.uno.example") == "https://mail.casa.example.atacante.example/x"
    assert d.cambiar_base("https://mail.casa.example/x", "https://mail.casa.example") == "https://mail.casa.example/x"


async def test_agrupa_las_cuentas_por_la_direccion_de_su_empresa():
    grupos = await d.agrupar_por_url(_Db(PORTALES), ["ana@uno.example", "eva@tres.example", "luis@dos.example", "leo@uno.example"])
    assert grupos == {
        "https://mail.uno.example": ["ana@uno.example", "leo@uno.example"],
        "https://mail.casa.example": ["eva@tres.example"],
        "https://mail.dos.example": ["luis@dos.example"],
    }


async def test_enlaces_seguros_con_la_direccion_del_portal():
    from app.safelinks import rewriter

    html = '<p><a class="x" href="https://destino.example/a?b=1&amp;c=2">ver</a></p>'
    general = rewriter.rewrite(html)
    suyo = rewriter.rewrite(html, "https://mail.uno.example")
    assert 'href="https://mail.uno.example/api/safelink?u=' in suyo
    assert "mail.uno.example" not in general
    # misma firma: el enlace vale entre por donde entre
    assert general.split("/api/safelink?")[1] == suyo.split("/api/safelink?")[1]


async def test_mensaje_seguro_lleva_el_portal_de_quien_envia():
    from app.secure_message import service

    assert service.portal_url("abc", "https://mail.uno.example/") == "https://mail.uno.example/secure/abc"
    assert service.portal_url("abc").endswith("/secure/abc")
