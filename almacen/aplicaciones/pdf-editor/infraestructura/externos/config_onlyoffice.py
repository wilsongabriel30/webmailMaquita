# -*- coding: utf-8 -*-
"""
Lectura de la configuración del OnlyOffice Document Server dedicado.
====================================================================
El secreto y las URLs del Document Server (VM 131) ya viven en la tabla
`config_kv` de la base `almacen`, que es de donde los lee el Almacén Maquita.
El Editor PDF los lee del MISMO sitio en lugar de duplicarlos: si Tecnología
rota el secreto, se rota una sola vez y los dos módulos se enteran.

Claves usadas: `onlyoffice_secret`, `onlyoffice_url_publica`,
`onlyoffice_url_interna`.

El valor se cachea en memoria unos minutos: se consulta en cada apertura de
documento y no tiene sentido ir a la base cada vez. Si algo falla se devuelve
cadena vacía y quien llama decide (el API responde 503 y el editor avisa al
usuario, en vez de romperse).

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

_SEGUNDOS_CACHE = 300
_cache = {}     # clave -> (valor, momento)

# Conexión a la base del Almacén. Se puede sobreescribir por entorno sin tocar
# código (por ejemplo si la base se muda de servidor).
_URI = os.getenv('ALMACEN_DATABASE_URI', '')


def valor_config_kv(clave):
    """Valor de `config_kv` en la base del Almacén, o '' si no se puede leer."""
    guardado = _cache.get(clave)
    if guardado and (time.time() - guardado[1]) < _SEGUNDOS_CACHE:
        return guardado[0]

    valor = ''
    try:
        import psycopg2
        conexion = psycopg2.connect(_URI, connect_timeout=5)
        try:
            with conexion.cursor() as cursor:
                cursor.execute('SELECT valor FROM config_kv WHERE clave = %s', (clave,))
                fila = cursor.fetchone()
                if fila and fila[0]:
                    valor = str(fila[0]).strip()
        finally:
            conexion.close()
    except Exception as excepcion:
        logger.warning('config_kv[%s] no se pudo leer: %s', clave, excepcion)
        # Si había un valor viejo cacheado, mejor eso que nada
        if guardado:
            return guardado[0]

    _cache[clave] = (valor, time.time())
    return valor
