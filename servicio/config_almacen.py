# -*- coding: utf-8 -*-
"""
Configuración del Almacén Maquita.
Todo valor sale de variables de entorno con un valor por defecto sensato,
para que el mismo código sirva en pruebas, piloto y producción.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
import os

# ── Disco ────────────────────────────────────────────────────────────────
# Raíz donde viven los archivos: <raiz>/<usuario_id>/archivos|papelera|retencion|versiones
# El valor por defecto (env) es el arranque; el master puede CAMBIARLO en caliente desde
# Configuración → Almacenamiento (se guarda en la tabla config_kv). Esto permite apuntar los
# datos a un disco USB, un NAS, una carpeta de red o una nube montada, sin tocar el código.
_log = logging.getLogger('almacen.config')

# Por defecto, el almacenamiento REAL (NFS de 25 TB servido por 193.16.0.26).
# Antes el valor por defecto era una carpeta local vacia; ver la nota de
# seguridad en raiz_datos().
RAIZ_DATOS_DEFAULT = os.getenv('ALMACEN_RAIZ_DATOS', '/mnt/almacen')

# Archivo centinela que SOLO existe en el almacenamiento de verdad. Es la
# forma fiable de distinguir «el NFS esta montado» de «el NFS se cayo y
# estoy viendo el directorio local vacio que hay debajo»: comprobar si el
# directorio existe no sirve —existe igual— y comprobar si esta vacio
# tampoco, porque un almacen recien creado tambien lo esta.
CENTINELA = '.almacen-maquita'

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
    except Exception as excepcion:
        # Antes esto era un `pass` silencioso. Si la BD no respondia, se caia
        # al valor por defecto sin que nadie se enterara. Ahora al menos queda
        # constancia; la validacion de abajo es la que impide el desastre.
        _log.error('No se pudo leer la raiz de datos de la BD (%s); '
                   'se usa el valor por defecto %s', excepcion, valor)

    # ── VALIDACION: esto es lo que evita escribir en el sitio equivocado ──
    # Sin esta comprobacion, un NFS caido o una BD lenta hacian que el Almacen
    # apuntara a un directorio local vacio: el Drive se veia VACIO y las
    # subidas nuevas se escribian ahi, partiendo la informacion en dos sitios.
    # Se prefiere FALLAR A LA VISTA antes que guardar datos donde no van: un
    # error se arregla en minutos, datos repartidos en dos discos no.
    centinela = os.path.join(valor, CENTINELA)
    if not os.path.exists(centinela):
        _log.critical('ALMACENAMIENTO NO DISPONIBLE: falta %s. '
                      'Lo normal es que el montaje se haya caido. NO se '
                      'escribe nada hasta que vuelva.', centinela)
        raise RuntimeError(
            'El almacenamiento del Drive no esta disponible (falta %s). '
            'Avisa a Tecnologia: probablemente se desmonto %s.'
            % (CENTINELA, valor))

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
    'host': os.getenv('ALMACEN_DB_HOST', '193.16.0.132'),
    'dbname': os.getenv('ALMACEN_DB_NAME', 'almacen'),
    'user': os.getenv('ALMACEN_DB_USER', 'sistemas'),
    'password': os.getenv('ALMACEN_DB_PASSWORD', 'Csimcchg2025.'),
}

# Base de nómina (solo LECTURA: búsqueda de usuarios para compartir)
BD_NOMINA = {
    'host': os.getenv('NOMINA_DB_HOST', '193.16.0.132'),
    'dbname': os.getenv('NOMINA_DB_NAME', 'nomina'),
    'user': os.getenv('NOMINA_DB_USER', 'sistemas'),
    'password': os.getenv('NOMINA_DB_PASSWORD', 'Csimcchg2025.'),
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
TAMANO_MAX_SUBIDA = int(os.getenv('ALMACEN_MAX_SUBIDA', 25 * 1024 ** 3))      # 25 GB (igual que nginx)

# Red de seguridad: cuando el usuario VACÍA su papelera, lo eliminado se guarda
# en una retención que SOLO un master puede recuperar, durante estos días.
# Es la "recuperación en minutos" que ofrecemos frente al soporte externo.
RETENCION_DIAS = int(os.getenv('ALMACEN_RETENCION_DIAS', 90))
# Unidades compartidas: contenido de uso COMUN, riesgo mas alto -> 120 dias.
RETENCION_DIAS_UNIDADES = int(os.getenv('ALMACEN_RETENCION_DIAS_UNIDADES', 120))

# Clave de sesión del servicio (en producción se comparte con FARO para SSO)
CLAVE_SESION = os.getenv('ALMACEN_CLAVE_SESION', 'cambiar-en-produccion-almacen')

# URL pública del servicio (para armar enlaces compartidos)
URL_PUBLICA = os.getenv('ALMACEN_URL_PUBLICA', 'https://datos.maquita.com.ec')
# Dominio para los ENLACES COMPARTIDOS que ven las personas (estilo Workspace):
# drive.maquita.com.ec (2026-07-24). Los callbacks internos de OnlyOffice siguen
# usando URL_PUBLICA (datos) porque el Document Server resuelve ese dominio.
URL_LINKS = os.getenv('ALMACEN_URL_LINKS', 'https://drive.maquita.com.ec')
