# -*- coding: utf-8 -*-
"""
Índice de nombres del Almacén (búsqueda instantánea, estilo Drive).
==================================================================
El motor guarda los archivos en disco; recorrerlo entero en cada búsqueda es lento
(sobre todo en almacenamiento de red). Este módulo mantiene en PostgreSQL una tabla
con el NOMBRE y la RUTA de cada elemento, para responder la búsqueda en milisegundos.

Reglas de diseño:
- El índice es un ESPEJO, nunca la verdad: la verdad es el disco. Si el índice se
  pierde o se desfasa, se reconstruye con `reindexar_usuario()` y no se pierde nada.
- Ninguna operación de archivos puede fallar por culpa del índice: todos los enganches
  van dentro de try/except y solo dejan un aviso en el registro.
- Se compara sin tildes ni mayúsculas ("informe" encuentra "INFORME" y "Informé").

Autoría: Equipo de Tecnología Maquita — 2026-07-22
"""
import logging
import os
import unicodedata
from datetime import datetime, timezone

import espacios_indice as espacios
import indice_titulos as titulos
from almacen_bd import conexion, consultar, ejecutar
from seguridad_rutas import raiz_usuario, ruta_fisica

log = logging.getLogger('almacen.indice')

LIMITE_POR_DEFECTO = 50


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para que la búsqueda no dependa de cómo se escriba."""
    if not texto:
        return ''
    descompuesto = unicodedata.normalize('NFD', texto.lower())
    return ''.join(c for c in descompuesto if unicodedata.category(c) != 'Mn')


def asegurar_esquema_indice() -> None:
    """Crea la tabla del índice y sus índices. Idempotente."""
    ejecutar("""
        CREATE TABLE IF NOT EXISTS indice_nombres (
            usuario_id     INTEGER     NOT NULL,
            ruta           TEXT        NOT NULL,
            nombre         TEXT        NOT NULL,
            nombre_norm    TEXT        NOT NULL,
            es_carpeta     BOOLEAN     NOT NULL DEFAULT FALSE,
            extension      TEXT        NOT NULL DEFAULT '',
            tamano         BIGINT      NOT NULL DEFAULT 0,
            modificado_en  TIMESTAMPTZ,
            PRIMARY KEY (usuario_id, ruta)
        )
    """)
    ejecutar("""
        CREATE TABLE IF NOT EXISTS indice_estado (
            usuario_id     INTEGER     PRIMARY KEY,
            elementos      INTEGER     NOT NULL DEFAULT 0,
            reindexado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    try:
        ejecutar("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception as e:                                    # sin superusuario, por ejemplo
        log.warning('indice: no se pudo asegurar pg_trgm (%s); la búsqueda sigue funcionando', e)
    try:
        ejecutar("""CREATE INDEX IF NOT EXISTS idx_indice_nombre_trgm
                    ON indice_nombres USING gin (nombre_norm gin_trgm_ops)""")
    except Exception as e:
        log.warning('indice: sin índice trigram (%s); se usará búsqueda secuencial', e)
    ejecutar("CREATE INDEX IF NOT EXISTS idx_indice_usuario ON indice_nombres (usuario_id)")
    # Título interno (ver `indice_titulos`): hay archivos cuyo nombre lo pone el
    # sistema y cuyo título de verdad vive dentro —los formularios, sin ir más
    # lejos—, y la gente los busca por ese título.
    ejecutar("ALTER TABLE indice_nombres ADD COLUMN IF NOT EXISTS titulo_norm TEXT")
    # `titulo_norm` es para BUSCAR (sin tildes ni mayúsculas) y `titulo` para
    # ENSEÑAR: si solo se guardara el normalizado, el desplegable escribiría
    # «encuesta diagnostica» donde la persona escribió «Encuesta Diagnóstica».
    ejecutar("ALTER TABLE indice_nombres ADD COLUMN IF NOT EXISTS titulo TEXT")
    try:
        ejecutar("""CREATE INDEX IF NOT EXISTS idx_indice_titulo_trgm
                    ON indice_nombres USING gin (titulo_norm gin_trgm_ops)""")
    except Exception as e:
        log.warning('indice: sin índice trigram de títulos (%s)', e)


# ---------------------------------------------------------------------------
# Altas y bajas (se llaman desde el núcleo tras cada operación de archivos)
# ---------------------------------------------------------------------------
def _datos_de(fisica: str, nombre: str):
    """(es_carpeta, extension, tamano, modificado) leídos del disco."""
    es_carpeta = os.path.isdir(fisica)
    extension = '' if es_carpeta or '.' not in nombre else nombre.rsplit('.', 1)[-1].lower()
    try:
        tamano = 0 if es_carpeta else os.path.getsize(fisica)
        modificado = datetime.fromtimestamp(os.path.getmtime(fisica), tz=timezone.utc)
    except OSError:
        tamano, modificado = 0, None
    return es_carpeta, extension, tamano, modificado


def agregar(usuario_id: int, ruta_virtual: str) -> None:
    """Registra (o actualiza) UN elemento. Si es carpeta, también su contenido.

    La fila se guarda en el ESPACIO del archivo (ver `espacios_indice`), no a
    nombre de quien hace la operación: lo de una unidad compartida es de la
    unidad, y lo que otra persona me compartió sigue siendo suyo.
    """
    try:
        fisica = ruta_fisica(usuario_id, ruta_virtual)
        if not os.path.exists(fisica):
            return
        usuario_id, ruta_virtual = espacios.espacio_de(usuario_id, ruta_virtual)
        nombre = os.path.basename(ruta_virtual.rstrip('/'))
        es_carpeta, extension, tamano, modificado = _datos_de(fisica, nombre)
        titulo = titulos.titulo_de(fisica, extension)
        ejecutar("""
            INSERT INTO indice_nombres
                   (usuario_id, ruta, nombre, nombre_norm, es_carpeta, extension,
                    tamano, modificado_en, titulo_norm, titulo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (usuario_id, ruta) DO UPDATE
               SET nombre = EXCLUDED.nombre, nombre_norm = EXCLUDED.nombre_norm,
                   es_carpeta = EXCLUDED.es_carpeta, extension = EXCLUDED.extension,
                   tamano = EXCLUDED.tamano, modificado_en = EXCLUDED.modificado_en,
                   titulo_norm = EXCLUDED.titulo_norm, titulo = EXCLUDED.titulo
        """, (usuario_id, ruta_virtual, nombre, normalizar(nombre),
              es_carpeta, extension, tamano, modificado,
              normalizar(titulo) or None, titulo or None))
        if es_carpeta:
            _indexar_arbol(usuario_id, fisica, ruta_virtual)
    except Exception as e:
        log.warning('indice: no se pudo indexar %s de %s: %s', ruta_virtual, usuario_id, e)


def eliminar(usuario_id: int, ruta_virtual: str) -> None:
    """Da de baja el elemento y todo lo que colgaba de él."""
    try:
        usuario_id, ruta_virtual = espacios.espacio_de(usuario_id, ruta_virtual)
        ejecutar("DELETE FROM indice_nombres WHERE usuario_id = %s AND (ruta = %s OR ruta LIKE %s)",
                 (usuario_id, ruta_virtual, ruta_virtual.rstrip('/') + '/%'))
    except Exception as e:
        log.warning('indice: no se pudo quitar %s de %s: %s', ruta_virtual, usuario_id, e)


def renombrar(usuario_id: int, origen: str, destino: str) -> None:
    """Mueve/renombra en el índice: cambia el elemento y el prefijo de sus hijos."""
    try:
        eliminar(usuario_id, destino)         # por si el destino ya existía
        eliminar(usuario_id, origen)
        agregar(usuario_id, destino)
    except Exception as e:
        log.warning('indice: no se pudo mover %s → %s de %s: %s', origen, destino, usuario_id, e)


# ---------------------------------------------------------------------------
# Reconstrucción completa
# ---------------------------------------------------------------------------
def _indexar_arbol(usuario_id: int, fisica_base: str, ruta_base: str) -> int:
    """Inserta todo lo que cuelga de una carpeta física. Devuelve cuántos elementos."""
    filas = []
    for carpeta, subcarpetas, archivos in os.walk(fisica_base):
        subcarpetas[:] = [c for c in subcarpetas if not c.startswith('.')]
        for nombre in subcarpetas + archivos:
            if nombre.startswith('.'):
                continue
            completo = os.path.join(carpeta, nombre)
            relativa = os.path.relpath(completo, fisica_base).replace(os.sep, '/')
            ruta = (ruta_base.rstrip('/') + '/' + relativa) if ruta_base != '/' else '/' + relativa
            es_carpeta, extension, tamano, modificado = _datos_de(completo, nombre)
            titulo = titulos.titulo_de(completo, extension)
            filas.append((usuario_id, ruta, nombre, normalizar(nombre),
                          es_carpeta, extension, tamano, modificado,
                          normalizar(titulo) or None, titulo or None))
    if not filas:
        return 0
    # Inserción por lotes en UNA sola conexión: reindexar un usuario con miles de
    # archivos no puede abrir una conexión por fila.
    from psycopg2.extras import execute_values
    with conexion() as con:
        with con.cursor() as cur:
            execute_values(cur, """
                INSERT INTO indice_nombres
                       (usuario_id, ruta, nombre, nombre_norm, es_carpeta, extension,
                        tamano, modificado_en, titulo_norm, titulo)
                VALUES %s
                ON CONFLICT (usuario_id, ruta) DO UPDATE
                   SET nombre = EXCLUDED.nombre, nombre_norm = EXCLUDED.nombre_norm,
                       es_carpeta = EXCLUDED.es_carpeta, extension = EXCLUDED.extension,
                       tamano = EXCLUDED.tamano, modificado_en = EXCLUDED.modificado_en,
                       titulo_norm = EXCLUDED.titulo_norm, titulo = EXCLUDED.titulo
            """, filas, page_size=500)
    return len(filas)


def reindexar_usuario(usuario_id: int) -> int:
    """Reconstruye desde cero el índice de un usuario leyendo su disco."""
    base = raiz_usuario(usuario_id, 'archivos')
    ejecutar("DELETE FROM indice_nombres WHERE usuario_id = %s", (usuario_id,))
    total = 0
    if os.path.isdir(base):
        total = _indexar_arbol(usuario_id, base, '/')
    ejecutar("""
        INSERT INTO indice_estado (usuario_id, elementos, reindexado_en)
        VALUES (%s, %s, now())
        ON CONFLICT (usuario_id) DO UPDATE
           SET elementos = EXCLUDED.elementos, reindexado_en = now()
    """, (usuario_id, total))
    log.info('indice: usuario %s reindexado (%d elementos)', usuario_id, total)
    return total


USUARIO_UNIDADES = 0   # dueño-índice del contenido de las unidades compartidas


def reindexar_unidades() -> int:
    """Reconstruye el índice de TODAS las unidades compartidas (12/08/2026).

    Se indexan bajo el usuario-índice 0 con rutas /unidades/<id>/... :
    así el listado puede mostrar el tamaño de las carpetas y la búsqueda
    las cubre. Es trabajo de LOTE (recorre el NFS): se corre desde el cron
    nocturno o a mano, nunca dentro de una petición web."""
    from config_almacen import raiz_datos
    base = os.path.join(raiz_datos(), '_unidades')
    ejecutar("DELETE FROM indice_nombres WHERE usuario_id = %s", (USUARIO_UNIDADES,))
    total = 0
    if os.path.isdir(base):
        for nombre in sorted(os.listdir(base)):
            if not nombre.isdigit():
                continue
            # La raíz VIRTUAL de la unidad es su subcarpeta física
            # «archivos» (papelera y versiones no se indexan).
            fisica = os.path.join(base, nombre, 'archivos')
            if os.path.isdir(fisica):
                total += _indexar_arbol(USUARIO_UNIDADES, fisica, '/unidades/' + nombre)
    ejecutar("""
        INSERT INTO indice_estado (usuario_id, elementos, reindexado_en)
        VALUES (%s, %s, now())
        ON CONFLICT (usuario_id) DO UPDATE
           SET elementos = EXCLUDED.elementos, reindexado_en = now()
    """, (USUARIO_UNIDADES, total))
    log.info('indice: unidades compartidas reindexadas (%d elementos)', total)
    return total


def usuario_indexado(usuario_id: int) -> bool:
    """¿Ya se construyó el índice de este usuario alguna vez?"""
    try:
        filas = consultar("SELECT 1 FROM indice_estado WHERE usuario_id = %s", (usuario_id,))
        return bool(filas)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------
def buscar_nombres(usuario_id: int, termino: str, limite: int = LIMITE_POR_DEFECTO,
                   espacios_permitidos: list = None) -> list:
    """
    Devuelve filas crudas del índice cuyo nombre contiene el término.
    Ordena: primero las que EMPIEZAN por el término, luego carpetas, luego alfabético.

    Busca en TODOS los espacios que la persona puede ver —su unidad, las
    unidades compartidas donde es miembro y lo que otras personas le
    compartieron—, no solo en el suyo: antes un archivo que tenía delante en el
    explorador no salía al buscarlo. El permiso se resuelve en cada búsqueda
    (`espacios_de_busqueda`), así que retirar el acceso lo quita de los
    resultados al instante.

    Se devuelve también `espacio`, porque la ruta guardada es la del dueño y la
    que hay que enseñar depende de por dónde llega la persona.
    """
    patron = '%' + normalizar(termino) + '%'
    inicio = normalizar(termino) + '%'
    if espacios_permitidos is None:
        espacios_permitidos = espacios.espacios_de_busqueda(usuario_id)
    condicion, parametros = espacios.condicion_sql(espacios_permitidos)
    # Orden: primero lo que EMPIEZA por lo escrito; a igualdad, lo de la propia
    # unidad antes que lo de las unidades compartidas —sin esa regla las
    # unidades de la casa, decenas de miles de archivos, llenaban la lista
    # entera—; y a igualdad de nuevo, **lo modificado más recientemente**. Lo
    # último era el orden alfabético, y eso hacía que una carpeta con cuarenta
    # archivos de nombre casi igual (los que acompañan a un vídeo, por ejemplo)
    # se quedara con todos los puestos por delante de lo que la persona buscaba.
    # Se busca por el nombre del archivo Y por su título interno (los
    # formularios se llaman todos «Nuevo Formulario N.forma»: quien creó la
    # «Encuesta Diagnóstica» la busca por ese nombre, que es el que ve al
    # abrirla, no por el que le puso el botón «+ Nuevo»).
    # COALESCE, no `titulo_norm LIKE` a secas: la mayoría de los archivos no
    # tienen título y `NULL LIKE …` vale NULL, no FALSE. En el ORDER BY esos
    # NULL se colocaban ANTES que las coincidencias de verdad (PostgreSQL ordena
    # NULLS FIRST en DESC) y el formulario que sí coincidía se quedaba fuera de
    # los primeros resultados.
    return consultar("""
        SELECT usuario_id AS espacio, ruta, nombre, es_carpeta, extension,
               tamano, modificado_en, titulo_norm, titulo
        FROM indice_nombres
        WHERE %s AND (nombre_norm LIKE %%s OR COALESCE(titulo_norm, '') LIKE %%s)
        ORDER BY (nombre_norm LIKE %%s
                  OR COALESCE(titulo_norm, '') LIKE %%s) DESC,
                 (usuario_id = %%s) DESC, es_carpeta DESC,
                 modificado_en DESC NULLS LAST, nombre
        LIMIT %%s
    """ % condicion,
        tuple(parametros) + (patron, patron, inicio, inicio,
                             int(usuario_id), limite))
