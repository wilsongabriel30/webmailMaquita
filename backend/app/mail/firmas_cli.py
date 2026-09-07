"""Normalización de una firma desde otro proceso (el panel de administración).

El panel corre con su propio entorno y no importa el código del correo; le manda la firma por la
entrada estándar y recibe el resultado por la salida, ambos en JSON:

    echo '{"html": "<table>…</table>", "correo": "persona@dominio"}' \\
      | /opt/maquita-webmail/backend/venv/bin/python -m app.mail.firmas_cli
    → {"html": "…", "avisos": ["…"], "imagenes": 2}

No necesita el `.env` del correo: solo FIRMAS_DIR si el directorio no es el de siempre.
"""

import json
import sys

from app.mail.firmas import normalizar_firma


def main() -> int:
    entrada = json.load(sys.stdin)
    resultado = normalizar_firma(
        entrada.get("html") or "", correo_usuario=entrada.get("correo")
    )
    json.dump(
        {
            "html": resultado.html,
            "avisos": resultado.avisos,
            "imagenes": resultado.imagenes,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
