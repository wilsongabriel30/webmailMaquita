"""Decodificador de adjuntos para el índice de texto completo de Dovecot (fts_decoder_driver = script).

Contrato de Dovecot (el mismo que su decode2text.sh de ejemplo):
  - sin argumentos: imprime los formatos que entiende, «Content-Type extensión…» por línea;
  - con el Content-Type como primer argumento: lee el adjunto de la entrada estándar y escribe su
    texto en UTF-8 en la salida estándar.

Lo lanza /usr/local/lib/maquita-fts/decode2text.sh (usuario sin privilegios «maquita-fts», con tiempo,
memoria y tamaño de archivo limitados). Siempre termina con 0: un adjunto que no se puede leer se
queda sin texto, pero el correo se indexa igual.
"""

import os
import sys
import tempfile

# Con «python3 -I» la carpeta del programa no entra en sys.path: se añade a mano (es de root, 0755).
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import limites  # noqa: E402
import tipos  # noqa: E402
from nucleo import Decodificador  # noqa: E402


def decodificar_bytes(datos: bytes, declarado: str, lim: limites.Limites, tmp: str) -> tuple[str, list[str]]:
    presupuesto = limites.Presupuesto(lim)
    try:
        Decodificador(lim, presupuesto, tmp).decodificar(datos, declarado)
    except limites.LimiteSuperado as exc:
        presupuesto.avisos.append(str(exc))
    return "".join(presupuesto.texto), presupuesto.avisos


def main(argv: list[str]) -> int:
    lim = limites.cargar()
    limites.aplicar_rlimits(lim)
    if len(argv) < 2 or not argv[1]:
        sys.stdout.write(tipos.lista_para_dovecot())
        return 0
    datos = sys.stdin.buffer.read(lim.max_entrada + 1)
    if len(datos) > lim.max_entrada:
        print(f"adjunto de más de {lim.max_entrada // limites.MB} MB: no se indexa su texto", file=sys.stderr)
        return 0
    with tempfile.TemporaryDirectory(prefix="fts-") as tmp:
        texto, avisos = decodificar_bytes(datos, argv[1], lim, tmp)
    sys.stdout.buffer.write(texto.encode("utf-8", errors="replace"))
    if avisos:
        print("; ".join(avisos[:5])[:500], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
