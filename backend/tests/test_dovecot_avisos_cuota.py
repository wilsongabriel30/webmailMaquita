"""Avisos de cuota (deploy/dovecot/avisos-cuota): plantilla de Dovecot 2.4 y guion de aviso."""

import os
import subprocess

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
D = os.path.join(RAIZ, "deploy", "dovecot", "avisos-cuota")


def test_plantilla_umbral_alto_primero_y_servicio():
    t = open(os.path.join(D, "avisos-cuota.conf.plantilla"), encoding="utf-8").read()
    # Dovecot ejecuta solo el primer aviso que se cumple: el 95 % debe ir antes que el 85 %.
    assert t.index("quota_storage_percentage = 95") < t.index("quota_storage_percentage = 85")
    assert 'quota "@CUOTA@" {' in t
    assert "executable = script /usr/local/bin/maquita-aviso-cuota" in t


def _aviso(tmp_path, pct, usuario="ana@example.org", uso="180000\t200000"):
    lda, enviado, org = tmp_path / "lda.sh", tmp_path / "enviado", tmp_path / "org.env"
    lda.write_text(f'#!/bin/sh\ncat >> "{tmp_path}/buzon"\n')
    (tmp_path / "sendmail.sh").write_text(f'#!/bin/sh\necho "$@" >> "{enviado}"\ncat >> "{enviado}"\n')
    (tmp_path / "doveadm.sh").write_text(f'#!/bin/sh\nprintf "Quota name\\tType\\tValue\\tLimit\\t%%\\nUser quota\\tSTORAGE\\t{uso}\\t90\\n"\n')
    for f in ("lda.sh", "sendmail.sh", "doveadm.sh"):
        os.chmod(tmp_path / f, 0o755)
    org.write_text('ORG_REMITENTE_AVISOS=postmaster@example.org\nORG_CORREOS_AVISOS="ti@example.org"\n')
    env = dict(os.environ, MAQUITA_ORG_ENV=str(org), MAQUITA_AVISO_CUOTA_DIR=str(tmp_path / "estado"),
               MAQUITA_LDA=str(lda), MAQUITA_SENDMAIL=str(tmp_path / "sendmail.sh"),
               MAQUITA_DOVEADM=str(tmp_path / "doveadm.sh"))
    subprocess.run(["bash", os.path.join(D, "aviso-cuota.sh"), pct, usuario], env=env, check=True)
    buzon = tmp_path / "buzon"
    return (buzon.read_text() if buzon.exists() else ""), (enviado.read_text() if enviado.exists() else "")


def test_aviso_85_al_usuario_sin_copia_a_ti(tmp_path):
    buzon, ti = _aviso(tmp_path, "85")
    assert "Auto-Submitted: auto-generated" in buzon
    assert "85 % de su espacio (176 MB de 195 MB)" in buzon
    assert "Vacíe la «Papelera»" in buzon
    assert ti == ""


def test_aviso_95_urgente_con_nota_a_ti_y_una_vez_por_semana(tmp_path):
    buzon, ti = _aviso(tmp_path, "95", uso="9961472\t10485760")
    assert "está al 95 % de su espacio (9,5 GB de 10 GB)" in buzon
    assert "ti@example.org" in ti and "ana@example.org" in ti
    buzon2, _ = _aviso(tmp_path, "95")
    assert buzon2.count("Auto-Submitted") == 1  # el segundo cruce en la misma semana no avisa


def test_rechaza_argumentos_raros(tmp_path):
    buzon, ti = _aviso(tmp_path, "85; rm", usuario="x")
    assert buzon == "" and ti == ""
