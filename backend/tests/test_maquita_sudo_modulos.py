"""maquita-sudo partido en módulos (v1.11.3): los validadores en deploy/sudoers/lib, cargados de forma segura."""

import importlib.machinery
import importlib.util
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RUTA = os.path.join(RAIZ, "deploy", "sudoers", "maquita-sudo")
_loader = importlib.machinery.SourceFileLoader("maquita_sudo_modulos", _RUTA)
_spec = importlib.util.spec_from_loader("maquita_sudo_modulos", _loader)
ms = importlib.util.module_from_spec(_spec)
_loader.exec_module(ms)


def test_cada_programa_tiene_validador_y_politica():
    assert set(ms.VALIDADORES) == set(ms.BINARIOS)
    for permisos in ms.POLITICA.values():
        assert set(permisos) <= set(ms.BINARIOS)


def test_en_el_repositorio_carga_los_modulos_de_deploy_sudoers_lib():
    assert ms.LIB == os.path.join(RAIZ, "deploy", "sudoers", "lib")
    assert ms._carpeta_lib() != ms.LIB_INSTALADA


def test_un_rechazo_de_un_modulo_es_el_mismo_rechazo():
    try:
        ms.autorizar(
            "maquita-admin", "maquita-sitios", ["borrar", "example.org", "example.com"]
        )
    except ms.Rechazo:
        pass
    else:
        raise AssertionError("debió rechazarse")


def test_solo_root_rechaza_lo_que_otro_puede_escribir(tmp_path):
    (tmp_path / "sudo_base.py").write_text("")
    os.chmod(tmp_path / "sudo_base.py", 0o664)
    assert ms._solo_root(str(tmp_path)) is False
    os.chmod(tmp_path / "sudo_base.py", 0o644)
    os.chmod(tmp_path, 0o755)
    # Fuera de root (CI) tampoco vale: el dueño tiene que ser root.
    assert ms._solo_root(str(tmp_path)) is (os.geteuid() == 0)


def test_lineas_maximas_por_archivo():
    for ruta in [_RUTA] + [
        os.path.join(RAIZ, "deploy", "sudoers", "lib", n)
        for n in os.listdir(os.path.join(RAIZ, "deploy", "sudoers", "lib"))
        if n.endswith(".py")
    ]:
        with open(ruta) as f:
            assert sum(1 for _ in f) < 800, ruta
