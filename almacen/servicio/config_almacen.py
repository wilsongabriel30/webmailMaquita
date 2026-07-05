# -*- coding: utf-8 -*-
"""
Configuración del Almacén Maquita.
Todo valor sale de variables de entorno con un valor por defecto sensato,
para que el mismo código sirva en pruebas, piloto y producción.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import os

# ── Disco ────────────────────────────────────────────────────────────────
# Raíz donde viven los archivos: <raiz>/<usuario_id>/archivos|papelera|retencion|versiones
# El valor por defecto (env) es el arranque; el master puede CAMBIARLO en caliente desde
# Configuración → Almacenamiento (se guarda en la tabla config_kv). Esto permite apuntar los
# datos a un disco USB, un NAS, una carpeta de red o una nube montada, sin tocar el código.
RAIZ_DATOS_DEFAULT = os.getenv('ALMACEN_RAIZ_DATOS', '/opt/maquita-webmail/almacen/datos')

_raiz_cache = {'valor': None}


def raiz_datos() -> str:
    """Raíz ACTIVA de los datos. Lee config_kv['raiz_datos'] (elegida por el master);
    si no hay o falla, usa el valor por defecto. Cacheada; set_raiz_datos la invalida."""
    if _raiz_cache['valor']:
        return _raiz_cache['valor']
    valor = RAIZ_DATOS_DEFAULT
    try:
        from almacen_bd import consultar
        filas = consultar("SELECT valor FROM config_kv WHERE clave = 'raiz_datos'")
        if filas and filas[0]['valor']:
            valor = filas[0]['valor']
    except Exception:
        pass
    _raiz_cache['valor'] = valor
    return valor


def set_raiz_datos(nueva_ruta: str) -> None:
    """Fija la raíz de datos (la guarda en BD y refresca la caché en memoria)."""
    from almacen_bd import ejecutar
    ejecutar("""
        INSERT INTO config_kv (clave, valor) VALUES ('raiz_datos', %s)
        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
    """, (nueva_ruta,))
    _raiz_cache['valor'] = nueva_ruta


# Compatibilidad: algunos módulos aún importan RAIZ_DATOS como constante de arranque.
RAIZ_DATOS = RAIZ_DATOS_DEFAULT

# ── Base de datos (metadatos: compartidos, papelera, favoritos, cuotas) ──
BD = {
    'host': os.getenv('ALMACEN_DB_HOST', '127.0.0.1'),
    'dbname': os.getenv('ALMACEN_DB_NAME', 'almacen'),
    'user': os.getenv('ALMACEN_DB_USER', 'almacen'),
    'password': os.getenv('ALMACEN_DB_PASSWORD', ''),
}

# Base de nómina (solo LECTURA: búsqueda de usuarios para compartir)
BD_NOMINA = {
    'host': os.getenv('NOMINA_DB_HOST', '127.0.0.1'),
    'dbname': os.getenv('NOMINA_DB_NAME', 'almacen'),
    'user': os.getenv('NOMINA_DB_USER', 'almacen'),
    'password': os.getenv('NOMINA_DB_PASSWORD', ''),
}

# ── Límites ──────────────────────────────────────────────────────────────
CUOTA_DEFECTO_BYTES = int(os.getenv('ALMACEN_CUOTA_DEFECTO', 20 * 1024 ** 3))  # 20 GB por defecto


def cuota_defecto_bytes() -> int:
    """Cuota por defecto de un usuario nuevo. El master puede cambiarla desde Configuración
    (se guarda en config_kv); si no, 20 GB."""
    try:
        from almacen_bd import consultar
        filas = consultar("SELECT valor FROM config_kv WHERE clave = 'cuota_defecto_bytes'")
        if filas and filas[0]['valor']:
            return int(filas[0]['valor'])
    except Exception:
        pass
    return CUOTA_DEFECTO_BYTES
TAMANO_MAX_SUBIDA = int(os.getenv('ALMACEN_MAX_SUBIDA', 16 * 1024 ** 3))      # 16 GB (igual que nginx)

# Red de seguridad: cuando el usuario VACÍA su papelera, lo eliminado se guarda
# en una retención que SOLO un master puede recuperar, durante estos días.
# Es la "recuperación en minutos" que ofrecemos frente al soporte externo.
RETENCION_DIAS = int(os.getenv('ALMACEN_RETENCION_DIAS', 90))

# Clave de sesión del servicio (en producción se comparte con el sistema central para SSO)
CLAVE_SESION = os.getenv('ALMACEN_CLAVE_SESION', 'cambiar-en-produccion-almacen')

# URL pública del servicio (para armar enlaces compartidos)
URL_PUBLICA = os.getenv('ALMACEN_URL_PUBLICA', 'http://localhost')
