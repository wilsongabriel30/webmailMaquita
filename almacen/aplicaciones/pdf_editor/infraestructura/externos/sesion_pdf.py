# -*- coding: utf-8 -*-
"""
El documento se queda en el servidor mientras se está editando.
================================================================
Hasta ahora, **cada clic mandaba el PDF entero y recibía el PDF entero**: en una
proforma de 130 páginas son 3 MB de subida y 3 MB de bajada por cada celda que
se guarda. Con mil personas trabajando a la vez, ese es el techo, y ya no es de
procesador sino de red.

Aquí el documento vive en el servidor mientras dura la edición y el navegador
solo manda **su identificador**. Y como el guardado es por añadido
(`guardado_pdf`), lo que hay que devolverle es únicamente **lo que se añadió**:
el navegador lo pega al final de su copia y ya tiene el documento nuevo. De 6 MB
por clic a unas decenas de kB.

Qué se guarda y por cuánto tiempo
---------------------------------
El archivo, y nada más: ni quién lo subió aparece en el nombre, ni queda rastro
en la base de datos. Vive en una carpeta que solo puede leer el usuario del
servicio, se borra **al cerrar el editor** y, si el navegador se cerró de golpe,
a las pocas horas (`VIDA`) lo barre el propio módulo.

Cada documento pertenece a un usuario, y su identificador va firmado con la
clave de la aplicación: nadie puede pedir el documento de otro cambiando un
número en la petición.

Autoría: Equipo de Tecnología Maquita — 2026-07-29
"""

import hashlib
import hmac
import logging
import os
import time
import uuid

from . import sesion_huellas

logger = logging.getLogger(__name__)

# EN MEMORIA, NUNCA EN DISCO. «no quiero nada de almacenamiento ocupado en el
# servidor» — el usuario, 29-jul-2026.  es memoria: lo que se escribe
# aquí no toca el disco y desaparece del todo al reiniciar la máquina. La
# carpeta lleva el identificador del usuario del sistema para que el
# mantenimiento hecho como root no deje al servicio sin sitio donde trabajar.
import tempfile

CARPETA = os.path.join('/dev/shm' if os.path.isdir('/dev/shm')
                       else tempfile.gettempdir(),
                       'faro-pdf-sesiones-%d' % os.getuid())

# Cuánto sobrevive un documento sin que nadie lo toque. Como ahora vive en
# memoria, se es tacaño: dos horas cubren de sobra una sesión de trabajo, y lo
# que pase de ahí es que el navegador se cerró y nadie va a volver. En cuanto se
# cierra el editor se borra, sin esperar a esto.
# (21-ago-2026: dos horas se quedaban cortas —quien deja la pestaña abierta
# mientras va a una reunión o almuerza volvía y el documento ya no estaba—;
# ahora dura una jornada. El tope de memoria de abajo sigue protegiendo.)
VIDA = 8 * 3600.0

# Tope de lo que puede ocupar todo esto. Son 4 GB de los 32 que tiene la memoria
# compartida de la máquina: da para unos 1.300 documentos de 3 MB a la vez, muy
# por encima de lo que se edita en paralelo. Si se pasara, se sueltan los más
# antiguos —quien vuelva solo tiene que subir su archivo otra vez— antes que
# comerse la memoria del servidor.
TOPE_TOTAL = 4 * 1024 * 1024 * 1024

# Y cuántos documentos puede tener abiertos UNA persona a la vez. Sin esto, quien
# abriera muchos documentos empujaba fuera los de los demás al llegar al tope
# general, y a los otros les tocaba volver a subir el suyo. Ocho cubre de sobra
# trabajar con varias pestañas. (Auditoría del 29-jul-2026.)
POR_USUARIO = 8

_ultimo_barrido = [0.0]


class SesionInvalida(Exception):
    """El identificador no vale, no es de este usuario o el documento ya no está."""


def _carpeta():
    try:
        os.makedirs(CARPETA, mode=0o700, exist_ok=True)
    except OSError:
        logger.exception('no se pudo preparar la carpeta de documentos en edición')
    return CARPETA


def _clave():
    """La clave con la que se firman los identificadores."""
    try:
        from flask import current_app
        secreto = current_app.config.get('SECRET_KEY')
        if secreto:
            return secreto if isinstance(secreto, bytes) else secreto.encode('utf-8')
    except Exception:
        pass
    # Sin aplicación alrededor (pruebas): una clave por arranque. Los
    # identificadores de una ejecución no valen en otra, que es lo correcto.
    global _CLAVE_SUELTA
    try:
        return _CLAVE_SUELTA
    except NameError:
        _CLAVE_SUELTA = os.urandom(32)
        return _CLAVE_SUELTA


def _firma(nombre, usuario):
    return hmac.new(_clave(), ('%s|%s' % (nombre, usuario)).encode('utf-8'),
                    hashlib.sha256).hexdigest()[:16]


def crear(contenido_pdf, usuario, huella=None):
    """Guarda el documento y devuelve su identificador."""
    return _guardar(usuario, lambda archivo: archivo.write(contenido_pdf), huella)


def crear_desde_flujo(flujo, usuario, tope, huella=None):
    """Igual, pero copiando del flujo de la petición trozo a trozo.

    Así el documento nunca está entero en la memoria del servidor: llega del
    navegador y se va escribiendo. En uno de 30 MB eso ahorra tenerlo dos veces
    en memoria y, sobre todo, el archivo temporal en DISCO que el formulario
    multiparte deja por el camino (todo lo demás vive en memoria compartida).

    Devuelve `(identificador, cuánto pesaba)`. Si se pasa del tope, no deja
    nada guardado y devuelve `(None, cuánto llevaba)`.
    """
    cuenta = [0]
    pasado = [False]

    def copiar(archivo):
        while True:
            trozo = flujo.read(256 * 1024)
            if not trozo:
                break
            cuenta[0] += len(trozo)
            if cuenta[0] > tope:
                pasado[0] = True
                return
            archivo.write(trozo)

    identificador = _guardar(usuario, copiar, huella, tirar=pasado)
    return (None if pasado[0] else identificador), cuenta[0]


def _guardar(usuario, escribir, huella=None, tirar=None):
    """Lo común: hacer sitio, escribir en un provisional y ponerle el nombre."""
    _barrer()
    _soltar_los_mios_si_paso(usuario)
    nombre = uuid.uuid4().hex
    ruta = os.path.join(_carpeta(), nombre + '.pdf')
    provisional = ruta + '.subiendo'
    with open(provisional, 'wb') as archivo:
        escribir(archivo)
    if tirar and tirar[0]:
        # No cabe: se deshace lo escrito sin dejar rastro ni ocupar memoria.
        try:
            os.unlink(provisional)
        except OSError:
            pass
        return None
    os.replace(provisional, ruta)
    os.chmod(ruta, 0o600)
    # De quién es, para poder contar cuántos tiene abiertos sin recorrer firmas.
    try:
        with open(os.path.join(_carpeta(), nombre + '.de'), 'w',
                  encoding='utf-8') as marca:
            marca.write(str(usuario))
    except OSError:
        pass
    # La huella, para reconocer este mismo documento si lo vuelven a abrir y no
    # tener que subirlo otra vez.
    sesion_huellas.anotar(_carpeta(), nombre, huella)
    return '%s.%s' % (nombre, _firma(nombre, usuario))


def buscar_por_huella(huella, tamano, usuario):
    """El identificador del documento que esta persona ya tiene subido, o None.

    Con esto el navegador se ahorra subir de nuevo un documento que ya está: al
    recargar la página, al abrirlo en otra pestaña o al volver a él más tarde.
    """
    def es_mio(nombre):
        marca = os.path.join(_carpeta(), nombre + '.de')
        try:
            with open(marca, encoding='utf-8') as ficha:
                return ficha.read().strip() == str(usuario)
        except OSError:
            return False

    nombre = sesion_huellas.buscar(_carpeta(), huella, tamano, es_mio)
    if not nombre:
        return None
    identificador = '%s.%s' % (nombre, _firma(nombre, usuario))
    try:
        ruta_de(identificador, usuario)      # lo toca para que no lo barran
    except SesionInvalida:
        return None
    return identificador


def ruta_de(identificador, usuario):
    """La ruta del documento, comprobando que es de quien dice serlo."""
    try:
        nombre, firma = (identificador or '').split('.', 1)
    except ValueError:
        raise SesionInvalida('El documento en edición no es válido.')
    # Solo letras y números: nada de subir por el árbol de carpetas.
    if not nombre.isalnum() or len(nombre) != 32:
        raise SesionInvalida('El documento en edición no es válido.')
    if not hmac.compare_digest(firma, _firma(nombre, usuario)):
        raise SesionInvalida('Ese documento no es tuyo.')
    ruta = os.path.join(_carpeta(), nombre + '.pdf')
    if not os.path.exists(ruta):
        raise SesionInvalida('El documento en edición ya no está en el servidor. '
                             'Vuelve a abrirlo.')
    # Que siga vivo aunque se lleve horas trabajando sobre él sin descanso.
    try:
        os.utime(ruta, None)
    except OSError:
        pass
    return ruta


def tamano(identificador, usuario):
    return os.path.getsize(ruta_de(identificador, usuario))


def leer(identificador, usuario):
    with open(ruta_de(identificador, usuario), 'rb') as archivo:
        return archivo.read()


def cerrar(identificador, usuario):
    """Borra el documento. Lo llama el editor al cerrarse."""
    try:
        ruta = ruta_de(identificador, usuario)
        os.unlink(ruta)
        sesion_huellas.olvidar(_carpeta(), os.path.basename(ruta)[:-4])
        return True
    except (SesionInvalida, OSError):
        return False


def _soltar_los_mios_si_paso(usuario):
    """Si esta persona ya tiene demasiados documentos abiertos, suelta los suyos
    más antiguos.

    Se tocan SOLO los de quien está subiendo: así nadie puede provocar que se
    borren los documentos de otro llenando el servidor.
    """
    try:
        mios = []
        for nombre in os.listdir(_carpeta()):
            if not nombre.endswith('.pdf'):
                continue
            base = nombre[:-4]
            ruta = os.path.join(CARPETA, nombre)
            marca = os.path.join(CARPETA, base + '.de')
            try:
                if open(marca, encoding='utf-8').read().strip() != str(usuario):
                    continue
            except OSError:
                continue
            mios.append((os.path.getmtime(ruta), ruta, marca))
        mios.sort()
        for _cuando, ruta, marca in mios[:max(0, len(mios) - POR_USUARIO + 1)]:
            for archivo in (ruta, marca, ruta[:-4] + sesion_huellas.SUFIJO):
                try:
                    os.unlink(archivo)
                except OSError:
                    pass
    except OSError:
        pass


def _barrer():
    """Fuera lo viejo, y si se pasa del tope, fuera lo más viejo hasta caber."""
    ahora = time.time()
    if ahora - _ultimo_barrido[0] < 300.0:
        return
    _ultimo_barrido[0] = ahora
    try:
        nombres = os.listdir(_carpeta())
    except OSError:
        return
    vivos, total = [], 0
    for nombre in nombres:
        ruta = os.path.join(CARPETA, nombre)
        try:
            edad = ahora - os.path.getmtime(ruta)
            peso = os.path.getsize(ruta)
            if edad > VIDA:
                os.unlink(ruta)
                if ruta.endswith('.pdf'):
                    for suelto in (ruta[:-4] + '.de',
                                   ruta[:-4] + sesion_huellas.SUFIJO):
                        try:
                            os.unlink(suelto)
                        except OSError:
                            pass
                continue
            vivos.append((edad, peso, ruta))
            total += peso
        except OSError:
            pass
    if total > TOPE_TOTAL:
        vivos.sort(reverse=True)                      # los más viejos primero
        for _edad, peso, ruta in vivos:
            if total <= TOPE_TOTAL:
                break
            try:
                os.unlink(ruta)
                total -= peso
            except OSError:
                pass
        logger.warning('documentos en edición por encima del tope: se soltaron '
                       'los más antiguos')
