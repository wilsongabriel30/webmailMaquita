"""R-03: los uploads de importación tienen límite en la aplicación y no se cargan enteros en memoria."""

import os

import pytest
from fastapi import HTTPException

from app.import_export import router as ie


class _Upload:
    def __init__(self, datos: bytes, trozo=64 * 1024):
        self.d, self.t, self.pos = datos, trozo, 0
        self.filename = "x.mbox"

    async def read(self, n=-1):
        r = self.d[self.pos : self.pos + self.t]
        self.pos += self.t
        return r


@pytest.mark.asyncio
async def test_supera_el_limite_413_y_no_deja_temporal():
    with pytest.raises(HTTPException) as e:
        await ie._guardar_upload(_Upload(b"x" * (3 * 1024 * 1024)), max_mb=2)
    assert e.value.status_code == 413


@pytest.mark.asyncio
async def test_dentro_del_limite_va_a_disco_en_trozos():
    ruta, n = await ie._guardar_upload(_Upload(b"y" * (1024 * 1024 + 5)), max_mb=2)
    try:
        assert n == 1024 * 1024 + 5 and os.path.getsize(ruta) == n
    finally:
        os.unlink(ruta)
