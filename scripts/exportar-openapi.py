#!/usr/bin/env python3
"""Exporta la especificación OpenAPI del webmail y del panel a docs/api/.

Uso (desde la raíz del repositorio, con el entorno de Python del backend):

    python3 scripts/exportar-openapi.py            # webmail y panel
    python3 scripts/exportar-openapi.py webmail    # solo uno
    python3 scripts/exportar-openapi.py --comprobar   # falla si docs/api/ está desactualizado
    python3 scripts/exportar-openapi.py webmail --v1  # además, la copia bajo /api/v1

Genera:
- docs/api/webmail-openapi.json     rutas de siempre (/api/...)
- docs/api/panel-openapi.json       panel de administración
- docs/api/webmail-openapi-v1.json  (solo con --v1; no se versiona) las mismas rutas bajo
                                     /api/v1/..., el alias estable, para generar clientes
                                     con openapi-generator u otra herramienta

No hace falta base de datos ni Redis: se importa la aplicación y se pide su esquema.
Las variables obligatorias que falten se rellenan con valores de relleno SOLO dentro de
este proceso (nunca se escriben a disco ni sirven para arrancar nada).
"""

import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "docs", "api")

SERVICIOS = {
    "webmail": os.path.join(RAIZ, "backend"),
    "panel": os.path.join(RAIZ, "admin-panel", "backend"),
}

# Relleno para poder IMPORTAR la aplicación (las comprobaciones de arranque exigen que
# existan). No son secretos de nada: el proceso no conecta con ningún servicio.
_RELLENO = {
    "SECRET_KEY": "relleno-solo-para-exportar-openapi",
    "ADMIN_JWT_SECRET": "relleno-solo-para-exportar-openapi",
    "MASTER_PASSWORD": "relleno-solo-para-exportar-openapi",
    "JWT_SECRET": "relleno-solo-para-exportar-openapi",
    "DB_PASS": "relleno-solo-para-exportar-openapi",
    "DATABASE_URL": "postgresql://relleno:relleno@127.0.0.1:1/relleno",
    "SECURITY_LOG_PATH": os.devnull,
}


def _esquema_en_este_proceso(servicio: str) -> dict:
    os.chdir(SERVICIOS[servicio])
    sys.path.insert(0, SERVICIOS[servicio])
    for k, v in _RELLENO.items():
        os.environ.setdefault(k, v)
    if "CREDENTIAL_ENCRYPTION_KEY" not in os.environ:
        from cryptography.fernet import Fernet

        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    from app.main import app  # noqa: E402

    return app.openapi()


def a_v1(esquema: dict) -> dict:
    """Copia del esquema con las rutas /api/... publicadas como /api/v1/..."""
    v1 = json.loads(json.dumps(esquema))
    v1["paths"] = {
        ("/api/v1" + r[len("/api"):] if r.startswith("/api/") else r): op
        for r, op in esquema.get("paths", {}).items()
    }
    info = v1.setdefault("info", {})
    info["title"] = f"{info.get('title', 'API')} v1"
    info["description"] = (
        "Alias estable /api/v1 de la API del webmail. Misma API que /api/...; "
        "ver docs/SOPORTE-Y-VERSIONES.md."
    )
    return v1


def _escribir(nombre: str, esquema: dict) -> str:
    os.makedirs(DESTINO, exist_ok=True)
    ruta = os.path.join(DESTINO, nombre)
    texto = json.dumps(esquema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


def _texto(esquema: dict) -> str:
    return json.dumps(esquema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _salidas(servicio: str, esquema: dict, con_v1: bool = False) -> dict:
    salidas = {f"{servicio}-openapi.json": esquema}
    if servicio == "webmail" and con_v1:
        salidas["webmail-openapi-v1.json"] = a_v1(esquema)
    return salidas


def main(argv: list[str]) -> int:
    # Modo interno: un proceso por servicio (los dos se llaman «app» y no conviven).
    if len(argv) == 3 and argv[1] == "--interno":
        json.dump(_esquema_en_este_proceso(argv[2]), sys.stdout)
        return 0
    comprobar = "--comprobar" in argv
    pedidos = [a for a in argv[1:] if not a.startswith("--")] or list(SERVICIOS)
    desfasados = []
    for servicio in pedidos:
        if servicio not in SERVICIOS:
            print(f"Servicio desconocido: {servicio} (válidos: {', '.join(SERVICIOS)})")
            return 2
        r = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--interno", servicio],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(f"No se pudo generar el esquema de {servicio}:\n{r.stderr[-2000:]}")
            return 1
        esquema = json.loads(r.stdout)
        for nombre, contenido in _salidas(servicio, esquema, "--v1" in argv).items():
            ruta = os.path.join(DESTINO, nombre)
            if comprobar:
                actual = open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""
                if actual != _texto(contenido):
                    desfasados.append(nombre)
                continue
            _escribir(nombre, contenido)
            print(f"{ruta}: {len(contenido.get('paths', {}))} rutas")
    if desfasados:
        print("Desactualizado (ejecuta scripts/exportar-openapi.py): " + ", ".join(desfasados))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
