"""Intermediario de sitios y base de datos simulados, para probar las rutas de «Mi sitio web» sin
servidor: un socket Unix de verdad (el cliente se prueba entero) que anota cada petición y
responde lo que diga cada prueba."""

import json
import os
import socketserver
import tempfile
import threading


class Intermediario:
    def __init__(self, dir_subidas: str):
        self.dir_subidas = dir_subidas
        self.peticiones: list[dict] = []
        self.respuestas: dict[str, dict] = {}
        carpeta = tempfile.mkdtemp(prefix="pds")
        if len(carpeta) > 80:  # los sockets Unix admiten rutas cortas
            carpeta = tempfile.mkdtemp(prefix="pds", dir="/tmp")
        self.socket = os.path.join(carpeta, "s.sock")
        simulado = self

        class Atender(socketserver.StreamRequestHandler):
            def handle(self):
                linea = self.rfile.readline(70000)
                peticion = json.loads(linea)
                simulado.peticiones.append(peticion)
                self.wfile.write(json.dumps(simulado.responder(peticion)).encode() + b"\n")

        self.servidor = socketserver.ThreadingUnixStreamServer(self.socket, Atender)
        self.hilo = threading.Thread(target=self.servidor.serve_forever, args=(0.05,), daemon=True)
        self.hilo.start()

    def responder(self, peticion: dict) -> dict:
        orden = peticion["orden"]
        if orden in ("paquete", "avanzado-archivo", "archivos-subir"):
            # El de verdad mueve lo subido a su carpeta; aquí se comprueba que llegó y se borra.
            args = peticion["args"]
            for clave in ("subida", "respaldo"):
                if args.get(clave):
                    ruta = os.path.join(self.dir_subidas, args[clave])
                    if not os.path.isfile(ruta):
                        return {"ok": False, "codigo": 400, "error": f"no está {clave}"}
                    with open(ruta, "rb") as f:
                        args[clave + "_contenido"] = f.read().decode(errors="replace")
                    os.remove(ruta)
        if orden in self.respuestas:
            return self.respuestas[orden]
        if orden == "listar":
            return {"ok": True, "datos": {"sitios": [
                {"dominio": "uno.example", "app": "wordpress", "ssl": True, "ftp": False, "php": "8.2", "ocupado_mb": 40},
                {"dominio": "blog.uno.example", "app": None, "ssl": False, "ftp": False, "php": "8.2", "ocupado_mb": 1},
            ], "dominios": [{"dominio": "uno.example", "cuota": {"max_sitios": 2, "disco_mb": 2048, "bases_mb": 1024},
                             "uso": {"sitios": 2, "disco_mb": 41, "bases_mb": 3}}], "dns": True}}
        if orden == "revisar":
            return {"ok": True, "datos": {"app": "wordpress", "version": "6.6.2",
                                          "actualizaciones": {"nucleo": [], "complementos": ["akismet"], "temas": []}}}
        return {"ok": True, "datos": {"hecho": orden}}

    def ordenes(self) -> list[str]:
        return [p["orden"] for p in self.peticiones]

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


class BaseSimulada:
    """Lo justo de asyncpg para auditoría y solicitudes."""

    def __init__(self):
        self.auditoria: list[tuple] = []
        self.solicitudes: list[dict] = []
        self.consultas: list[str] = []

    async def execute(self, consulta, *args):
        self.consultas.append(consulta)
        if "pd_auditoria" in consulta:
            self.auditoria.append(args)

    async def fetch(self, consulta, *args):
        self.consultas.append(consulta)
        if "pd_solicitudes" in consulta:
            return [s for s in self.solicitudes if s["estado"] == "pendiente" and s["dominio"] in args[0]]
        return []

    async def fetchval(self, consulta, *args):
        self.consultas.append(consulta)
        if consulta.lstrip().startswith("SELECT 1 FROM pd_solicitudes"):
            return 1 if any(s["objetivo"] == args[0] and s["estado"] == "pendiente" for s in self.solicitudes) else None
        if "INSERT INTO pd_solicitudes" in consulta:
            self.solicitudes.append({"id": len(self.solicitudes) + 1, "admin_id": args[0], "tipo": "baja_sitio",
                                     "objetivo": args[2], "dominio": args[3], "motivo": args[4], "estado": "pendiente",
                                     "creado_en": "2026-10-21T10:00:00+00:00"})
            return len(self.solicitudes)
        return None
