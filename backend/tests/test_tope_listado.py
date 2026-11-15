"""El listado de correos tiene tope de tiempo y se corta si el navegador ya no espera."""

import asyncio

import pytest
from fastapi import HTTPException

from app.mail.services import tope_listado as tl


class _Transporte:
    cerrado = False

    def close(self):
        self.cerrado = True


class _Protocolo:
    def __init__(self):
        self.transport = _Transporte()


class _Imap:
    def __init__(self):
        self.protocol = _Protocolo()


class _Peticion:
    def __init__(self, se_va_a_la=None):
        self.consultas, self.se_va_a_la = 0, se_va_a_la

    async def is_disconnected(self):
        self.consultas += 1
        return self.se_va_a_la is not None and self.consultas >= self.se_va_a_la


@pytest.fixture(autouse=True)
def _rapido(monkeypatch):
    monkeypatch.setattr(tl, "CADA_S", 0.02)


async def _lento(estado, segundos=5):
    try:
        await asyncio.sleep(segundos)
    except asyncio.CancelledError:
        estado["cancelado"] = True
        raise
    return "tarde"


def test_un_listado_normal_devuelve_su_resultado_y_no_toca_la_conexion():
    async def listado():
        return {"total": 3}

    imap = _Imap()
    assert asyncio.run(tl.ejecutar(_Peticion(), imap, listado())) == {"total": 3}
    assert not imap.protocol.transport.cerrado and not hasattr(imap, "conexion_sucia")


def test_al_pasar_del_tope_se_cierra_la_conexion_y_responde_504():
    async def caso():
        imap, estado = _Imap(), {}
        with pytest.raises(HTTPException) as error:
            await tl.ejecutar(_Peticion(), imap, _lento(estado), tope=0.05)
        await asyncio.sleep(0)
        return imap, estado, error.value

    imap, estado, error = asyncio.run(caso())
    assert error.status_code == 504 and "Inténtelo" in error.detail
    assert imap.protocol.transport.cerrado and imap.conexion_sucia
    assert estado.get("cancelado"), "el listado no sigue trabajando por detrás"


def test_si_el_navegador_cierra_la_peticion_se_corta():
    async def caso():
        imap, estado = _Imap(), {}
        with pytest.raises(HTTPException) as error:
            await tl.ejecutar(_Peticion(se_va_a_la=2), imap, _lento(estado), tope=30)
        await asyncio.sleep(0)
        return imap, estado, error.value

    imap, estado, error = asyncio.run(caso())
    assert error.status_code == 499
    assert imap.protocol.transport.cerrado and estado.get("cancelado")


def test_si_el_servidor_web_cancela_la_peticion_tambien_se_corta():
    async def caso():
        imap, estado = _Imap(), {}
        peticion = asyncio.ensure_future(tl.ejecutar(_Peticion(), imap, _lento(estado)))
        await asyncio.sleep(0.05)
        peticion.cancel()
        with pytest.raises(asyncio.CancelledError):
            await peticion
        await asyncio.sleep(0)
        return imap, estado

    imap, estado = asyncio.run(caso())
    assert imap.protocol.transport.cerrado and estado.get("cancelado")


def test_los_errores_del_listado_pasan_tal_cual():
    """Una conexión caída debe llegar al listado para que la reintente con otra."""

    async def roto():
        raise ConnectionError("the handler is closed")

    imap = _Imap()
    with pytest.raises(ConnectionError):
        asyncio.run(tl.ejecutar(_Peticion(), imap, roto()))
    assert not imap.protocol.transport.cerrado


def test_un_navegador_que_no_sabe_decir_si_sigue_ahi_no_corta_nada():
    class Rara:
        async def is_disconnected(self):
            raise RuntimeError("sin canal")

    async def listado():
        await asyncio.sleep(0.06)
        return "ok"

    assert asyncio.run(tl.ejecutar(Rara(), _Imap(), listado())) == "ok"
