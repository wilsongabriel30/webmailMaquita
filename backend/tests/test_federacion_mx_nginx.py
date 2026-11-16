"""El MX con nombre distinto al del correo web debe atender /api/federacion/ sin redirigir (Andes, 16/11/2026)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GUION = RAIZ / "deploy/tools/federacion-mx-nginx.sh"
PLANTILLA = RAIZ / "deploy/webmail/nginx/federacion-mx.conf"

pytestmark = pytest.mark.skipif(
    not shutil.which("openssl"), reason="hace falta openssl para el certificado de prueba"
)


def _certificado(carpeta: Path, nombre: str, alternativos: list[str]) -> None:
    destino = carpeta / nombre
    destino.mkdir(parents=True)
    san = ",".join(f"DNS:{a}" for a in alternativos)
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-subj", f"/CN={nombre}", "-addext", f"subjectAltName={san}",
         "-keyout", str(destino / "privkey.pem"), "-out", str(destino / "fullchain.pem")],
        check=True, capture_output=True,
    )  # fmt: skip


def _entorno(tmp_path: Path, nginx_valida: bool = True) -> dict:
    binarios = tmp_path / "bin"
    binarios.mkdir(exist_ok=True)
    (binarios / "nginx").write_text(f"#!/bin/sh\nexit {0 if nginx_valida else 1}\n")
    (binarios / "systemctl").write_text(
        f"#!/bin/sh\necho \"$@\" >> {tmp_path}/systemctl.log\n"
    )
    for b in binarios.iterdir():
        b.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{binarios}:{os.environ['PATH']}",
        "DESTINO": str(tmp_path / "sites-available/federacion-mx"),
        "ENLACE": str(tmp_path / "sites-enabled/federacion-mx"),
        "RESPALDOS": str(tmp_path / "respaldos"),
        "DIR_CERT": str(tmp_path / "live"),
    }


def _correr(env, *args):
    for d in ("sites-available", "sites-enabled"):
        Path(env["DESTINO"]).parents[1].joinpath(d).mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", str(GUION), *args], env=env, capture_output=True, text=True
    )


def test_la_plantilla_solo_atiende_la_federacion_y_no_redirige():
    texto = PLANTILLA.read_text(encoding="utf-8")
    codigo = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("#"))
    assert "location /api/federacion/" in codigo and "proxy_pass http://webmail_api;" in codigo
    assert "return 301" not in codigo and "return 302" not in codigo
    assert codigo.count("return 404;") == 2
    # Los demás servidores llegan desde cualquier país: aquí no va el filtro por país.
    assert "filtro-pais" not in codigo


def test_escribe_el_sitio_con_los_nombres_y_recarga(tmp_path):
    env = _entorno(tmp_path)
    _certificado(tmp_path / "live", "mail.example.org", ["mail.example.org", "mail2.example.org"])
    r = _correr(env, "mail.example.org", "mail2.example.org")
    assert r.returncode == 0, r.stderr
    sitio = Path(env["DESTINO"]).read_text(encoding="utf-8")
    assert sitio.count("server_name mail.example.org mail2.example.org;") == 2
    assert "/live/mail.example.org/fullchain.pem" in sitio and "__" not in sitio
    assert Path(env["ENLACE"]).is_symlink()
    assert "reload nginx" in (tmp_path / "systemctl.log").read_text()
    # Segunda vez: nada que hacer.
    assert "Sin cambios" in _correr(env, "mail.example.org", "mail2.example.org").stdout


def test_sin_certificado_o_sin_cubrir_el_nombre_no_toca_nada(tmp_path):
    env = _entorno(tmp_path)
    r = _correr(env, "mail.example.org")
    assert r.returncode == 1 and "No existe el certificado" in r.stderr
    _certificado(tmp_path / "live", "mail.example.org", ["mail.example.org"])
    r = _correr(env, "mail.example.org", "mail2.example.org")
    assert r.returncode == 1 and "no cubre mail2.example.org" in r.stderr
    assert not Path(env["DESTINO"]).exists()


def test_un_comodin_cubre_un_solo_nivel(tmp_path):
    env = _entorno(tmp_path)
    _certificado(tmp_path / "live", "comodin", ["*.example.org"])
    assert _correr(env, "--certificado", "comodin", "mail.example.org").returncode == 0
    r = _correr(env, "--certificado", "comodin", "a.mail.example.org")
    assert r.returncode == 1 and "no cubre" in r.stderr


def test_si_nginx_no_valida_se_deja_como_estaba(tmp_path):
    env = _entorno(tmp_path, nginx_valida=False)
    _certificado(tmp_path / "live", "mail.example.org", ["mail.example.org"])
    r = _correr(env, "mail.example.org")
    assert r.returncode == 1 and "se dejó como estaba" in r.stderr
    assert not Path(env["DESTINO"]).exists() and not Path(env["ENLACE"]).exists()
    assert not (tmp_path / "systemctl.log").exists()


def test_simular_y_nombres_invalidos(tmp_path):
    env = _entorno(tmp_path)
    _certificado(tmp_path / "live", "mail.example.org", ["mail.example.org"])
    r = _correr(env, "--simular", "mail.example.org")
    assert r.returncode == 0 and not Path(env["DESTINO"]).exists()
    assert _correr(env, "mail.example.org;rm").returncode == 2
    assert _correr(env).returncode == 2


def test_el_validador_comprueba_el_mx_sin_seguir_redirecciones():
    validador = (RAIZ / "deploy/tools/validar-despliegue.sh").read_text(encoding="utf-8")
    assert "--max-redirs 0" in validador and "/api/federacion/v1/recuperacion" in validador
    assert "federacion-mx-nginx.sh" in validador
