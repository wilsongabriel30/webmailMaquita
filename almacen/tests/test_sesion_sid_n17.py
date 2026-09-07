# -*- coding: utf-8 -*-
"""N-17: el Almacén valida la sesión del webmail con la MISMA clave de Redis que escribe el correo
(`imap_pass:<usuario>:<sid>`, F-01). Prueba de contrato entre las dos aplicaciones."""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
# El módulo exige estas variables al importarse; aquí no se conecta a nada (valores de prueba).
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow
import auth_webmail as aw  # noqa: E402


class _RedisFalso:
    def __init__(self, claves):
        self.claves, self.pedidas = set(claves), []

    def exists(self, clave):
        self.pedidas.append(clave)
        return 1 if clave in self.claves else 0


def _con_redis(monkeypatch, claves):
    falso = _RedisFalso(claves)
    monkeypatch.setattr(aw, "_REDIS_URL", "redis://localhost/0")
    monkeypatch.setattr(aw, "_redis_cliente", falso)
    return falso


def test_sesion_del_webmail_se_valida_por_sid(monkeypatch):
    falso = _con_redis(monkeypatch, {"imap_pass:ana@ejemplo.org:SID1"})
    assert aw._sesion_viva("ana@ejemplo.org", sid="SID1") is True
    assert aw._sesion_viva("ana@ejemplo.org", sid="SID2") is False  # otra sesión (revocada o ajena)
    assert falso.pedidas == ["imap_pass:ana@ejemplo.org:SID1", "imap_pass:ana@ejemplo.org:SID2"]


def test_la_clave_antigua_sin_sid_ya_no_da_acceso_a_una_sesion_con_sid(monkeypatch):
    _con_redis(monkeypatch, {"imap_pass:ana@ejemplo.org"})
    assert aw._sesion_viva("ana@ejemplo.org", sid="SID1") is False


def test_cuenta_externa_sigue_con_su_clave(monkeypatch):
    falso = _con_redis(monkeypatch, {"sesion_externa:pasante@fuera.org"})
    assert aw._sesion_viva("pasante@fuera.org", "sesion_externa:%s") is True
    assert falso.pedidas == ["sesion_externa:pasante@fuera.org"]


def test_resolver_cookie_exige_sid():
    src = open(os.path.join(RAIZ, "servicio", "auth_webmail.py"), encoding="utf-8").read()
    bloque = src.split("def _resolver_cookie", 1)[1]
    assert "payload.get('sid')" in bloque and "_sesion_viva(username, sid=sid)" in bloque


def test_contrato_con_el_correo():
    """La forma de la clave la define backend/app/auth/sesiones.py; si cambia allí, esto avisa."""
    sesiones = open(os.path.join(os.path.dirname(RAIZ), "backend", "app", "auth", "sesiones.py"), encoding="utf-8").read()
    assert re.search(r'f"imap_pass:\{username\}:\{sid\}"', sesiones), "el correo cambió la clave de sesión: adaptar auth_webmail._sesion_viva"
