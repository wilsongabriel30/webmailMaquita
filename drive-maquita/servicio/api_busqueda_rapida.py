# -*- coding: utf-8 -*-
"""
Sugerencias de búsqueda instantáneas (el desplegable del buscador).
===================================================================
Lo que se abre bajo la caja de búsqueda MIENTRAS se escribe, como en Drive: unas
pocas coincidencias con su icono, quién es el dueño y cuándo se modificó, más el
final de la palabra sugerido para completarla con el tabulador.

Va aparte de `/buscar` a propósito, porque responden a preguntas distintas:

- `/buscar` es la búsqueda COMPLETA: mira también dentro de los documentos, y
  eso cuesta unos cientos de milisegundos. Está bien cuando alguien pulsa Enter
  y espera una lista.
- `/buscar/sugerencias` se dispara con cada tecla. Solo mira nombres y títulos
  —las dos columnas con índice trigram—, devuelve 8 y **nunca** entra en el
  contenido: tiene que contestar antes de que la persona escriba la letra
  siguiente o el desplegable va a trompicones.

Autoría: Equipo de Tecnología Maquita — 2026-08-27
"""
import logging

from flask import Blueprint, jsonify, request

import indice_busqueda as indice
import espacios_indice as espacios
from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, unidad_de_ruta

log = logging.getLogger('almacen.sugerencias')

bp_busqueda_rapida = Blueprint('busqueda_rapida', __name__)

CUANTAS = 8          # las que caben en el desplegable sin taparlo todo
MINIMO = 2           # con una letra sola, todo coincide: no vale de nada
MAXIMO_POR_CARPETA = 2   # que una sola carpeta no se quede con el desplegable
MAXIMO_POR_FAMILIA = 2   # ni una sola familia de nombres (ver `_familia`)
LARGO_FAMILIA = 24       # letras del nombre que se consideran «la misma familia»


@bp_busqueda_rapida.route('/buscar/sugerencias', methods=['GET'])
def sugerencias():
    """GET /buscar/sugerencias?q= — para el desplegable del buscador."""
    usuario = usuario_actual()
    termino = (request.args.get('q') or '').strip()
    if len(termino) < MINIMO:
        return jsonify({'success': True, 'sugerencias': [], 'completar': ''})

    try:
        permitidos = espacios.espacios_de_busqueda(usuario)
        filas = indice.buscar_nombres(usuario, termino, CUANTAS * 3,
                                      espacios_permitidos=permitidos)
    except Exception as excepcion:
        log.warning('sugerencias de "%s": %s', termino, excepcion)
        return jsonify({'success': True, 'sugerencias': [], 'completar': ''})

    nombres_unidades = _nombres_de_unidades()
    nombres_personas = _nombres_de_personas(
        {int(f['espacio']) for f in filas} - {0, int(usuario)})

    vistas, por_carpeta, por_familia, resultado = set(), {}, {}, []
    for fila in filas:
        if len(resultado) >= CUANTAS:
            break
        espacio = int(fila['espacio'])
        try:
            ruta = espacios.ruta_visible(permitidos, espacio, fila['ruta'])
        except Exception:
            ruta = fila['ruta']
        # El mismo nombre repetido en diez subcarpetas llena el desplegable y no
        # ayuda a nadie: se enseña una vez por nombre y el resto se ve al pulsar
        # Enter, que para eso está la búsqueda completa.
        clave = (fila['nombre'].lower(), bool(fila['es_carpeta']))
        if clave in vistas:
            continue
        # Y como mucho DOS por carpeta y DOS por «familia» de nombre. Un vídeo
        # exportado deja a su lado `X.mp4`, `X.zip`, `X_player.html`,
        # `X_Thumbnails.png`…: son nombres distintos, en carpetas distintas, y
        # entre todos se quedaban con el desplegable entero. La familia es el
        # principio del nombre sin la extensión, que es lo que comparten.
        carpeta = ruta.rsplit('/', 1)[0] or '/'
        familia = _familia(fila['nombre'])
        if (por_carpeta.get(carpeta, 0) >= MAXIMO_POR_CARPETA
                or por_familia.get(familia, 0) >= MAXIMO_POR_FAMILIA):
            continue
        por_carpeta[carpeta] = por_carpeta.get(carpeta, 0) + 1
        por_familia[familia] = por_familia.get(familia, 0) + 1
        vistas.add(clave)
        resultado.append({
            'nombre': fila['nombre'],
            # El título interno es lo que la persona reconoce de un formulario;
            # el nombre del archivo lo puso el botón «+ Nuevo».
            'titulo': _titulo_visible(fila),
            'ruta': ruta,
            'carpeta': ruta.rsplit('/', 1)[0] or '/',
            'es_carpeta': bool(fila['es_carpeta']),
            'extension': fila['extension'] or '',
            'de': _de_quien(espacio, fila['ruta'], usuario,
                            nombres_unidades, nombres_personas),
            'modificado': (fila['modificado_en'].isoformat()
                           if fila['modificado_en'] else None),
        })

    return jsonify({'success': True, 'sugerencias': resultado,
                    'completar': _completar(termino, resultado)})


def _familia(nombre):
    """Principio del nombre, sin extensión, con el que se agrupan los archivos
    que salen juntos de una misma exportación."""
    base = nombre.rsplit('.', 1)[0] if '.' in nombre else nombre
    return indice.normalizar(base)[:LARGO_FAMILIA]


def _titulo_visible(fila):
    """Título interno del archivo si lo tiene y dice algo distinto del nombre."""
    titulo = (fila.get('titulo') or '').strip()
    if not titulo:
        return ''
    nombre = (fila.get('nombre') or '')
    return '' if indice.normalizar(nombre).startswith(indice.normalizar(titulo)) else titulo


def _completar(termino, sugerencias):
    """Palabra completa que propone el buscador para el tabulador.

    Se propone SOLO cuando lo escrito es el principio de un nombre: completar
    con algo que no empieza igual sería cambiarle a la persona lo que escribió.
    """
    escrito = indice.normalizar(termino)
    for una in sugerencias:
        for candidato in (una['nombre'], una['titulo']):
            if not candidato:
                continue
            if indice.normalizar(candidato).startswith(escrito):
                return candidato
    return ''


def _de_quien(espacio, ruta, usuario, nombres_unidades, nombres_personas):
    """Quién es el dueño, en las palabras que la persona espera leer."""
    if espacio == int(usuario):
        return 'Yo'
    if espacio == espacios.ESPACIO_UNIDADES:
        try:
            unidad_id, _sub = unidad_de_ruta(ruta)
        except RutaInvalida:
            unidad_id = None
        return nombres_unidades.get(unidad_id) or 'Unidad compartida'
    return nombres_personas.get(espacio) or 'Compartido conmigo'


def _nombres_de_unidades():
    try:
        from almacen_bd import consultar
        return {f['id']: f['nombre']
                for f in consultar('SELECT id, nombre FROM unidades_compartidas')}
    except Exception as excepcion:
        log.debug('sugerencias: sin nombres de unidades (%s)', excepcion)
        return {}


def _nombres_de_personas(ids):
    if not ids:
        return {}
    try:
        from almacen_bd import consultar
        filas = consultar("""
            SELECT u.id,
                   COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id IN %s
        """, (tuple(ids),), nomina=True)
        return {f['id']: f['nombre'] for f in filas}
    except Exception as excepcion:
        log.debug('sugerencias: sin nombres de personas (%s)', excepcion)
        return {}
