"""¿Puede este usuario REFERENCIAR (leer) esta hoja de cálculo?

Responsabilidad ÚNICA: decidir el permiso de lectura para las referencias entre
libros (IMPORTRANGE), que es la función que más se usa del Drive.

Existe porque `api_vinculos.puede_leer()` sola no basta: solo reconoce el
compartido de RUTA EXACTA al correo, y deja fuera dos casos legítimos que sí
deben funcionar:

  1. **Unidades compartidas.** En `/unidades/<id>/...` el espacio es de la
     organización, no de una persona: `seguridad_rutas.ruta_fisica()` ignora el
     `usuario_id` en esas rutas. Quien manda ahí es la MEMBRESÍA de la unidad,
     no el dueño que venga en el `fileKey`.

  2. **Libro dentro de una CARPETA compartida.** Si me comparten `/Proyectos`,
     debo poder referenciar `/Proyectos/datos.xlsx`. `puede_leer()` compara la
     ruta exacta y lo rechazaría.

Se respeta «Limitar el acceso» (CO-03): un elemento marcado no se alcanza a
través del compartido de una carpeta superior.

IMPORTANTE sobre la consulta por prefijo: el parámetro del cliente va SIEMPRE en
el lado izquierdo del LIKE (`%s LIKE ruta || '/%%'`). Al revés, un `%` en la
ruta enviada actuaría de comodín y convertiría el filtro en un colador.
"""

import logging

from almacen_bd import consultar, es_master
from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.permisos_referencia')


def _correo(usuario_id):
    filas = consultar('SELECT LOWER(email) AS email FROM usuarios WHERE id = %s',
                      (int(usuario_id),), nomina=True)
    return filas[0]['email'] if filas and filas[0]['email'] else None


def puede_referenciar(usuario_id, dueno_id, ruta):
    """(permitido: bool, motivo: str). Falla CERRADO: ante cualquier error, False."""
    try:
        usuario_id = int(usuario_id)
        dueno_id = int(dueno_id)

        # 1) Unidad compartida: manda la membresía, no el dueño del fileKey.
        unidad_id, _ = unidad_de_ruta(ruta)
        if unidad_id is not None:
            from api_unidades import rol_en_unidad
            if rol_en_unidad(usuario_id, unidad_id) is not None:
                return True, 'miembro de la unidad'
            return False, 'no es miembro de la unidad'

        # 2) Su propio espacio.
        if usuario_id == dueno_id:
            return True, 'es suyo'

        # 3) Master.
        try:
            if es_master(usuario_id):
                return True, 'master'
        except Exception:
            pass

        # 4) Compartido a su correo: la ruta pedida o una carpeta superior.
        correo = _correo(usuario_id)
        if not correo:
            return False, 'sin correo'

        filas = consultar(
            "SELECT ruta FROM compartidos "
            "WHERE propietario_id = %s AND LOWER(email) = %s "
            "AND (expira_en IS NULL OR expira_en > NOW()) "
            "AND (ruta = %s OR %s LIKE ruta || '/%%') "
            "ORDER BY LENGTH(ruta) DESC LIMIT 1",
            (dueno_id, correo, ruta, ruta))
        if not filas:
            return False, 'sin compartido vigente'

        origen = filas[0]['ruta']
        if origen != ruta:
            # Llega por herencia de una carpeta: respeta «Limitar el acceso».
            from ajustes_compartir import bloqueado_bajo
            if bloqueado_bajo(dueno_id, origen, ruta):
                return False, 'acceso limitado por el dueño'
        return True, 'compartido'
    except Exception as excepcion:
        log.warning('puede_referenciar falló (se deniega): %s', excepcion)
        return False, 'error al comprobar'
