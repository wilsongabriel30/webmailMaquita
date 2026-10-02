# -*- coding: utf-8 -*-
"""
Tamaño de las carpetas: lo que ocupan de verdad (02/10/2026)
============================================================
Wilson: «las carpetas son pequeñas y aparecen más grandes». El Drive
deduplica: un mismo contenido subido en varios sitios se guarda UNA vez en
disco (enlace duro, `_publicar_con_dedup`) pero el índice lo sumaba por cada
copia. «Contabilidad General» mostraba 188,6 GB ocupando 113,4 GB.

Aquí el tamaño de cada carpeta hija se calcula contando cada inodo UNA sola
vez dentro de esa carpeta (la columna `inodo` del índice, que rellenan
`indice_busqueda.agregar` y la reconstrucción nocturna). Las filas sin inodo
(índice aún no reconstruido) cuentan como antes, una por archivo.

También se escapan `%` y `_` del prefijo: una carpeta «IBI_2025» sumaba lo de
«IBI 2025» porque `_` en LIKE vale por cualquier carácter.
"""
from almacen_bd import consultar


def _escapar_like(texto: str) -> str:
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def por_hijo(usuario_indice: int, prefijo: str) -> dict:
    """{nombre de carpeta hija: bytes que ocupa de verdad} bajo `prefijo`
    ('' para la raíz). Cada contenido repetido dentro de la hija cuenta una vez."""
    filas = consultar("""
        SELECT hijo, SUM(tamano) AS total
        FROM (
            SELECT DISTINCT ON (hijo, clave) hijo, tamano
            FROM (
                SELECT split_part(substr(ruta, %s), '/', 1) AS hijo,
                       tamano,
                       COALESCE(inodo::text, ruta) AS clave
                FROM indice_nombres
                WHERE usuario_id = %s AND NOT es_carpeta AND ruta LIKE %s ESCAPE '\\'
            ) f
        ) u
        GROUP BY hijo
    """, (len(prefijo) + 2, usuario_indice, _escapar_like(prefijo) + '/%'))
    return {f['hijo']: int(f['total'] or 0) for f in filas}
