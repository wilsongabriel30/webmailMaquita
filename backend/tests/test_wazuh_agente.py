"""deploy/wazuh/: estado del agente para el panel, bloque de Maquita en ossec.conf y reglas del manager."""

import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WAZUH = os.path.join(REPO, "deploy", "wazuh")
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="sin bash")

CONF_BASE = """<ossec_config>
  <client>
    <server>
      <address>siem.example.org</address>
      <port>1514</port>
    </server>
  </client>
  <localfile>
    <log_format>syslog</log_format>
    <location>/var/log/auth.log</location>
  </localfile>
</ossec_config>
"""


def _estado(raiz):
    r = subprocess.run(["python3", os.path.join(WAZUH, "maquita-wazuh"), "estado"], capture_output=True, text=True,
                       env=dict(os.environ, WAZUH_RAIZ=str(raiz)), timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_estado_sin_agente(tmp_path):
    assert _estado(tmp_path / "no-hay") == {"instalado": False}


def test_estado_conectado(tmp_path):
    (tmp_path / "etc").mkdir()
    (tmp_path / "var/run").mkdir(parents=True)
    (tmp_path / "etc/ossec.conf").write_text(CONF_BASE + "<!-- maquita: inicio -->\n")
    (tmp_path / "var/run/wazuh-agentd.state").write_text(
        "# State file\nstatus='connected'\nlast_keepalive='2026-10-21 10:00:00'\nlast_ack='2026-10-21 10:00:05'\nmsg_sent='42'\n")
    e = _estado(tmp_path)
    assert e["instalado"] and e["conectado"] and e["estado"] == "connected"
    assert e["manager"] == "siem.example.org" and e["ultimo_contacto"] == "2026-10-21 10:00:00"
    assert e["bloque_propio"] is True


def test_estado_solo_acepta_estado():
    r = subprocess.run(["python3", os.path.join(WAZUH, "maquita-wazuh"), "registrar"], capture_output=True, text=True)
    assert r.returncode == 2


def _bloque(conf, raiz):
    r = subprocess.run(["bash", os.path.join(WAZUH, "bloque-ossec.sh"), str(conf), "/opt/maquita-webmail"],
                       capture_output=True, text=True, env=dict(os.environ, WAZUH_LOG_RAIZ=str(raiz)), timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_bloque_ossec_idempotente(tmp_path):
    raiz = tmp_path / "raiz"
    for f in ("var/log/auth.log", "var/log/mail.log", "var/log/nginx/activesync-access.log", "var/log/guardian-web-correo.log"):
        (raiz / f).parent.mkdir(parents=True, exist_ok=True)
        (raiz / f).write_text("")
    conf = tmp_path / "ossec.conf"
    conf.write_text(CONF_BASE)
    uno = _bloque(conf, raiz)
    assert uno.startswith(CONF_BASE.rstrip("\n"))
    assert uno.count("<!-- maquita: inicio") == 1 and uno.count("<!-- maquita: fin -->") == 1
    assert "<location>/var/log/maquita/seguridad.json</location>" in uno
    assert "<location>/var/log/mail.log</location>" in uno
    assert "<location>/var/log/nginx/activesync-access.log</location>" in uno
    assert uno.count("<location>/var/log/auth.log</location>") == 1  # ya estaba: no se duplica
    assert "/var/log/maquita/diario.log" not in uno  # no existe en esta máquina
    assert "/etc/postfix" in uno and "<directories>/opt/maquita-webmail</directories>" in uno
    assert "report_changes" not in uno.split("<!-- maquita: inicio")[1].split("-->", 1)[1].split("<syscheck>")[1]
    conf.write_text(uno)
    assert _bloque(conf, raiz) == uno  # repetir no cambia nada
    # XML bien formado (Wazuh admite varias raíces <ossec_config>)
    ET.fromstring("<r>" + re.sub(r"<!--.*?-->", "", uno, flags=re.S) + "</r>")


def test_reglas_del_manager_bien_formadas():
    reglas = ET.fromstring("<r>" + open(os.path.join(WAZUH, "manager/rules/maquita_rules.xml")).read() + "</r>")
    ids = [int(r.get("id")) for r in reglas.iter("rule")]
    assert ids and all(100800 <= i <= 100899 for i in ids) and len(ids) == len(set(ids))
    decos = ET.fromstring("<r>" + open(os.path.join(WAZUH, "manager/decoders/maquita_decoders.xml")).read() + "</r>")
    expresiones = [re.compile(d.text) for d in decos.iter("regex")]
    ok = "MAQUITA_SUDO ok usuario=maquita-admin postqueue -p"
    rechazo = "MAQUITA_SUDO rechazado usuario=www-data programa=doveadm motivo=www-data no puede ejecutar doveadm pw args=pw"
    assert expresiones[0].match(ok).groups() == ("ok", "maquita-admin", "postqueue")
    assert expresiones[1].match(rechazo).group(4) == "www-data no puede ejecutar doveadm pw"


def test_instalador_de_wazuh_valida_antes_de_tocar_nada():
    if os.geteuid() != 0:
        pytest.skip("el instalador exige root")
    env = dict(os.environ, WAZUH_MANAGER="siem.example.org;rm -rf /")
    r = subprocess.run(["bash", os.path.join(WAZUH, "instalar.sh"), "--simular"], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 2 and "no es un nombre ni una IP" in r.stdout
    env = dict(os.environ, WAZUH_MANAGER="siem.example.org", WAZUH_VERSION="4.12")
    r = subprocess.run(["bash", os.path.join(WAZUH, "instalar.sh"), "--simular"], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 2 and "WAZUH_VERSION" in r.stdout


def test_recolector_sin_panel_no_hace_nada(tmp_path):
    if os.geteuid() != 0:
        pytest.skip("el instalador exige root")
    r = subprocess.run(["bash", os.path.join(REPO, "deploy/seguridad/instalar.sh"), "--simular"],
                       capture_output=True, text=True, env=dict(os.environ, APP_DIR=str(tmp_path)), timeout=30)
    assert r.returncode == 0 and r.stdout.startswith("Sin cambios: el panel general no está instalado")
