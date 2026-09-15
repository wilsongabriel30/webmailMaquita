# -*- coding: utf-8 -*-
"""
Archivos que se adjuntan al RESPONDER un formulario (tipo «Subir archivos»).
============================================================================
No confundir con `encuestas_imagenes.py`, que son las imágenes que pone quien
ARMA el formulario. Aquí el que sube es quien responde, que muchas veces no
tiene cuenta en Raíces.

EL RECORRIDO DE UN ARCHIVO
--------------------------
1. Quien responde lo elige y se sube **en el momento**, no al enviar: una
   respuesta con cuatro adjuntos de 10 MB sería un envío de 40 MB que, si se
   corta, se pierde entero y hay que volver a elegirlo todo.
2. Queda **pendiente** en `<raiz>/_formularios/<encuesta_id>/adjuntos/`, fuera
   del Drive de nadie. Ahí no molesta: si la persona cierra la página sin
   enviar, ese archivo no ha aparecido en el Drive del dueño del formulario.
3. Al **registrar la respuesta** se entrega al Drive del dueño, a la carpeta
   «<nombre del formulario> (archivos)», junto al `.forma`. Desde ese momento es
   un archivo suyo como cualquier otro: lo ve, lo comparte, lo mueve, lo baja.
4. Entregado, se borra el pendiente. No se guarda dos veces.

Los pendientes que nunca llegaron a enviarse se barren a las
`HORAS_PENDIENTES`.

POR QUÉ NO SE EXIGE INICIAR SESIÓN (a diferencia de Google)
-----------------------------------------------------------
En Google Forms subir archivos obliga a tener cuenta. Aquí los formularios se
responden desde FUERA de la fundación —comunidades, productores, público—, y
exigir cuenta dejaría el tipo inservible justo para lo que se usa. A cambio, lo
que entra está acotado: tamaño, cantidad, y qué extensiones se admiten.

QUÉ NO SE ADMITE, NUNCA
-----------------------
Ejecutables y guiones (`.exe`, `.bat`, `.js`, `.ps1`…). Un formulario público lo
puede abrir cualquiera con el enlace: sin este filtro sería una vía cómoda para
repartir un ejecutable desde nuestro dominio y con nuestro nombre encima.

Y lo que se admite se sirve SIEMPRE como descarga y como
`application/octet-stream`, jamás con el tipo que dijera el navegador de quien
lo subió: así un `.html` o un `.svg` adjuntos se bajan, no se ejecutan en
nuestro dominio.

Autoría: Equipo de Tecnología Maquita — 2026-09-08
"""
import json
import logging
import os
import re
import time
import unicodedata
import uuid

log = logging.getLogger('almacen.encuestas.archivos')

CARPETA = '_formularios'
SUBCARPETA = 'adjuntos'
SUFIJO_CARPETA = ' (archivos)'

MB = 1024 * 1024
LIMITE_DEFECTO_MB = 10
LIMITE_MAXIMO_MB = 100
MAX_ARCHIVOS_DEFECTO = 1
MAX_ARCHIVOS = 10
HORAS_PENDIENTES = 24

# Grupos que se pueden exigir en la pregunta. Vacío = cualquier archivo (salvo
# los prohibidos de abajo, que no se admiten nunca).
GRUPOS = {
    'documento': ('doc', 'docx', 'odt', 'rtf', 'txt', 'md'),
    'hoja': ('xls', 'xlsx', 'ods', 'csv'),
    'presentacion': ('ppt', 'pptx', 'odp'),
    'pdf': ('pdf',),
    'imagen': ('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff', 'heic'),
    'video': ('mp4', 'mov', 'avi', 'mkv', 'webm', '3gp'),
    'audio': ('mp3', 'wav', 'ogg', 'm4a', 'aac'),
    'comprimido': ('zip', 'rar', '7z', 'tar', 'gz'),
}

NOMBRES_GRUPO = {
    'documento': 'Documento', 'hoja': 'Hoja de cálculo',
    'presentacion': 'Presentación', 'pdf': 'PDF', 'imagen': 'Imagen',
    'video': 'Vídeo', 'audio': 'Audio', 'comprimido': 'Comprimido (ZIP)',
}

# No se admiten nunca, esté el formulario configurado como esté.
PROHIBIDAS = {
    'exe', 'com', 'scr', 'pif', 'msi', 'msp', 'cpl', 'dll', 'sys', 'drv',
    'bat', 'cmd', 'ps1', 'psm1', 'vbs', 'vbe', 'js', 'jse', 'wsf', 'wsh',
    'hta', 'jar', 'apk', 'app', 'deb', 'rpm', 'sh', 'bash', 'run', 'bin',
    'reg', 'lnk', 'url', 'scf', 'inf', 'gadget',
}

_ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
                 r'[0-9a-f]{4}-[0-9a-f]{12}$')


class ArchivoInvalido(Exception):
    """Lo que llegó no se puede aceptar, y el motivo es para enseñarlo."""


# ---------------------------------------------------------------------------
# Rutas en disco
# ---------------------------------------------------------------------------
def _validar_id(valor, que='identificador'):
    """Los ids son UUID y se comprueban ANTES de tocar el disco: es lo que
    impide que un `../..` en la petición se convierta en una ruta."""
    texto = str(valor or '').lower()
    if not _ID.match(texto):
        raise ArchivoInvalido('%s inválido' % que.capitalize())
    return texto


def carpeta_de(encuesta_id):
    from config_almacen import raiz_datos
    return os.path.join(raiz_datos(), CARPETA,
                        _validar_id(encuesta_id, 'formulario'), SUBCARPETA)


def _camino(encuesta_id, adjunto_id, extension):
    return os.path.join(carpeta_de(encuesta_id),
                        _validar_id(adjunto_id, 'archivo') + '.' + extension)


def camino_pendiente(encuesta_id, adjunto_id):
    """Dónde está el archivo pendiente, o None si ya no está."""
    try:
        camino = _camino(encuesta_id, adjunto_id, 'dat')
    except ArchivoInvalido:
        return None
    return camino if os.path.isfile(camino) else None


def ficha(encuesta_id, adjunto_id):
    """Los datos del pendiente (nombre original, tamaño), o None."""
    try:
        camino = _camino(encuesta_id, adjunto_id, 'json')
    except ArchivoInvalido:
        return None
    if not os.path.isfile(camino):
        return None
    try:
        with open(camino, encoding='utf-8') as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Nombres
# ---------------------------------------------------------------------------
def extension_de(nombre):
    return os.path.splitext(str(nombre or ''))[1].lstrip('.').lower()[:12]


def nombre_seguro(nombre):
    """El nombre original, dejado en algo que se pueda escribir en el Drive.

    Se conserva reconocible —quien recibe los archivos necesita saber cuál es
    cuál—, pero sin nada que pueda alterar una ruta ni confundir a un sistema
    de archivos: se van las barras, los caracteres de control y los nombres que
    empiezan por punto.
    """
    texto = unicodedata.normalize('NFC', str(nombre or '')).strip()
    texto = re.sub(r'[\x00-\x1f\x7f]', '', texto)
    texto = re.sub(r'[/\\:*?"<>|]', '-', texto)
    texto = texto.lstrip('. ').strip()
    return texto[:120] or 'archivo'


def _texto_grupos(grupos):
    return ', '.join(NOMBRES_GRUPO.get(g, g) for g in grupos)


# ---------------------------------------------------------------------------
# Recibir
# ---------------------------------------------------------------------------
def limite_de(pregunta):
    """Cuántos megas admite esa pregunta."""
    try:
        megas = int(pregunta.get('archivo_mb') or LIMITE_DEFECTO_MB)
    except (TypeError, ValueError):
        megas = LIMITE_DEFECTO_MB
    return min(max(megas, 1), LIMITE_MAXIMO_MB)


def cuantos_de(pregunta):
    try:
        cuantos = int(pregunta.get('archivo_max') or MAX_ARCHIVOS_DEFECTO)
    except (TypeError, ValueError):
        cuantos = MAX_ARCHIVOS_DEFECTO
    return min(max(cuantos, 1), MAX_ARCHIVOS)


def comprobar_nombre(nombre, grupos):
    """Levanta ArchivoInvalido si esa extensión no se admite."""
    extension = extension_de(nombre)
    if not extension:
        raise ArchivoInvalido('El archivo no tiene extensión, así que no se '
                              'puede saber qué es. Ponle uno con extensión '
                              '(por ejemplo .pdf).')
    if extension in PROHIBIDAS:
        raise ArchivoInvalido('Por seguridad no se admiten programas ni '
                              'guiones (.%s).' % extension)
    if not grupos:
        return extension
    admitidas = set()
    for grupo in grupos:
        admitidas.update(GRUPOS.get(grupo, ()))
    if extension not in admitidas:
        raise ArchivoInvalido('Este formulario admite solo: %s.'
                              % _texto_grupos(grupos))
    return extension


def guardar_pendiente(encuesta_id, flujo, nombre_original, limite_mb, grupos):
    """Recibe un archivo y lo deja pendiente. Devuelve su ficha.

    Se escribe por trozos y se corta EN CUANTO se pasa del límite: leer el
    archivo entero para después decir que era demasiado grande deja el disco
    lleno de todos modos.
    """
    nombre = nombre_seguro(nombre_original)
    comprobar_nombre(nombre, grupos)

    tope = min(max(int(limite_mb or LIMITE_DEFECTO_MB), 1), LIMITE_MAXIMO_MB) * MB
    carpeta = carpeta_de(encuesta_id)
    os.makedirs(carpeta, exist_ok=True)

    adjunto_id = str(uuid.uuid4())
    destino = os.path.join(carpeta, adjunto_id + '.dat')
    temporal = destino + '.parcial'
    escrito = 0
    try:
        with open(temporal, 'wb') as salida:
            while True:
                trozo = flujo.read(MB)
                if not trozo:
                    break
                escrito += len(trozo)
                if escrito > tope:
                    raise ArchivoInvalido(
                        '«%s» pasa del máximo de %d MB que admite esta '
                        'pregunta.' % (nombre, tope // MB))
                salida.write(trozo)
        if not escrito:
            raise ArchivoInvalido('«%s» llegó vacío.' % nombre)
        os.replace(temporal, destino)        # publicación atómica
    except Exception:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise

    datos = {'id': adjunto_id, 'nombre': nombre, 'tamano': escrito,
             'subido_en': int(time.time())}
    with open(os.path.join(carpeta, adjunto_id + '.json'), 'w',
              encoding='utf-8') as archivo:
        json.dump(datos, archivo, ensure_ascii=False)

    limpiar_pendientes(encuesta_id)
    return datos


# ---------------------------------------------------------------------------
# Entregar al Drive del dueño
# ---------------------------------------------------------------------------
def carpeta_destino(ruta_forma):
    """«/Proyectos/Encuesta.forma» → «/Proyectos/Encuesta (archivos)».

    Al lado del formulario, como la hoja de respuestas: quien lo creó encuentra
    ahí lo que le mandaron sin tener que buscar por el Drive.
    """
    padre = ruta_forma.rsplit('/', 1)[0] or '/'
    nombre = ruta_forma.rsplit('/', 1)[-1]
    if '.' in nombre:
        nombre = nombre.rsplit('.', 1)[0]
    return ('' if padre == '/' else padre) + '/' + \
        nombre_seguro(nombre)[:80] + SUFIJO_CARPETA


def _nombre_libre(propietario, carpeta, nombre):
    """Un nombre que no pise nada de lo que ya hay en esa carpeta.

    Importa: `nucleo.subir()` sobre una ruta existente convierte lo anterior en
    una VERSIÓN, que es lo que se quiere al reeditar un documento y lo contrario
    de lo que se quiere aquí. Dos personas que adjunten «cedula.pdf» tienen que
    acabar con dos archivos, no con uno y el historial del otro.
    """
    from seguridad_rutas import ruta_fisica
    base, extension = os.path.splitext(nombre)
    for intento in range(1, 200):
        candidato = nombre if intento == 1 else '%s (%d)%s' % (base, intento,
                                                               extension)
        completa = ('' if carpeta == '/' else carpeta) + '/' + candidato
        try:
            if not os.path.exists(ruta_fisica(propietario, completa,
                                              escritura=True)):
                return candidato
        except Exception:
            return candidato
    return '%s-%s%s' % (base, uuid.uuid4().hex[:8], extension)


def entregar(propietario, ruta_forma, encuesta_id, fichas, quien=''):
    """Mueve al Drive del dueño los archivos de una respuesta ya aceptada.

    Devuelve las fichas con `ruta` puesta en las que se entregaron. Las que
    fallen se quedan **sin** `ruta` y su archivo sigue pendiente: la respuesta
    no se pierde por un problema al copiar, y el adjunto se puede seguir
    descargando desde la vista de respuestas.
    """
    import nucleo_archivos as nucleo

    carpeta = carpeta_destino(ruta_forma)
    try:
        nucleo.crear_carpeta(propietario, carpeta.rsplit('/', 1)[0] or '/',
                             carpeta.rsplit('/', 1)[-1])
    except Exception as excepcion:
        # Que ya exista es lo normal a partir de la segunda respuesta.
        log.debug('carpeta de adjuntos %s: %s', carpeta, excepcion)

    marca = time.strftime('%Y-%m-%d %H%M')
    prefijo = '%s %s - ' % (marca, nombre_seguro(quien)[:40]) if quien \
        else '%s - ' % marca

    entregadas = []
    for ficha_archivo in fichas:
        camino = camino_pendiente(encuesta_id, ficha_archivo.get('id'))
        if not camino:
            entregadas.append(ficha_archivo)
            continue
        nombre = _nombre_libre(propietario, carpeta,
                               (prefijo + ficha_archivo['nombre'])[:150])
        try:
            with open(camino, 'rb') as flujo:
                nucleo.subir(propietario, carpeta, nombre, flujo)
            ficha_archivo = dict(ficha_archivo,
                                 ruta=('' if carpeta == '/' else carpeta) +
                                 '/' + nombre)
            _borrar_pendiente(encuesta_id, ficha_archivo['id'])
        except Exception as excepcion:
            # Se registra y se sigue: la respuesta ya está aceptada y perderla
            # por esto sería mucho peor que dejar el archivo donde está.
            log.error('No se pudo entregar el adjunto %s de %s: %s',
                      ficha_archivo.get('id'), encuesta_id, excepcion)
        entregadas.append(ficha_archivo)
    return entregadas


def _borrar_pendiente(encuesta_id, adjunto_id):
    for extension in ('dat', 'json'):
        try:
            camino = _camino(encuesta_id, adjunto_id, extension)
            if os.path.isfile(camino):
                os.remove(camino)
        except (OSError, ArchivoInvalido):
            pass


def limpiar_pendientes(encuesta_id, horas=HORAS_PENDIENTES):
    """Barre los pendientes que nunca llegaron a enviarse.

    Pasa siempre: se eligen archivos y se cierra la página. Sin esto, cada
    formulario con adjuntos acumularía para siempre lo que nadie envió.
    """
    try:
        carpeta = carpeta_de(encuesta_id)
    except ArchivoInvalido:
        return 0
    if not os.path.isdir(carpeta):
        return 0
    limite = time.time() - horas * 3600
    borrados = 0
    for nombre in os.listdir(carpeta):
        camino = os.path.join(carpeta, nombre)
        try:
            if os.path.getmtime(camino) < limite:
                os.remove(camino)
                borrados += 1
        except OSError:
            pass
    return borrados
