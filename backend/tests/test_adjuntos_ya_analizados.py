"""El envío no repite el análisis de un adjunto que ya salió limpio (memoria compartida con el filtro)."""

import asyncio

from app.mail.services import adjuntos_ya_analizados as m


class RedisDePrueba:
    def __init__(self, falla=False):
        self.datos, self.falla = {}, falla

    async def ttl(self, clave):
        if self.falla:
            raise ConnectionError("sin redis")
        return self.datos.get(clave, -2)

    async def set(self, clave, valor, ex=None):
        if self.falla:
            raise ConnectionError("sin redis")
        self.datos[clave] = ex


def _analizador(resultado, errores=None):
    llamadas = []

    async def analizar(contenido, nombre, tipo):
        llamadas.append(nombre)
        return {
            "result": resultado,
            "threats": [],
            "details": {},
            "errors": errores or [],
        }

    return analizar, llamadas


def _correr(c):
    return asyncio.run(c)


def test_lo_limpio_se_analiza_una_sola_vez():
    r = RedisDePrueba()
    analizar, llamadas = _analizador("clean")
    uno = _correr(
        m.analizar_con_memoria(r, b"zz prueba", "a.pdf", "application/pdf", analizar)
    )
    dos = _correr(
        m.analizar_con_memoria(r, b"zz prueba", "a.pdf", "application/pdf", analizar)
    )
    assert uno["result"] == dos["result"] == "clean"
    assert llamadas == ["a.pdf"]
    assert dos["details"] == {"memoria": "limpio-ya-analizado"}


def test_usa_la_misma_clave_que_el_filtro():
    r = RedisDePrueba()
    analizar, _ = _analizador("clean")
    _correr(m.analizar_con_memoria(r, b"abc", "a.txt", "text/plain", analizar))
    assert list(r.datos) == ["maquita:milter:limpio:" + m.huella(b"abc")]
    assert r.datos["maquita:milter:limpio:" + m.huella(b"abc")] == m.VIGENCIA_S


def test_lo_sospechoso_se_analiza_siempre():
    r = RedisDePrueba()
    for resultado in ("malicious", "suspicious"):
        analizar, llamadas = _analizador(resultado)
        _correr(m.analizar_con_memoria(r, b"malo", "x.docm", "", analizar))
        _correr(m.analizar_con_memoria(r, b"malo", "x.docm", "", analizar))
        assert len(llamadas) == 2
    assert r.datos == {}


def test_un_motor_caido_no_cuenta_como_limpio():
    r = RedisDePrueba()
    analizar, llamadas = _analizador("clean", errores=["clamav"])
    _correr(m.analizar_con_memoria(r, b"dudoso", "a.pdf", "", analizar))
    _correr(m.analizar_con_memoria(r, b"dudoso", "a.pdf", "", analizar))
    assert len(llamadas) == 2 and r.datos == {}


def test_sin_redis_se_analiza_como_antes():
    for redis in (None, RedisDePrueba(falla=True)):
        analizar, llamadas = _analizador("clean")
        v = _correr(m.analizar_con_memoria(redis, b"abc", "a.txt", "", analizar))
        _correr(m.analizar_con_memoria(redis, b"abc", "a.txt", "", analizar))
        assert v["result"] == "clean" and len(llamadas) == 2


def test_bytes_distintos_no_comparten_veredicto():
    r = RedisDePrueba()
    analizar, llamadas = _analizador("clean")
    _correr(m.analizar_con_memoria(r, b"uno", "a.txt", "", analizar))
    _correr(m.analizar_con_memoria(r, b"dos", "a.txt", "", analizar))
    assert len(llamadas) == 2
