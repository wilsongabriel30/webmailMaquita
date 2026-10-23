# -*- coding: utf-8 -*-
"""«Mover a…» dentro de una unidad compartida (editor).

El diálogo de destino del explorador arrancaba siempre en la raíz propia («Mis archivos»)
y las rutas que ofrecía no llevaban el prefijo `/unidades/<id>`. Quien reorganizaba dentro
de una unidad elegía «Carpeta B» y el destino salía como `/B/…`: el servidor lo aceptaba
como un movimiento al espacio PERSONAL y el archivo desaparecía de la unidad para todo el
equipo. Estas pruebas fijan lo que hace el núcleo con cada forma de destino; el arreglo
está en el frontend (`rutasEspacio.ts`), que ahora conserva el prefijo.
"""
import os
import sys

import pytest

os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import congelados  # noqa: E402
import nucleo_archivos as nucleo  # noqa: E402
import permisos_unidad  # noqa: E402
import seguridad_rutas  # noqa: E402

EDITOR = 11
UNIDAD = 5


@pytest.fixture
def disco(tmp_path, monkeypatch):
    monkeypatch.setattr(seguridad_rutas, "raiz_datos", lambda: str(tmp_path))
    monkeypatch.setattr(congelados, "esta_congelado", lambda _u: False)
    roles = {(UNIDAD, EDITOR): "editor"}
    monkeypatch.setattr(permisos_unidad, "rol_en_unidad", lambda u, un: roles.get((int(un), int(u))))
    unidad = tmp_path / "_unidades" / str(UNIDAD) / "archivos"
    (unidad / "A").mkdir(parents=True)
    (unidad / "B").mkdir()
    (unidad / "A" / "informe.txt").write_text("datos")
    return tmp_path, unidad


def test_destino_con_prefijo_reorganiza_dentro_de_la_unidad(disco):
    _raiz, unidad = disco
    nucleo.mover(EDITOR, f"/unidades/{UNIDAD}/A/informe.txt", f"/unidades/{UNIDAD}/B/informe.txt")
    assert (unidad / "B" / "informe.txt").read_text() == "datos"
    assert not (unidad / "A" / "informe.txt").exists()


def test_destino_sin_prefijo_saca_el_archivo_de_la_unidad(disco):
    """El fallo: el destino que armaba el diálogo antiguo (`/B/…`) cae en el espacio
    personal del editor. No hay error: el archivo deja de estar en la unidad."""
    raiz, unidad = disco
    nucleo.mover(EDITOR, f"/unidades/{UNIDAD}/A/informe.txt", "/B/informe.txt")
    assert not (unidad / "A" / "informe.txt").exists()
    assert not (unidad / "B" / "informe.txt").exists()
    assert (raiz / str(EDITOR) / "archivos" / "B" / "informe.txt").exists()


def test_lector_no_puede_mover_dentro_de_la_unidad(disco, monkeypatch):
    monkeypatch.setattr(permisos_unidad, "rol_en_unidad", lambda u, un: "viewer")
    with pytest.raises(permisos_unidad.SinPermisoUnidad):
        nucleo.mover(EDITOR, f"/unidades/{UNIDAD}/A/informe.txt", f"/unidades/{UNIDAD}/B/informe.txt")
