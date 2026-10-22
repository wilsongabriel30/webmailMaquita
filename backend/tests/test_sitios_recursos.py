"""CPU y memoria por sitio (deploy/sitios/lib/recursos.py): /proc y el grupo de control de la aplicación propia,
falsos y en una carpeta temporal. Lecturas sucesivas, procesos que se reinician, la unidad que no se cuenta dos
veces, la ventana de 24 horas y la limpieza de los sitios dados de baja."""

import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sitios_lib import cargar, sitio  # noqa: E402

m = cargar()
rc = m["recursos"]
D = "example.org"


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    meta = sitio(tmp_path, monkeypatch, propia={"tipo": "python"}, php_ajustes={"memory_limit": "512M"})
    for carpeta in ("proc", "cgroup", "recursos"):
        (tmp_path / carpeta).mkdir()
    monkeypatch.setattr(rc, "PROC", str(tmp_path / "proc"))
    monkeypatch.setattr(rc, "CGROUP", str(tmp_path / "cgroup"))
    monkeypatch.setattr(rc, "DIR", str(tmp_path / "recursos"))
    monkeypatch.setattr(rc, "TICKS", 100)
    # Los procesos falsos son del usuario que corre las pruebas: ese es el uid del sitio.
    uids = {"web0000": os.getuid()}
    monkeypatch.setattr(rc, "pwd", types.SimpleNamespace(getpwnam=lambda u: types.SimpleNamespace(pw_uid=uids[u])))
    return types.SimpleNamespace(meta=meta, tmp=tmp_path)


def proceso(w, pid, ticks, arranque=1000, pss_kb=10240):
    carpeta = w.tmp / "proc" / str(pid)
    carpeta.mkdir(exist_ok=True)
    utime, stime = ticks // 2, ticks - ticks // 2
    campos = ["S", "1"] + ["0"] * 9 + [str(utime), str(stime)] + ["0"] * 6 + [str(arranque), "0", "0"]
    (carpeta / "stat").write_text(f"{pid} (php-fpm: pool web0000) " + " ".join(campos) + "\n")
    (carpeta / "smaps_rollup").write_text(f"Rss:  {pss_kb * 2} kB\nPss:  {pss_kb} kB\n")


def unidad(w, usec, bytes_, pids):
    carpeta = w.tmp / "cgroup" / "sitio-web0000.service"
    carpeta.mkdir(exist_ok=True)
    (carpeta / "cpu.stat").write_text(f"usage_usec {usec}\nuser_usec 0\n")
    (carpeta / "memory.current").write_text(f"{bytes_}\n")
    (carpeta / "cgroup.procs").write_text("".join(f"{p}\n" for p in pids))


def serie(w):
    return json.loads((w.tmp / "recursos" / f"{D}.json").read_text())["puntos"]


def test_dos_lecturas(mundo):
    proceso(mundo, 101, ticks=500)
    proceso(mundo, 102, ticks=100)
    proceso(mundo, 103, ticks=900, pss_kb=51200)  # el de la aplicación: lo cuenta su grupo de control
    unidad(mundo, usec=10_000_000, bytes_=100 * 1048576, pids=[103])
    assert rc.recoger(ahora=100_000)["medidos"] == 1
    assert serie(mundo) == [[100_000, None, 120.0]]  # sin lectura anterior no hay CPU; 10 + 10 MB de PHP + 100 de la app
    proceso(mundo, 101, ticks=800)  # +3 s
    proceso(mundo, 102, ticks=50, arranque=2000)  # se reinició: cuenta todo lo suyo (0,5 s)
    proceso(mundo, 103, ticks=5000, pss_kb=51200)  # no se cuenta por /proc
    unidad(mundo, usec=13_000_000, bytes_=100 * 1048576, pids=[103])  # +3 s
    rc.recoger(ahora=100_300)
    assert serie(mundo)[-1] == [100_300, round(6.5 / 300 * 100, 1), 120.0]


def test_lecturas_muy_separadas_sin_cpu(mundo):
    proceso(mundo, 101, ticks=0)
    rc.recoger(ahora=100_000)
    proceso(mundo, 101, ticks=100)
    rc.recoger(ahora=100_000 + 4 * rc.INTERVALO)  # el temporizador estuvo parado: no se inventa un promedio
    assert serie(mundo)[-1][1] is None


def test_ventana_de_24_horas_y_huerfanos(mundo):
    (mundo.tmp / "recursos" / f"{D}.json").write_text(json.dumps({"puntos": [[1, 5.0, 10.0], [90_000, 1.0, 20.0]]}))
    (mundo.tmp / "recursos" / "baja.example.org.json").write_text(json.dumps({"puntos": []}))
    datos = rc.recoger(ahora=100_000)
    assert [p[0] for p in serie(mundo)] == [90_000, 100_000]
    assert datos["borrados"] == ["baja.example.org"]
    assert sorted(os.listdir(mundo.tmp / "recursos")) == ["estado.json", f"{D}.json"]


def test_ver(mundo, monkeypatch):
    import time

    ahora = int(time.time())
    (mundo.tmp / "recursos" / f"{D}.json").write_text(json.dumps({"puntos": [
        [ahora - 90_000, 99.0, 999.0], [ahora - 600, None, 30.0], [ahora - 300, 4.0, 40.0], [ahora, 2.0, 50.0]]}))
    datos = rc.ver(D)
    assert datos["instalado"] and datos["intervalo"] == 300 and len(datos["puntos"]) == 3
    assert datos["resumen"] == {"cpu_media": 3.0, "cpu_maxima": 4.0, "memoria_media_mb": 40.0, "memoria_maxima_mb": 50.0,
                                "ultimo": [ahora, 2.0, 50.0]}
    assert datos["limites"] == {"php_procesos": 6, "php_memoria_mb": 512, "app_memoria_mb": 768, "app_cpu": 150}


def test_ver_sin_temporizador(mundo, monkeypatch):
    monkeypatch.setattr(rc, "DIR", str(mundo.tmp / "no-esta"))
    datos = rc.ver(D)
    assert datos["instalado"] is False and datos["puntos"] == []


def test_ver_sitio_que_no_existe(mundo):
    with pytest.raises(m["comun"].ErrorSitio):
        rc.ver("nada.example.org")


def test_proceso_que_desaparece_o_raro(mundo):
    proceso(mundo, 101, ticks=10)
    (mundo.tmp / "proc" / "102").mkdir()  # sin stat: terminó mientras se leía
    (mundo.tmp / "proc" / "102" / "stat").write_text("roto")
    (mundo.tmp / "proc" / "self").mkdir()
    rc.recoger(ahora=100_000)
    assert serie(mundo) == [[100_000, None, 10.0]]
