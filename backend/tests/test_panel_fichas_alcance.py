"""Panel general, v1.11: alcance de las fichas de API (admin-panel/backend/app/fichas_api/alcance.py). Falla cerrado:
la cuenta, los administradores, las fichas, el correo ajeno y el cortafuegos del servidor nunca con una ficha."""

import importlib.util
import os

import pytest

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "admin-panel", "backend", "app", "fichas_api", "alcance.py")
_spec = importlib.util.spec_from_file_location("alcance_fichas_panel", _RUTA)
alcance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alcance)
TODOS = list(alcance.ALCANCES)


@pytest.mark.parametrize("alcances,metodo,ruta,esperado", [
    (["lectura"], "GET", "/api/sitios", True),
    (["lectura"], "GET", "/api/sitios/example.org/cortafuegos", True),
    (["lectura"], "PUT", "/api/sitios/example.org/cortafuegos", False),
    (["sitios"], "PUT", "/api/sitios/example.org/cortafuegos", True),
    (["sitios"], "POST", "/api/dns/example.org", False),
    (["dns"], "POST", "/api/dns/example.org", True),
    (["buzones"], "POST", "/api/mailboxes", True),
    (["lectura"], "GET", "/api/auth/me", True),
    (TODOS, "POST", "/api/auth/change-password", False),
    (TODOS, "POST", "/api/auth/totp/setup", False),
    (TODOS, "POST", "/api/fichas-api", False),
    (TODOS, "GET", "/api/fichas-api", False),
    (TODOS, "POST", "/api/admin/users", False),
    (TODOS, "GET", "/api/admin-recovery", False),
    (TODOS, "GET", "/api/segundo-factor", False),
    (TODOS, "GET", "/api/mailviewer/ana@example.org", False),
    (TODOS, "POST", "/api/recovery/restore", False),
    (TODOS, "GET", "/api/quarantine", False),
    (TODOS, "GET", "/api/ediscovery", False),
    (TODOS, "PUT", "/api/cortafuegos", False),
    (TODOS, "POST", "/api/actualizaciones/aplicar", False),
    (TODOS, "GET", "/api/sitiosx", False),
    (TODOS, "GET", "/api/sitios/../admin/users", False),
    ("lectura", "GET", "/api/sitios", False),
    (None, "GET", "/api/sitios", False),
])
def test_alcance(alcances, metodo, ruta, esperado):
    assert alcance.permitido(alcances, metodo, ruta) is esperado


def test_validar_alcances():
    assert alcance.validar_alcances(["sitios", "lectura"]) == ["lectura", "sitios"]
    for malo in ([], ["superadmin"], ["lectura", "admin"], "lectura", None, [None]):
        assert alcance.validar_alcances(malo) is None


def test_fichas_distinguibles_de_las_del_portal():
    assert alcance.PREFIJO == "mqa_"
