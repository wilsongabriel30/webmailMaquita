"""El endurecimiento opcional de systemd no debe impedir «sudo» dentro del backend (Andes, 16/11/2026)."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO = RAIZ / "deploy/hardening/systemd/maquita-webmail.service.d/hardening.conf"


def _directivas() -> dict[str, list[str]]:
    d: dict[str, list[str]] = {}
    for linea in ARCHIVO.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith(("#", "[")) and "=" in linea:
            clave, valor = linea.split("=", 1)
            d.setdefault(clave, []).append(valor)
    return d


def test_sudo_puede_elevar_dentro_del_servicio():
    d = _directivas()
    assert d["NoNewPrivileges"] == ["no"]
    capacidades = set(d["CapabilityBoundingSet"][0].split())
    assert {"CAP_SETUID", "CAP_SETGID"} <= capacidades


def test_no_trae_topes_ocultos_de_memoria_ni_de_tareas():
    d = _directivas()
    assert "MemoryMax" not in d and "TasksMax" not in d


def test_las_rutas_que_pueden_no_existir_son_opcionales():
    rutas = " ".join(_directivas()["ReadWritePaths"]).split()
    assert "/opt/maquita-webmail" in rutas and "-/var/vmail" in rutas
    for r in rutas:
        if r.lstrip("-") not in ("/opt/maquita-webmail", "/var/log"):
            assert r.startswith("-"), r


def test_el_validador_detecta_un_servicio_que_no_puede_usar_sudo():
    v = (RAIZ / "deploy/tools/validar-despliegue.sh").read_text(encoding="utf-8")
    assert "-p NoNewPrivileges --value" in v and "cap_setuid" in v and "cap_setgid" in v
