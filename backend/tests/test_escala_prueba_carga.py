"""deploy/escala/prueba-carga-webmail.py contra un servidor de mentira (sin red real)."""

import http.server
import importlib.util
import json
import os
import subprocess
import sys
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(RAIZ, "deploy", "escala", "prueba-carga-webmail.py")


class _Falso(http.server.BaseHTTPRequestHandler):
    vistas: list = []

    def log_message(self, *a):
        pass

    def _responder(self, codigo, cuerpo, cookie=None):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(datos)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        _Falso.vistas.append(("POST", self.path))
        if self.path == "/api/auth/login":
            if cuerpo.get("password") == "buena":
                return self._responder(200, {"ok": 1}, "access_token=t; Path=/")
            return self._responder(401, {"detail": "no"})
        return self._responder(200, {})

    def do_GET(self):
        _Falso.vistas.append(("GET", self.path))
        if "access_token=t" not in (self.headers.get("Cookie") or ""):
            return self._responder(401, {"detail": "sin sesión"})
        return self._responder(200, {"messages": []})


def _servidor():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Falso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _correr(srv, clave, *extra):
    entorno = {**os.environ, "CLAVE": clave}
    return subprocess.run(
        [sys.executable, SCRIPT, "--url", f"http://127.0.0.1:{srv.server_port}",
         "--usuario", "carga@example.org", "--concurrencia", "4", "--duracion", "0.5",
         *extra],
        capture_output=True, text=True, env=entorno, timeout=60,
    )


def test_mide_login_bandeja_y_busqueda_y_cierra_sesion():
    _Falso.vistas = []
    srv = _servidor()
    try:
        r = _correr(srv, "buena")
    finally:
        srv.shutdown()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "bandeja" in r.stdout and "busqueda" in r.stdout and "login" in r.stdout
    rutas = [p for _, p in _Falso.vistas]
    assert rutas[0] == "/api/auth/login" and rutas[-1] == "/api/auth/logout"
    assert any("search=factura" in p for p in rutas)


def test_falla_si_no_puede_entrar():
    srv = _servidor()
    try:
        r = _correr(srv, "mala")
    finally:
        srv.shutdown()
    assert r.returncode == 1


def test_percentil_rango_mas_cercano():
    spec = importlib.util.spec_from_file_location("carga", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    v = list(range(1, 101))
    assert m.percentil(v, 50) == 50 and m.percentil(v, 95) == 95
    assert m.percentil([7], 99) == 7 and m.percentil([], 50) is None
