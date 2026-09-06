# -*- coding: utf-8 -*-
"""
Base de datos del Almacén Maquita (metadatos).
==============================================
Los ARCHIVOS viven en el filesystem (fuente de verdad); PostgreSQL guarda
solo lo que el disco no sabe: compartidos, papelera, favoritos y cuotas.
Esa separación evita, por diseño, los des-sincronismos clásicos.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

from config_almacen import BD, BD_NOMINA

log = logging.getLogger('almacen.bd')

_pool = None          # conexiones a la BD propia (almacen)
_pool_nomina = None   # conexiones de SOLO LECTURA a nomina (búsqueda de usuarios)


def _obtener_pool():
    """Pool perezoso hacia la BD del almacén."""
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(minconn=1, maxconn=8, **BD)
    return _pool


def _obtener_pool_nomina():
    """Pool perezoso de solo lectura hacia nómina."""
    global _pool_nomina
    if _pool_nomina is None:
        _pool_nomina = SimpleConnectionPool(minconn=1, maxconn=4, **BD_NOMINA)
    return _pool_nomina


def _conexion_viva(con) -> bool:
    """True si la conexión responde a un SELECT 1. Las conexiones idle a la BD
    remota se cortan (SSL closed) y el pool las reutilizaba muertas → 500."""
    try:
        con.reset() if con.closed else None
        with con.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        con.rollback()
        return True
    except Exception:
        return False


@contextmanager
def conexion(nomina: bool = False):
    """Presta una conexión del pool, VALIDÁNDOLA antes de usarla; si está
    caída la descarta y toma/crea otra. commit al salir bien, rollback si falla."""
    pool = _obtener_pool_nomina() if nomina else _obtener_pool()
    con = pool.getconn()
    if con.closed or not _conexion_viva(con):
        # conexión muerta: descartarla del pool y pedir/crear una nueva
        try:
            pool.putconn(con, close=True)
        except Exception:
            pass
        con = pool.getconn()
        if con.closed or not _conexion_viva(con):
            # segunda muerta: reponerla también y crear una fresca fuera del pool
            try:
                pool.putconn(con, close=True)
            except Exception:
                pass
            con = pool.getconn()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        pool.putconn(con)


def consultar(sql: str, parametros=None, nomina: bool = False):
    """SELECT que devuelve lista de diccionarios."""
    with conexion(nomina=nomina) as con:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, parametros or ())
            return cur.fetchall()


def ejecutar(sql: str, parametros=None):
    """INSERT/UPDATE/DELETE. Devuelve la primera fila si hay RETURNING."""
    with conexion() as con:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, parametros or ())
            try:
                return cur.fetchone()
            except psycopg2.ProgrammingError:
                return None


_cache_roles = {}   # usuario_id -> rol (los roles casi no cambian)


def rol_usuario(usuario_id: int) -> str:
    """Rol del usuario en el directorio (master, master_admin, admin, user...), leído de nómina.
    Cacheado en memoria porque cambia rara vez."""
    usuario_id = int(usuario_id)
    if usuario_id in _cache_roles:
        return _cache_roles[usuario_id]
    filas = consultar('SELECT role FROM usuarios WHERE id = %s', (usuario_id,), nomina=True)
    rol = (filas[0]['role'] if filas else 'user') or 'user'
    _cache_roles[usuario_id] = rol
    return rol


def es_master(usuario_id: int) -> bool:
    """True si el usuario puede administrar/recuperar archivos de CUALQUIER persona."""
    return rol_usuario(usuario_id) in ('master', 'master_admin')


def asegurar_esquema():
    """Crea las tablas si no existen. Idempotente; se llama al arrancar."""
    with conexion() as con:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS compartidos (
                    id SERIAL PRIMARY KEY,
                    propietario_id INTEGER NOT NULL,
                    ruta TEXT NOT NULL,
                    tipo SMALLINT NOT NULL,          -- 0=usuario, 1=grupo, 3=enlace público
                    destinatario TEXT,               -- usuario/grupo destino (tipos 0 y 1)
                    token TEXT UNIQUE,               -- enlaces públicos (tipo 3)
                    permisos SMALLINT NOT NULL DEFAULT 1,   -- 1=leer, +2 editar, +4 crear, +8 borrar
                    clave_hash TEXT,                 -- clave opcional del enlace
                    expira_en TIMESTAMPTZ,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_compartidos_propietario
                    ON compartidos(propietario_id);
                CREATE INDEX IF NOT EXISTS idx_compartidos_destinatario
                    ON compartidos(destinatario) WHERE destinatario IS NOT NULL;
                -- ¿el enlace/compartido permite descargar y copiar? (control tipo Drive)
                ALTER TABLE compartidos ADD COLUMN IF NOT EXISTS permite_descarga BOOLEAN NOT NULL DEFAULT TRUE;
                -- Compartir con una PERSONA por correo (interno o externo) y su permiso
                ALTER TABLE compartidos ADD COLUMN IF NOT EXISTS email VARCHAR(255);
                ALTER TABLE compartidos ADD COLUMN IF NOT EXISTS puede_editar BOOLEAN NOT NULL DEFAULT FALSE;
                -- [F-07] version del compartido: las capacidades emitidas la llevan y caducan al cambiar
                ALTER TABLE compartidos ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
                -- [F-08] intentos fallidos de clave por enlace + IP
                CREATE TABLE IF NOT EXISTS compartidos_intentos (
                    token TEXT NOT NULL, ip TEXT NOT NULL, ventana BIGINT NOT NULL,
                    n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (token, ip, ventana));
                ALTER TABLE compartidos ADD COLUMN IF NOT EXISTS accesos INTEGER NOT NULL DEFAULT 0;

                CREATE TABLE IF NOT EXISTS papelera (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    ruta_original TEXT NOT NULL,     -- dónde estaba (para restaurar)
                    nombre TEXT NOT NULL,
                    nombre_fisico TEXT NOT NULL,     -- nombre único dentro de la papelera
                    es_carpeta BOOLEAN NOT NULL DEFAULT FALSE,
                    tamano_bytes BIGINT NOT NULL DEFAULT 0,
                    eliminado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_papelera_usuario ON papelera(usuario_id);

                CREATE TABLE IF NOT EXISTS favoritos (
                    usuario_id INTEGER NOT NULL,
                    ruta TEXT NOT NULL,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (usuario_id, ruta)
                );

                CREATE TABLE IF NOT EXISTS cuotas (
                    usuario_id INTEGER PRIMARY KEY,
                    limite_bytes BIGINT NOT NULL
                );

                -- Uso de disco cacheado (recalcular el arbol sobre NFS es caro)
                CREATE TABLE IF NOT EXISTS cuotas_uso (
                    usuario_id INTEGER PRIMARY KEY,
                    usado_bytes BIGINT NOT NULL DEFAULT 0,
                    calculado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                -- Configuración clave/valor del motor (ej: raiz_datos = dónde se guardan los archivos)
                CREATE TABLE IF NOT EXISTS config_kv (
                    clave VARCHAR(50) PRIMARY KEY,
                    valor TEXT
                );

                -- Actividad reciente / auditoría (quién hizo qué sobre qué archivo)
                CREATE TABLE IF NOT EXISTS actividad (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    accion VARCHAR(30) NOT NULL,      -- subio, elimino, renombro, movio, copio, compartio, restauro, comento, creo_carpeta
                    ruta TEXT,
                    detalle TEXT,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_actividad_usuario ON actividad(usuario_id, creado_en DESC);
                CREATE INDEX IF NOT EXISTS idx_actividad_ruta ON actividad(ruta);

                -- Comentarios en archivos/carpetas (colaboración estilo Drive)
                CREATE TABLE IF NOT EXISTS comentarios (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    ruta TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_comentarios_ruta ON comentarios(ruta, creado_en);

                -- Unidades Compartidas (drives de equipo, propiedad de la organización)
                CREATE TABLE IF NOT EXISTS unidades_compartidas (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(150) NOT NULL,
                    creado_por INTEGER NOT NULL,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                -- Miembros y su rol: manager (gestiona todo), editor (sube/edita/borra), viewer (solo ve)
                CREATE TABLE IF NOT EXISTS unidad_miembros (
                    unidad_id INTEGER NOT NULL REFERENCES unidades_compartidas(id) ON DELETE CASCADE,
                    usuario_id INTEGER NOT NULL,
                    rol VARCHAR(20) NOT NULL DEFAULT 'editor',
                    PRIMARY KEY (unidad_id, usuario_id)
                );
                CREATE INDEX IF NOT EXISTS idx_unidad_miembros_usuario ON unidad_miembros(usuario_id);

                -- Deduplicación: por cada contenido (hash) guardamos UNA ruta
                -- canónica. Subir un archivo idéntico crea un enlace duro a ella
                -- en vez de otra copia → ahorro de disco. El contador de enlaces
                -- del filesystem protege los datos: borrar el de un usuario nunca
                -- afecta al de otro (son el mismo inodo, refcuenta el sistema).
                CREATE TABLE IF NOT EXISTS contenidos (
                    hash TEXT PRIMARY KEY,        -- SHA-256 del contenido
                    ruta_canonica TEXT NOT NULL,  -- ruta física de la primera copia
                    tamano_bytes BIGINT NOT NULL,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                -- Retención: lo que el usuario VACÍA de su papelera no se destruye,
                -- se guarda aquí. Solo un master lo recupera, hasta RETENCION_DIAS.
                CREATE TABLE IF NOT EXISTS retencion (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    ruta_original TEXT NOT NULL,
                    nombre TEXT NOT NULL,
                    nombre_fisico TEXT NOT NULL,   -- nombre único dentro de la zona retención
                    es_carpeta BOOLEAN NOT NULL DEFAULT FALSE,
                    tamano_bytes BIGINT NOT NULL DEFAULT 0,
                    eliminado_definitivo_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_retencion_usuario ON retencion(usuario_id);
                CREATE INDEX IF NOT EXISTS idx_retencion_fecha ON retencion(eliminado_definitivo_en);

                -- Versiones: cada vez que se re-sube un archivo a la misma ruta,
                -- la copia anterior se conserva aquí (como el historial de Drive).
                CREATE TABLE IF NOT EXISTS versiones (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,         -- id estable del archivo (hash de su ruta)
                    ruta TEXT NOT NULL,            -- ruta virtual actual del archivo
                    version_fisico TEXT NOT NULL,  -- nombre único en la zona 'versiones'
                    tamano_bytes BIGINT NOT NULL DEFAULT 0,
                    guardar_siempre BOOLEAN NOT NULL DEFAULT FALSE,  -- "keep forever"
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_versiones_file ON versiones(usuario_id, file_id);

                -- Estilo de carpeta (color / icono), como los colores de carpeta de Drive.
                CREATE TABLE IF NOT EXISTS estilos_carpeta (
                    usuario_id INTEGER NOT NULL,
                    folder_id TEXT NOT NULL,       -- id estable de la carpeta
                    color VARCHAR(20),
                    icono VARCHAR(50),
                    PRIMARY KEY (usuario_id, folder_id)
                );
            """)
    log.info('Esquema del Almacén verificado')
