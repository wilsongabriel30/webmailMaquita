# -*- coding: utf-8 -*-
"""
Núcleo de archivos del Almacén Maquita.
=======================================
Todas las operaciones sobre el disco: listar, subir, descargar, carpetas,
renombrar, copiar, mover, papelera, búsqueda y cuota.

El FILESYSTEM es la fuente de verdad de los archivos: aquí no hay caché que
des-sincronizar ni tabla espejo que corromper — el mal clásico que motivó
este proyecto.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import hashlib
import logging
import threading as _threading
import os
import re
import shutil
import time
from datetime import datetime, timezone

from almacen_bd import consultar, ejecutar
from config_almacen import CUOTA_DEFECTO_BYTES
import espacios_indice as espacios
import indice_busqueda as indice
import indice_contenido as contenido
import nombres_archivo as nombres
from seguridad_rutas import (RutaInvalida, normalizar_ruta_virtual, raiz_usuario,
                             ruta_fisica, unidad_de_ruta)
from config_almacen import raiz_datos

log = logging.getLogger('almacen.nucleo')


class DestinoOcupado(Exception):
    """Ya hay algo con ese nombre en el destino.

    Se lanza en vez de sobrescribir: `os.replace()` machaca el destino sin
    avisar, y asi se perdio un archivo el 31/08/2026 —se renombro una copia con
    el nombre del bueno y el bueno desaparecio sin dejar rastro—. Quien llama
    decide: preguntar a la persona, o pasar `sobrescribir=True` a conciencia.
    """

    def __init__(self, ruta):
        self.ruta = ruta
        super().__init__('Ya existe «%s» en esa carpeta' % str(ruta).rsplit('/', 1)[-1])


# ── Clasificación de archivos (misma semántica que consume el explorador) ──
TIPOS_POR_EXTENSION = {
    'imagen':    {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'heic', 'avif', 'tiff'},
    'video':     {'mp4', 'avi', 'mkv', 'mov', 'webm', 'wmv', 'flv'},
    'audio':     {'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac'},
    'documento': {'doc', 'docx', 'odt', 'pdf', 'rtf'},
    'hoja':      {'xls', 'xlsx', 'ods', 'csv'},
    'presentacion': {'ppt', 'pptx', 'odp'},
    'texto':     {'txt', 'md', 'log', 'json', 'xml', 'yml', 'yaml'},
    'comprimido': {'zip', 'rar', '7z', 'tar', 'gz'},
}
ICONOS_POR_TIPO = {
    'carpeta': 'folder', 'imagen': 'image', 'video': 'movie', 'audio': 'audiotrack',
    'documento': 'description', 'hoja': 'table_chart', 'presentacion': 'slideshow',
    'texto': 'article', 'comprimido': 'folder_zip', 'archivo': 'insert_drive_file',
}
MIMES_BASICOS = {
    'pdf': 'application/pdf', 'txt': 'text/plain', 'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'mp4': 'video/mp4',
    'mp3': 'audio/mpeg', 'zip': 'application/zip', 'csv': 'text/csv',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}
EXTENSIONES_EDITABLES = {'docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp', 'txt', 'md', 'csv'}


def clasificar(nombre: str, es_carpeta: bool) -> tuple:
    """Devuelve (tipo, extension, mime, icono, es_editable) de un nombre."""
    if es_carpeta:
        return 'carpeta', '', '', ICONOS_POR_TIPO['carpeta'], False
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    tipo = 'archivo'
    for nombre_tipo, extensiones in TIPOS_POR_EXTENSION.items():
        if extension in extensiones:
            tipo = nombre_tipo
            break
    mime = MIMES_BASICOS.get(extension, 'application/octet-stream')
    icono = ICONOS_POR_TIPO.get(tipo, ICONOS_POR_TIPO['archivo'])
    return tipo, extension, mime, icono, extension in EXTENSIONES_EDITABLES


def tamano_humano(n: int) -> str:
    """Bytes → texto legible ('550.0 B', '2.3 MB'...)."""
    n = float(n or 0)
    for unidad in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unidad == 'TB':
            return f'{n:.1f} {unidad}'
        n /= 1024


def _id_estable(usuario_id: int, ruta_virtual: str) -> str:
    """Identificador estable de un item (hash corto de usuario+ruta)."""
    crudo = f'{usuario_id}:{ruta_virtual}'.encode('utf-8')
    return hashlib.sha1(crudo).hexdigest()[:16]


def _item_a_dict(usuario_id: int, ruta_carpeta: str, entrada: os.DirEntry,
                 favoritos: set, compartidas: set) -> dict:
    """Convierte una entrada del disco al diccionario del CONTRATO (campos que
    el explorador consume — ver docs/CONTRATO-API.md)."""
    es_carpeta = entrada.is_dir(follow_symlinks=False)
    info = entrada.stat(follow_symlinks=False)
    ruta_virtual = ('' if ruta_carpeta == '/' else ruta_carpeta) + '/' + entrada.name
    # Acceso directo (marcador en disco): se muestra apuntando a su destino
    es_acceso = (not es_carpeta) and entrada.name.endswith(SUFIJO_ACCESO)
    destino_acceso = None
    nombre_mostrar = entrada.name
    if es_acceso:
        info_ac = _leer_acceso_directo(entrada.path)
        destino_acceso = info_ac.get('destino')
        nombre_mostrar = info_ac.get('nombre') or entrada.name[:-len(SUFIJO_ACCESO)]
        es_carpeta = bool(info_ac.get('es_carpeta'))   # se comporta como su destino

    tipo, extension, mime, icono, es_editable = clasificar(nombre_mostrar, es_carpeta)
    if es_acceso:
        icono = 'shortcut'
    modificado = datetime.fromtimestamp(info.st_mtime, tz=timezone.utc)
    identificador = _id_estable(usuario_id, ruta_virtual)
    return {
        'id': identificador,
        'file_id': identificador,
        'folder_id': identificador if es_carpeta else None,
        'nombre': nombre_mostrar,
        'ruta': ruta_virtual,
        'ruta_completa': ruta_virtual,
        'es_acceso_directo': es_acceso,
        'destino': destino_acceso,
        'es_carpeta': es_carpeta,
        'tipo': tipo,
        'extension': extension,
        'tamano_bytes': 0 if es_carpeta else info.st_size,
        'tamano_humano': '—' if es_carpeta else tamano_humano(info.st_size),
        'mime_type': mime,
        'icono': icono,
        'color': None,
        'es_favorito': ruta_virtual in favoritos,
        'es_compartido': ruta_virtual in compartidas,
        'es_editable': es_editable,
        'tiene_preview': tipo in ('imagen', 'video'),
        'modificado_at': modificado.isoformat(),
        'creado_at': modificado.isoformat(),
    }


# ── Archivos internos del sistema, que NO son del usuario ────────────────────
# `.comprobacion-drive-maquita` es el CENTINELA de la app de Windows (v2.5.0):
# rclone bisync lo usa con --check-access para abortar si el servidor listara
# vacío o roto, en vez de propagar un borrado masivo a todos los equipos.
# Si el usuario lo ve en la web y lo borra —y lo va a ver, porque el listado no
# escondía nada—, la sincronización de esa persona queda en pausa hasta que el
# cliente lo recree. Así que ni se muestra ni se deja borrar.
# Solo se ocultan estos nombres EXACTOS, no todo lo que empieza por punto: hay
# gente con archivos propios así (.gitkeep, .env) y esos deben seguir viéndose.
ARCHIVOS_INTERNOS = {'.comprobacion-drive-maquita'}


def es_archivo_interno(nombre: str) -> bool:
    """¿Es un archivo del sistema que el usuario no debe ver ni borrar?"""
    return (nombre or '') in ARCHIVOS_INTERNOS


def listar_unidades(usuario_id: int) -> list:
    """Unidades compartidas de las que el usuario es miembro, como items-carpeta
    (para verlas dentro del explorador en la ruta virtual /unidades)."""
    filas = consultar("""
        SELECT u.id, u.nombre, m.rol
        FROM unidades_compartidas u
        JOIN unidad_miembros m ON m.unidad_id = u.id
        WHERE m.usuario_id = %s
        ORDER BY u.nombre
    """, (usuario_id,))
    items = []
    for f in filas:
        ruta = f'/unidades/{f["id"]}'
        items.append({
            'id': _id_estable(usuario_id, ruta),
            'folder_id': _id_estable(usuario_id, ruta),
            'nombre': f['nombre'],
            'ruta': ruta, 'ruta_completa': ruta,
            'es_carpeta': True, 'tipo': 'carpeta',
            'icono': 'groups',            # icono de "equipo"
            'es_unidad_compartida': True, 'mi_rol': f['rol'],
            'tamano_bytes': 0, 'tamano_humano': '—',
            'es_favorito': False, 'es_compartido': True, 'es_editable': f['rol'] != 'viewer',
        })
    return items


def listar(usuario_id: int, ruta_virtual: str) -> tuple:
    """
    Lista una carpeta. Devuelve (carpetas, archivos) como listas de dicts del
    contrato, ordenadas por nombre natural (igual que el explorador).
    """
    ruta_virtual = normalizar_ruta_virtual(ruta_virtual)
    if ruta_virtual == '/unidades':            # carpeta virtual: lista los drives de equipo
        unidades = listar_unidades(usuario_id)
        _tamanos_de_carpetas(usuario_id, '/unidades', unidades)
        return unidades, []
    fisica = ruta_fisica(usuario_id, ruta_virtual)

    favoritos = {f['ruta'] for f in consultar(
        'SELECT ruta FROM favoritos WHERE usuario_id = %s', (usuario_id,))}
    compartidas = {c['ruta'] for c in consultar(
        'SELECT ruta FROM compartidos WHERE propietario_id = %s', (usuario_id,))}
    estilos = {e['folder_id']: e for e in consultar(
        'SELECT folder_id, color, icono FROM estilos_carpeta WHERE usuario_id = %s', (usuario_id,))}

    def _recorrer_disco():
        # (2026-08-13) TODO el trabajo de NFS (isdir + scandir + un stat por
        # entrada) vive aqui para poder ejecutarlo en un HILO NATIVO via
        # eventlet.tpool: bajo eventlet una llamada NFS lenta congelaba el
        # event loop del worker entero (picos de 216-363 s que arrastraban a
        # todas las peticiones de la instancia). En hilo nativo el worker
        # sigue atendiendo mientras el disco responde. Sin eventlet (scripts
        # de consola) se ejecuta directo, igual que siempre.
        if not os.path.isdir(fisica):
            raise FileNotFoundError(f'Carpeta no encontrada: {ruta_virtual}')
        carpetas, archivos = [], []
        with os.scandir(fisica) as entradas:
            for entrada in entradas:
                if es_archivo_interno(entrada.name):
                    continue
                item = _item_a_dict(usuario_id, ruta_virtual, entrada, favoritos, compartidas)
                if item['es_carpeta'] and item['id'] in estilos:   # color/icono personalizado
                    estilo = estilos[item['id']]
                    if estilo['color']:
                        item['color'] = estilo['color']
                    if estilo['icono']:
                        item['icono'] = estilo['icono']
                (carpetas if item['es_carpeta'] else archivos).append(item)
        return carpetas, archivos

    try:
        from eventlet import patcher as _patcher, tpool as _tpool
        _bajo_eventlet = _patcher.is_monkey_patched('socket')
    except ImportError:
        _bajo_eventlet = False
    if _bajo_eventlet:
        carpetas, archivos = _tpool.execute(_recorrer_disco)
    else:
        carpetas, archivos = _recorrer_disco()

    # Orden "natural": archivo2 antes que archivo10 (igual que el explorador).
    # Tuplas (tipo, valor) porque int y str no son comparables entre sí: sin
    # esto, una carpeta con nombres mixtos ("006.FFVV..." junto a "Anexos")
    # rompía el listado con TypeError.
    clave = lambda item: [(0, int(t)) if t.isdigit() else (1, t.lower())
                          for t in re.split(r'(\d+)', (item['nombre'] or '').strip()) if t]
    carpetas.sort(key=clave)
    archivos.sort(key=clave)
    _tamanos_de_carpetas(usuario_id, ruta_virtual, carpetas)
    return carpetas, archivos


def _tamanos_de_carpetas(usuario_id: int, ruta_virtual: str, carpetas: list) -> None:
    """Rellena tamano/tamano_humano de las carpetas desde `indice_nombres`
    (12/08/2026): UNA consulta agrupada por hijo, cero recorridos del NFS.
    En unidades compartidas se usa el usuario-índice 0 (reindexar_unidades).
    FAIL-SILENT: si el índice no está, la carpeta se queda con el guion."""
    if not carpetas:
        return
    try:
        es_unidades = (ruta_virtual == '/unidades'
                       or ruta_virtual.startswith('/unidades/'))
        uid_indice = 0 if es_unidades else usuario_id
        prefijo = '' if ruta_virtual == '/' else ruta_virtual
        filas = consultar("""
            SELECT split_part(substr(ruta, %s), '/', 1) AS hijo,
                   SUM(tamano) AS total
            FROM indice_nombres
            WHERE usuario_id = %s AND NOT es_carpeta AND ruta LIKE %s
            GROUP BY 1
        """, (len(prefijo) + 2, uid_indice, prefijo + '/%'))
        por_hijo = {f['hijo']: int(f['total'] or 0) for f in filas}
        for c in carpetas:
            segmento = (c.get('ruta') or '').rsplit('/', 1)[-1]
            n = por_hijo.get(segmento)
            if n:
                c['tamano'] = n
                c['tamano_bytes'] = n
                c['tamano_humano'] = tamano_humano(n)
    except Exception as excepcion:
        log.debug('Tamaños de carpeta no disponibles para %s: %s',
                  ruta_virtual, excepcion)


def crear_carpeta(usuario_id: int, ruta_padre: str, nombre: str) -> dict:
    """Crea una carpeta (mkdir -p del padre incluido) y devuelve su item."""
    nombre = (nombre or '').strip()
    if not nombre or '/' in nombre or nombre in ('.', '..'):
        raise RutaInvalida('Nombre de carpeta inválido')
    ruta_padre = normalizar_ruta_virtual(ruta_padre)
    ruta_nueva = ('' if ruta_padre == '/' else ruta_padre) + '/' + nombre
    fisica = ruta_fisica(usuario_id, ruta_nueva, escritura=True)
    os.makedirs(fisica, exist_ok=True)
    indice.agregar(usuario_id, ruta_nueva)
    identificador = _id_estable(usuario_id, ruta_nueva)
    return {'id': identificador, 'folder_id': identificador, 'nombre': nombre,
            'ruta': ruta_nueva, 'es_carpeta': True, 'tipo': 'carpeta',
            'icono': ICONOS_POR_TIPO['carpeta']}


def _purgar_versiones(usuario_id: int, ruta_virtual: str, incluir_hijos: bool = False) -> None:
    """Elimina las versiones (filas y archivos físicos) de una ruta; con
    incluir_hijos también las de todo lo que cuelga de ella (carpetas)."""
    if incluir_hijos:
        filas = consultar("""
            SELECT id, version_fisico FROM versiones
            WHERE usuario_id = %s AND (ruta = %s OR ruta LIKE %s)
        """, (usuario_id, ruta_virtual, ruta_virtual.rstrip('/') + '/%'))
    else:
        filas = consultar('SELECT id, version_fisico FROM versiones '
                          'WHERE usuario_id = %s AND ruta = %s', (usuario_id, ruta_virtual))
    if not filas:
        return
    base_ver = raiz_usuario(usuario_id, 'versiones')
    for fila in filas:
        try:
            fisico = os.path.join(base_ver, fila['version_fisico'])
            if os.path.exists(fisico):
                os.remove(fisico)
        except OSError as excepcion:
            log.warning('No se pudo borrar versión física %s: %s',
                        fila['version_fisico'], excepcion)
        ejecutar('DELETE FROM versiones WHERE id = %s', (fila['id'],))


def subir(usuario_id: int, ruta_carpeta: str, nombre: str, flujo) -> dict:
    """
    Guarda un archivo por STREAMING (nunca se carga completo a memoria),
    calculando su hash SHA-256 al vuelo para DEDUPLICAR.

    - Escribe a un temporal mientras calcula el hash.
    - Si ese contenido ya existe en el almacén (otro usuario o carpeta subió
      lo mismo), descarta el temporal y crea un ENLACE DURO a la copia canónica
      → cero bytes extra en disco. Si es nuevo, el temporal pasa a ser canónico.
    - Publicación atómica con os.replace: una subida cortada nunca deja basura.

    Seguridad de la dedup: los enlaces duros comparten inodo pero el sistema de
    archivos lleva su propio contador; borrar el archivo de un usuario jamás
    afecta al de otro. Los archivos nunca se editan en sitio (una versión nueva
    es otra subida = otro inodo), así que compartir inodo es seguro.
    """
    if not nombre or '/' in nombre:
        raise RutaInvalida('Nombre de archivo inválido')
    ruta_carpeta = normalizar_ruta_virtual(ruta_carpeta)
    ruta_final = ('' if ruta_carpeta == '/' else ruta_carpeta) + '/' + nombre
    fisica = ruta_fisica(usuario_id, ruta_final, escritura=True)
    os.makedirs(os.path.dirname(fisica), exist_ok=True)

    # Si ya existe un archivo en esa ruta, su contenido actual pasa a ser una
    # VERSIÓN antes de sobrescribir (historial estilo Google Drive).
    if os.path.isfile(fisica):
        _guardar_version(usuario_id, ruta_final, fisica)
    else:
        # Archivo NUEVO: si quedaron versiones de un archivo anterior ya
        # eliminado en esta misma ruta (el file_id es hash de la ruta), se
        # purgan — el archivo nuevo no debe heredar historial ajeno.
        _purgar_versiones(usuario_id, ruta_final)

    temporal = fisica + f'.subiendo-{os.getpid()}-{int(time.time()*1000)}'
    hasher = hashlib.sha256()
    escrito = 0
    try:
        with open(temporal, 'wb') as destino:
            while True:
                trozo = flujo.read(1024 * 1024)   # 1 MB por vuelta
                if not trozo:
                    break
                destino.write(trozo)
                hasher.update(trozo)
                escrito += len(trozo)

        digest = hasher.hexdigest()
        if _publicar_con_dedup(temporal, fisica, digest, escrito):
            temporal = None   # el temporal ya fue consumido (movido o borrado)
    finally:
        if temporal and os.path.exists(temporal):
            os.remove(temporal)

    indice.agregar(usuario_id, ruta_final)
    contenido.encolar(usuario_id, ruta_final)
    log.info('Subido %s (%d bytes) usuario %s', ruta_final, escrito, usuario_id)
    return {'nombre': nombre, 'ruta': ruta_final, 'tamano_bytes': escrito,
            'tamano_humano': tamano_humano(escrito)}


def _contenido_coincide(ruta: str, digest: str, tamano: int) -> bool:
    """¿El archivo de esa ruta es de verdad el contenido de ese hash?

    El tamano se mira primero porque es gratis y descarta casi todo. Solo si
    coincide se relee el archivo para comparar el hash: es el precio de no
    entregarle a alguien un archivo que no es el suyo.
    """
    try:
        if os.path.getsize(ruta) != tamano:
            return False
        hasher = hashlib.sha256()
        with open(ruta, 'rb') as archivo:
            for trozo in iter(lambda: archivo.read(1024 * 1024), b''):
                hasher.update(trozo)
        return hasher.hexdigest() == digest
    except OSError:
        return False


def _publicar_con_dedup(temporal: str, fisica: str, digest: str, tamano: int) -> bool:
    """
    Publica el archivo recién escrito aplicando deduplicación.
    Devuelve True (el temporal fue consumido). Si algo de la dedup falla,
    cae con elegancia a una publicación normal (nunca pierde el archivo).
    """
    try:
        filas = consultar('SELECT ruta_canonica FROM contenidos WHERE hash = %s', (digest,))
        if filas and os.path.exists(filas[0]['ruta_canonica']):
            canonica = filas[0]['ruta_canonica']
            # COMPROBACION OBLIGATORIA (31/08/2026): que la ruta canonica siga
            # teniendo ESE contenido. Cada version nueva de un archivo registra
            # un hash nuevo con la MISMA ruta, asi que las filas anteriores
            # quedan apuntando a una ruta cuyo contenido ya es otro. Sin esta
            # comprobacion, el enlace duro entregaba un archivo AJENO al que se
            # acababa de subir: corrupcion silenciosa. Paso de verdad.
            if _contenido_coincide(canonica, digest, tamano):
                if os.path.exists(fisica):
                    os.remove(fisica)
                os.link(canonica, fisica)     # mismo inodo, 0 bytes nuevos
                os.remove(temporal)
                return True
            log.warning('Dedup: la ruta canonica de %s ya no tiene ese contenido '
                        '(%s); se republica y se corrige la fila', digest[:12], canonica)
        # Contenido nuevo, o el canónico registrado ya no existe en disco (p.ej.
        # tras mover la raíz de datos): este archivo pasa a ser el canónico.
        # ON CONFLICT DO UPDATE para que la fila vieja se autorrepare — con
        # DO NOTHING quedaba apuntando para siempre a una ruta muerta y la
        # dedup de ese contenido no volvía a funcionar.
        os.replace(temporal, fisica)
        ejecutar("""
            INSERT INTO contenidos (hash, ruta_canonica, tamano_bytes)
            VALUES (%s, %s, %s)
            ON CONFLICT (hash) DO UPDATE
                SET ruta_canonica = EXCLUDED.ruta_canonica,
                    tamano_bytes = EXCLUDED.tamano_bytes
        """, (digest, fisica, tamano))
        return True
    except Exception as excepcion:
        # Degradación elegante: si la dedup falla, publicar sin ella
        log.warning('Dedup falló (%s); se publica copia normal', excepcion)
        os.replace(temporal, fisica)
        return True


MAX_VERSIONES = 100   # como Drive: se conservan hasta 100 versiones por archivo


def _guardar_version(usuario_id: int, ruta_virtual: str, fisica_actual: str) -> None:
    """Mueve el contenido actual del archivo a la zona 'versiones' y lo registra.
    Se llama ANTES de sobrescribir. Poda las versiones más viejas más allá del tope
    (respetando las marcadas 'guardar_siempre'). FAIL-SILENT: nunca frena la subida."""
    try:
        file_id = _id_estable(usuario_id, ruta_virtual)
        marca = f'{int(time.time()*1000)}__{os.path.basename(fisica_actual)}'
        base_ver = raiz_usuario(usuario_id, 'versiones')
        destino = os.path.join(base_ver, f'{file_id}__{marca}')
        tamano = os.path.getsize(fisica_actual)
        shutil.move(fisica_actual, destino)
        ejecutar("""
            INSERT INTO versiones (usuario_id, file_id, ruta, version_fisico, tamano_bytes)
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id, file_id, ruta_virtual, os.path.basename(destino), tamano))
        _podar_versiones(usuario_id, file_id)
    except Exception as excepcion:
        log.warning('No se pudo versionar %s: %s', ruta_virtual, excepcion)


def _podar_versiones(usuario_id: int, file_id: str) -> None:
    """Deja como máximo MAX_VERSIONES por archivo; borra las más viejas que NO
    estén marcadas 'guardar_siempre'."""
    filas = consultar("""
        SELECT id, version_fisico FROM versiones
        WHERE usuario_id = %s AND file_id = %s AND NOT guardar_siempre
        ORDER BY creado_en DESC OFFSET %s
    """, (usuario_id, file_id, MAX_VERSIONES))
    base_ver = raiz_usuario(usuario_id, 'versiones')
    for fila in filas:
        ruta = os.path.join(base_ver, fila['version_fisico'])
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
            ejecutar('DELETE FROM versiones WHERE id = %s', (fila['id'],))
        except OSError:
            pass


def listar_versiones(usuario_id: int, file_id: str) -> list:
    """Historial de versiones de un archivo (más reciente primero)."""
    filas = consultar("""
        SELECT id, ruta, tamano_bytes, guardar_siempre, creado_en
        FROM versiones WHERE usuario_id = %s AND file_id = %s
        ORDER BY creado_en DESC
    """, (usuario_id, file_id))
    return [{
        'version_id': str(f['id']),
        'tamano_bytes': f['tamano_bytes'],
        'tamano_humano': tamano_humano(f['tamano_bytes']),
        'guardar_siempre': f['guardar_siempre'],
        'creado_en': f['creado_en'].isoformat(),
    } for f in filas]


def restaurar_version(usuario_id: int, file_id: str, version_id: int) -> None:
    """
    Restaura una versión anterior. El contenido ACTUAL se guarda como versión
    nueva antes (no se pierde nada), luego se coloca la versión elegida.
    """
    filas = consultar("""
        SELECT ruta, version_fisico FROM versiones
        WHERE id = %s AND usuario_id = %s AND file_id = %s
    """, (version_id, usuario_id, file_id))
    if not filas:
        raise FileNotFoundError('Versión no encontrada')
    ruta_virtual = filas[0]['ruta']
    version_fisico = filas[0]['version_fisico']

    fisica = ruta_fisica(usuario_id, ruta_virtual, escritura=True)
    if os.path.isfile(fisica):
        _guardar_version(usuario_id, ruta_virtual, fisica)   # preserva el actual

    origen = os.path.join(raiz_usuario(usuario_id, 'versiones'), version_fisico)
    shutil.copy2(origen, fisica)


def set_estilo_carpeta(usuario_id: int, folder_id: str, color, icono) -> None:
    """Guarda color/icono de una carpeta (None = no cambiar, '' = quitar)."""
    actual = consultar("""
        SELECT color, icono FROM estilos_carpeta
        WHERE usuario_id = %s AND folder_id = %s
    """, (usuario_id, folder_id))
    color_final = (actual[0]['color'] if actual else None) if color is None else (color or None)
    icono_final = (actual[0]['icono'] if actual else None) if icono is None else (icono or None)
    ejecutar("""
        INSERT INTO estilos_carpeta (usuario_id, folder_id, color, icono)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (usuario_id, folder_id)
        DO UPDATE SET color = EXCLUDED.color, icono = EXCLUDED.icono
    """, (usuario_id, folder_id, color_final, icono_final))


def renombrar(usuario_id: int, ruta_virtual: str, nuevo_nombre: str,
              forzar_extension: bool = False, sobrescribir: bool = False,
              conservar_ambos: bool = False) -> str:
    """Renombra un archivo o carpeta dentro de su misma ubicación.

    forzar_extension permite CAMBIAR la extensión, cosa que normalmente no se
    deja (ver nombres_archivo.py). Es para arreglar un archivo mal nombrado
    —un .xlsx guardado como .xls, que OnlyOffice abre sin barra de edición— y
    NO se expone en la API: se usa desde el servidor, a mano y a conciencia.
    """
    nuevo_nombre = (nuevo_nombre or '').strip()
    if not nuevo_nombre or '/' in nuevo_nombre:
        raise RutaInvalida('Nombre nuevo inválido')
    ruta_virtual = normalizar_ruta_virtual(ruta_virtual)
    if es_archivo_interno(ruta_virtual.rsplit('/', 1)[-1]):
        raise RutaInvalida(
            'Este archivo protege la sincronización de tu Drive y no se '
            'puede eliminar.')
    origen = ruta_fisica(usuario_id, ruta_virtual, escritura=True)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_virtual)
    # La extension NO se pierde al cambiar el nombre: es lo que decide con que
    # programa se abre el archivo (ver nombres_archivo.py). Se aplica aqui, en
    # el nucleo, para que valga por igual en todas las vias de renombrado.
    if not forzar_extension:
        nuevo_nombre = nombres.conservar_extension(
            ruta_virtual.rsplit('/', 1)[-1], nuevo_nombre, os.path.isdir(origen))
    ruta_nueva = ruta_virtual.rsplit('/', 1)[0] + '/' + nuevo_nombre
    destino = ruta_fisica(usuario_id, ruta_nueva, escritura=True)
    if destino != origen and os.path.exists(destino) and not sobrescribir:
        if not conservar_ambos:
            raise DestinoOcupado(ruta_nueva)
        # Se conservan los dos: el que llega recibe un «(n)» y nadie pierde nada.
        carpeta_fisica = os.path.dirname(destino)
        nuevo_nombre = nombres.nombre_libre(
            lambda n: os.path.exists(os.path.join(carpeta_fisica, n)), nuevo_nombre)
        ruta_nueva = ruta_virtual.rsplit('/', 1)[0] + '/' + nuevo_nombre
        destino = ruta_fisica(usuario_id, ruta_nueva, escritura=True)
    os.replace(origen, destino)
    indice.renombrar(usuario_id, ruta_virtual, ruta_nueva)
    contenido.olvidar(usuario_id, ruta_virtual)
    contenido.encolar(usuario_id, ruta_nueva)
    return ruta_nueva


def mover(usuario_id: int, ruta_origen: str, ruta_destino: str,
          sobrescribir: bool = False, conservar_ambos: bool = False) -> str:
    """Mueve archivo/carpeta a otra ruta virtual (renombrar entre carpetas)."""
    origen = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_origen), escritura=True)
    destino = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_destino), escritura=True)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_origen)
    ruta_final = normalizar_ruta_virtual(ruta_destino)
    if destino != origen and os.path.exists(destino) and not sobrescribir:
        if not conservar_ambos:
            raise DestinoOcupado(ruta_final)
        carpeta_fisica = os.path.dirname(destino)
        libre = nombres.nombre_libre(
            lambda n: os.path.exists(os.path.join(carpeta_fisica, n)),
            ruta_final.rsplit('/', 1)[-1])
        ruta_final = ruta_final.rsplit('/', 1)[0] + '/' + libre
        destino = ruta_fisica(usuario_id, ruta_final, escritura=True)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    os.replace(origen, destino)
    indice.renombrar(usuario_id, normalizar_ruta_virtual(ruta_origen), ruta_final)
    contenido.olvidar(usuario_id, normalizar_ruta_virtual(ruta_origen))
    contenido.encolar(usuario_id, ruta_final)
    return ruta_final


def copiar(usuario_id: int, ruta_origen: str, ruta_destino: str) -> None:
    """Copia archivo (o carpeta completa) a otra ruta virtual."""
    origen = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_origen))
    destino = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_destino), escritura=True)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_origen)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.isdir(origen):
        shutil.copytree(origen, destino)
    else:
        shutil.copy2(origen, destino)
    indice.agregar(usuario_id, normalizar_ruta_virtual(ruta_destino))
    contenido.encolar(usuario_id, normalizar_ruta_virtual(ruta_destino))


def _tamano_arbol(fisica: str) -> int:
    """Bytes totales de un archivo o árbol de carpetas."""
    if os.path.isfile(fisica):
        return os.path.getsize(fisica)
    total = 0
    for carpeta, _, archivos in os.walk(fisica):
        for archivo in archivos:
            try:
                total += os.path.getsize(os.path.join(carpeta, archivo))
            except OSError:
                pass
    return total


def enviar_a_papelera(usuario_id: int, ruta_virtual: str) -> str:
    """
    'Elimina' moviendo a la papelera del usuario (recuperable, como en Drive).
    Registra en BD la ruta original para poder restaurar.

    DEVUELVE el `nombre_fisico`, que es el identificador con el que
    `restaurar_de_papelera()` encuentra el elemento. Antes no se devolvia y el
    navegador no tenia forma de saber que restaurar, asi que no se podia
    ofrecer un "Deshacer" (29/07/2026).
    """
    # El centinela de sincronización no se borra: si desaparece, la app de
    # Windows de esa persona deja de sincronizar hasta recrearlo. Ver
    # ARCHIVOS_INTERNOS arriba.
    if es_archivo_interno(normalizar_ruta_virtual(ruta_virtual).rsplit('/', 1)[-1]):
        raise RutaInvalida(
            'Este archivo protege la sincronización de tu Drive y no se '
            'puede eliminar.')
    ruta_virtual = normalizar_ruta_virtual(ruta_virtual)
    origen = ruta_fisica(usuario_id, ruta_virtual, escritura=True)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_virtual)
    nombre = os.path.basename(origen)
    es_carpeta = os.path.isdir(origen)
    tamano = _tamano_arbol(origen)

    nombre_fisico = f'{int(time.time()*1000)}__{nombre}'
    # Si el elemento es de una UNIDAD compartida, va a la papelera de la UNIDAD,
    # no a la personal de quien borra: asi cualquier administrador de la unidad
    # lo ve y lo puede restaurar, y no se dispersa por las papeleras de la gente.
    unidad_id, _sub_pap = unidad_de_ruta(ruta_virtual)
    if unidad_id is not None:
        pap = os.path.join(raiz_datos(), '_unidades', str(unidad_id), 'papelera')
        os.makedirs(pap, exist_ok=True)
        destino = os.path.join(pap, nombre_fisico)
    else:
        destino = os.path.join(raiz_usuario(usuario_id, 'papelera'), nombre_fisico)
    shutil.move(origen, destino)
    ejecutar("""
        INSERT INTO papelera (usuario_id, ruta_original, nombre, nombre_fisico,
                              es_carpeta, tamano_bytes, unidad_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (usuario_id, ruta_virtual, nombre, nombre_fisico, es_carpeta, tamano, unidad_id))
    indice.eliminar(usuario_id, ruta_virtual)
    contenido.olvidar(usuario_id, ruta_virtual)
    return nombre_fisico


SEGUNDOS_MAXIMOS_BUSQUEDA = 8      # tope del recorrido en disco


def buscar(usuario_id: int, termino: str, limite: int = 50) -> list:
    """
    Busca por nombre (contiene, sin distinguir mayúsculas ni tildes) en todo lo
    que esta persona puede ver: su unidad, las unidades compartidas donde es
    miembro y lo que otras personas le compartieron. Responde desde el ÍNDICE de
    PostgreSQL — instantáneo. Si el usuario todavía no está indexado, se indexa
    al vuelo la primera vez.

    Los espacios se calculan UNA vez y se pasan a las dos consultas (nombres y
    contenido): son la misma pregunta de permisos y hacerla dos veces solo
    añadiría latencia y el riesgo de que las dos mitades no coincidieran.
    """
    termino = (termino or '').strip()
    if len(termino) < 2:
        return []
    try:
        if not indice.usuario_indexado(usuario_id):
            indice.reindexar_usuario(usuario_id)
        permitidos = espacios.espacios_de_busqueda(usuario_id)
        filas = indice.buscar_nombres(usuario_id, termino, limite,
                                      espacios_permitidos=permitidos)
        resultados = [_item_de_indice(fila, permitidos) for fila in filas]
        return _sumar_coincidencias_de_contenido(usuario_id, termino, resultados,
                                                 limite, permitidos)
    except Exception as e:
        log.warning('busqueda: el índice falló (%s); se recorre el disco', e)
        return _buscar_en_disco(usuario_id, termino, limite)


def _sumar_coincidencias_de_contenido(usuario_id, termino, resultados, limite,
                                      permitidos=None):
    """
    Añade los documentos cuyo TEXTO coincide, aunque el nombre no diga nada
    ("el informe de Esmeraldas" → lo encuentra dentro de doc_final_v3.pdf).
    Los que ya venían por nombre solo se enriquecen con el fragmento encontrado.
    """
    try:
        por_ruta = {r['ruta']: r for r in resultados}
        for fila in contenido.buscar_en_contenido(usuario_id, termino, limite,
                                                  espacios_permitidos=permitidos):
            visible = espacios.ruta_visible(permitidos or [], fila['espacio'],
                                            fila['ruta'])
            existente = por_ruta.get(visible)
            if existente is not None:
                existente['fragmento'] = fila['fragmento']
                existente['coincide_en'] = 'nombre y contenido'
                continue
            if len(resultados) >= limite:
                break
            item = _item_de_ruta(fila['espacio'], fila['ruta'], permitidos)
            if item:
                item['fragmento'] = fila['fragmento']
                item['coincide_en'] = 'contenido'
                resultados.append(item)
                por_ruta[visible] = item
        for r in resultados:
            r.setdefault('coincide_en', 'nombre')
    except Exception as e:
        log.warning('busqueda: no se pudo sumar el contenido (%s)', e)
    return resultados


def _item_de_ruta(espacio: int, ruta_virtual: str, permitidos=None):
    """Construye el item del contrato leyendo el índice de nombres (o el disco)."""
    filas = indice.consultar("""
        SELECT usuario_id AS espacio, ruta, nombre, es_carpeta, extension,
               tamano, modificado_en
        FROM indice_nombres WHERE usuario_id = %s AND ruta = %s
    """, (espacio, ruta_virtual))
    return _item_de_indice(filas[0], permitidos) if filas else None


def _item_de_indice(fila, permitidos=None) -> dict:
    """Convierte una fila del índice al formato del contrato de /buscar.

    La ruta que se devuelve es la que esa persona puede ABRIR: lo que está en el
    espacio de otra se enseña como «/compartido/<dueño>/…», que es el único
    camino por el que el explorador la sabe pedir.
    """
    nombre = fila['nombre']
    es_carpeta = fila['es_carpeta']
    tipo, extension, _, _, _ = clasificar(nombre, es_carpeta)
    modificado = fila['modificado_en'] or datetime.now(timezone.utc)
    tamano = fila['tamano'] or 0
    ruta = fila['ruta']
    if permitidos is not None and 'espacio' in fila:
        ruta = espacios.ruta_visible(permitidos, fila['espacio'], ruta)
    return {
        'nombre': nombre, 'ruta': ruta, 'ruta_completa': ruta,
        'es_carpeta': es_carpeta, 'extension': extension, 'tipo': tipo,
        'tamano': tamano, 'tamano_humano': tamano_humano(tamano),
        'modificado_at': modificado.strftime('%a, %d %b %Y %H:%M:%S GMT'),
    }


def _buscar_en_disco(usuario_id: int, termino: str, limite: int = 50) -> list:
    """Respaldo: recorrido directo del disco, con tope de tiempo."""
    termino_min = (termino or '').lower()
    base = raiz_usuario(usuario_id, 'archivos')
    resultados = []
    corte = time.monotonic() + SEGUNDOS_MAXIMOS_BUSQUEDA
    for carpeta, subcarpetas, archivos in os.walk(base):
        subcarpetas[:] = [c for c in subcarpetas if not c.startswith('.')]
        if time.monotonic() > corte:
            return resultados
        for nombre in subcarpetas + archivos:
            if termino_min in nombre.lower():
                fisica = os.path.join(carpeta, nombre)
                relativa = '/' + os.path.relpath(fisica, base).replace(os.sep, '/')
                es_carpeta = os.path.isdir(fisica)
                tipo, extension, _, _, _ = clasificar(nombre, es_carpeta)
                tamano = 0 if es_carpeta else os.path.getsize(fisica)
                modificado = datetime.fromtimestamp(os.path.getmtime(fisica), tz=timezone.utc)
                resultados.append({
                    'nombre': nombre, 'ruta': relativa, 'ruta_completa': relativa,
                    'es_carpeta': es_carpeta, 'extension': extension, 'tipo': tipo,
                    'tamano': tamano, 'tamano_humano': tamano_humano(tamano),
                    'modificado_at': modificado.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                })
                if len(resultados) >= limite:
                    return resultados
    return resultados


def listar_papelera(usuario_id: int) -> tuple:
    """Contenido de la papelera del usuario (carpetas, archivos) con formato del contrato."""
    filas = consultar("""
        SELECT id, ruta_original, nombre, nombre_fisico, es_carpeta, tamano_bytes, eliminado_en
        FROM papelera WHERE usuario_id = %s AND unidad_id IS NULL ORDER BY eliminado_en DESC
    """, (usuario_id,))
    carpetas, archivos = [], []
    for fila in filas:
        tipo, extension, mime, icono, editable = clasificar(fila['nombre'], fila['es_carpeta'])
        item = {
            'id': str(fila['id']),
            'nombre': fila['nombre'],
            'ruta': fila['nombre_fisico'],          # identificador dentro de la papelera
            'ruta_original': fila['ruta_original'],
            'es_carpeta': fila['es_carpeta'],
            'tipo': tipo, 'extension': extension, 'mime_type': mime, 'icono': icono,
            'tamano_bytes': fila['tamano_bytes'],
            'tamano_humano': tamano_humano(fila['tamano_bytes']),
            'es_favorito': False, 'es_compartido': False, 'es_editable': editable,
            'eliminado_en': fila['eliminado_en'].isoformat(),
        }
        (carpetas if fila['es_carpeta'] else archivos).append(item)
    return carpetas, archivos


def _item_papelera(fila):
    """Formatea una fila de papelera al contrato del explorador."""
    tipo, extension, mime, icono, editable = clasificar(fila['nombre'], fila['es_carpeta'])
    return {
        'id': str(fila['id']), 'nombre': fila['nombre'],
        'usuario_id': fila.get('usuario_id'),
        'ruta': fila['nombre_fisico'], 'ruta_original': fila['ruta_original'],
        'es_carpeta': fila['es_carpeta'], 'tipo': tipo, 'extension': extension,
        'mime_type': mime, 'icono': icono, 'tamano_bytes': fila['tamano_bytes'],
        'tamano_humano': tamano_humano(fila['tamano_bytes']),
        'es_favorito': False, 'es_compartido': False, 'es_editable': editable,
        'eliminado_en': fila['eliminado_en'].isoformat(),
    }


def listar_papelera_unidad(unidad_id: int) -> tuple:
    """Papelera de UNA unidad: lo que se borro de ella, lo haya borrado quien
    sea. La ven y restauran los administradores de la unidad."""
    filas = consultar("""
        SELECT id, usuario_id, ruta_original, nombre, nombre_fisico, es_carpeta, tamano_bytes, eliminado_en
        FROM papelera WHERE unidad_id = %s ORDER BY eliminado_en DESC
    """, (unidad_id,))
    carpetas, archivos = [], []
    for fila in filas:
        item = _item_papelera(fila)
        (carpetas if fila['es_carpeta'] else archivos).append(item)
    return carpetas, archivos


def restaurar_papelera_unidad(unidad_id: int, nombre_fisico: str) -> str:
    """Devuelve un elemento a la unidad desde su papelera. Cualquier
    administrador de la unidad puede hacerlo (el permiso se valida arriba)."""
    filas = consultar(
        "SELECT ruta_original FROM papelera WHERE unidad_id = %s AND nombre_fisico = %s",
        (unidad_id, nombre_fisico))
    if not filas:
        raise FileNotFoundError('No esta en la papelera de la unidad')
    ruta_original = filas[0]['ruta_original']
    origen = os.path.join(raiz_datos(), '_unidades', str(unidad_id), 'papelera', nombre_fisico)
    destino = ruta_fisica(0, ruta_original)   # ruta_fisica ignora el usuario en rutas de unidad
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino):
        raiz, ext = os.path.splitext(destino)
        destino = f'{raiz}_restaurado{ext}'
    shutil.move(origen, destino)
    ejecutar('DELETE FROM papelera WHERE unidad_id = %s AND nombre_fisico = %s',
             (unidad_id, nombre_fisico))
    return ruta_original


def ruta_original_en_papelera(usuario_id: int, nombre_fisico: str):
    """Donde volveria ese elemento si se restaura, o None si no esta.

    Lo pregunta la API ANTES de restaurar, para comprobar que quien restaura
    puede escribir en esa carpeta (01/09/2026).
    """
    filas = consultar(
        "SELECT ruta_original FROM papelera WHERE usuario_id = %s AND nombre_fisico = %s",
        (usuario_id, nombre_fisico))
    return filas[0]['ruta_original'] if filas else None


def restaurar_de_papelera(usuario_id: int, nombre_fisico: str) -> str:
    """Devuelve un item de la papelera a su ruta original. Devuelve la ruta restaurada."""
    filas = consultar("""
        SELECT ruta_original, nombre_fisico, unidad_id FROM papelera
        WHERE usuario_id = %s AND nombre_fisico = %s
    """, (usuario_id, nombre_fisico))
    if not filas:
        raise FileNotFoundError('No está en la papelera')
    # Si el elemento era de una UNIDAD, se restaura a la unidad (el fisico vive
    # en la papelera de la unidad, no en la del usuario). Asi el "Deshacer" tras
    # borrar tambien funciona para las unidades.
    if filas[0].get('unidad_id') is not None:
        return restaurar_papelera_unidad(filas[0]['unidad_id'], nombre_fisico)
    ruta_original = filas[0]['ruta_original']
    origen = os.path.join(raiz_usuario(usuario_id, 'papelera'), nombre_fisico)
    destino = ruta_fisica(usuario_id, ruta_original, escritura=True)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    # Si ya existe algo con ese nombre, restaurar con sufijo (no pisar)
    if os.path.exists(destino):
        raiz, ext = os.path.splitext(destino)
        destino = f'{raiz}_restaurado{ext}'
        ruta_original = ruta_original.rsplit('.', 1)[0] + '_restaurado' + \
            (('.' + ruta_original.rsplit('.', 1)[1]) if '.' in os.path.basename(ruta_original) else '')
    shutil.move(origen, destino)
    ejecutar('DELETE FROM papelera WHERE usuario_id = %s AND nombre_fisico = %s',
             (usuario_id, nombre_fisico))
    indice.agregar(usuario_id, ruta_original)
    contenido.encolar(usuario_id, ruta_original)
    return ruta_original


def vaciar_papelera(usuario_id: int) -> int:
    """
    Vacía la papelera del usuario, pero NO destruye: mueve todo a la retención
    (red de seguridad de RETENCION_DIAS que solo un master recupera).
    Devuelve cuántos elementos pasaron a retención.
    """
    filas = consultar('SELECT * FROM papelera WHERE usuario_id = %s AND unidad_id IS NULL', (usuario_id,))
    base_papelera = raiz_usuario(usuario_id, 'papelera')
    base_retencion = raiz_usuario(usuario_id, 'retencion')
    movidos = 0
    for fila in filas:
        origen = os.path.join(base_papelera, fila['nombre_fisico'])
        nf = fila['nombre_fisico']
        destino = os.path.join(base_retencion, nf)
        try:
            if os.path.exists(origen):
                if os.path.exists(destino):
                    # Colision: nombre unico en retencion (no chocar ni anidar).
                    raiz, ext = os.path.splitext(nf)
                    nf = '%s_%s%s' % (raiz, fila['id'], ext)
                    destino = os.path.join(base_retencion, nf)
                try:
                    os.replace(origen, destino)   # atomico (mismo sistema de archivos)
                except OSError:
                    shutil.move(origen, destino)  # respaldo si difieren de fs
            # Aunque el origen ya no exista (movido en un intento previo), se
            # registra en retencion y se limpia la papelera: asi NUNCA queda
            # trabado y el vaciar deja de dar error intermitente.
            ejecutar("""
                INSERT INTO retencion (usuario_id, ruta_original, nombre, nombre_fisico,
                                       es_carpeta, tamano_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (usuario_id, fila['ruta_original'], fila['nombre'], nf,
                  fila['es_carpeta'], fila['tamano_bytes']))
            ejecutar('DELETE FROM papelera WHERE id = %s', (fila['id'],))
            movidos += 1
        except Exception as excepcion:
            log.warning('No se pudo retener id=%s %s: %r',
                        fila['id'], fila['nombre_fisico'], excepcion)
    log.info('Papelera de usuario %s vaciada a retención (%d elementos)', usuario_id, movidos)
    return movidos


def eliminar_de_papelera(usuario_id: int, nombre_fisico: str) -> bool:
    """Elimina UN item de la papelera del usuario. Igual que vaciar pero individual:
    NO se destruye, pasa a la retención (red de seguridad de RETENCION_DIAS que solo
    un master recupera)."""
    filas = consultar('SELECT * FROM papelera WHERE usuario_id = %s AND nombre_fisico = %s',
                      (usuario_id, nombre_fisico))
    if not filas:
        raise FileNotFoundError('No está en la papelera')
    fila = filas[0]
    origen = os.path.join(raiz_usuario(usuario_id, 'papelera'), fila['nombre_fisico'])
    destino = os.path.join(raiz_usuario(usuario_id, 'retencion'), fila['nombre_fisico'])
    if os.path.exists(origen):
        shutil.move(origen, destino)
    ejecutar("""
        INSERT INTO retencion (usuario_id, ruta_original, nombre, nombre_fisico,
                               es_carpeta, tamano_bytes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (usuario_id, fila['ruta_original'], fila['nombre'], fila['nombre_fisico'],
          fila['es_carpeta'], fila['tamano_bytes']))
    ejecutar('DELETE FROM papelera WHERE id = %s', (fila['id'],))
    log.info('Item %s de usuario %s pasado a retención', nombre_fisico, usuario_id)
    return True


def listar_retencion(usuario_id: int = None) -> list:
    """
    Elementos en retención (solo master). Si usuario_id es None, de TODOS.
    Cada item indica los días que le quedan antes de purgarse.
    """
    from config_almacen import RETENCION_DIAS, RETENCION_DIAS_UNIDADES
    if usuario_id is not None:
        filas = consultar("""
            SELECT * FROM retencion WHERE usuario_id = %s
            ORDER BY eliminado_definitivo_en DESC
        """, (usuario_id,))
    else:
        filas = consultar("SELECT * FROM retencion ORDER BY eliminado_definitivo_en DESC")
    items = []
    from datetime import datetime, timezone
    ahora = datetime.now(timezone.utc)
    for fila in filas:
        transcurridos = (ahora - fila['eliminado_definitivo_en']).days
        items.append({
            'id': str(fila['id']),
            'usuario_id': fila['usuario_id'],
            'nombre': fila['nombre'],
            'ruta': fila['nombre_fisico'],
            'ruta_original': fila['ruta_original'],
            'es_carpeta': fila['es_carpeta'],
            'tamano_bytes': fila['tamano_bytes'],
            'tamano_humano': tamano_humano(fila['tamano_bytes']),
            'eliminado_definitivo_en': fila['eliminado_definitivo_en'].isoformat(),
            'dias_restantes': max(0, (RETENCION_DIAS_UNIDADES if str(fila['ruta_original'] or '').startswith('/unidades') else RETENCION_DIAS) - transcurridos),
        })
    return items


def restaurar_de_retencion(usuario_id: int, nombre_fisico: str) -> str:
    """Un master devuelve un elemento retenido a la unidad de su dueño."""
    filas = consultar("""
        SELECT ruta_original FROM retencion
        WHERE usuario_id = %s AND nombre_fisico = %s
    """, (usuario_id, nombre_fisico))
    if not filas:
        raise FileNotFoundError('No está en retención')
    ruta_original = filas[0]['ruta_original']
    origen = os.path.join(raiz_usuario(usuario_id, 'retencion'), nombre_fisico)
    destino = ruta_fisica(usuario_id, ruta_original, escritura=True)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino):
        raiz, ext = os.path.splitext(destino)
        destino = f'{raiz}_recuperado{ext}'
        ruta_original = ruta_original + '_recuperado'
    shutil.move(origen, destino)
    ejecutar('DELETE FROM retencion WHERE usuario_id = %s AND nombre_fisico = %s',
             (usuario_id, nombre_fisico))
    indice.agregar(usuario_id, ruta_original)
    contenido.encolar(usuario_id, ruta_original)
    return ruta_original


def purgar_retencion() -> int:
    """
    Borra DEFINITIVAMENTE lo retenido que superó RETENCION_DIAS.
    Pensado para un cron diario. Devuelve cuántos se purgaron.
    """
    from config_almacen import RETENCION_DIAS, RETENCION_DIAS_UNIDADES
    from datetime import datetime, timezone, timedelta
    vencidos = consultar("""
        SELECT id, usuario_id, ruta_original, nombre, nombre_fisico, es_carpeta,
               eliminado_definitivo_en
        FROM retencion
        WHERE eliminado_definitivo_en < NOW() - (%s || ' days')::interval
    """, (min(RETENCION_DIAS, RETENCION_DIAS_UNIDADES),))
    purgados = 0
    ahora = datetime.now(timezone.utc)
    for fila in vencidos:
        # Contenido de UNIDADES COMPARTIDAS: ventana ampliada (12/08/2026) —
        # uso comun, riesgo mas alto de perdida: se retiene mas tiempo.
        dias = RETENCION_DIAS_UNIDADES if str(fila['ruta_original'] or '').startswith('/unidades') else RETENCION_DIAS
        if fila['eliminado_definitivo_en'] > ahora - timedelta(days=dias):
            continue
        ruta = os.path.join(raiz_usuario(fila['usuario_id'], 'retencion'), fila['nombre_fisico'])
        try:
            if os.path.isdir(ruta):
                shutil.rmtree(ruta)
            elif os.path.exists(ruta):
                os.remove(ruta)
            ejecutar('DELETE FROM retencion WHERE id = %s', (fila['id'],))
            # Sus versiones también mueren aquí (destrucción definitiva)
            base = fila['ruta_original'].rstrip('/') or ''
            ruta_virtual = f"{base}/{fila['nombre']}" if base else f"/{fila['nombre']}"
            _purgar_versiones(fila['usuario_id'], ruta_virtual,
                              incluir_hijos=bool(fila['es_carpeta']))
            purgados += 1
        except OSError as excepcion:
            log.warning('No se pudo purgar %s: %s', fila['nombre_fisico'], excepcion)
    return purgados


def toggle_favorito(usuario_id: int, ruta_virtual: str) -> bool:
    """Marca/desmarca favorito. Devuelve el nuevo estado (True=favorito)."""
    ruta_virtual = normalizar_ruta_virtual(ruta_virtual)
    existe = consultar('SELECT 1 FROM favoritos WHERE usuario_id = %s AND ruta = %s',
                       (usuario_id, ruta_virtual))
    if existe:
        ejecutar('DELETE FROM favoritos WHERE usuario_id = %s AND ruta = %s',
                 (usuario_id, ruta_virtual))
        return False
    ejecutar('INSERT INTO favoritos (usuario_id, ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING',
             (usuario_id, ruta_virtual))
    return True


def listar_favoritos(usuario_id: int) -> tuple:
    """Items marcados como favoritos que aún existen en disco."""
    filas = consultar('SELECT ruta FROM favoritos WHERE usuario_id = %s', (usuario_id,))
    favoritas = {f['ruta'] for f in filas}
    compartidas = {c['ruta'] for c in consultar(
        'SELECT ruta FROM compartidos WHERE propietario_id = %s', (usuario_id,))}
    carpetas, archivos = [], []
    for ruta in favoritas:
        try:
            fisica = ruta_fisica(usuario_id, ruta)
        except RutaInvalida:
            continue
        if not os.path.exists(fisica):
            continue   # se borró: se ignora (limpieza perezosa)
        entrada_falsa = _EntradaFalsa(fisica)
        carpeta_padre = ruta.rsplit('/', 1)[0] or '/'
        item = _item_a_dict(usuario_id, carpeta_padre, entrada_falsa, favoritas, compartidas)
        (carpetas if item['es_carpeta'] else archivos).append(item)
    return carpetas, archivos


class _EntradaFalsa:
    """Imita os.DirEntry para reutilizar _item_a_dict con una ruta suelta
    (favoritos vienen de BD, no de un scandir)."""
    def __init__(self, ruta_fisica):
        self._ruta = ruta_fisica
        self.name = os.path.basename(ruta_fisica)

    def is_dir(self, follow_symlinks=True):
        return os.path.isdir(self._ruta)

    def stat(self, follow_symlinks=True):
        return os.stat(self._ruta)


SUFIJO_ACCESO = '.acceso-directo'   # marcador en disco de un acceso directo


def crear_acceso_directo(usuario_id: int, carpeta: str, destino: str, nombre: str = None) -> dict:
    """Crea un acceso directo (como en Drive) a otro archivo/carpeta. Se guarda como un
    pequeño archivo marcador `<nombre>.acceso-directo` cuyo contenido es la ruta destino."""
    import json as _json
    carpeta = normalizar_ruta_virtual(carpeta)
    destino = normalizar_ruta_virtual(destino)
    fis_destino = ruta_fisica(usuario_id, destino)
    if not os.path.exists(fis_destino):
        raise FileNotFoundError('El destino del acceso directo no existe')
    es_carpeta = os.path.isdir(fis_destino)
    if not nombre:
        nombre = os.path.basename(destino.rstrip('/')) or 'acceso'
    marcador = ('' if carpeta == '/' else carpeta) + '/' + nombre + SUFIJO_ACCESO
    fisica = ruta_fisica(usuario_id, marcador, escritura=True)
    os.makedirs(os.path.dirname(fisica), exist_ok=True)
    with open(fisica, 'w', encoding='utf-8') as f:
        _json.dump({'destino': destino, 'es_carpeta': es_carpeta, 'nombre': nombre}, f)
    indice.agregar(usuario_id, marcador)
    return {'nombre': nombre, 'destino': destino, 'es_carpeta_destino': es_carpeta}


def _leer_acceso_directo(fisica: str) -> dict:
    """Lee el marcador de un acceso directo. Devuelve {} si no es válido."""
    import json as _json
    try:
        with open(fisica, encoding='utf-8') as f:
            return _json.load(f)
    except Exception:
        return {}


def recientes(usuario_id: int, limite: int = 50) -> list:
    """Archivos modificados más recientemente en toda la unidad del usuario.
    Devuelve items con el formato del contrato (para el grid del explorador)."""
    base = raiz_usuario(usuario_id, 'archivos')
    favoritos = {f['ruta'] for f in consultar(
        'SELECT ruta FROM favoritos WHERE usuario_id = %s', (usuario_id,))}
    compartidas = {c['ruta'] for c in consultar(
        'SELECT ruta FROM compartidos WHERE propietario_id = %s', (usuario_id,))}
    # RÁPIDO (2026-07-24): usar el ÍNDICE de BD (indice_nombres.modificado_en) en
    # vez de recorrer TODO el árbol por NFS. os.walk colgaba con usuarios de decenas
    # de miles de archivos -> el gateway daba 504 y los workers quedaban trabados
    # (inestabilidad de todo el Drive). N stats en vez de decenas de miles.
    items = []
    try:
        filas = consultar("""
            SELECT ruta, MAX(creado_en) AS f FROM actividad
            WHERE usuario_id = %s
              AND accion = ANY(%s)
              AND ruta IS NOT NULL
            GROUP BY ruta ORDER BY f DESC LIMIT %s
        """, (usuario_id,
              ['apertura', 'abrio', 'subio', 'edito', 'renombro', 'movio',
               'creo_carpeta', 'copio', 'creo', 'descargo'],
              limite))
    except Exception:
        filas = []
    if filas:
        for f in filas:
            ruta = f['ruta']
            ruta_carpeta = ruta.rsplit('/', 1)[0] or '/'
            try:
                fisica = ruta_fisica(usuario_id, ruta)   # personal Y /unidades
            except Exception:
                continue
            if not os.path.isfile(fisica):
                continue
            items.append(_item_a_dict(usuario_id, ruta_carpeta,
                                      _EntradaFalsa(fisica), favoritos, compartidas))
        return items

    # FALLBACK (índice vacío): recorrido de disco (comportamiento anterior)
    hallados = []
    for carpeta, _subcarpetas, archivos in os.walk(base):
        for nombre in archivos:
            fisica = os.path.join(carpeta, nombre)
            try:
                mtime = os.path.getmtime(fisica)
            except OSError:
                continue
            hallados.append((mtime, carpeta, nombre))
    hallados.sort(reverse=True)
    for mtime, carpeta, nombre in hallados[:limite]:
        ruta_carpeta = '/' + os.path.relpath(carpeta, base).replace(os.sep, '/')
        ruta_carpeta = '/' if ruta_carpeta == '/.' else ruta_carpeta
        entrada = _EntradaFalsa(os.path.join(carpeta, nombre))
        items.append(_item_a_dict(usuario_id, ruta_carpeta, entrada, favoritos, compartidas))
    return items


def por_tamano(usuario_id: int, limite: int = 200) -> list:
    """Archivos de toda la unidad del usuario ordenados por TAMANO (mayor primero).
    Alimenta la vista 'Almacenamiento' (estilo Drive). Solo archivos (no carpetas);
    se omiten archivos y carpetas ocultos (versiones/miniaturas internas)."""
    base = raiz_usuario(usuario_id, 'archivos')
    favoritos = {f['ruta'] for f in consultar(
        'SELECT ruta FROM favoritos WHERE usuario_id = %s', (usuario_id,))}
    compartidas = {c['ruta'] for c in consultar(
        'SELECT ruta FROM compartidos WHERE propietario_id = %s', (usuario_id,))}
    def _recorrer_disco():
        # (2026-08-13) os.walk + getsize por archivo sobre NFS: en unidades
        # grandes son MILES de stats (11-44 s medidos) que congelaban el event
        # loop del worker entero. Todo el trabajo de disco corre en un hilo
        # nativo (tpool), igual que en listar(); las consultas de BD quedan
        # FUERA (arriba): el pool de almacen_bd es SimpleConnectionPool y no
        # es seguro entre hilos.
        hallados = []
        for carpeta, subcarpetas, archivos in os.walk(base):
            subcarpetas[:] = [d for d in subcarpetas if not d.startswith('.')]
            for nombre in archivos:
                if nombre.startswith('.'):
                    continue
                fisica = os.path.join(carpeta, nombre)
                try:
                    size = os.path.getsize(fisica)
                except OSError:
                    continue
                hallados.append((size, carpeta, nombre))
        hallados.sort(key=lambda t: t[0], reverse=True)   # mayor primero
        items = []
        for size, carpeta, nombre in hallados[:limite]:
            ruta_carpeta = '/' + os.path.relpath(carpeta, base).replace(os.sep, '/')
            ruta_carpeta = '/' if ruta_carpeta == '/.' else ruta_carpeta
            entrada = _EntradaFalsa(os.path.join(carpeta, nombre))
            items.append(_item_a_dict(usuario_id, ruta_carpeta, entrada, favoritos, compartidas))
        return items

    # (2026-08-27) Vía rápida: el índice de nombres ya guarda ruta + tamaño de
    # cada archivo (se mantiene en cada subida/borrado/renombrado). En unidades
    # grandes (50 000+ archivos) el recorrido del NFS tardaba 10-40 s y la vista
    # 'Almacenamiento' se perdía; con el índice responde en milisegundos. El
    # recorrido de disco queda SOLO como respaldo si la unidad no está indexada.
    try:
        if indice.usuario_indexado(usuario_id):
            filas = consultar(
                "SELECT ruta, tamano FROM indice_nombres "
                "WHERE usuario_id = %s AND NOT es_carpeta AND nombre NOT LIKE '.%%' "
                "AND ruta NOT LIKE '%%/.%%' ORDER BY tamano DESC, ruta LIMIT %s",
                (usuario_id, limite))
            items = []
            for fila in filas:
                ruta_v = '/' + str(fila['ruta']).strip('/')
                fisica = os.path.join(base, ruta_v.lstrip('/'))
                if not os.path.isfile(fisica):
                    continue
                ruta_carpeta = ruta_v.rsplit('/', 1)[0] or '/'
                entrada = _EntradaFalsa(fisica)
                items.append(_item_a_dict(usuario_id, ruta_carpeta, entrada, favoritos, compartidas))
            return items
    except Exception as exc:
        log.warning('por_tamano: índice no disponible (%s); se recorre el disco', exc)

    try:
        from eventlet import patcher as _patcher, tpool as _tpool
        _bajo_eventlet = _patcher.is_monkey_patched('socket')
    except ImportError:
        _bajo_eventlet = False
    if _bajo_eventlet:
        return _tpool.execute(_recorrer_disco)
    return _recorrer_disco()



def _hash_archivo(fisica: str, bloque: int = 1 << 20) -> str:
    """SHA-256 del contenido de un archivo, leído por bloques."""
    hasher = hashlib.sha256()
    with open(fisica, 'rb') as manejador:
        for trozo in iter(lambda: manejador.read(bloque), b''):
            hasher.update(trozo)
    return hasher.hexdigest()


def duplicados(usuario_id: int, tope_segundos: int = SEGUNDOS_MAXIMOS_BUSQUEDA) -> dict:
    """Detecta archivos con contenido IDÉNTICO en la unidad del usuario
    (para 'Liberar espacio' → duplicados). Barato: agrupa por TAMANO y solo
    calcula el hash SHA-256 dentro de grupos de igual tamano (>=2). Los archivos
    que comparten inodo (ya deduplicados por enlace duro) NO cuentan como espacio
    recuperable. Recorre con TOPE de tiempo para no colgar el worker sobre NFS."""
    base = raiz_usuario(usuario_id, 'archivos')
    inicio = time.monotonic()
    truncado = False
    por_size = {}
    for carpeta, subcarpetas, archivos in os.walk(base):
        subcarpetas[:] = [d for d in subcarpetas if not d.startswith('.')]
        if time.monotonic() - inicio > tope_segundos:
            truncado = True
            break
        for nombre in archivos:
            if nombre.startswith('.'):
                continue
            fisica = os.path.join(carpeta, nombre)
            try:
                st = os.stat(fisica)
            except OSError:
                continue
            if st.st_size == 0:
                continue
            por_size.setdefault(st.st_size, []).append((fisica, st.st_ino, st.st_mtime))
    grupos = []
    recuperable_total = 0
    for size, lista in por_size.items():
        if len(lista) < 2:
            continue
        if time.monotonic() - inicio > tope_segundos:
            truncado = True
            break
        por_hash = {}
        for fisica, ino, mtime in lista:
            try:
                digest = _hash_archivo(fisica)
            except OSError:
                continue
            por_hash.setdefault(digest, []).append((fisica, ino, mtime))
        for digest, copias in por_hash.items():
            if len(copias) < 2:
                continue
            copias.sort(key=lambda t: t[2])   # más antigua primero (se conserva)
            inodos = {ino for _, ino, _ in copias}
            recuperable = size * (len(inodos) - 1)
            recuperable_total += recuperable
            items = []
            for fisica, ino, mtime in copias:
                ruta_rel = '/' + os.path.relpath(fisica, base).replace(os.sep, '/')
                items.append({
                    'ruta': ruta_rel,
                    'nombre': os.path.basename(fisica),
                    'inodo': ino,
                    'modificado_at': datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                })
            grupos.append({
                'hash': digest,
                'tamano_bytes': size,
                'tamano_humano': tamano_humano(size),
                'copias': items,
                'total_copias': len(items),
                'recuperable_bytes': recuperable,
                'recuperable_humano': tamano_humano(recuperable),
            })
    grupos.sort(key=lambda g: g['recuperable_bytes'], reverse=True)
    return {
        'grupos': grupos,
        'total_grupos': len(grupos),
        'recuperable_bytes': recuperable_total,
        'recuperable_humano': tamano_humano(recuperable_total),
        'truncado': truncado,
    }



# El uso de disco se guarda en cuotas_uso y se recalcula como maximo cada
# _CUOTA_TTL_SEG en un hilo de fondo: recorrer el arbol completo sobre NFS
# (/mnt/almacen) tomaba ~40s con decenas de miles de archivos y, al hacerse
# en CADA GET /cuota, bloqueaba los workers de gunicorn (504 en todo el motor).
_CUOTA_TTL_SEG = 600
_cuota_recalculando: set = set()
_cuota_lock = _threading.Lock()


def _calcular_uso_disco(usuario_id: int) -> int:
    """Uso REAL recorriendo el arbol. Exacto pero LENTO (~41 s con 56 mil
    archivos sobre NFS): solo para verificacion o si el indice esta vacio."""
    return _tamano_arbol(raiz_usuario(usuario_id, 'archivos')) \
        + _tamano_arbol(raiz_usuario(usuario_id, 'papelera'))


def _calcular_uso(usuario_id: int) -> int:
    """Uso del usuario calculado desde el INDICE (instantaneo).

    Antes recorria todo el arbol por NFS: la barra de Almacenamiento se quedaba
    "cargando" 15-46 s y, con eventlet, ese recorrido BLOQUEA al worker entero
    (mismo problema que tuvo `recientes()`).
    Validado 2026-07-24: indice y recorrido coinciden al 0,0 % (13,5 GB), pero el
    indice tarda 0,012 s frente a 41 s. Si el indice estuviera vacio se recurre al
    recorrido para no reportar 0 por error.
    """
    try:
        filas = consultar(
            'SELECT COALESCE(SUM(tamano), 0) AS s FROM indice_nombres '
            "WHERE usuario_id = %s AND NOT es_carpeta "
            "AND ruta NOT LIKE '/unidades/%%'", (usuario_id,))
        total = int(filas[0]['s']) if filas else 0
    except Exception as excepcion:
        log.warning('uso por indice fallo (%s), se recorre el disco: %s',
                    usuario_id, excepcion)
        return _calcular_uso_disco(usuario_id)
    if total <= 0:
        return _calcular_uso_disco(usuario_id)   # indice vacio: no reportar 0
    # La papelera no esta en el indice; suele ser pequena.
    try:
        total += _tamano_arbol(raiz_usuario(usuario_id, 'papelera'))
    except Exception:
        pass
    return total


def _guardar_uso(usuario_id: int, usado: int) -> None:
    ejecutar("""
        INSERT INTO cuotas_uso (usuario_id, usado_bytes, calculado_en)
        VALUES (%s, %s, NOW())
        ON CONFLICT (usuario_id) DO UPDATE
            SET usado_bytes = EXCLUDED.usado_bytes, calculado_en = NOW()
    """, (usuario_id, usado))


def _refrescar_uso_en_fondo(usuario_id: int) -> None:
    with _cuota_lock:
        if usuario_id in _cuota_recalculando:
            return
        _cuota_recalculando.add(usuario_id)

    def _trabajo():
        try:
            _guardar_uso(usuario_id, _calcular_uso(usuario_id))
        except Exception as excepcion:
            log.warning('recalculo de cuota %s fallo: %s', usuario_id, excepcion)
        finally:
            with _cuota_lock:
                _cuota_recalculando.discard(usuario_id)

    _threading.Thread(target=_trabajo, daemon=True,
                      name=f'cuota-{usuario_id}').start()


def cuota(usuario_id: int) -> dict:
    """Uso y límite de almacenamiento del usuario (contando su papelera)."""
    from config_almacen import cuota_defecto_bytes
    fila = consultar('SELECT limite_bytes FROM cuotas WHERE usuario_id = %s', (usuario_id,))
    limite = fila[0]['limite_bytes'] if fila else cuota_defecto_bytes()
    fila_uso = consultar("""
        SELECT usado_bytes, EXTRACT(EPOCH FROM (NOW() - calculado_en)) AS edad
        FROM cuotas_uso WHERE usuario_id = %s
    """, (usuario_id,))
    if fila_uso:
        usado = int(fila_uso[0]['usado_bytes'])
        if float(fila_uso[0]['edad']) > _CUOTA_TTL_SEG:
            _refrescar_uso_en_fondo(usuario_id)
    else:
        # Primera vez de este usuario: se calcula sincronico y queda cacheado.
        usado = _calcular_uso(usuario_id)
        _guardar_uso(usuario_id, usado)
    porcentaje = round(usado * 100 / limite, 1) if limite else 0.0
    return {
        'usado': usado, 'usado_humano': tamano_humano(usado),
        'total': limite, 'total_humano': tamano_humano(limite),
        'libre': max(0, limite - usado), 'porcentaje': porcentaje,
        'cuota': limite,
    }
