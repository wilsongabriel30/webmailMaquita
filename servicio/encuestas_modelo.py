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
import encuestas_validacion as validacion_mod
import uuid

VERSION = 2

LIMITE_ELEMENTOS = 200
LIMITE_OPCIONES = 60

TIPOS_PREGUNTA = ('texto_corto', 'parrafo', 'opcion_unica', 'casillas',
                  'desplegable', 'archivo', 'escala', 'calificacion',
                  'cuadricula_opciones', 'cuadricula_casillas',
                  'fecha', 'hora')

# «Subir archivos» (08/09/2026). Su respuesta es una lista de FICHAS
# —`[{id, nombre, tamano, ruta}]`—, no de textos: el archivo en sí acaba en el
# Drive del dueño del formulario, y aquí solo queda constancia de cuál es.
# Todo lo demás de este tipo (dónde se guarda, qué extensiones se admiten, cómo
# se entrega) vive en `encuestas_archivos.py`.
ARCHIVOS_MAXIMOS = 10
ARCHIVO_MB_DEFECTO = 10
ARCHIVO_MB_MAXIMO = 100
# Solo los NOMBRES de los grupos; qué extensión cae en cada uno lo decide
# `encuestas_archivos.GRUPOS`, que es quien tiene que saberlo para validar.
GRUPOS_ARCHIVO = ('documento', 'hoja', 'presentacion', 'pdf', 'imagen',
                  'video', 'audio', 'comprimido')

# Las dos cuadrículas (08/09/2026): una tabla de FILAS por COLUMNAS en la que
# cada fila elige una columna («…_opciones») o varias («…_casillas»).
#
# Su respuesta NO es un texto ni una lista como la de los demás tipos, sino un
# mapa {fila: columna} —o {fila: [columnas]}—. Se guardan fila y columna por su
# TEXTO y no por su posición, igual que las opciones del resto de tipos: si
# alguien reordena las filas después de recibir respuestas, lo respondido sigue
# significando lo mismo. `texto_de()` es quien sabe volcar eso a una línea para
# la hoja de cálculo y el correo, que no pueden pintar una tabla.
TIPOS_CUADRICULA = ('cuadricula_opciones', 'cuadricula_casillas')
LIMITE_FILAS = 40
LIMITE_COLUMNAS = 20

# Calificación: de 1 a N iconos. El mínimo es 2 porque una calificación de un
# solo nivel no distingue nada; el máximo, 10, es el de la escala lineal.
CALIFICACION_MIN, CALIFICACION_MAX, CALIFICACION_DEFECTO = 2, 10, 5
ICONOS_CALIFICACION = ('estrella', 'corazon', 'pulgar')
ICONO_CALIFICACION_DEFECTO = 'estrella'

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
# Clave del salto de «Otro» (10/09/2026). Lo que se escribe en «Otro» es texto
# libre y no puede ser la clave del salto: se guarda con esta. La misma
# constante está en `encuesta-recorrido.js` y en el editor.
SALTO_OTRO = '__otro__'
# Dónde caben imágenes en las opciones. En un desplegable no: sus entradas
# son texto del sistema y no pueden llevar imagen, igual que en Google.
TIPOS_CON_IMAGEN_OPCION = ('opcion_unica', 'casillas')

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
# Tipos que el sistema puede calificar solo. Los demás (párrafo, escala,
# calificación, cuadrículas, fecha, hora) admiten puntos, pero los pone una
# persona al revisar: no hay forma honesta de decidir por su cuenta si un texto
# largo o una fecha «acierta».
#
# Las cuadrículas se quedan fuera A PROPÓSITO aunque lo que se responde en ellas
# sí sean opciones cerradas: su clave tendría que decir qué columna es la
# correcta en CADA fila, y con eso viene la decisión de si acertar tres filas de
# cinco vale puntos parciales, todos o ninguno. Mientras esa decisión no esté
# tomada, se corrigen a mano —que es lo que el modo cuestionario ya hace con el
# párrafo— en vez de inventarse un criterio.
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


def _lista_textos(bruto, defecto, limite):
    """Una lista de textos cortos (las filas o las columnas de una cuadrícula).

    Nunca vuelve vacía: una cuadrícula sin filas no pregunta nada y sin columnas
    no se puede responder, así que se le pone la primera por defecto, igual que
    una pregunta de opciones arranca con «Opción 1».
    """
    if not isinstance(bruto, list):
        return [defecto]
    entradas = [_texto(v, 300) for v in bruto]
    entradas = [v for v in entradas if v][:limite]
    return entradas or [defecto]


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
        # «Validación de respuestas» del menú ⋮ (09/09/2026): qué tiene que
        # cumplir lo que se responde. None si la pregunta no la usa o si el
        # tipo no la admite; las reglas viven en `encuestas_validacion.py`.
        'validacion': validacion_mod.limpiar(bruto.get('validacion'), tipo),
    }

    if tipo in TIPOS_CON_OPCIONES:
        opciones = [_texto(o, 300) for o in (bruto.get('opciones') or [])]
        pregunta['opciones'] = [o for o in opciones if o][:LIMITE_OPCIONES]
        if not pregunta['opciones']:
            pregunta['opciones'] = ['Opción 1']
        pregunta['barajar'] = bool(bruto.get('barajar'))
        # Imagen por opción (09/09/2026), como en Google. Va en una lista
        # PARALELA a `opciones` y no dentro de cada opción porque una opción
        # es un texto: convertirla en objeto obligaría a migrar todos los
        # `.forma` que existen y a tocar cada sitio que las lee (el resumen,
        # el Excel, los saltos, la clave del cuestionario). La lista se recorta
        # o se rellena para que tenga SIEMPRE tantas entradas como opciones:
        # así el índice de una nunca señala la imagen de otra.
        if tipo in TIPOS_CON_IMAGEN_OPCION:
            brutas = bruto.get('opciones_imagenes')
            brutas = brutas if isinstance(brutas, list) else []
            imagenes = [_limpiar_imagen(x) for x in brutas]
            imagenes = imagenes[:len(pregunta['opciones'])]
            faltan = len(pregunta['opciones']) - len(imagenes)
            pregunta['opciones_imagenes'] = imagenes + [None] * faltan
        if tipo in TIPOS_CON_OTRO:
            pregunta['otro'] = bool(bruto.get('otro'))
        if tipo in TIPOS_CON_SALTO:
            pregunta['saltos'] = _limpiar_saltos(bruto.get('saltos'),
                                                 pregunta['opciones'],
                                                 pregunta.get('otro'))
            # «Ir a la sección según la respuesta», el interruptor del menú ⋮
            # (08/09/2026). Los saltos se guardan esté encendido o apagado: si
            # se apaga y se vuelve a encender, siguen ahí y no hay que rehacer
            # el recorrido.
            #
            # Cuando la clave no viene —un `.forma` anterior a esa fecha— el
            # interruptor se abre encendido SI ya había saltos guardados. Esos
            # formularios ya estaban ramificando, y arrancarlos apagados los
            # habría dejado en línea recta sin que nadie tocara nada.
            pregunta['saltos_activos'] = bool(
                bruto.get('saltos_activos', bool(pregunta['saltos'])))

    elif tipo == 'fecha':
        # Las dos opciones del menú ⋮ de Google. El año viene puesto salvo que
        # se diga lo contrario, así que los `.forma` anteriores a hoy —que no
        # traen la clave— siguen pidiéndolo como siempre.
        pregunta['fecha_con_hora'] = bool(bruto.get('fecha_con_hora'))
        pregunta['fecha_con_anio'] = bruto.get('fecha_con_anio') is not False

    elif tipo == 'hora':
        pregunta['hora_modo'] = ('duracion'
                                 if bruto.get('hora_modo') == 'duracion'
                                 else 'hora')

    elif tipo == 'escala':
        try:
            maximo = int(bruto.get('escala_max') or 5)
        except (TypeError, ValueError):
            maximo = 5
        pregunta['escala_max'] = min(max(maximo, 2), 10)
        pregunta['escala_min_etiqueta'] = _texto(bruto.get('escala_min_etiqueta'), 60)
        pregunta['escala_max_etiqueta'] = _texto(bruto.get('escala_max_etiqueta'), 60)

    elif tipo == 'calificacion':
        try:
            maximo = int(bruto.get('calificacion_max') or CALIFICACION_DEFECTO)
        except (TypeError, ValueError):
            maximo = CALIFICACION_DEFECTO
        pregunta['calificacion_max'] = min(max(maximo, CALIFICACION_MIN),
                                           CALIFICACION_MAX)
        # El icono se acota a la lista: es un nombre que acaba dentro del HTML,
        # y un `.forma` puede llegar editado a mano.
        icono = _texto(bruto.get('calificacion_icono'), 20)
        pregunta['calificacion_icono'] = (icono if icono in ICONOS_CALIFICACION
                                          else ICONO_CALIFICACION_DEFECTO)

    elif tipo in TIPOS_CUADRICULA:
        pregunta['filas'] = _lista_textos(bruto.get('filas'), 'Fila 1',
                                          LIMITE_FILAS)
        pregunta['columnas'] = _lista_textos(bruto.get('columnas'), 'Columna 1',
                                             LIMITE_COLUMNAS)
        # Opciones del menú ⋮, como en Google (09/09/2026). «Exigir una
        # respuesta en cada fila» no es «Obligatorio»: obligatorio pide que la
        # tabla no quede en blanco, esto pide que no falte NINGUNA fila.
        pregunta['exigir_fila'] = bool(bruto.get('exigir_fila'))
        # Aquí «barajar» son las FILAS, no las opciones: en una cuadrícula lo
        # que se lista son las filas.
        pregunta['barajar'] = bool(bruto.get('barajar'))
        if tipo == 'cuadricula_opciones':
            # Con casillas no cabe: una columna se puede marcar en varias
            # filas por definición.
            pregunta['una_por_columna'] = bool(bruto.get('una_por_columna'))

    elif tipo == 'archivo':
        try:
            cuantos = int(bruto.get('archivo_max') or 1)
        except (TypeError, ValueError):
            cuantos = 1
        pregunta['archivo_max'] = min(max(cuantos, 1), ARCHIVOS_MAXIMOS)
        try:
            megas = int(bruto.get('archivo_mb') or ARCHIVO_MB_DEFECTO)
        except (TypeError, ValueError):
            megas = ARCHIVO_MB_DEFECTO
        pregunta['archivo_mb'] = min(max(megas, 1), ARCHIVO_MB_MAXIMO)
        # Los límites se acotan aquí, no solo en la pantalla: son lo único que
        # impide que un `.forma` editado a mano deje pasar archivos de 2 GB.
        grupos = bruto.get('archivo_tipos')
        grupos = grupos if isinstance(grupos, list) else []
        pregunta['archivo_tipos'] = [g for g in [_texto(v, 20) for v in grupos]
                                     if g in GRUPOS_ARCHIVO]

    return pregunta


def _limpiar_saltos(bruto, opciones, otro=False):
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
    # «Otro» también puede llevar a una sección, como en Google, pero solo
    # mientras la pregunta tenga «Otro»: si se quita, su salto se va con él.
    for opcion in list(opciones) + ([SALTO_OTRO] if otro else []):
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


def _destino_valido(bruto, elementos):
    """Como `_destino()`, pero comprobando que la sección exista."""
    destino = _destino(bruto)
    if destino in (SALTO_SIGUIENTE, SALTO_ENVIAR):
        return destino
    hay = any(e.get('clase') == 'seccion' and e['id'] == destino
              for e in elementos)
    return destino if hay else SALTO_SIGUIENTE


def _destino(bruto):
    """Un destino de recorrido saneado. Lo normal (`siguiente`) es el valor
    por defecto de todo lo que no se entienda: ante la duda, se sigue el orden
    del formulario y nadie se queda sin a dónde ir."""
    destino = _texto(bruto, 60)
    return destino or SALTO_SIGUIENTE


def _saltos_coherentes(elementos):
    """Descarta los saltos que apuntan a una sección que ya no existe.

    Pasa al borrar una sección: el salto se quedaría apuntando al vacío y quien
    respondiera esa opción se encontraría el formulario terminando de golpe o
    saltando a donde no toca. Ante la duda, se sigue el orden normal.
    """
    secciones = {e['id'] for e in elementos if e.get('clase') == 'seccion'}
    for elemento in elementos:
        # El destino de la sección se comprueba igual que los saltos: si
        # apunta a una sección borrada, se vuelve al orden normal.
        destino = elemento.get('destino')
        if destino and destino != SALTO_ENVIAR and destino not in secciones:
            elemento['destino'] = SALTO_SIGUIENTE
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
    bloque = {
        'clase': clase,
        'id': _id(bruto.get('id')),
        'titulo': _rico(bruto.get('titulo'),
                        300) or ('Sección sin título' if clase == 'seccion'
                                 else 'Título sin texto'),
        'descripcion': _rico(bruto.get('descripcion'), 2000),
        'imagen': _limpiar_imagen(bruto.get('imagen')),
    }
    if clase == 'seccion':
        # «Después de la sección…» (09/09/2026): a dónde va quien la termina
        # sin que ninguna opción diga otra cosa. `siguiente`, `enviar` o el id
        # de otra sección; que ese id exista se mira en `_saltos_coherentes`,
        # igual que con los saltos por opción.
        bloque['destino'] = _destino(bruto.get('destino'))
    return bloque


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
        # «Después de la primera página»: su destino no puede vivir en una
        # sección, porque lo que va antes de la primera sección no tiene
        # ninguna que lo abra. Se comprueba aquí, con las secciones ya limpias.
        'destino_inicio': _destino_valido(bruto.get('destino_inicio'), elementos),
        'elementos': elementos,
    }


# ---------------------------------------------------------------------------
# Vistas derivadas
# ---------------------------------------------------------------------------
def texto_de(pregunta, valor):
    """Lo respondido, en una línea.

    Lo usan la hoja de cálculo, el correo con la copia de la respuesta y la
    tabla de la vista de respuestas: sitios que no pueden pintar una cuadrícula
    y necesitan una celda. Vive aquí, al lado de la definición de los tipos,
    para que no acabe habiendo tres versiones distintas de «cómo se lee esto»
    diciendo cada una una cosa.
    """
    if valor is None or valor == '' or valor == [] or valor == {}:
        return ''

    if isinstance(valor, dict):
        # Cuadrícula. Se recorre por el orden de las FILAS de la pregunta y no
        # por el del mapa: así todas las respuestas se leen en el mismo orden,
        # que es lo que permite compararlas de un vistazo en la hoja.
        filas = pregunta.get('filas') or list(valor)
        partes = []
        for fila in filas:
            elegido = valor.get(fila)
            if elegido in (None, '', []):
                continue
            if isinstance(elegido, list):
                elegido = ', '.join(str(v) for v in elegido)
            partes.append('%s: %s' % (fila, elegido))
        return ' · '.join(partes)

    if isinstance(valor, list):
        # «Subir archivos» responde con fichas, no con textos: interesa el
        # nombre del archivo, que es lo que se busca luego en el Drive.
        if valor and isinstance(valor[0], dict):
            return ', '.join(str(v.get('nombre') or '') for v in valor
                             if isinstance(v, dict))
        return ', '.join(str(v) for v in valor)

    if pregunta.get('tipo') == 'calificacion':
        # «4» solo no dice nada: puede ser 4 sobre 5 o sobre 10.
        return '%s de %s' % (valor, pregunta.get('calificacion_max')
                             or CALIFICACION_DEFECTO)

    return str(valor)


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
