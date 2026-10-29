"""Abrir .rar y .7z con 7-Zip (paquete «7zip» de Debian) desde el administrador de archivos y «Subir y migrar».

Mismas reglas que los .zip y .tar.gz de archivos_zip.py: primero se lista el archivo (7z l -slt) y se rechaza entero si trae
rutas absolutas o con «..», enlaces simbólicos o duros, dispositivos o contraseña; quien llama aplica los topes de elementos y
de bytes declarados. Se extrae a una carpeta temporal oculta junto al destino, con los enlaces desactivados (-snl-), y cada
archivo se entrega como un flujo de lectura: así archivos_zip._extraer lo escribe sin seguir enlaces y contando los bytes
reales (un archivo que se infla más de lo que declara se descarta). Como 7z escribe en disco antes de que se cuenten esos
bytes, el proceso corre con RLIMIT_FSIZE al tope de bytes: ningún archivo puede pasar de ahí aunque mienta en lo que
declara. Sin shell: 7z recibe los argumentos como lista.

.rar: el paquete «7zip» de Debian 13 lista el formato pero no trae el códec (es propietario; viene en «7zip-rar», sección
non-free). Si el códec no está cargado, se dice claramente que este servidor no tiene soporte para .rar.
"""

import contextlib
import os
import resource
import shutil
import signal
import stat
import subprocess
import tempfile

from comun import ErrorSitio

EXTENSIONES = (".rar", ".7z")
EJECUTABLE = shutil.which("7z") or shutil.which("7zz") or shutil.which("7za")
TIEMPO_LISTAR = 120
TIEMPO_EXTRAER = 900
SIN_RAR = "este servidor no tiene soporte para .rar (falta el paquete 7zip-rar): envíe el sitio en .zip o .7z"
_rar = None  # None: aún no se miró; True/False: si 7z tiene cargado el códec de RAR


def disponible():
    return bool(EJECUTABLE)


def es_7z(nombre):
    return str(nombre).lower().endswith(EXTENSIONES)


def es_rar(nombre):
    return str(nombre).lower().endswith(".rar")


def soporta_rar():
    """Si 7z tiene el códec de RAR: aparece en la sección «Codecs» de `7z i` (la de «Formats» lo lista aunque falte)."""
    global _rar
    if _rar is None:
        _rar = _hay_codec_rar(_correr(["i"], TIEMPO_LISTAR).stdout)
    return _rar


def _hay_codec_rar(informe):
    """Lee la salida de `7z i`: el códec aparece en «Codecs» (Rar1…Rar5) y la biblioteca en «Libs» (…/Codecs/Rar.so)."""
    seccion = ""
    for linea in informe.splitlines():
        if not linea.strip():
            seccion = ""
        elif linea[0] != " " and linea.endswith(":"):
            seccion = linea[:-1]
        elif seccion == "Codecs" and linea.split()[-1].startswith("Rar"):
            return True
        elif seccion == "Libs" and os.path.basename(linea.split()[-1]).startswith("Rar"):
            return True
    return False


def _comprobar_formato(ruta):
    if es_rar(ruta) and not soporta_rar():
        raise ErrorSitio(SIN_RAR)


def _limitar_tamano(tope_bytes):
    """Para preexec_fn: ningún archivo que escriba 7z puede pasar del tope (el proceso muere con SIGXFSZ)."""
    def preparar():
        resource.setrlimit(resource.RLIMIT_FSIZE, (tope_bytes, tope_bytes))
    return preparar


def _correr(argumentos, tiempo, preparar=None):
    if not EJECUTABLE:
        raise ErrorSitio("este servidor no puede abrir .rar ni .7z (falta 7-Zip)")
    try:
        return subprocess.run([EJECUTABLE] + argumentos, capture_output=True, text=True, timeout=tiempo, stdin=subprocess.DEVNULL,
                              preexec_fn=preparar)
    except subprocess.TimeoutExpired:
        raise ErrorSitio("el archivo comprimido tarda demasiado en abrirse")


def listar(ruta):
    """[(nombre, es_carpeta, tamaño declarado)] tal como vienen en el archivo. Rechaza enlaces, especiales y cifrados."""
    _comprobar_formato(ruta)
    r = _correr(["l", "-slt", "-ba", "-p", "--", ruta], TIEMPO_LISTAR)  # -p con clave vacía: si pide clave, falla en vez de esperar
    if r.returncode != 0:
        raise ErrorSitio("no se pudo leer el archivo comprimido (¿está dañado o tiene contraseña?)")
    miembros, actual = [], {}
    for linea in r.stdout.splitlines() + [""]:
        if linea.strip():
            clave, _, valor = linea.partition(" = ")
            actual[clave.strip()] = valor.strip()
            continue
        if actual.get("Path"):
            miembros.append(_miembro(actual))
        actual = {}
    return miembros


def _miembro(datos):
    nombre = datos["Path"]
    if datos.get("Encrypted", "-") not in ("-", ""):
        raise ErrorSitio("el archivo comprimido tiene contraseña: quítesela y vuelva a subirlo")
    if datos.get("Symbolic Link") or datos.get("Hard Link"):
        raise ErrorSitio(f"el archivo trae un enlace o un archivo especial: {nombre[:100]}")
    atributos = datos.get("Attributes", "")
    modo = atributos.split(" ")[-1] if " " in atributos else ""
    es_carpeta = atributos.startswith("D") or modo.startswith("d")
    if modo and modo[0] not in ("-", "d"):
        raise ErrorSitio(f"el archivo trae un enlace o un archivo especial: {nombre[:100]}")
    try:
        tamano = int(datos.get("Size") or 0)
    except ValueError:
        tamano = 0
    return nombre, es_carpeta, tamano


@contextlib.contextmanager
def extraido(ruta, junto_a, tope_bytes):
    """Extrae a una carpeta temporal oculta dentro de `junto_a` y devuelve abrir(nombre) → archivo abierto solo lectura.

    7z corre con RLIMIT_FSIZE = `tope_bytes`: si un archivo se infla por encima, el proceso muere y no se escribe nada en el
    destino. Solo se abren archivos regulares (nada de enlaces ni dispositivos, aunque 7z los hubiera creado). Al salir se
    borra todo.
    """
    _comprobar_formato(ruta)
    tmp = tempfile.mkdtemp(prefix=".descomprimiendo-", dir=junto_a)
    try:
        r = _correr(["x", "-y", "-snl-", "-p", "-bso0", "-bse0", "-o" + tmp, "--", ruta], TIEMPO_EXTRAER, _limitar_tamano(tope_bytes))
        if r.returncode == -signal.SIGXFSZ:
            raise ErrorSitio("el paquete se infla más de lo que declara (posible bomba de descompresión)")
        if r.returncode != 0:
            raise ErrorSitio("el archivo comprimido está dañado o no se pudo descomprimir")

        def abrir(nombre):
            destino = os.path.join(tmp, *nombre.split("/"))
            info = os.lstat(destino)
            if not stat.S_ISREG(info.st_mode):
                raise ErrorSitio(f"el archivo trae un enlace o un archivo especial: {nombre[:100]}")
            return open(os.open(destino, os.O_RDONLY | os.O_NOFOLLOW), "rb")

        yield abrir
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def medir(ruta):
    """(bytes declarados, número de elementos) sin descomprimir, para las cuotas."""
    miembros = listar(ruta)
    return sum(t for _, _, t in miembros), len(miembros)


def extraer_a(ruta, destino, seguro, tope_bytes, tope_elementos):
    """Para «Subir y migrar»: extrae todo en `destino` (carpeta vacía) tras validar nombres con `seguro(nombre)`.

    Se copian solo archivos regulares y carpetas; lo que no sea eso se ignora. Devuelve los nombres de los miembros.
    """
    miembros = listar(ruta)
    if len(miembros) > tope_elementos:
        raise ErrorSitio(f"el paquete tiene más de {tope_elementos} elementos")
    if sum(t for _, _, t in miembros) > tope_bytes:
        raise ErrorSitio("el paquete descomprimido ocuparía demasiado")
    nombres = [n for n, _, _ in miembros]
    if not all(seguro(n) for n in nombres):
        raise ErrorSitio("paquete con rutas no válidas")
    os.makedirs(destino, exist_ok=True)
    total = 0
    with extraido(ruta, destino, tope_bytes) as abrir:
        for nombre, es_carpeta, _ in miembros:
            final = os.path.join(destino, *nombre.split("/"))
            if es_carpeta:
                os.makedirs(final, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(final), exist_ok=True)
            with abrir(nombre) as fuente, open(os.open(final, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o640), "wb") as f:
                while bloque := fuente.read(1 << 20):
                    total += len(bloque)
                    if total > tope_bytes:
                        raise ErrorSitio("el paquete se infla más de lo que declara (posible bomba de descompresión)")
                    f.write(bloque)
    return nombres
