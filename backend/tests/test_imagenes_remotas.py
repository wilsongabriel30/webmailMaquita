"""Las imágenes remotas se muestran solas, salvo en no deseado o si la persona las bloqueó."""

import asyncio

from app.mail.services import imagenes_remotas


class _Db:
    def __init__(self, valor=None, falla=False):
        self.valor = valor
        self.falla = falla

    async def fetchval(self, *_):
        if self.falla:
            raise RuntimeError("sin base de datos")
        return self.valor


def _bloquea(db, carpeta):
    return asyncio.run(imagenes_remotas.debe_bloquear(db, "ana@example.com", carpeta))


def test_por_defecto_se_muestran():
    assert _bloquea(_Db(None), "INBOX") is False
    assert _bloquea(_Db(False), "INBOX") is False


def test_quien_las_bloqueo_las_sigue_bloqueando():
    assert _bloquea(_Db(True), "INBOX") is True


def test_en_no_deseado_siempre_se_bloquean():
    assert _bloquea(_Db(False), "Junk") is True
    assert _bloquea(_Db(False), "Compartidos,ventas@example.com,Junk") is True


def test_si_falla_la_base_no_se_rompe_la_lectura():
    assert _bloquea(_Db(falla=True), "INBOX") is False
