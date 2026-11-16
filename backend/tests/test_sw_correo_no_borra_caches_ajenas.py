"""El service worker del correo solo borra sus propias copias antiguas, no las de otros (chat)."""

from pathlib import Path

SW = Path(__file__).resolve().parents[2] / "frontend/public/sw.js"


def _codigo():
    lineas = SW.read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lineas if not l.lstrip().startswith("//"))


def test_la_limpieza_se_limita_a_las_copias_propias():
    codigo = _codigo()
    activar = codigo.split('addEventListener("activate"')[1].split("addEventListener(")[0]
    assert "key.startsWith(PREFIJO_PROPIO)" in activar
    assert "caches.delete(key)" in activar


def test_el_prefijo_sale_del_nombre_que_sella_el_despliegue():
    codigo = _codigo()
    assert 'const CACHE_NAME = "' in codigo
    assert 'CACHE_NAME.lastIndexOf("-v")' in codigo
