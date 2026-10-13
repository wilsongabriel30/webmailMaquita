# -*- coding: utf-8 -*-
"""
Propietario real de cada archivo y carpeta del listado (02/10/2026)
==================================================================
Wilson: «debe salir en nombre de la persona que lo subió o lo creó». El
listado no enviaba `propietario_*` y la interfaz ponía «yo» en todo (unidades
compartidas, carpetas que otra persona te compartió).

Cómo se decide, por cada item y en este orden (el primero que exista):
1. Primer registro de alta en `actividad` sobre su ruta: subió, creó carpeta,
   copió, creó, convirtió o movió ahí.
2. Si no tiene registro propio (entró al mover o copiar una carpeta entera,
   o llegó por la sincronización con Google), el autor de la carpeta más
   cercana que SÍ lo tenga.
3. Si tampoco, la primera persona que lo editó.
4. Si nada de lo anterior: en una unidad, quien creó la unidad; en el espacio
   de otra persona, esa persona; en el propio, nada (la interfaz pone «yo»).

Si la persona resultante es quien mira, no se anota nada («yo»). Las rutas se
buscan en todas sus formas: la del dueño (`/carpeta/x`) y la del espacio
compartido (`/compartido/<dueño>/carpeta/x`), porque quien sube a una carpeta
ajena deja el registro con la segunda. Nunca lanza.
"""
import logging

from almacen_bd import consultar
from permisos_compartidos import compartido_de_ruta, ruta_compartida
from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.propietarios')

ACCIONES_ALTA = ('subio', 'creo_carpeta', 'copio', 'creo', 'convirtio', 'movio')
_PARTICULAS = {'de', 'del', 'la', 'las', 'los', 'y', 'e', 'da', 'do', 'dos', 'van', 'von'}


# ── nombres ──────────────────────────────────────────────────────────────────
def _titulo(texto: str) -> str:
    """«ORQUIDIA DE LAS MERCEDES» → «Orquidia de las Mercedes»."""
    palabras = []
    for i, p in enumerate((texto or '').split()):
        b = p.lower()
        palabras.append(b if (i and b in _PARTICULAS) else b[:1].upper() + b[1:])
    return ' '.join(palabras)


def _primera(texto: str) -> str:
    for p in (texto or '').split():
        if p.lower() not in _PARTICULAS:
            return p
    return ''


def nombre_corto(persona: dict) -> str:
    """«Karen Armas»: primer nombre y primer apellido de nómina; si no hay
    desglose, las dos primeras palabras del nombre completo."""
    if not persona:
        return ''
    nombres, apellidos = persona.get('nombres') or '', persona.get('apellidos') or ''
    if nombres or apellidos:
        return _titulo(' '.join(x for x in (_primera(nombres), _primera(apellidos)) if x))
    nombre = persona.get('nombre') or ''
    if '@' in nombre and ' ' not in nombre:
        # Cuenta sin ficha de nómina: el nombre es su correo. «martin.deblire@…» → «Martin Deblire».
        return _titulo(' '.join(nombre.split('@', 1)[0].replace('_', '.').replace('-', '.').split('.')[:2]))
    return _titulo(' '.join(nombre.split()[:2]))


def nombre_completo(persona: dict) -> str:
    return _titulo(persona.get('nombre') or '') if persona else ''


# ── registros ────────────────────────────────────────────────────────────────
def _registros(rutas: set) -> dict:
    """{ruta: [(usuario_id, es_edicion), …]} en orden cronológico.

    OJO: `actividad.ruta` no lleva el espacio. «/Archivos del chat» existe en
    el espacio de todo el mundo, así que una ruta «lisa» solo vale si la firmó
    el dueño de ese espacio (filtro que aplica `_autor`)."""
    if not rutas:
        return {}
    filas = consultar("""
        SELECT ruta, usuario_id, (accion = 'edito') AS es_edicion
        FROM actividad
        WHERE ruta = ANY(%s) AND (accion = ANY(%s) OR accion = 'edito')
        ORDER BY ruta, creado_en
    """, (list(rutas), list(ACCIONES_ALTA)))
    salida = {}
    for f in filas:
        salida.setdefault(f['ruta'], []).append((int(f['usuario_id']), bool(f['es_edicion'])))
    return salida


def _autor(registros: dict, formas: list, edicion: bool):
    """Primera persona con alta (o edición, si `edicion`) en alguna de las
    formas; cada forma es (ruta, usuario_exigido | None)."""
    for ruta, exigido in formas:
        for usuario, es_edicion in registros.get(ruta, ()):
            if es_edicion != edicion:
                continue
            if exigido is None or usuario == exigido:
                return usuario
    return None


def _ancestros(ruta: str, tope: str) -> list:
    """Carpetas por encima de `ruta`, de la más cercana a `tope` (sin incluirlo)."""
    lista = []
    actual = ruta.rsplit('/', 1)[0]
    while actual and actual != tope and actual.startswith(tope):
        lista.append(actual)
        actual = actual.rsplit('/', 1)[0]
    return lista


def _creadores_unidades(ids: set) -> dict:
    if not ids:
        return {}
    filas = consultar("SELECT id, creado_por FROM unidades_compartidas WHERE id = ANY(%s)", (list(ids),))
    return {int(f['id']): int(f['creado_por']) for f in filas}


def _formas(ruta: str, dueno) -> list:
    """Formas (ruta, usuario_exigido) en que puede estar escrita la ruta en
    `actividad`: la lisa del dueño (solo vale firmada por él) y la del espacio
    compartido (la firma quien sube a una carpeta ajena)."""
    if dueno is None:
        return [(ruta, None)]
    if ruta.startswith('/compartido/'):
        _, sub = compartido_de_ruta(ruta)
        return [(ruta, None), (sub, dueno)]
    return [(ruta, dueno), (ruta_compartida(dueno, ruta), None)]


# ── principal ────────────────────────────────────────────────────────────────
def foto_de(persona: dict) -> str:
    """URL de la foto de perfil (nómina primero, luego la de la cuenta) o ''."""
    if not persona:
        return ''
    if persona.get('foto_perfil'):
        return '/static/' + str(persona['foto_perfil']).lstrip('/')
    if persona.get('profile_picture'):
        return '/static/uploads/profiles/' + str(persona['profile_picture'])
    return ''


def _poner(item: dict, persona: dict, usuario_id):
    item['propietario_id'] = usuario_id
    item['propietario_nombre'] = nombre_corto(persona) or f'Usuario {usuario_id}'
    item['propietario_nombre_completo'] = nombre_completo(persona) or f'Usuario {usuario_id}'
    item['propietario_email'] = persona.get('email') or ''
    item['propietario_foto'] = foto_de(persona)


def anotar(items: list, usuario_actual: int) -> None:
    """Añade propietario_id / propietario_nombre / propietario_nombre_completo /
    propietario_email a los items cuyo autor NO es quien mira. En sitio."""
    try:
        from vista_compartidos import _nombres_de
        yo = int(usuario_actual)
        plan = []     # (item, formas propias, formas de ancestros [cercano→lejano], respaldo)
        unidades = set()
        for item in items:
            ruta = item.get('ruta_completa') or item.get('ruta') or ''
            if not ruta:
                continue
            unidad_id, _ = unidad_de_ruta(ruta)
            if unidad_id is not None:
                unidades.add(unidad_id)
                tope = f'/unidades/{unidad_id}'
                plan.append((item, [(ruta, None)], [[(a, None)] for a in _ancestros(ruta, tope)], ('unidad', unidad_id)))
                continue
            dueno, sub = compartido_de_ruta(ruta)
            if dueno is not None and int(dueno) != yo:
                tope = f'/compartido/{int(dueno)}'
                plan.append((item, _formas(ruta, int(dueno)),
                             [_formas(a, int(dueno)) for a in _ancestros(ruta, tope)], ('dueno', int(dueno))))
            else:
                plan.append((item, _formas(ruta, yo), [_formas(a, yo) for a in _ancestros(ruta, '')], ('yo', None)))

        rutas = set()
        for _, propias, ancestros, _ in plan:
            rutas.update(r for r, _ in propias)
            for formas in ancestros:
                rutas.update(r for r, _ in formas)
        registros = _registros(rutas)
        creadores = _creadores_unidades(unidades)

        def alta_de(formas):
            return _autor(registros, formas, edicion=False)

        def edicion_de(formas):
            return _autor(registros, formas, edicion=True)

        resultado = []
        for item, propias, ancestros, respaldo in plan:
            autor = alta_de(propias)
            if autor is None:
                for formas in ancestros:
                    autor = alta_de(formas)
                    if autor is not None:
                        break
            if autor is None:
                autor = edicion_de(propias)
            if autor is None:
                tipo, dato = respaldo
                autor = creadores.get(dato) if tipo == 'unidad' else (dato if tipo == 'dueno' else None)
            resultado.append((item, autor))

        personas = _nombres_de({a for _, a in resultado if a is not None and a != yo})
        for item, autor in resultado:
            if autor is not None and autor != yo:
                _poner(item, personas.get(autor) or {}, autor)
    except Exception as excepcion:
        log.warning('propietarios: no se pudieron anotar (%s)', excepcion)
