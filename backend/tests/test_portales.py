"""Portales por empresa: quién puede entrar por cada nombre de servidor.

Regla: desde el portal de una empresa solo entran cuentas de esa empresa; desde el portal
padre entra cualquiera.
"""

import pytest

from app.portales import resolucion


class _PeticionFalsa:
    def __init__(self, host: str):
        self.headers = {"host": host}


class _BaseFalsa:
    """Base de datos de mentira con dos portales de empresa."""

    def __init__(self, filas=None, falla: bool = False):
        self.filas = filas if filas is not None else [
            {"host": "mail.turismo.example", "dominio": "turismo.example"},
            {"host": "mail.agro.example", "dominio": "agro.example"},
        ]
        self.falla = falla
        self.consultas = 0

    async def fetch(self, *_args, **_kwargs):
        self.consultas += 1
        if self.falla:
            raise RuntimeError("la base no responde")
        return self.filas


@pytest.fixture(autouse=True)
def _sin_cache():
    resolucion.olvidar_cache()
    yield
    resolucion.olvidar_cache()


@pytest.mark.parametrize(
    "cabecera,esperado",
    [
        ("mail.padre.example", "mail.padre.example"),
        ("mail.padre.example:8443", "mail.padre.example"),
        ("MAIL.Padre.EXAMPLE", "mail.padre.example"),
        ("mail.padre.example.", "mail.padre.example"),
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("", ""),
    ],
)
def test_host_peticion_normaliza(cabecera, esperado):
    assert resolucion.host_peticion(_PeticionFalsa(cabecera)) == esperado


@pytest.mark.asyncio
async def test_portal_de_empresa_devuelve_su_dominio():
    db = _BaseFalsa()
    peticion = _PeticionFalsa("mail.turismo.example")
    assert await resolucion.dominio_del_portal(db, peticion) == "turismo.example"


@pytest.mark.asyncio
async def test_portal_padre_no_restringe():
    db = _BaseFalsa()
    assert await resolucion.dominio_del_portal(db, _PeticionFalsa("mail.padre.example")) is None


@pytest.mark.asyncio
async def test_cada_empresa_solo_admite_sus_cuentas():
    db = _BaseFalsa()
    turismo = _PeticionFalsa("mail.turismo.example")
    assert await resolucion.cuenta_admitida(db, turismo, "ana@turismo.example")
    assert not await resolucion.cuenta_admitida(db, turismo, "ana@agro.example")
    assert not await resolucion.cuenta_admitida(db, turismo, "ana@otra.example")


@pytest.mark.asyncio
async def test_el_portal_padre_admite_cualquier_cuenta():
    db = _BaseFalsa()
    padre = _PeticionFalsa("mail.padre.example")
    for cuenta in ("ana@turismo.example", "ana@agro.example", "ana@otra.example"):
        assert await resolucion.cuenta_admitida(db, padre, cuenta)


@pytest.mark.asyncio
async def test_comparacion_de_dominio_sin_distinguir_mayusculas():
    db = _BaseFalsa()
    turismo = _PeticionFalsa("mail.turismo.example")
    assert await resolucion.cuenta_admitida(db, turismo, "Ana@Turismo.EXAMPLE")


@pytest.mark.asyncio
async def test_si_la_base_falla_no_se_deja_a_nadie_fuera():
    """Un fallo interno no debe impedir que la gente entre a su correo."""
    db = _BaseFalsa(falla=True)
    peticion = _PeticionFalsa("mail.turismo.example")
    assert await resolucion.dominio_del_portal(db, peticion) is None
    assert await resolucion.cuenta_admitida(db, peticion, "ana@agro.example")


@pytest.mark.asyncio
async def test_la_consulta_se_guarda_en_cache():
    db = _BaseFalsa()
    peticion = _PeticionFalsa("mail.agro.example")
    for _ in range(5):
        await resolucion.dominio_del_portal(db, peticion)
    assert db.consultas == 1


@pytest.mark.asyncio
async def test_un_nombre_de_servidor_desconocido_no_restringe():
    db = _BaseFalsa()
    assert await resolucion.dominio_del_portal(db, _PeticionFalsa("otro.ejemplo.com")) is None
