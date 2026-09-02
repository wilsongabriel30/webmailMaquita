"""Ajustes de compartición por elemento, estilo Drive.

Responsabilidad ÚNICA: leer y escribir los ajustes de la tabla
`ajustes_compartir`, y resolver si un elemento queda fuera del alcance del
enlace de una carpeta superior.

Contexto de los dos ajustes (hallazgos CO-02 y CO-03 de la auditoría 1:1):

- `acceso_limitado` — «Limitar el acceso a NOMBRE». Quien llegue por el enlace
  de una carpeta que lo contiene deja de verlo. El acceso DIRECTO a ese
  elemento (compartido explícitamente) sigue funcionando, que es exactamente lo
  que hace Drive.

- `editores_comparten` — «Permitir que los editores cambien los permisos y lo
  compartan». Se guarda, pero HOY NO TIENE EFECTO: en `POST /compartir` el
  `propietario_id` es siempre quien llama, así que un editor no puede
  recompartir nada. Cuando se construya esa capacidad, este es el interruptor
  que debe consultarse. No exponer la casilla en la interfaz hasta entonces:
  una casilla que no hace nada es peor que no tenerla.
"""

from almacen_bd import consultar, ejecutar

POR_DEFECTO = {'acceso_limitado': False, 'editores_comparten': False}


def obtener(propietario_id, ruta):
    """Ajustes de un elemento. Sin fila -> valores por defecto."""
    filas = consultar(
        'SELECT acceso_limitado, editores_comparten FROM ajustes_compartir '
        'WHERE propietario_id = %s AND ruta = %s',
        (int(propietario_id), ruta))
    if not filas:
        return dict(POR_DEFECTO)
    fila = dict(filas[0])
    return {'acceso_limitado': bool(fila['acceso_limitado']),
            'editores_comparten': bool(fila['editores_comparten'])}


def establecer(propietario_id, ruta, acceso_limitado=None, editores_comparten=None):
    """Guarda los ajustes indicados; los omitidos se dejan como estaban."""
    actual = obtener(propietario_id, ruta)
    if acceso_limitado is None:
        acceso_limitado = actual['acceso_limitado']
    if editores_comparten is None:
        editores_comparten = actual['editores_comparten']
    ejecutar(
        'INSERT INTO ajustes_compartir '
        '(propietario_id, ruta, acceso_limitado, editores_comparten, actualizado_en) '
        'VALUES (%s, %s, %s, %s, NOW()) '
        'ON CONFLICT (propietario_id, ruta) DO UPDATE SET '
        'acceso_limitado = EXCLUDED.acceso_limitado, '
        'editores_comparten = EXCLUDED.editores_comparten, '
        'actualizado_en = NOW()',
        (int(propietario_id), ruta, bool(acceso_limitado), bool(editores_comparten)))
    return {'acceso_limitado': bool(acceso_limitado),
            'editores_comparten': bool(editores_comparten)}


def bloqueado_bajo(propietario_id, raiz, ruta_destino):
    """¿`ruta_destino` queda fuera del alcance del enlace de la carpeta `raiz`?

    Se comprueba cada nivel entre `raiz` (excluida) y `ruta_destino` (incluida):
    basta con que uno solo esté limitado para cortar el acceso, igual que en
    Drive, donde limitar una carpeta corta también lo que hay dentro.

    `raiz` nunca se comprueba: quien tiene el enlace de la carpeta compartida sí
    debe poder abrirla; limitarla se hace revocando ese enlace.
    """
    raiz = (raiz or '/').rstrip('/')
    destino = (ruta_destino or '/').rstrip('/')
    if not destino or destino == raiz:
        return False

    restantes = destino[len(raiz):].strip('/')
    if not restantes:
        return False

    acumulado = raiz
    niveles = []
    for parte in restantes.split('/'):
        acumulado = acumulado + '/' + parte
        niveles.append(acumulado)
    if not niveles:
        return False

    marcadores = ','.join(['%s'] * len(niveles))
    filas = consultar(
        'SELECT 1 FROM ajustes_compartir WHERE propietario_id = %s '
        'AND acceso_limitado = TRUE AND ruta IN (' + marcadores + ') LIMIT 1',
        tuple([int(propietario_id)] + niveles))
    return bool(filas)
