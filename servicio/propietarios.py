# -*- coding: utf-8 -*-
"""
Propietario real de cada archivo y carpeta del listado (02/10/2026)
==================================================================
Wilson: «en algunos archivos o carpetas salgo yo como propietario y no lo soy,
sobre todo en unidades compartidas». El listado no enviaba `propietario_*` y
la interfaz ponía «yo» por defecto en TODO: en las unidades compartidas y
dentro de las carpetas que otra persona te compartió.

Reglas (por cada item, según su propia ruta):
- Unidad compartida (`/unidades/<id>/…`): propietario = quien lo subió, creó,
  copió o movió ahí (primer registro de alta en `actividad`). Si fue la propia
  persona, no se anota nada (la interfaz muestra «yo»). Si no hay registro
  (contenido migrado por fuera de la API), el propietario es la unidad misma.
- Espacio de otra persona (`/compartido/<dueño>/…`): propietario = el dueño.
- Espacio propio: nada (es «yo»).

Nunca lanza: si algo falla, los items salen como hasta ahora.
"""
import logging

from almacen_bd import consultar
from permisos_compartidos import compartido_de_ruta
from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.propietarios')

ACCIONES_ALTA = ('subio', 'creo_carpeta', 'copio', 'creo', 'convirtio', 'movio')


def _autores(rutas: list) -> dict:
    """{ruta: usuario_id del primer alta registrada}."""
    if not rutas:
        return {}
    filas = consultar("""
        SELECT DISTINCT ON (ruta) ruta, usuario_id
        FROM actividad
        WHERE accion = ANY(%s) AND ruta = ANY(%s)
        ORDER BY ruta, creado_en
    """, (list(ACCIONES_ALTA), rutas))
    return {f['ruta']: int(f['usuario_id']) for f in filas}


def _nombres_unidades(ids: set) -> dict:
    if not ids:
        return {}
    filas = consultar("SELECT id, nombre FROM unidades_compartidas WHERE id = ANY(%s)", (list(ids),))
    return {int(f['id']): f['nombre'] for f in filas}


def _poner(item: dict, persona: dict, usuario_id):
    item['propietario_id'] = usuario_id
    item['propietario_nombre'] = persona.get('nombre') or f'Usuario {usuario_id}'
    item['propietario_email'] = persona.get('email') or ''


def anotar(items: list, usuario_actual: int) -> None:
    """Añade propietario_id / propietario_nombre / propietario_email a los
    items que NO son de la persona que mira. Modifica la lista en sitio."""
    try:
        from vista_compartidos import _nombres_de
        pendientes_unidad = []      # (item, unidad_id)
        por_dueno = {}              # item -> dueño del espacio compartido
        for item in items:
            ruta = item.get('ruta_completa') or item.get('ruta') or ''
            unidad_id, _ = unidad_de_ruta(ruta)
            if unidad_id is not None:
                pendientes_unidad.append((item, unidad_id))
                continue
            dueno, _ = compartido_de_ruta(ruta)
            if dueno is not None and int(dueno) != int(usuario_actual):
                por_dueno[id(item)] = (item, int(dueno))
        if not pendientes_unidad and not por_dueno:
            return

        autores = _autores([it.get('ruta_completa') or it.get('ruta') for it, _ in pendientes_unidad])
        ids_personas = {d for _, d in por_dueno.values()}
        ids_personas |= {a for a in autores.values() if a != int(usuario_actual)}
        personas = _nombres_de(ids_personas) if ids_personas else {}
        unidades = _nombres_unidades({u for _, u in pendientes_unidad})

        for item, dueno in por_dueno.values():
            _poner(item, personas.get(dueno) or {}, dueno)
        for item, unidad_id in pendientes_unidad:
            autor = autores.get(item.get('ruta_completa') or item.get('ruta'))
            if autor is None:
                item['propietario_id'] = None
                item['propietario_nombre'] = unidades.get(unidad_id) or 'Unidad compartida'
                item['propietario_email'] = ''
                item['propietario_es_unidad'] = True
            elif autor != int(usuario_actual):
                _poner(item, personas.get(autor) or {}, autor)
    except Exception as excepcion:
        log.warning('propietarios: no se pudieron anotar (%s)', excepcion)
