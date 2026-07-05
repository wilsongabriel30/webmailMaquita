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
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, raiz_usuario, ruta_fisica

log = logging.getLogger('almacen.nucleo')

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
        return listar_unidades(usuario_id), []
    fisica = ruta_fisica(usuario_id, ruta_virtual)
    if not os.path.isdir(fisica):
        raise FileNotFoundError(f'Carpeta no encontrada: {ruta_virtual}')

    favoritos = {f['ruta'] for f in consultar(
        'SELECT ruta FROM favoritos WHERE usuario_id = %s', (usuario_id,))}
    compartidas = {c['ruta'] for c in consultar(
        'SELECT ruta FROM compartidos WHERE propietario_id = %s', (usuario_id,))}
    estilos = {e['folder_id']: e for e in consultar(
        'SELECT folder_id, color, icono FROM estilos_carpeta WHERE usuario_id = %s', (usuario_id,))}

    carpetas, archivos = [], []
    with os.scandir(fisica) as entradas:
        for entrada in entradas:
            item = _item_a_dict(usuario_id, ruta_virtual, entrada, favoritos, compartidas)
            if item['es_carpeta'] and item['id'] in estilos:   # color/icono personalizado
                estilo = estilos[item['id']]
                if estilo['color']:
                    item['color'] = estilo['color']
                if estilo['icono']:
                    item['icono'] = estilo['icono']
            (carpetas if item['es_carpeta'] else archivos).append(item)

    # Orden "natural": archivo2 antes que archivo10 (igual que el explorador).
    # Tuplas (tipo, valor) porque int y str no son comparables entre sí: sin
    # esto, una carpeta con nombres mixtos ("006.FFVV..." junto a "Anexos")
    # rompía el listado con TypeError.
    clave = lambda item: [(0, int(t)) if t.isdigit() else (1, t.lower())
                          for t in re.split(r'(\d+)', item['nombre']) if t]
    carpetas.sort(key=clave)
    archivos.sort(key=clave)
    return carpetas, archivos


def crear_carpeta(usuario_id: int, ruta_padre: str, nombre: str) -> dict:
    """Crea una carpeta (mkdir -p del padre incluido) y devuelve su item."""
    if not nombre or '/' in nombre or nombre in ('.', '..'):
        raise RutaInvalida('Nombre de carpeta inválido')
    ruta_padre = normalizar_ruta_virtual(ruta_padre)
    ruta_nueva = ('' if ruta_padre == '/' else ruta_padre) + '/' + nombre
    fisica = ruta_fisica(usuario_id, ruta_nueva)
    os.makedirs(fisica, exist_ok=True)
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
    fisica = ruta_fisica(usuario_id, ruta_final)
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

    log.info('Subido %s (%d bytes) usuario %s', ruta_final, escrito, usuario_id)
    return {'nombre': nombre, 'ruta': ruta_final, 'tamano_bytes': escrito,
            'tamano_humano': tamano_humano(escrito)}


def _publicar_con_dedup(temporal: str, fisica: str, digest: str, tamano: int) -> bool:
    """
    Publica el archivo recién escrito aplicando deduplicación.
    Devuelve True (el temporal fue consumido). Si algo de la dedup falla,
    cae con elegancia a una publicación normal (nunca pierde el archivo).
    """
    try:
        filas = consultar('SELECT ruta_canonica FROM contenidos WHERE hash = %s', (digest,))
        if filas and os.path.exists(filas[0]['ruta_canonica']):
            # Contenido ya conocido → enlace duro a la copia canónica
            canonica = filas[0]['ruta_canonica']
            if os.path.exists(fisica):
                os.remove(fisica)
            os.link(canonica, fisica)     # mismo inodo, 0 bytes nuevos
            os.remove(temporal)
            return True
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

    fisica = ruta_fisica(usuario_id, ruta_virtual)
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


def renombrar(usuario_id: int, ruta_virtual: str, nuevo_nombre: str) -> str:
    """Renombra un archivo o carpeta dentro de su misma ubicación."""
    if not nuevo_nombre or '/' in nuevo_nombre:
        raise RutaInvalida('Nombre nuevo inválido')
    ruta_virtual = normalizar_ruta_virtual(ruta_virtual)
    origen = ruta_fisica(usuario_id, ruta_virtual)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_virtual)
    ruta_nueva = ruta_virtual.rsplit('/', 1)[0] + '/' + nuevo_nombre
    destino = ruta_fisica(usuario_id, ruta_nueva)
    os.replace(origen, destino)
    return ruta_nueva


def mover(usuario_id: int, ruta_origen: str, ruta_destino: str) -> None:
    """Mueve archivo/carpeta a otra ruta virtual (renombrar entre carpetas)."""
    origen = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_origen))
    destino = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_destino))
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_origen)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    os.replace(origen, destino)


def copiar(usuario_id: int, ruta_origen: str, ruta_destino: str) -> None:
    """Copia archivo (o carpeta completa) a otra ruta virtual."""
    origen = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_origen))
    destino = ruta_fisica(usuario_id, normalizar_ruta_virtual(ruta_destino))
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_origen)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.isdir(origen):
        shutil.copytree(origen, destino)
    else:
        shutil.copy2(origen, destino)


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


def enviar_a_papelera(usuario_id: int, ruta_virtual: str) -> None:
    """
    'Elimina' moviendo a la papelera del usuario (recuperable, como en Drive).
    Registra en BD la ruta original para poder restaurar.
    """
    ruta_virtual = normalizar_ruta_virtual(ruta_virtual)
    origen = ruta_fisica(usuario_id, ruta_virtual)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_virtual)
    nombre = os.path.basename(origen)
    es_carpeta = os.path.isdir(origen)
    tamano = _tamano_arbol(origen)

    nombre_fisico = f'{int(time.time()*1000)}__{nombre}'
    destino = os.path.join(raiz_usuario(usuario_id, 'papelera'), nombre_fisico)
    shutil.move(origen, destino)
    ejecutar("""
        INSERT INTO papelera (usuario_id, ruta_original, nombre, nombre_fisico,
                              es_carpeta, tamano_bytes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (usuario_id, ruta_virtual, nombre, nombre_fisico, es_carpeta, tamano))


def buscar(usuario_id: int, termino: str, limite: int = 50) -> list:
    """
    Busca por nombre (contiene, sin distinguir mayúsculas) en todo el árbol
    del usuario. Devuelve items con el formato del contrato de /buscar.
    """
    termino_min = (termino or '').lower()
    if len(termino_min) < 2:
        return []
    base = raiz_usuario(usuario_id, 'archivos')
    resultados = []
    for carpeta, subcarpetas, archivos in os.walk(base):
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
        FROM papelera WHERE usuario_id = %s ORDER BY eliminado_en DESC
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


def restaurar_de_papelera(usuario_id: int, nombre_fisico: str) -> str:
    """Devuelve un item de la papelera a su ruta original. Devuelve la ruta restaurada."""
    filas = consultar("""
        SELECT ruta_original, nombre_fisico FROM papelera
        WHERE usuario_id = %s AND nombre_fisico = %s
    """, (usuario_id, nombre_fisico))
    if not filas:
        raise FileNotFoundError('No está en la papelera')
    ruta_original = filas[0]['ruta_original']
    origen = os.path.join(raiz_usuario(usuario_id, 'papelera'), nombre_fisico)
    destino = ruta_fisica(usuario_id, ruta_original)
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
    return ruta_original


def vaciar_papelera(usuario_id: int) -> int:
    """
    Vacía la papelera del usuario, pero NO destruye: mueve todo a la retención
    (red de seguridad de RETENCION_DIAS que solo un master recupera).
    Devuelve cuántos elementos pasaron a retención.
    """
    filas = consultar('SELECT * FROM papelera WHERE usuario_id = %s', (usuario_id,))
    base_papelera = raiz_usuario(usuario_id, 'papelera')
    base_retencion = raiz_usuario(usuario_id, 'retencion')
    movidos = 0
    for fila in filas:
        origen = os.path.join(base_papelera, fila['nombre_fisico'])
        destino = os.path.join(base_retencion, fila['nombre_fisico'])
        try:
            if os.path.exists(origen):
                shutil.move(origen, destino)
            ejecutar("""
                INSERT INTO retencion (usuario_id, ruta_original, nombre, nombre_fisico,
                                       es_carpeta, tamano_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (usuario_id, fila['ruta_original'], fila['nombre'], fila['nombre_fisico'],
                  fila['es_carpeta'], fila['tamano_bytes']))
            ejecutar('DELETE FROM papelera WHERE id = %s', (fila['id'],))
            movidos += 1
        except OSError as excepcion:
            log.warning('No se pudo retener %s: %s', fila['nombre_fisico'], excepcion)
    log.info('Papelera de usuario %s vaciada a retención (%d elementos)', usuario_id, movidos)
    return movidos


def listar_retencion(usuario_id: int = None) -> list:
    """
    Elementos en retención (solo master). Si usuario_id es None, de TODOS.
    Cada item indica los días que le quedan antes de purgarse.
    """
    from config_almacen import RETENCION_DIAS
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
            'dias_restantes': max(0, RETENCION_DIAS - transcurridos),
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
    destino = ruta_fisica(usuario_id, ruta_original)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino):
        raiz, ext = os.path.splitext(destino)
        destino = f'{raiz}_recuperado{ext}'
        ruta_original = ruta_original + '_recuperado'
    shutil.move(origen, destino)
    ejecutar('DELETE FROM retencion WHERE usuario_id = %s AND nombre_fisico = %s',
             (usuario_id, nombre_fisico))
    return ruta_original


def purgar_retencion() -> int:
    """
    Borra DEFINITIVAMENTE lo retenido que superó RETENCION_DIAS.
    Pensado para un cron diario. Devuelve cuántos se purgaron.
    """
    from config_almacen import RETENCION_DIAS
    vencidos = consultar("""
        SELECT id, usuario_id, ruta_original, nombre, nombre_fisico, es_carpeta
        FROM retencion
        WHERE eliminado_definitivo_en < NOW() - (%s || ' days')::interval
    """, (RETENCION_DIAS,))
    purgados = 0
    for fila in vencidos:
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
    fisica = ruta_fisica(usuario_id, marcador)
    os.makedirs(os.path.dirname(fisica), exist_ok=True)
    with open(fisica, 'w', encoding='utf-8') as f:
        _json.dump({'destino': destino, 'es_carpeta': es_carpeta, 'nombre': nombre}, f)
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
    hallados = []
    for carpeta, _subcarpetas, archivos in os.walk(base):
        for nombre in archivos:
            fisica = os.path.join(carpeta, nombre)
            try:
                mtime = os.path.getmtime(fisica)
            except OSError:
                continue
            hallados.append((mtime, carpeta, nombre))
    hallados.sort(reverse=True)   # más reciente primero
    items = []
    for mtime, carpeta, nombre in hallados[:limite]:
        ruta_carpeta = '/' + os.path.relpath(carpeta, base).replace(os.sep, '/')
        ruta_carpeta = '/' if ruta_carpeta == '/.' else ruta_carpeta
        entrada = _EntradaFalsa(os.path.join(carpeta, nombre))
        items.append(_item_a_dict(usuario_id, ruta_carpeta, entrada, favoritos, compartidas))
    return items


# El uso de disco se guarda en cuotas_uso y se recalcula como maximo cada
# _CUOTA_TTL_SEG en un hilo de fondo: recorrer el arbol completo sobre NFS
# (/mnt/almacen) tomaba ~40s con decenas de miles de archivos y, al hacerse
# en CADA GET /cuota, bloqueaba los workers de gunicorn (504 en todo el motor).
_CUOTA_TTL_SEG = 600
_cuota_recalculando: set = set()
_cuota_lock = _threading.Lock()


def _calcular_uso(usuario_id: int) -> int:
    return _tamano_arbol(raiz_usuario(usuario_id, 'archivos')) \
        + _tamano_arbol(raiz_usuario(usuario_id, 'papelera'))


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
