# -*- coding: utf-8 -*-
"""
Modelo del formulario `.forma` — validación y compatibilidad de versiones.
==========================================================================
Se separa de `api_encuestas.py` porque es la pieza que más va a crecer: cada
elemento nuevo del editor (secciones, bloques de título, imágenes) se define
aquí, y la API se queda solo con las rutas.

Un `.forma` versión 2 tiene una lista de ELEMENTOS, no solo de preguntas:

    {"version": 2, "id": ..., "titulo": ..., "descripcion": ...,
     "tema": {"color": "#5b2d8e"},
     "elementos": [
        {"clase": "pregunta", "tipo": "opcion_unica", ...},
        {"clase": "titulo",   "titulo": ..., "descripcion": ...},
        {"clase": "seccion",  "titulo": ..., "descripcion": ...}
     ]}

Los `.forma` versión 1 (lista plana `preguntas`) se convierten al vuelo, así que
los formularios creados antes siguen abriendo sin que nadie tenga que migrarlos.

Nada de lo que envía el editor se guarda tal cual: el editor es JavaScript en el
navegador y un `.forma` puede editarse a mano. Todo pasa por `limpiar()`.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import re

import encuestas_texto as texto_rico
import uuid

VERSION = 2

LIMITE_ELEMENTOS = 200
LIMITE_OPCIONES = 60

TIPOS_PREGUNTA = ('texto_corto', 'parrafo', 'opcion_unica', 'casillas',
                  'desplegable', 'escala', 'fecha', 'hora')

# El 27/08/2026 existió un tipo 'correo' durante unas horas. Se retiró porque
# duplicaba lo que ya hacía «Recopilar el correo» de la pestaña Configuración
# —que además ya valida la dirección y es de lo que dependen «enviar copia» y
# «permitir modificar la respuesta»—, y tener dos formas de pedir el mismo dato
# llevaba a formularios que lo pedían dos veces. Las preguntas que se crearan
# con aquel tipo se convierten en «Respuesta corta» al abrirlas: se conserva la
# pregunta y lo respondido, que es lo que importa.
TIPOS_RETIRADOS = {'correo': 'texto_corto'}
TIPOS_CON_OPCIONES = ('opcion_unica', 'casillas', 'desplegable')
# Tipos que pueden decidir a qué sección se salta según lo que se responda. Solo
# los de UNA respuesta: con casillas se podrían marcar dos opciones que llevan a
# secciones distintas y no habría forma de decidir cuál gana (27/08/2026).
TIPOS_CON_SALTO = ('opcion_unica', 'desplegable')
SALTO_SIGUIENTE = 'siguiente'      # lo normal: continuar en orden
SALTO_ENVIAR = 'enviar'            # terminar y mandar el formulario
TIPOS_CON_OTRO = ('opcion_unica', 'casillas')      # como en Google Forms
CLASES = ('pregunta', 'titulo', 'seccion', 'imagen', 'video')

# Un id de YouTube son 11 caracteres de un alfabeto conocido. Se guarda
# SOLO el id, nunca una URL: así no hay forma de que un `.forma` editado a
# mano acabe incrustando un iframe de cualquier sitio.
_YOUTUBE = re.compile(r'^[A-Za-z0-9_-]{11}$')

COLOR_POR_DEFECTO = '#5b2d8e'                       # morado institucional

# Paleta sugerida (12, como el panel «Tema» de Google Forms). No es una lista
# cerrada: el editor admite además cualquier color propio, por eso la validación
# comprueba la FORMA del color y no su pertenencia a esta tupla.
COLORES_TEMA = ('#d93025', '#5b2d8e', '#3f51b5', '#1a73e8', '#00acc1', '#00bcd4',
                '#f4511e', '#f09300', '#188038', '#00897b', '#455a64', '#5f6368')

# Fondo: en vez de un color suelto se guarda cuál de los cuatro tonos derivados
# del color del tema se eligió, para que fondo y color nunca se descuadren.
TONOS_FONDO = 4
FONDO_POR_DEFECTO = 1

# Tipografía. Se limita a fuentes que existen en cualquier equipo (o que ya
# carga FARO), para que el formulario se vea igual en el navegador de quien
# responde, aunque sea un teléfono viejo.
FUENTES = ('Roboto', 'Arial', 'Verdana', 'Georgia', 'Times New Roman',
           'Courier New')
FUENTE_POR_DEFECTO = 'Roboto'
TAMANOS = {
    'encabezado': (18, 44, 30),      # (mínimo, máximo, por defecto)
    'pregunta':   (12, 24, 16),
    'texto':      (10, 20, 14),
}

# Alto de la banda del encabezado, en píxeles.
ALTURA_MIN, ALTURA_MAX, ALTURA_POR_DEFECTO = 90, 460, 240
# Zoom de la imagen dentro de la banda, en %. 100 = cubre la banda justo;
# por encima se acerca y por debajo se encoge, dejando ver el fondo alrededor.
# El rango es ancho a propósito: hay fotos panorámicas en las que hace falta
# acercarse mucho, y logotipos que se quieren pequeños y centrados.
ZOOM_MIN, ZOOM_MAX, ZOOM_POR_DEFECTO = 20, 400, 100
# Cómo encaja la imagen del encabezado en su banda.
AJUSTES = ('rellenar', 'completa')
AJUSTE_POR_DEFECTO = 'rellenar'

_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
_UUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                   r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

ETIQUETA_OTRO = 'Otro'


def _texto(valor, maximo):
    return str(valor if valor is not None else '').strip()[:maximo]


def _rico(valor, maximo):
    """Texto que admite formato (negrita, cursiva, subrayado y fuente).

    Pasa SIEMPRE por el saneador: un `.forma` es un archivo del Drive y puede
    llegar editado a mano, así que esta es la frontera, no el editor.
    """
    return texto_rico.sanear(valor, FUENTES, maximo)


def plano(valor):
    """El mismo texto sin formato, para el Excel, las tablas y los títulos de
    pestaña, que no pueden mostrar HTML."""
    return texto_rico.quitar_etiquetas(valor)


def _id(valor=None):
    return _texto(valor, 60) or str(uuid.uuid4())


def nuevo_id():
    return str(uuid.uuid4())


def _limpiar_imagen(bruto):
    """Ficha de una imagen dentro del `.forma`: solo id y medidas.

    El `.forma` NO guarda rutas ni URLs: guarda el id, y quien sirve la imagen es
    el endpoint, que comprueba que ese id pertenece a este formulario. Si aquí se
    guardara una URL, un `.forma` editado a mano podría apuntar a cualquier sitio.
    """
    if not isinstance(bruto, dict) or not bruto.get('id'):
        return None
    identificador = _texto(bruto.get('id'), 60)
    if not _UUID.match(identificador):
        return None
    ficha = {'id': identificador.lower()}
    for clave in ('ancho', 'alto'):
        try:
            valor = int(bruto.get(clave) or 0)
        except (TypeError, ValueError):
            valor = 0
        if valor > 0:
            ficha[clave] = min(valor, 10000)
    alineacion = _texto(bruto.get('alineacion'), 10)
    ficha['alineacion'] = alineacion if alineacion in ('izquierda', 'centro',
                                                       'derecha') else 'izquierda'

    # Ajustes del encabezado: alto de la banda y qué parte de la imagen se ve.
    # Una foto apaisada recortada a una banda deja fuera arriba o abajo; con el
    # encuadre se elige qué franja se enseña, en vez de conformarse con el
    # centro.
    try:
        altura = int(bruto.get('altura') or 0)
    except (TypeError, ValueError):
        altura = 0
    if altura:
        ficha['altura'] = min(max(altura, ALTURA_MIN), ALTURA_MAX)

    try:
        encuadre = float(bruto.get('encuadre'))
    except (TypeError, ValueError):
        encuadre = None
    if encuadre is not None:
        ficha['encuadre'] = round(min(max(encuadre, 0), 100), 1)

    try:
        zoom = int(bruto.get('zoom') or 0)
    except (TypeError, ValueError):
        zoom = 0
    if zoom:
        ficha['zoom'] = min(max(zoom, ZOOM_MIN), ZOOM_MAX)

    # Cómo encaja la imagen en la banda:
    #   «rellenar» — la cubre entera y recorta lo que sobra (lo de siempre).
    #   «completa» — se ve la imagen COMPLETA, sin recortar nada.
    ajuste = _texto(bruto.get('ajuste'), 12)
    if ajuste in AJUSTES:
        ficha['ajuste'] = ajuste

    return ficha


# ---------------------------------------------------------------------------
# Semilla
# ---------------------------------------------------------------------------
def formulario_vacio(titulo='Formulario sin título'):
    """Definición de un `.forma` recién creado, con una pregunta lista."""
    return {
        'version': VERSION,
        'id': nuevo_id(),
        'titulo': titulo,
        'descripcion': '',
        'mensaje_final': '¡Gracias! Tu respuesta fue registrada.',
        'tema': _limpiar_tema(None),
        'cabecera': None,
        'elementos': [{
            'clase': 'pregunta',
            'id': nuevo_id(),
            'tipo': 'opcion_unica',
            'titulo': 'Pregunta sin título',
            'ayuda': '',
            'obligatoria': False,
            'opciones': ['Opción 1'],
            'otro': False,
            'barajar': False,
            'imagen': None,
        }],
    }


# ---------------------------------------------------------------------------
# Limpieza de cada elemento
# ---------------------------------------------------------------------------
# Tipos que el sistema puede calificar solo. Los demás (párrafo, escala, fecha,
# hora) admiten puntos, pero los pone una persona al revisar: no hay forma
# honesta de decidir por su cuenta si un texto largo o una fecha «acierta».
TIPOS_AUTOCALIFICABLES = ('opcion_unica', 'casillas', 'desplegable', 'texto_corto')

PUNTOS_MAXIMOS = 1000


def _limpiar_clave(bruto, tipo):
    """Clave de respuestas de una pregunta: qué vale, cuánto y qué se comenta."""
    bruto = bruto if isinstance(bruto, dict) else {}

    try:
        puntos = float(bruto.get('puntos') or 0)
    except (TypeError, ValueError):
        puntos = 0.0
    puntos = max(0.0, min(puntos, PUNTOS_MAXIMOS))
    # Se guarda entero cuando lo es, para que no aparezca «2.0 puntos».
    if puntos == int(puntos):
        puntos = int(puntos)

    correctas = bruto.get('correctas')
    correctas = correctas if isinstance(correctas, list) else []
    correctas = [_texto(v, 300) for v in correctas][:LIMITE_OPCIONES]

    return {
        'puntos': puntos,
        'correctas': [v for v in correctas if v],
        'comentario_correcto': _rico(bruto.get('comentario_correcto'), 1000),
        'comentario_incorrecto': _rico(bruto.get('comentario_incorrecto'), 1000),
        'autocalificable': tipo in TIPOS_AUTOCALIFICABLES,
    }


def _limpiar_pregunta(bruto):
    tipo = bruto.get('tipo')
    # Un tipo retirado no se descarta: se traduce al que ocupó su sitio, para
    # que la pregunta y sus respuestas sigan ahí (ver TIPOS_RETIRADOS).
    tipo = TIPOS_RETIRADOS.get(tipo, tipo)
    if tipo not in TIPOS_PREGUNTA:
        return None
    pregunta = {
        'clase': 'pregunta',
        'id': _id(bruto.get('id')),
        'tipo': tipo,
        'titulo': _rico(bruto.get('titulo'), 500) or 'Pregunta sin título',
        'ayuda': _rico(bruto.get('ayuda'), 500),
        'obligatoria': bool(bruto.get('obligatoria')),
        'opciones': [],
        'otro': False,
        'barajar': False,
        'imagen': _limpiar_imagen(bruto.get('imagen')),
        # Clave de respuestas del modo cuestionario. Se guarda siempre, aunque
        # el formulario no sea cuestionario ahora mismo: si se apaga y se
        # vuelve a encender, la clave sigue ahí y no hay que rehacerla.
        'clave': _limpiar_clave(bruto.get('clave'), tipo),
    }

    if tipo in TIPOS_CON_OPCIONES:
        opciones = [_texto(o, 300) for o in (bruto.get('opciones') or [])]
        pregunta['opciones'] = [o for o in opciones if o][:LIMITE_OPCIONES]
        if not pregunta['opciones']:
            pregunta['opciones'] = ['Opción 1']
        pregunta['barajar'] = bool(bruto.get('barajar'))
        if tipo in TIPOS_CON_OTRO:
            pregunta['otro'] = bool(bruto.get('otro'))
        if tipo in TIPOS_CON_SALTO:
            pregunta['saltos'] = _limpiar_saltos(bruto.get('saltos'),
                                                 pregunta['opciones'])

    elif tipo == 'escala':
        try:
            maximo = int(bruto.get('escala_max') or 5)
        except (TypeError, ValueError):
            maximo = 5
        pregunta['escala_max'] = min(max(maximo, 2), 10)
        pregunta['escala_min_etiqueta'] = _texto(bruto.get('escala_min_etiqueta'), 60)
        pregunta['escala_max_etiqueta'] = _texto(bruto.get('escala_max_etiqueta'), 60)

    return pregunta


def _limpiar_saltos(bruto, opciones):
    """A qué sección lleva cada opción: {opción: destino}.

    El destino es `siguiente`, `enviar` o el **id de una sección**. Se guarda el
    id y no el número de sección a propósito: mover o insertar secciones cambia
    los números, y un salto que apunta a «la sección 3» acabaría llevando a otro
    sitio sin que nadie lo tocara.

    Solo se conservan los saltos de opciones que existen: si se borra una
    opción, su salto se va con ella en vez de quedarse como basura invisible.
    Que el id de sección exista de verdad se comprueba después, cuando ya están
    limpios todos los elementos (ver `_saltos_coherentes`).
    """
    if not isinstance(bruto, dict):
        return {}
    limpios = {}
    for opcion in opciones:
        destino = bruto.get(opcion)
        if not isinstance(destino, str) or not destino.strip():
            continue
        destino = destino.strip()[:60]
        # No se comprueba aquí la FORMA del id: los ids son texto y lo que
        # importa es que la sección exista, que se mira en `_saltos_coherentes`
        # cuando ya están limpios todos los elementos.
        if destino != SALTO_SIGUIENTE:          # lo normal no hace falta guardarlo
            limpios[opcion] = destino
    return limpios


def _saltos_coherentes(elementos):
    """Descarta los saltos que apuntan a una sección que ya no existe.

    Pasa al borrar una sección: el salto se quedaría apuntando al vacío y quien
    respondiera esa opción se encontraría el formulario terminando de golpe o
    saltando a donde no toca. Ante la duda, se sigue el orden normal.
    """
    secciones = {e['id'] for e in elementos if e.get('clase') == 'seccion'}
    for elemento in elementos:
        saltos = elemento.get('saltos')
        if not saltos:
            continue
        elemento['saltos'] = {
            opcion: destino for opcion, destino in saltos.items()
            if destino == SALTO_ENVIAR or destino in secciones}
    return elementos


def _limpiar_bloque(bruto, clase):
    """Bloque de texto: un título con descripción («titulo») o el comienzo de una
    página nueva del formulario («seccion»)."""
    return {
        'clase': clase,
        'id': _id(bruto.get('id')),
        'titulo': _rico(bruto.get('titulo'),
                        300) or ('Sección sin título' if clase == 'seccion'
                                 else 'Título sin texto'),
        'descripcion': _rico(bruto.get('descripcion'), 2000),
        'imagen': _limpiar_imagen(bruto.get('imagen')),
    }


def id_youtube(bruto):
    """Saca el id de un enlace de YouTube, o None si no lo es.

    Se aceptan las formas habituales (youtu.be, /watch?v=, /embed/, /shorts/)
    porque la gente pega el enlace tal como lo copia, no el id.
    """
    texto = _texto(bruto, 300)
    if not texto:
        return None
    if _YOUTUBE.match(texto):
        return texto

    import re as _re
    patrones = (
        r'youtu\.be/([A-Za-z0-9_-]{11})',
        r'[?&]v=([A-Za-z0-9_-]{11})',
        r'/embed/([A-Za-z0-9_-]{11})',
        r'/shorts/([A-Za-z0-9_-]{11})',
        r'/live/([A-Za-z0-9_-]{11})',
    )
    for patron in patrones:
        hallazgo = _re.search(patron, texto)
        if hallazgo:
            return hallazgo.group(1)
    return None


def _limpiar_video(bruto):
    """Bloque de vídeo: solo el id de YouTube y su pie."""
    video = id_youtube(bruto.get('video'))
    return {
        'clase': 'video',
        'id': _id(bruto.get('id')),
        'video': video or '',
        'titulo': _rico(bruto.get('titulo'), 300),
        'descripcion': _rico(bruto.get('descripcion'), 2000),
    }


def _limpiar_imagen_suelta(bruto):
    """Bloque de imagen: la imagen como elemento propio, no dentro de una
    pregunta."""
    return {
        'clase': 'imagen',
        'id': _id(bruto.get('id')),
        'titulo': _rico(bruto.get('titulo'), 300),
        'imagen': _limpiar_imagen(bruto.get('imagen')),
    }


def _limpiar_elemento(bruto):
    if not isinstance(bruto, dict):
        return None
    clase = bruto.get('clase') or 'pregunta'
    if clase == 'pregunta':
        return _limpiar_pregunta(bruto)
    if clase in ('titulo', 'seccion'):
        return _limpiar_bloque(bruto, clase)
    if clase == 'imagen':
        return _limpiar_imagen_suelta(bruto)
    if clase == 'video':
        return _limpiar_video(bruto)
    return None


def _limpiar_tema(bruto):
    """Color, fondo y tipografía del formulario.

    El color se acepta por su FORMA (#rrggbb), no por estar en la paleta: el
    editor deja elegir un color propio. Todo lo demás se acota a lo permitido.
    """
    bruto = bruto or {}

    color = _texto(bruto.get('color'), 7)
    if not _HEX.match(color):
        color = COLOR_POR_DEFECTO

    try:
        fondo = int(bruto.get('fondo', FONDO_POR_DEFECTO))
    except (TypeError, ValueError):
        fondo = FONDO_POR_DEFECTO
    fondo = min(max(fondo, 0), TONOS_FONDO - 1)

    fuente = _texto(bruto.get('fuente'), 40)
    if fuente not in FUENTES:
        fuente = FUENTE_POR_DEFECTO

    tema = {'color': color.lower(), 'fondo': fondo, 'fuente': fuente}
    for nombre, (minimo, maximo, defecto) in TAMANOS.items():
        clave = 'tam_' + nombre
        try:
            valor = int(bruto.get(clave, defecto))
        except (TypeError, ValueError):
            valor = defecto
        tema[clave] = min(max(valor, minimo), maximo)
    return tema


# ---------------------------------------------------------------------------
# Limpieza del formulario completo
# ---------------------------------------------------------------------------
def limpiar(bruto, id_previo=None):
    """Deja la definición en una forma segura y predecible.

    Acepta tanto el formato versión 2 (`elementos`) como el versión 1
    (`preguntas`), de modo que un `.forma` viejo se abre sin migración previa.
    """
    if not isinstance(bruto, dict):
        raise ValueError('Formulario inválido')

    crudos = bruto.get('elementos')
    if not isinstance(crudos, list):
        # Versión 1: lista plana de preguntas.
        crudos = [dict(p, clase='pregunta')
                  for p in (bruto.get('preguntas') or []) if isinstance(p, dict)]

    elementos = []
    for crudo in crudos[:LIMITE_ELEMENTOS]:
        limpio = _limpiar_elemento(crudo)
        if limpio:
            elementos.append(limpio)

    if not any(e['clase'] == 'pregunta' for e in elementos):
        elementos.append(formulario_vacio()['elementos'][0])

    # Los saltos se comprueban cuando ya están TODOS los elementos: hasta aquí no
    # se sabe qué secciones existen de verdad.
    elementos = _saltos_coherentes(elementos)

    return {
        'version': VERSION,
        'id': _id(bruto.get('id')) if bruto.get('id') else (id_previo or nuevo_id()),
        'titulo': _rico(bruto.get('titulo'), 300) or 'Formulario sin título',
        'descripcion': _rico(bruto.get('descripcion'), 2000),
        'mensaje_final': (_rico(bruto.get('mensaje_final'), 500) or
                          '¡Gracias! Tu respuesta fue registrada.'),
        'tema': _limpiar_tema(bruto.get('tema')),
        'cabecera': _limpiar_imagen(bruto.get('cabecera')),
        'elementos': elementos,
    }


# ---------------------------------------------------------------------------
# Vistas derivadas
# ---------------------------------------------------------------------------
def preguntas(definicion):
    """Solo las preguntas, en orden. Es lo que valida y tabula las respuestas."""
    return [e for e in definicion.get('elementos', []) if e['clase'] == 'pregunta']


def paginas(definicion):
    """Los elementos repartidos en páginas: cada «seccion» abre una nueva.

    La página pública las presenta de una en una, como hace Google Forms con sus
    secciones; un formulario sin secciones es una sola página.
    """
    resultado, actual = [], []
    for elemento in definicion.get('elementos', []):
        if elemento['clase'] == 'seccion' and actual:
            resultado.append(actual)
            actual = []
        actual.append(elemento)
    if actual:
        resultado.append(actual)
    return resultado or [[]]
