"""Rutas, umbrales y lectura del .env del backend."""
import os

BASE_BACKEND = '/opt/maquita-webmail/backend'
ARCHIVO_ENV = os.path.join(BASE_BACKEND, '.env')
ARCHIVO_ORG = '/etc/maquita-mail/organizacion.env'
ARCHIVO_NOMBRES = '/var/lib/maquita-webmail/nombres.json'
DIR_INFORMES = '/var/lib/maquita-webmail/revision-telemetria'
SERVICIO_JOURNAL = 'maquita-webmail'
ZONA_HORARIA = 'America/Guayaquil'

SENDMAIL = '/usr/sbin/sendmail'

# Umbrales (en una sola parte para ajustarlos sin tocar la lógica)
HORAS_VENTANA = 24
BUSQUEDA_LENTA_MS = 5000
REINTENTOS_MINIMO = 5          # misma ruta POST fallando más de N veces
LLM_LENTO_MS = 20000
ERRORES_JS_MINIMO_ALTO = 5     # a partir de aquí el error JS pasa a gravedad alta


def leer_env(clave, archivo=ARCHIVO_ENV, defecto=None):
    """Devuelve el valor de una clave del .env sin cargar todo el entorno."""
    try:
        with open(archivo, encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if linea.startswith(clave + '='):
                    return linea.split('=', 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return os.environ.get(clave, defecto)


def dsn_postgres():
    return leer_env('DATABASE_URL').replace('+asyncpg', '')


def url_redis():
    return leer_env('REDIS_URL', defecto='redis://localhost:6379/0')


def _org(clave, defecto=''):
    """Datos de la organización: organizacion.env y, si no están, el .env del backend."""
    return leer_env(clave, ARCHIVO_ORG) or leer_env(clave, defecto=defecto)


# Fuera del código (07/11/2026): el repositorio es público.
DESTINO_CORREO = _org('TELEMETRIA_DESTINO')
REMITENTE_CORREO = _org('TELEMETRIA_REMITENTE')   # debe estar exento del DLP
CUENTAS_PRUEBA = set(_org('TELEMETRIA_CUENTAS_PRUEBA').replace(',', ' ').split())
URL_CORREO = _org('ORG_URL_CORREO')
