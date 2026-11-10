"""Marca de asignaciones faltantes, su limpieza al reaparecer, conteo vigente y purga a los 7 días."""

import datetime as dt

import pytest

from app.mail.services import etiquetas_faltantes as falt
from app.mail.services import etiquetas_huerfanas as huer
from tests._bd_etiquetas_falsa import BDEtiquetasFalsa, fila

OWNER = "persona@example.com"


def test_faltantes_de_pagina_solo_de_carpetas_que_respondieron():
    pedidos = {"INBOX": [1, 2, 3], "Junk": [9]}
    devueltos = {"INBOX": {1, 3}}  # Junk no se pudo seleccionar
    assert falt.faltantes_de_pagina(pedidos, devueltos) == [("INBOX", 2)]


@pytest.mark.asyncio
async def test_marcar_y_contar_vigentes():
    db = BDEtiquetasFalsa(
        [
            fila(1, OWNER, "INBOX", 1, 22),
            fila(2, OWNER, "INBOX", 2, 22),
            fila(3, OWNER, "INBOX", 3, 22),
        ]
    )
    assert await falt.marcar_faltantes(db, OWNER, 22, [("INBOX", 2)]) == 1
    assert await falt.contar_vigentes(db, OWNER, 22) == 2
    assert await falt.contar_vigentes_por_etiqueta(db, OWNER) == {22: 2}
    # Volver a marcar no cambia la fecha original (ya no está NULL): 0 filas
    assert await falt.marcar_faltantes(db, OWNER, 22, [("INBOX", 2)]) == 0


@pytest.mark.asyncio
async def test_el_correo_reaparece_y_deja_de_ser_faltante():
    ya = dt.datetime.now(dt.timezone.utc)
    db = BDEtiquetasFalsa(
        [fila(1, OWNER, "INBOX", 2, 22, faltante=ya), fila(2, OWNER, "INBOX", 5, 22)]
    )
    assert await falt.limpiar_faltantes_vistos(db, OWNER, "INBOX", [2, 5, 6]) == 1
    assert await falt.contar_vigentes(db, OWNER, 22) == 2


@pytest.mark.asyncio
async def test_purga_borra_solo_las_antiguas_y_respeta_simulacion():
    ahora = dt.datetime.now(dt.timezone.utc)
    db = BDEtiquetasFalsa(
        [
            fila(1, OWNER, "INBOX", 1, 22, faltante=ahora - dt.timedelta(days=10)),
            fila(2, OWNER, "INBOX", 2, 22, faltante=ahora - dt.timedelta(days=2)),
            fila(3, OWNER, "INBOX", 3, 22),
        ]
    )
    assert await huer.purgar_faltantes(db, 7, simular=True) == 1
    assert len(db.filas) == 3
    assert await huer.purgar_faltantes(db, 7) == 1
    assert sorted(f["id"] for f in db.filas) == [2, 3]
    assert await huer.purgar_faltantes(db, 7) == 0
