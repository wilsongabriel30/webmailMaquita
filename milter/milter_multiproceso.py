"""Arranque del milter en varios procesos (07/11/2026).

Medido en la simulación masiva del 07/11/2026: con adjuntos el milter era el techo del servidor
(3,3 correos/s con 16 vCPU y la CPU a medio usar), porque un solo proceso de Python usa un solo
núcleo (GIL) y el análisis DLP de adjuntos es cálculo puro. Aquí el puerto se abre UNA vez y se
reparten las conexiones de Postfix entre varios procesos hijos que aceptan sobre el mismo socket
(modelo pre-fork, como nginx o Postfix). La lógica de análisis no cambia: cada hijo carga
maquita_milter.py tal cual.

  MILTER_PROCESOS   número de procesos hijos (por defecto 6)
  MILTER_PUERTO     puerto de escucha (por defecto 11335)

Si un hijo muere, el padre lo reemplaza. Con SIGTERM/SIGINT el padre avisa a los hijos y espera.
Vuelta atrás: quitar el ExecStart de maquita-milter.service.d/capacidad.conf (un solo proceso).
"""
from __future__ import annotations

import asyncio
import functools
import logging
import os
import signal
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())  # WorkingDirectory del servicio = carpeta del milter

PROCESOS = max(1, int(os.getenv("MILTER_PROCESOS", "6")))
PUERTO = int(os.getenv("MILTER_PUERTO", "11335"))
log = logging.getLogger("maquita_milter.multiproceso")


def _abrir_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PUERTO))
    s.listen(1024)
    s.setblocking(False)
    return s


async def _servir(srv, sock: socket.socket) -> None:
    """Igual que MilterServer.start_server de purepythonmilter, pero sobre un socket ya abierto."""
    from purepythonmilter.server import milterserver

    def cancelar(sig: signal.Signals) -> None:
        log.info("Hijo %d: cerrando por %s", os.getpid(), sig.name)
        for t in asyncio.all_tasks():
            t.cancel()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, functools.partial(cancelar, sig))
    srv._state = milterserver.MilterServerState.STARTING
    async with await asyncio.start_server(srv.handle_connection, sock=sock) as servidor:
        srv._state = milterserver.MilterServerState.STARTED
        try:
            await servidor.serve_forever()
        except asyncio.CancelledError:
            await srv.shutdown()


def _hijo(sock: socket.socket) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    import maquita_milter as mm
    from purepythonmilter.server import milterserver

    mm._load_env_keys()
    if not mm._dsn():
        log.error("Falta DATABASE_URL: el hijo %d no arranca", os.getpid())
        os._exit(3)
    srv = milterserver.MilterServer(app_factory=mm.milter._get_factory())
    try:
        asyncio.run(_servir(srv, sock))
    finally:
        os._exit(0)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("maquita_milter").setLevel(logging.INFO)
    sock = _abrir_socket()
    hijos: dict[int, float] = {}
    saliendo = False

    def lanzar() -> None:
        pid = os.fork()
        if pid == 0:
            _hijo(sock)
        hijos[pid] = time.monotonic()

    def terminar(sig, _frame) -> None:
        nonlocal saliendo
        saliendo = True
        for pid in list(hijos):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    signal.signal(signal.SIGTERM, terminar)
    signal.signal(signal.SIGINT, terminar)
    for _ in range(PROCESOS):
        lanzar()
    log.info("Milter en %d procesos sobre 127.0.0.1:%d (padre %d)", PROCESOS, PUERTO, os.getpid())

    while hijos:
        try:
            pid, estado = os.wait()
        except ChildProcessError:
            break
        except InterruptedError:
            continue
        inicio = hijos.pop(pid, None)
        if inicio is None or saliendo:
            continue
        log.warning("Hijo %d terminó (estado %s); se reemplaza", pid, estado)
        # Si muere nada más arrancar, esperar un poco para no girar en vacío.
        if time.monotonic() - inicio < 5:
            time.sleep(2)
        lanzar()
    log.info("Milter detenido")


if __name__ == "__main__":
    main()
