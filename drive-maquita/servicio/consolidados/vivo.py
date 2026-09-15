# -*- coding: utf-8 -*-
"""Consolidados ASC «en vivo»: que un consolidado ABIERTO en el editor reciba
el bloque recién consolidado sin cerrarlo (11/09/2026, pedido de Wilson para
la salida a producción del 28/09).

Cómo: el complemento residente del editor (`respuestas-vivo`) escribe en la
sesión abierta cualquier vínculo de `vinculos_datos` cuyo destino sea el libro
abierto. Aquí, tras cada consolidación, se registra (o se refresca) un
AUTOVÍNCULO por bloque: origen y destino son el MISMO archivo y la misma hoja,
y el rango es el bloque consolidado. Al subir `actualizado_en`, el complemento
lo recoge en la siguiente vuelta (5 s) y copia el bloque del archivo en disco
—que acaba de escribir la consolidación— a la sesión abierta.

Los autovínculos NO los procesa el servidor en ningún otro camino
(`refrescar_por_origen`, `refrescar_por_destino`, listado del panel): son
solo la señal para el complemento. Nunca lanza: si esto falla, la
consolidación ya está escrita y se ve al reabrir, como hasta hoy.
"""
import logging

from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import coordinate_to_tuple

log = logging.getLogger('consolidar-asc.vivo')


def registrar_bloques(usuario, ruta_virtual, hoja, bloques, invalidar=True):
    """`bloques`: lista de (celda_destino, alto, ancho) ya escritos en el archivo."""
    try:
        import almacen_bd as bd
        for celda, alto, ancho in bloques:
            if not alto or not ancho:
                continue
            fila0, col0 = coordinate_to_tuple(celda)
            rango = '%s%d:%s%d' % (get_column_letter(col0), fila0,
                                   get_column_letter(col0 + ancho - 1), fila0 + alto - 1)
            existente = bd.consultar(
                """SELECT id FROM vinculos_datos
                    WHERE origen_ruta = destino_ruta AND destino_ruta = %s
                      AND destino_hoja = %s AND destino_celda = %s""",
                (ruta_virtual, hoja, celda))
            if existente:
                bd.ejecutar(
                    """UPDATE vinculos_datos
                          SET origen_rango = %s, activo = TRUE, actualizado_en = NOW()
                        WHERE id = %s""", (rango, existente[0]['id']))
            else:
                bd.ejecutar(
                    """INSERT INTO vinculos_datos
                       (origen_usuario, origen_ruta, origen_hoja, origen_rango,
                        destino_usuario, destino_ruta, destino_hoja, destino_celda,
                        creado_por, actualizado_en)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())""",
                    (int(usuario), ruta_virtual, hoja, rango,
                     int(usuario), ruta_virtual, hoja, celda, int(usuario)))
        log.info('  en vivo: %d bloque(s) señalados para el editor', len(bloques))
        # El archivo se acaba de reescribir por fuera del editor: sin esto, el
        # Document Server sirve su copia en caché (con la clave de antes) y
        # quien lo abra ve el consolidado anterior. Comprobado el 11/09/2026.
        if not invalidar:
            return          # camino rápido: el disco no cambió, la caché del DS vale
        try:
            from api_onlyoffice import invalidar_cache
            invalidar_cache(int(usuario), ruta_virtual)
        except Exception as excepcion:
            log.warning('  en vivo: no se pudo refrescar la caché del editor (%s)', excepcion)
    except Exception as excepcion:
        log.warning('  en vivo: no se pudo señalar el consolidado (%s)', excepcion)
