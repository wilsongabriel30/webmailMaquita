#!/usr/bin/env python3
"""Barrido de DATOS PROPIOS de la organización en lo que va al repositorio.

Uso:
  barrido-datos-propios.py --staged          (hook pre-commit: líneas que se van a confirmar)
  barrido-datos-propios.py --diff BASE       (CI: líneas añadidas respecto de BASE)
  barrido-datos-propios.py --arbol [RAIZ]    (todo el árbol)

  --excluir PREFIJO   deja fuera una carpeta (se puede repetir). Para lo que se publica
                      desde otro repositorio y hay que limpiar en su origen.
  --solo PREFIJO      revisa solo esa carpeta (se puede repetir).

Sale con 1 si encuentra algo, 0 si no.

POR QUÉ EXISTE
El repositorio es público. El barrido de secretos busca claves; el de datos personales, personas.
Ninguno busca lo que identifica a la organización que lo instala: sus dominios, las direcciones
de su red, sus correos. Así se fueron acumulando en el código, los ejemplos y la documentación.
Este barrido busca eso.

DÓNDE VIVEN LOS PATRONES
No aquí: este fichero se publica, y si nombrara lo que busca lo estaría publicando. Se leen de

  1. la variable GUARDIAN_DATOS_PROPIOS (en el CI, un secreto del repositorio), o
  2. el fichero .git/guardian-datos-propios (en cada copia de trabajo; lo crea instalar.sh).

Una línea por patrón, con su categoría delante:

  dominio: ejemplo-real\\.org
  red: 198\\.18\\.[0-9]+\\.[0-9]+
  correo: persona\\.real@

Las líneas vacías y las que empiezan por # se ignoran. Los patrones son expresiones regulares y
no distinguen mayúsculas.

LO QUE SÍ BUSCA SIN NECESIDAD DE PATRONES
Direcciones IPv4 públicas escritas en el código. Una dirección de verdad casi nunca es un buen
ejemplo: para eso están los rangos de documentación (192.0.2.x, 198.51.100.x, 203.0.113.x) y los
privados. Se dejan pasar los resolutores públicos conocidos. Si una dirección pública tiene que
estar, la línea lo declara con el comentario «guardian: ip-publica».

QUÉ NO SE IMPRIME
El texto encontrado. Se dice fichero, línea y categoría; el registro del CI es público.
"""
import ipaddress
import os
import re
import subprocess
import sys

EXCLUIR_DIRS = ("node_modules", "venv", ".venv", ".git", "dist", "build", "__pycache__", "vendor")
EXCLUIR_SUFIJOS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".pdf", ".zip",
                   ".gz", ".tar", ".pyc", ".lock", ".svg", ".min.js", ".min.css", ".map", ".apk", ".webp")
EXCLUIR_FICHEROS = ("package-lock.json",)
PERMISO_IP = "guardian: ip-publica"

RE_IPV4 = re.compile(r"(?<![\w.\-/])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?![\w\-]|\.\d)")
REDES_DE_EJEMPLO = [ipaddress.ip_network(r) for r in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
    "192.0.0.0/24", "192.0.2.0/24", "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24",
    "203.0.113.0/24", "224.0.0.0/3")]
RESOLUTORES_PUBLICOS = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112",
                        "208.67.222.222", "208.67.220.220"}
# Números de versión y similares que tienen forma de dirección.
RE_PARECE_VERSION = re.compile(r"(versi[oó]n|version|\bv\d|chrome/|firefox/|safari/|edg/|==|>=|<=|~=|\^)", re.I)


def cargar_patrones(raiz: str) -> list[tuple[str, re.Pattern]]:
    texto = os.environ.get("GUARDIAN_DATOS_PROPIOS", "")
    if not texto.strip():
        try:
            comun = subprocess.run(["git", "-C", raiz, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                   capture_output=True, text=True).stdout.strip()
            with open(os.path.join(comun, "guardian-datos-propios"), encoding="utf-8") as f:
                texto = f.read()
        except OSError:
            texto = ""
    patrones = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        categoria, _, expresion = linea.partition(":")
        if not expresion.strip():
            categoria, expresion = "dato propio", linea
        try:
            patrones.append((categoria.strip(), re.compile(expresion.strip(), re.I)))
        except re.error:
            print(f"  aviso: un patrón de «{categoria.strip()}» no es una expresión regular válida; se ignora")
    return patrones


def ip_publica(texto: str) -> bool:
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return False
    return texto not in RESOLUTORES_PUBLICOS and not any(ip in red for red in REDES_DE_EJEMPLO)


def revisar_linea(linea: str, patrones) -> list[str]:
    motivos = [categoria for categoria, p in patrones if p.search(linea)]
    if PERMISO_IP not in linea and not RE_PARECE_VERSION.search(linea):
        if any(ip_publica(m.group(1)) for m in RE_IPV4.finditer(linea)):
            motivos.append("dirección IP pública (usa un rango de documentación: 192.0.2.x)")
    return sorted(set(motivos))


def se_revisa(ruta: str) -> bool:
    partes = ruta.replace("\\", "/").split("/")
    if any(p in EXCLUIR_DIRS for p in partes) or partes[-1] in EXCLUIR_FICHEROS:
        return False
    return not ruta.lower().endswith(EXCLUIR_SUFIJOS)


def lineas_anadidas(orden: list[str], raiz: str):
    """(fichero, número de línea, texto) de cada línea añadida en un diff sin contexto."""
    salida = subprocess.run(orden, cwd=raiz, capture_output=True, text=True, errors="replace").stdout
    fichero, numero = None, 0
    for linea in salida.splitlines():
        if linea.startswith("+++ "):
            fichero = linea[6:] if linea.startswith("+++ b/") else None
        elif linea.startswith("@@"):
            m = re.search(r"\+(\d+)", linea)
            numero = int(m.group(1)) if m else 0
        elif linea.startswith("+") and fichero:
            yield fichero, numero, linea[1:]
            numero += 1


def lineas_del_arbol(raiz: str):
    ficheros = subprocess.run(["git", "ls-files"], cwd=raiz, capture_output=True, text=True).stdout.splitlines()
    for fichero in ficheros:
        if not se_revisa(fichero):
            continue
        try:
            with open(os.path.join(raiz, fichero), encoding="utf-8") as f:
                for numero, linea in enumerate(f, 1):
                    yield fichero, numero, linea
        except (OSError, UnicodeDecodeError):
            continue


def _opcion(argv: list[str], nombre: str) -> list[str]:
    """Saca de argv todas las apariciones de «nombre VALOR» y devuelve los valores."""
    valores = []
    while nombre in argv:
        i = argv.index(nombre)
        if i + 1 >= len(argv):
            raise SystemExit(f"Falta el valor de {nombre}")
        valores.append(argv[i + 1])
        del argv[i:i + 2]
    return valores


def main(argv: list[str]) -> int:
    argv = list(argv)
    excluir, solo = tuple(_opcion(argv, "--excluir")), tuple(_opcion(argv, "--solo"))
    if not argv or argv[0] not in ("--staged", "--diff", "--arbol"):
        print(__doc__)
        return 2
    raiz = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
    if argv[0] == "--staged":
        origen = lineas_anadidas(["git", "diff", "--cached", "-U0", "--no-color"], raiz)
    elif argv[0] == "--diff":
        if len(argv) < 2:
            print("Falta la base: --diff BASE")
            return 2
        origen = lineas_anadidas(["git", "diff", "-U0", "--no-color", argv[1] + "...HEAD"], raiz)
    else:
        raiz = argv[1] if len(argv) > 1 else raiz
        origen = lineas_del_arbol(raiz)

    patrones = cargar_patrones(raiz)
    if not patrones:
        print("  aviso: no hay patrones de datos propios (ni GUARDIAN_DATOS_PROPIOS ni .git/guardian-datos-propios): "
              "solo se comprueban direcciones IP públicas. Ejecuta deploy/hooks/instalar.sh y rellena el fichero.")

    hallazgos, por_fichero = [], {}
    for fichero, numero, linea in origen:
        if not se_revisa(fichero) or fichero.startswith(excluir) or (solo and not fichero.startswith(solo)):
            continue
        for motivo in revisar_linea(linea, patrones):
            hallazgos.append((fichero, numero, motivo))
            por_fichero[fichero] = por_fichero.get(fichero, 0) + 1

    if not hallazgos:
        print("  datos propios: nada encontrado")
        return 0
    print(f"\033[0;31m✗ DATOS PROPIOS de la organización: {len(hallazgos)} líneas en {len(por_fichero)} ficheros.\033[0m")
    if argv[0] == "--arbol":
        for fichero, cuantas in sorted(por_fichero.items(), key=lambda x: -x[1])[:40]:
            print(f"    {cuantas:4d}  {fichero}")
        if len(por_fichero) > 40:
            print(f"    … y {len(por_fichero) - 40} ficheros más")
    else:
        for fichero, numero, motivo in hallazgos[:60]:
            print(f"    {fichero}:{numero}  {motivo}")
    print("  Usa valores de ejemplo (example.org, 192.0.2.x, usuario@example.org) y deja el valor real en la "
          "configuración del servidor, fuera del repositorio.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
