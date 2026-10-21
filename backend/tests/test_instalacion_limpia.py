"""Instalación limpia: certificado provisional de nginx y datos de la organización (aviso de Andes)."""

import os
import subprocess

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
PROVISIONAL = os.path.join(RAIZ, "deploy", "webmail", "nginx", "certificado-provisional.sh")
ORGANIZACION = os.path.join(RAIZ, "deploy", "webmail", "configs", "crear-organizacion-env.sh")


def _provisional(tmp_path, vhost_texto):
    cert, llave = tmp_path / "snakeoil.pem", tmp_path / "snakeoil.key"
    cert.write_text("c")
    llave.write_text("k")
    vhost = tmp_path / "hosting.example.org"
    vhost.write_text(vhost_texto)
    env = dict(os.environ, MAQUITA_CERT_PROVISIONAL=str(cert), MAQUITA_LLAVE_PROVISIONAL=str(llave))
    subprocess.run(["bash", PROVISIONAL, str(vhost)], env=env, check=True, capture_output=True)
    return vhost.read_text(), str(cert), str(llave)


def test_certificado_que_falta_pasa_al_provisional(tmp_path):
    texto, cert, llave = _provisional(tmp_path, (
        "    ssl_certificate /etc/letsencrypt/live/mail.hosting.example.org/fullchain.pem;\n"
        "    ssl_certificate_key /etc/letsencrypt/live/mail.hosting.example.org/privkey.pem;\n"))
    assert f"ssl_certificate {cert};" in texto
    assert f"ssl_certificate_key {llave};" in texto
    assert "letsencrypt" not in texto


def test_certificado_existente_no_se_toca(tmp_path):
    real = tmp_path / "live"
    real.mkdir()
    (real / "fullchain.pem").write_text("x")
    (real / "privkey.pem").write_text("y")
    linea = f"    ssl_certificate {real}/fullchain.pem;\n    ssl_certificate_key {real}/privkey.pem;\n"
    texto, _, _ = _provisional(tmp_path, linea)
    assert texto == linea


def test_instalador_traduce_mail_host_en_autodiscover():
    s = open(os.path.join(RAIZ, "deploy", "webmail", "instalar.sh"), encoding="utf-8").read()
    # El vhost de autodiscover pedía live/mail.<dominio>/ aunque el servidor se llamara de otra forma.
    assert 's/mail\\.tudominio\\.com/${MAIL_HOST}/g; s/tudominio\\.com/${DOMAIN}/g" "${APP_DIR}/deploy/webmail/nginx/autodiscover-dominios.conf"' in s
    assert "certificado-provisional.sh\" --todos" in s
    assert "crear-organizacion-env.sh" in s


def test_organizacion_env_se_crea_y_no_se_pisa(tmp_path):
    destino = tmp_path / "organizacion.env"
    env = dict(os.environ, ORG_FICHERO=str(destino))
    r = subprocess.run(["bash", ORGANIZACION, "example.org", "hosting.example.org", "ti@example.org"],
                       env=env, check=True, capture_output=True, text=True)
    assert "Listo" in r.stdout
    texto = destino.read_text()
    assert "ORG_DOMINIO=example.org" in texto
    assert "ORG_URL_CORREO=https://hosting.example.org" in texto
    assert 'ORG_CORREOS_AVISOS="ti@example.org"' in texto
    destino.write_text("ORG_DOMINIO=propio.example.org\n")
    r = subprocess.run(["bash", ORGANIZACION, "example.org", "hosting.example.org"],
                       env=env, check=True, capture_output=True, text=True)
    assert "Sin cambios" in r.stdout
    assert destino.read_text() == "ORG_DOMINIO=propio.example.org\n"


def test_organizacion_env_rechaza_valores_raros(tmp_path):
    env = dict(os.environ, ORG_FICHERO=str(tmp_path / "o.env"))
    r = subprocess.run(["bash", ORGANIZACION, "example.org;rm", "hosting.example.org"], env=env, capture_output=True)
    assert r.returncode != 0
    assert not (tmp_path / "o.env").exists()
