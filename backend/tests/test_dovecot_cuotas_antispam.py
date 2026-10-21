"""Estructura de las cuotas y del aprendizaje antispam de Dovecot 2.4 (deploy/dovecot).

Lo probado a mano con Dovecot 2.4.1 (20/10/2026) que estas pruebas protegen:
- la cuota por usuario solo se aplica si el userdb devuelve quota_storage_size (quota_rule de la 2.3 se ignora);
- un storage_size dentro del bloque quota tapa el de cada usuario: el valor por defecto va fuera.
"""

import os
import re

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
DOVECOT = os.path.join(RAIZ, "deploy", "dovecot")


def _leer(*partes):
    with open(os.path.join(RAIZ, *partes), encoding="utf-8") as f:
        return f.read()


def _bloque(texto, cabecera):
    """Contenido entre la llave de «cabecera {» y su cierre."""
    i = texto.index(cabecera)
    j, prof = texto.index("{", i), 0
    for k in range(j, len(texto)):
        prof += {"{": 1, "}": -1}.get(texto[k], 0)
        if prof == 0:
            return texto[j + 1 : k]
    raise AssertionError(f"bloque sin cerrar: {cabecera}")


def test_userdb_de_la_plantilla_devuelve_quota_storage_size():
    conf = _leer("deploy", "webmail", "configs", "dovecot.conf")
    userdb = _bloque(conf, "userdb sql")
    assert "AS quota_storage_size" in userdb
    assert "quota_rule" not in userdb


def test_valor_por_defecto_fuera_del_bloque_quota():
    conf = _leer("deploy", "dovecot", "cuotas-y-antispam.conf")
    bloque = _bloque(conf, 'quota "User quota"')
    assert "storage_size" not in bloque
    assert re.search(r"^quota_storage_size = ", conf, re.M)
    assert "quota = yes" in _bloque(conf, "protocol lmtp")


def test_filtros_y_programas_referidos_existen():
    conf = _leer("deploy", "dovecot", "cuotas-y-antispam.conf")
    for ruta in re.findall(r"path = /var/vmail/sieve/(\S+)", conf):
        assert os.path.exists(os.path.join(DOVECOT, ruta)), ruta
    for sieve in ("report-spam.sieve", "report-ham.sieve"):
        for programa in re.findall(r'pipe :copy "([^"]+)"', _leer("deploy", "dovecot", sieve)):
            assert os.access(os.path.join(DOVECOT, "pipe-bin", programa), os.X_OK), programa


def test_el_ajuste_y_el_instalador_usan_la_misma_ruta_incluida():
    include = "!include_try /etc/dovecot/maquita.d/*.conf"
    assert include in _leer("deploy", "dovecot", "instalar-cuotas-antispam.sh")
    ajuste = _leer("deploy", "ajustes", "51-cuotas-y-aprendizaje-antispam.sh")
    assert include in ajuste
    assert "maquita.d/cuotas-y-antispam.conf" in ajuste
