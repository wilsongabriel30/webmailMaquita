"""Herramientas comunes de las recetas del catálogo: así cada aplicación es un archivo corto que solo dice de
dónde se descarga, cómo se verifica, qué carpeta sirve la web, qué no debe servirse y cómo se instala.

Verificación de los paquetes (en orden de preferencia, ver descargas.py):
- «suma oficial»: SHA-256 (o MD5) que publica el propio proyecto junto al paquete;
- «GitHub»: SHA-256 que GitHub calcula del archivo que el proyecto adjunta a su versión;
- «HTTPS»: el proyecto no publica suma; se descarga solo por HTTPS de su origen oficial y se anota la suma
  del archivo instalado (queda en los datos del sitio y en «Seguridad»).
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from comun import ErrorSitio, ejecutar

from . import descargas


@dataclass
class Fuente:
    version: str
    url: str
    suma: str | None = None
    algoritmo: str = "sha256"
    verificacion: str = "GitHub"


def url(meta):
    return ("https://" if meta.get("ssl") else "http://") + meta["dominio"]


def github(repo, patron):
    """Archivo adjunto a la última versión estable de GitHub, con la SHA-256 que calcula GitHub."""
    version, enlace, sha = descargas.github_ultima(repo, patron)
    return Fuente(version, enlace, sha, "sha256", "GitHub")


def github_etiqueta(repo, plantilla_url, patron_etiqueta=r"v?(\d+(?:\.\d+)+)"):
    """Proyectos que no adjuntan paquete: versión de la última etiqueta estable y su archivo oficial por HTTPS
    (sin suma publicada). `plantilla_url` lleva {version} y {etiqueta}."""
    import json

    datos = json.loads(descargas.texto(f"https://api.github.com/repos/{repo}/releases/latest"))
    etiqueta = datos.get("tag_name", "")
    m = re.fullmatch(patron_etiqueta, etiqueta)
    if datos.get("prerelease") or not m:
        raise ErrorSitio(f"la última versión publicada de {repo} no es estable")
    return Fuente(m.group(1), plantilla_url.format(version=m.group(1), etiqueta=etiqueta), None, "sha256", "HTTPS")


def suma_publicada(enlace_suma, nombre_archivo=None, algoritmo="sha256"):
    """Lee una suma de un archivo .sha256/.md5 o de una lista «suma  archivo»."""
    longitud = {"sha256": 64, "sha512": 128, "md5": 32}[algoritmo]
    texto = descargas.texto(enlace_suma, tope=256 * 1024)
    for linea in texto.splitlines():
        m = re.search(r"\b([0-9a-fA-F]{%d})\b" % longitud, linea)
        if m and (not nombre_archivo or nombre_archivo in linea or len(texto.splitlines()) == 1):
            return m.group(1).lower()
    raise ErrorSitio("el proyecto no publica la suma de ese paquete")


def preparar(meta, fuente, nombre, subcarpeta=None):
    """Descarga, verifica y deja el contenido del paquete en la carpeta pública del sitio.

    Si el paquete trae todo dentro de una carpeta, se quita; `subcarpeta` elige una carpeta concreta del
    paquete (p. ej. «upload» en OpenCart). Devuelve la suma del archivo instalado."""
    with tempfile.TemporaryDirectory(dir=meta["tmp"]) as tmp:
        extension = ".zip" if fuente.url.split("?")[0].endswith(".zip") else ".tar"
        paquete = os.path.join(tmp, "paquete" + extension)
        descargas.descargar(fuente.url, paquete)
        if fuente.suma:
            descargas.comprobar(paquete, fuente.suma, fuente.algoritmo, nombre)
        suma = descargas.suma(paquete, "sha256")
        extraido = os.path.join(tmp, "extraido")
        descargas.extraer(paquete, extraido)
        origen = os.path.join(extraido, subcarpeta) if subcarpeta else extraido
        if not os.path.isdir(origen):
            raise ErrorSitio(f"el paquete de {nombre} no tiene la estructura esperada")
        for n in os.listdir(origen):
            shutil.move(os.path.join(origen, n), os.path.join(meta["publico"], n))
    permisos(meta)
    meta["app_version"] = fuente.version
    meta["app_verificacion"] = fuente.verificacion
    meta["app_suma"] = suma
    return suma


def permisos(meta):
    """Todo del usuario del sitio (PHP corre con él); nginx (www-data) solo lee."""
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    ejecutar(["chmod", "-R", "u+rwX,g+rX,g-w,o-rwx", meta["publico"]])


def privada(meta, nombre):
    """Carpeta de datos fuera de la web (en la carpeta privada del sitio)."""
    ruta = os.path.join(meta["tmp"], nombre)
    os.makedirs(ruta, exist_ok=True)
    # Se anota para borrarla si la instalación falla (aplicaciones._deshacer_instalacion).
    if nombre not in meta.setdefault("privadas", []):
        meta["privadas"].append(nombre)
    ejecutar(["chown", "-R", f"{meta['usuario']}:{meta['usuario']}", ruta])
    os.chmod(ruta, 0o700)
    return ruta


def php(meta, *args, cwd=None, tiempo=900, entrada=None):
    """PHP de la línea de órdenes con el usuario del sitio (desde su carpeta pública por defecto)."""
    return ejecutar(["php", "-d", "memory_limit=512M", *args], como=meta["usuario"], cwd=cwd or meta["publico"],
                    tiempo=tiempo, entrada=entrada)


def sql(meta, consulta, base=None):
    ejecutar(["mariadb", "--protocol=socket", "-u", "root", base or meta["bd"], "-e", consulta])


def hash_clave(clave, algoritmo="PASSWORD_BCRYPT"):
    r = subprocess.run(["php", "-r", f"echo password_hash(stream_get_contents(STDIN), {algoritmo});"],
                       input=clave, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.startswith("$"):
        raise ErrorSitio("no se pudo calcular la contraseña")
    return r.stdout


def literal(texto):
    """Literal de SQL (las claves y nombres que genera el panel no llevan comillas; por si acaso)."""
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "''") + "'"


def escribir(meta, ruta_relativa, contenido, modo=0o640):
    ruta = os.path.join(meta["publico"], ruta_relativa)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w") as f:
        f.write(contenido)
    os.chmod(ruta, modo)
    ejecutar(["chown", f"{meta['usuario']}:www-data", ruta])
    return ruta


def quitar(meta, *rutas_relativas):
    for r in rutas_relativas:
        ruta = os.path.join(meta["publico"], r)
        if os.path.isdir(ruta) and not os.path.islink(ruta):
            shutil.rmtree(ruta)
        elif os.path.lexists(ruta):
            os.remove(ruta)


class Web:
    """Recorre el instalador web de una aplicación desde el propio servidor, como lo haría una persona."""

    def __init__(self, meta):
        import sitio

        sitio.escribir_vhost(meta)  # el vhost ya debe servir la aplicación con sus reglas
        sitio.recargar_nginx()
        self.meta = meta
        self.base = url(meta)
        self._cookies = tempfile.NamedTemporaryFile(dir=meta["tmp"], prefix=".instalacion-", delete=False).name

    def pedir(self, ruta, datos=None, archivo_datos=None, tiempo=600, cabeceras=None):
        """(código, texto, redirección). `datos`: formulario (dict o lista de pares)."""
        puerto = "443" if self.base.startswith("https") else "80"
        orden = ["curl", "-s", "-k", "--max-time", str(tiempo), "--resolve", f"{self.meta['dominio']}:{puerto}:127.0.0.1",
                 "-b", self._cookies, "-c", self._cookies, "-w", "\n%{http_code} %{redirect_url}"]
        for c in cabeceras or []:
            orden += ["-H", c]
        pares = datos.items() if isinstance(datos, dict) else (datos or [])
        for clave, valor in pares:
            orden += ["--data-urlencode", f"{clave}={valor}"]
        if archivo_datos is not None:
            orden += ["--data-binary", "@-"]
        r = subprocess.run(orden + [self.base + ruta], input=archivo_datos, capture_output=True, text=True,
                           timeout=tiempo + 30)
        cuerpo, _, final = r.stdout.rpartition("\n")
        codigo, _, destino = final.partition(" ")
        return codigo, cuerpo, destino

    @staticmethod
    def campo(html, nombre):
        """Valor de un campo oculto (fichas CSRF y similares)."""
        for patron in (r'name=["\']%s["\'][^>]*value=["\']([^"\']*)' % re.escape(nombre),
                       r'value=["\']([^"\']*)["\'][^>]*name=["\']%s["\']' % re.escape(nombre)):
            m = re.search(patron, html)
            if m:
                return m.group(1)
        raise ErrorSitio(f"el instalador no mostró el campo «{nombre}»")

    def cerrar(self):
        if os.path.exists(self._cookies):
            os.remove(self._cookies)
