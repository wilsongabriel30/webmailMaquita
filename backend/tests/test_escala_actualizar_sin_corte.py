"""deploy/escala/actualizar-sin-corte.sh con réplicas de mentira en esta máquina.

Cada «réplica» es un servidor HTTP local que responde /api/salud y /api/listo (503 si
existe su archivo de drenaje, o si quedó «rota»). `systemctl` se sustituye por un guion
que anota qué se reinició y si en ese momento la réplica estaba drenada.
"""

import http.server
import os
import shutil
import subprocess
import threading

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(RAIZ, "deploy", "escala", "actualizar-sin-corte.sh")

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("curl")), reason="hace falta bash y curl"
)


def _servidor(drenaje: str):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/api/salud":
                codigo = 200
            elif self.path == "/api/listo":
                fuera = os.path.exists(drenaje) or os.path.exists(drenaje + ".roto")
                codigo = 503 if fuera else 200
            else:
                codigo = 404
            self.send_response(codigo)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return H


@pytest.fixture
def entorno(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    registro = tmp_path / "reinicios.log"
    # systemctl falso: anota el servicio y si su drenaje existía en ese momento; si el
    # servicio está en ROMPER, la réplica queda «rota» (/api/listo ya no vuelve a 200).
    (bin_ / "systemctl").write_text(
        "#!/bin/bash\n"
        'svc="$2"; d="$DRENAJES_DIR/drenar-${svc##*@}"\n'
        '[ -e "$d" ] && e=drenada || e=SIN-DRENAR\n'
        f'echo "$1 $svc $e" >> "{registro}"\n'
        'case " ${ROMPER:-} " in *" $svc "*) touch "$d.roto";; esac\n'
    )
    (bin_ / "systemctl").chmod(0o755)
    servidores = []

    def replica(drenada=False):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        puerto = srv.server_port
        drenaje = str(tmp_path / f"drenar-{puerto}")
        srv.RequestHandlerClass = _servidor(drenaje)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servidores.append(srv)
        if drenada:
            open(drenaje, "w").close()
        return f"local:{puerto}:maquita-webmail@{puerto}:{drenaje}"

    def correr(replicas, **extra):
        env = {
            **os.environ,
            "PATH": f"{bin_}:{os.environ.get('PATH', '')}",
            "REPLICAS": " ".join(replicas),
            "ESPERA_DRENAJE": "0",
            "TIEMPO_MAX": "4",
            "DRENAJES_DIR": str(tmp_path),
            **extra,
        }
        return subprocess.run(
            ["bash", SCRIPT], capture_output=True, text=True, env=env, timeout=60
        )

    def reinicios():
        return registro.read_text().splitlines() if registro.exists() else []

    yield replica, correr, reinicios, tmp_path
    for s in servidores:
        s.shutdown()
        s.server_close()


def _servicio(destino):
    return destino.split(":")[2]


def test_reinicia_una_a_una_drenando_antes(entorno):
    replica, correr, reinicios, tmp_path = entorno
    replicas = [replica() for _ in range(3)]
    r = correr(replicas)
    assert r.returncode == 0, r.stdout + r.stderr
    assert reinicios() == [f"restart {_servicio(x)} drenada" for x in replicas]
    assert not list(tmp_path.glob("drenar-*"))  # ninguna queda fuera del balanceador


def test_no_toca_nada_si_una_replica_no_esta_lista(entorno):
    replica, correr, reinicios, _ = entorno
    r = correr([replica(), replica(drenada=True)])
    assert r.returncode == 1
    assert reinicios() == []  # con una ya caída, reiniciar otra dejaría el servicio sin nadie


def test_se_detiene_si_una_replica_no_vuelve(entorno):
    replica, correr, reinicios, _ = entorno
    replicas = [replica(), replica()]
    r = correr(replicas, ROMPER=_servicio(replicas[0]))
    assert r.returncode == 1
    # Solo se tocó la primera: la segunda sigue sirviendo con la versión anterior.
    assert reinicios() == [f"restart {_servicio(replicas[0])} drenada"]
    assert "Se detiene" in r.stderr


def test_una_sola_replica_avisa_del_corte(entorno):
    replica, correr, reinicios, _ = entorno
    r = correr([replica()])
    assert r.returncode == 0
    assert "Solo hay una réplica" in r.stdout
    assert len(reinicios()) == 1
