# -*- coding: utf-8 -*-
"""
El trabajo con PDF, fuera del worker que atiende a la gente.
=============================================================
«no quisiera que se cuelgue y debe tener alta disponibilidad» — el usuario,
29-jul-2026.

El problema, medido: FARO back-office corre con **3 workers eventlet**, que son
cooperativos —un solo hilo de verdad cada uno, repartido entre miles de
conexiones—. PyMuPDF es código C que **no suelta el GIL** (comprobado: dos hilos
tardan 1,71 veces lo que uno, en vez de 1,0). Mientras un worker edita un PDF,
ese worker **no atiende a nadie más**: ni nómina, ni CRM, ni admin. Con diez
guardados a la vez, 15,6 s con el worker congelado.

Aquí el trabajo se manda a unos **procesos ayudantes** (`worker_pdf`) que se
levantan al arrancar y se quedan esperando encargos. El worker les pasa el
encargo por un tubo y espera la respuesta dentro de `eventlet.tpool`, o sea en
un hilo **de verdad** del sistema operativo: el bucle de eventlet sigue girando
y el worker sigue atendiendo a todo el mundo.

Lo que se probó antes y NO sirve
--------------------------------
· `ProcessPoolExecutor` **se cuelga**: se gobierna con hilos, y eventlet los
  convierte en greenlets; mientras el greenlet que pidió el trabajo espera, el
  que gobierna el grupo no llega a correr nunca.
· El método 'forkserver' **no está disponible**: eventlet parchea los sockets
  que necesita.
· `os.fork` en cada encargo **se cuelga** en cuanto hay varios a la vez: partir
  en dos un proceso que tiene hilos trabajando le deja al hijo cerrojos cogidos
  por hilos que en él no existen.

Por eso los ayudantes se lanzan **una sola vez y al arrancar**, con un intérprete
limpio, cuando todavía no hay nada en marcha que se pueda heredar a medias.

Con esto:

  · el worker sigue respondiendo mientras se edita un PDF;
  · el trabajo usa varias CPU de las 24 de la máquina, no solo 3;
  · un PDF que tumbe a PyMuPDF se lleva por delante a un ayudante —que se
    repone solo— y no al worker que atiende a todo el back-office;
  · lo que pase del tope espera turno, que es lo que evita que la máquina se
    ahogue cuando entran muchos usuarios a la vez.

Autoría: Equipo de Tecnología Maquita — 2026-07-29
"""

import logging
import os
import pickle
import struct
import sys
import threading

logger = logging.getLogger(__name__)

# La carpeta de FARO, desde la que los ayudantes tienen que poder importar.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

# El ayudante se lanza por su ARCHIVO, no con `-m`: con `-m`, Python importa
# antes todos los paquetes del camino y `modulos/__init__.py` se trae FARO
# entero (4,3 s). Medido el 31-jul-2026: el primer encargo tardaba 3,8 s.
ARCHIVO_AYUDANTE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'worker_pdf.py')


def _cuantos():
    """Cuántos ayudantes por worker.

    Son 3 workers de gunicorn, así que el total es el triple: con las 24 CPU de
    la máquina salen 4×3 = 12 ediciones a la vez y quedan 12 CPU para todo lo
    demás (los otros gunicorn, PostgreSQL, nginx). Se puede fijar con
    FARO_PDF_PROCESOS.
    """
    pedido = os.environ.get('FARO_PDF_PROCESOS')
    if pedido:
        try:
            return max(1, int(pedido))
        except ValueError:
            pass
    return max(2, min(6, (os.cpu_count() or 6) // 6))


AYUDANTES = _cuantos()

# Una operación que pase de aquí se da por perdida: al ayudante se le corta y al
# usuario se le dice, en vez de dejarlo mirando una rueda que no acaba nunca.
TIEMPO_MAXIMO = 120.0

# Cuánto se espera a que quede un ayudante libre. Si en todo este rato no hay
# ninguno, el servidor está desbordado y es mejor decirlo que seguir acumulando.
ESPERA_TURNO = 60.0

_libres = None
_candado = threading.Lock()
_vivos = []


class PdfOcupado(Exception):
    """No queda ningún ayudante libre: el servidor da lo que puede."""


class ErrorDeTarea(Exception):
    """El ayudante contestó, pero el trabajo falló (documento ilegible, por ejemplo).

    Hace falta distinguirlo de un fallo del tubo: si el ayudante contestó, está
    vivo y sano y hay que devolverlo a la cola. Antes se daba por muerto y se
    remataba, así que un PDF corrupto costaba un proceso nuevo —unos cinco
    segundos de arranque para el siguiente usuario— cada vez.
    (Auditoría del 29-jul-2026.)
    """


def _sistema():
    """El módulo `os` de verdad, sin el parcheo de eventlet.

    Eventlet cambia `os.read` y `os.write` por versiones que hablan con su bucle
    de greenlets. Aquí estorban: la conversación con el ayudante ocurre en un
    hilo del sistema operativo y lo que se quiere es justo bloquear ese hilo, y
    solo ese.
    """
    try:
        from eventlet import patcher
        return patcher.original('os')
    except ImportError:
        return os


def _cola():
    """La fila de ayudantes libres."""
    global _libres
    if _libres is None:
        try:
            from eventlet.queue import LightQueue as Cola
        except ImportError:
            from queue import Queue as Cola
        _libres = Cola()
    return _libres


class _Ayudante(object):
    """Un proceso de trabajo y sus dos tubos."""

    __slots__ = ('proceso', 'entrada', 'salida')

    def __init__(self, proceso):
        self.proceso = proceso
        self.entrada = proceso.stdin.fileno()     # se le escribe el encargo
        self.salida = proceso.stdout.fileno()     # se le lee la respuesta

    def vivo(self):
        return self.proceso.poll() is None

    def rematar(self):
        try:
            self.proceso.kill()
        except Exception:
            pass
        try:
            self.proceso.wait(timeout=5)
        except Exception:
            pass


def _lanzar():
    """Levanta un ayudante con un intérprete limpio."""
    try:
        from eventlet import patcher
        subprocess = patcher.original('subprocess')
    except ImportError:
        import subprocess

    entorno = dict(os.environ)
    entorno['PYTHONPATH'] = RAIZ + os.pathsep + entorno.get('PYTHONPATH', '')
    # Que el ayudante no herede el aviso de arranque de FARO por su salida.
    entorno['FARO_AYUDANTE_PDF'] = '1'
    proceso = subprocess.Popen(
        [sys.executable, '-u', ARCHIVO_AYUDANTE],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=RAIZ, env=entorno, close_fds=True)
    return _Ayudante(proceso)


def preparar():
    """Levanta los ayudantes. Se llama al arrancar el worker.

    También vale llamarla tarde, con el servidor lleno de trabajo: el ayudante
    se lanza con `Popen`, que arranca un intérprete nuevo de cero, y no hereda
    nada del proceso que lo lanza. (Eso es justo lo que distingue esto de un
    `fork` a secas, que sí heredaba —y por eso se colgaba—.)

    Se levantan la primera vez que alguien edita un PDF, no al cargar el módulo:
    las instancias de FARO que nunca tocan PDF no gastan ni un proceso.
    """
    with _candado:
        if _vivos:
            return
        cola = _cola()
        for _ in range(AYUDANTES):
            try:
                ayudante = _lanzar()
            except Exception:
                logger.exception('no se pudo levantar un ayudante de PDF')
                continue
            _vivos.append(ayudante)
            cola.put(ayudante)
    logger.info('ayudantes de PDF listos: %d', len(_vivos))


def _reponer(viejo):
    """Sustituye a un ayudante que se murió, para no quedarse sin ninguno."""
    try:
        viejo.rematar()
    except Exception:
        pass
    with _candado:
        if viejo in _vivos:
            _vivos.remove(viejo)
        try:
            nuevo = _lanzar()
        except Exception:
            logger.exception('no se pudo reponer el ayudante de PDF')
            return None
        _vivos.append(nuevo)
    # Arrancar cuesta unos cinco segundos: si se encolara ya, el siguiente
    # usuario pagaría esa espera sin saber por qué. Se le pregunta primero.
    try:
        _conversar(nuevo, 'ping', (), {})
    except Exception:
        logger.warning('el ayudante repuesto no contesta', exc_info=True)
    logger.warning('ayudante de PDF repuesto')
    return nuevo


def _leer_todo(sistema, descriptor, cuantos):
    partes, faltan = [], cuantos
    while faltan > 0:
        trozo = sistema.read(descriptor, min(faltan, 1 << 20))
        if not trozo:
            raise EOFError('el ayudante se cortó a media respuesta')
        partes.append(trozo)
        faltan -= len(trozo)
    return b''.join(partes)


def _escribir_todo(sistema, descriptor, datos):
    puestos = 0
    while puestos < len(datos):
        puestos += sistema.write(descriptor, datos[puestos:puestos + (1 << 20)])


def _conversar(ayudante, tarea, argumentos, nombrados):
    """Le pasa el encargo al ayudante y espera su respuesta.

    Corre dentro de `tpool`, en un hilo del sistema operativo: aquí sí se puede
    bloquear sin dejar tirado a nadie.
    """
    sistema = _sistema()
    paquete = pickle.dumps((tarea, argumentos, nombrados),
                           protocol=pickle.HIGHEST_PROTOCOL)
    _escribir_todo(sistema, ayudante.entrada, struct.pack('!Q', len(paquete)))
    _escribir_todo(sistema, ayudante.entrada, paquete)

    (largo,) = struct.unpack('!Q', _leer_todo(sistema, ayudante.salida, 8))
    estado, contenido = pickle.loads(_leer_todo(sistema, ayudante.salida, largo))
    if estado == 'bien':
        return contenido
    nombre, mensaje = contenido
    if nombre == 'ValueError':
        # Los avisos con sentido para el usuario («Esa celda no existe») viajan
        # como ValueError y la API los enseña tal cual: hay que conservarlos.
        raise ValueError(mensaje)
    # El ayudante contestó: está sano. Se marca como fallo DE LA TAREA para que
    # quien llama no lo confunda con un tubo roto y no lo remate.
    raise ErrorDeTarea('%s: %s' % (nombre, mensaje))


def ejecutar(tarea, *argumentos, **nombrados):
    """Encarga `tarea` a un ayudante y devuelve su resultado.

    `tarea` es el nombre de una de las que `worker_pdf` sabe hacer. Los
    argumentos y el resultado viajan por el tubo, así que han de poder
    empaquetarse: bytes, texto, números, listas y diccionarios, que es todo lo
    que usan estas operaciones.

    Si no hay ayudantes (no se pudieron levantar), el trabajo se hace aquí
    mismo: más lento y bloqueando, pero el usuario recibe su documento igual.
    """
    tiempo_maximo = nombrados.pop('tiempo_maximo', TIEMPO_MAXIMO)

    try:
        from eventlet import tpool
        import eventlet
    except ImportError:
        return _aqui_mismo(tarea, argumentos, nombrados)

    if not _vivos:
        preparar()
    if not _vivos:
        return _aqui_mismo(tarea, argumentos, nombrados)

    cola = _cola()
    try:
        ayudante = cola.get(timeout=ESPERA_TURNO)
    except Exception:
        raise PdfOcupado('El servidor está atendiendo muchos documentos a la '
                         'vez. Vuelve a intentarlo en unos segundos.')

    devolver = True
    try:
        with eventlet.Timeout(tiempo_maximo, False):
            return tpool.execute(_conversar, ayudante, tarea,
                                 argumentos, nombrados)
        # Se agotó el tiempo: ese ayudante se queda con el encargo a medias y ya
        # no sirve para otro. Se sustituye.
        devolver = False
        nuevo = _reponer(ayudante)
        if nuevo is not None:
            cola.put(nuevo)
        raise PdfOcupado('El documento tardó demasiado en procesarse. '
                         'Puede que sea demasiado grande o complejo.')
    except (ValueError, ErrorDeTarea):
        # El trabajo falló pero el ayudante sigue vivo: se devuelve a la cola (lo
        # hace el ) y el error sube tal cual.
        raise
    except (EOFError, OSError, RuntimeError, struct.error, pickle.PickleError):
        # El ayudante se murió con el documento (PyMuPDF puede tumbarse con un
        # PDF roto). Se repone y se avisa; el worker ni se ha enterado.
        devolver = False
        nuevo = _reponer(ayudante)
        if nuevo is not None:
            cola.put(nuevo)
        raise
    finally:
        if devolver:
            cola.put(ayudante)


def _aqui_mismo(tarea, argumentos, nombrados):
    """Último recurso: hacerlo en este mismo proceso."""
    logger.warning('sin ayudantes de PDF: la tarea "%s" se hace en el worker', tarea)
    from . import worker_pdf
    funcion = worker_pdf._tareas().get(tarea)
    if funcion is None:
        raise ValueError('Tarea desconocida: %s' % tarea)
    return funcion(*argumentos, **nombrados)
