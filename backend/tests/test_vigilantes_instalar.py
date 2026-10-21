"""deploy/vigilantes/instalar.sh: instala, es idempotente y no pisa versiones propias del servidor."""

import os
import shutil
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INSTALADOR = os.path.join(REPO, "deploy", "vigilantes", "instalar.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="sin bash")


def _correr(raiz, *args):
    env = dict(os.environ, APP_DIR=REPO, VIGILANTES_RAIZ=str(raiz))
    r = subprocess.run(["bash", INSTALADOR, *args], capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout + r.stderr


def test_instala_y_luego_no_hay_cambios(tmp_path):
    rc, salida = _correr(tmp_path, "--simular")
    assert rc == 0 and salida.startswith("Pendiente")
    assert not (tmp_path / "usr").exists()  # simular no escribe nada

    rc, salida = _correr(tmp_path)
    assert rc == 0, salida
    assert "Listo" in salida
    assert os.access(tmp_path / "usr/local/sbin/guardian-web-correo", os.X_OK)
    assert (tmp_path / "etc/systemd/system/vigilar-milter.timer").is_file()
    assert (tmp_path / "etc/cron.d/vigila-entrega-local").is_file()

    rc, salida = _correr(tmp_path)
    assert rc == 0 and "Sin cambios" in salida


def test_respeta_las_versiones_propias_del_servidor(tmp_path):
    propio = tmp_path / "usr/local/sbin/aviso-limitado"
    propio.parent.mkdir(parents=True)
    propio.write_text("#!/bin/bash\n# versión a medida de este servidor\n")
    unidad = tmp_path / "etc/systemd/system/guardian-web-correo.timer"
    unidad.parent.mkdir(parents=True)
    unidad.write_text("[Timer]\nOnUnitActiveSec=5min\n")

    rc, salida = _correr(tmp_path)
    assert rc == 0, salida
    assert "versiones propias" in salida
    assert "a medida" in propio.read_text()
    assert "5min" in unidad.read_text()


def test_actualiza_lo_que_instalo_antes(tmp_path):
    assert _correr(tmp_path)[0] == 0
    nuestro = tmp_path / "usr/local/bin/vigila-entrega-local.sh"
    nuestro.write_text(nuestro.read_text().replace("UMBRAL_COLA=3", "UMBRAL_COLA=9"))

    rc, salida = _correr(tmp_path)
    assert rc == 0 and "Listo" in salida
    assert "UMBRAL_COLA=3" in nuestro.read_text()
    assert list(nuestro.parent.glob("vigila-entrega-local.sh.bak.*"))
