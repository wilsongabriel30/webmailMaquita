# -*- coding: utf-8 -*-
"""Formularios en varios idiomas (30/10/2026).

Un mismo formulario se responde en el idioma que elija quien responde, y TODAS
las respuestas caen en las mismas columnas, escritas en el idioma base. Así el
resumen, el Excel, los saltos y la calificación no saben nada de idiomas.

DÓNDE SE GUARDA (dentro del `.forma`)
-------------------------------------
    "idiomas": {
      "base": "es",
      "lista": ["es", "en", "fr", "it"],
      "pregunta": "<id de la pregunta «Idioma»>",
      "textos": {
        "en": {
          "titulo": "...", "descripcion": "...", "mensaje_final": "...",
          "elementos": {
            "<id>": {"titulo": "...", "ayuda": "...", "descripcion": "...",
                     "opciones": [...], "filas": [...], "columnas": [...],
                     "escala_min_etiqueta": "...", "escala_max_etiqueta": "..."}
          }
        }
      }
    }

Las opciones, filas y columnas se traducen POR POSICIÓN: la 2.ª opción en
inglés es la 2.ª en español. Lo que falte se muestra en el idioma base.

LA PREGUNTA «IDIOMA»
--------------------
Es una pregunta normal de varias opciones, con los idiomas escritos en su propia
lengua («Español», «English»…). Sale en el resumen y en el Excel como cualquier
otra, sin tocar el motor de la hoja. Al elegirla, la página se recarga traducida;
al enviar, su respuesta dice en qué idioma vienen las demás.
"""

import copy

import encuestas_modelo as modelo

# El nombre de cada idioma en su propia lengua: es lo que lee quien todavía no
# ha elegido idioma.
CATALOGO = {
    'es': 'Español',
    'en': 'English',
    'fr': 'Français',
    'it': 'Italiano',
    'pt': 'Português',
    'de': 'Deutsch',
    'qu': 'Kichwa',
}
LIMITE_IDIOMAS = len(CATALOGO)

_RICOS = ('titulo', 'ayuda', 'descripcion')
_LISTAS = ('opciones', 'filas', 'columnas')
_ETIQUETAS = ('escala_min_etiqueta', 'escala_max_etiqueta')


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------
def _textos_elemento(bruto, elemento):
    if not isinstance(bruto, dict):
        return {}
    limpio = {}
    for campo in _RICOS:
        if campo in elemento:
            texto = modelo._rico(bruto.get(campo), 2000 if campo == 'descripcion' else 500)
            if texto:
                limpio[campo] = texto
    for campo in _LISTAS:
        base = elemento.get(campo)
        if not base:
            continue
        lista = bruto.get(campo)
        lista = lista if isinstance(lista, list) else []
        # Tantas como en el idioma base: un índice nunca señala otra opción.
        lista = [modelo._texto(x, 300) for x in lista[:len(base)]]
        lista += [''] * (len(base) - len(lista))
        if any(lista):
            limpio[campo] = lista
    for campo in _ETIQUETAS:
        if campo in elemento:
            texto = modelo._texto(bruto.get(campo), 60)
            if texto:
                limpio[campo] = texto
    return limpio


def limpiar(bruto, elementos):
    """La parte `idiomas` del `.forma`, saneada; None si no hay varios idiomas."""
    if not isinstance(bruto, dict):
        return None
    lista = []
    for codigo in bruto.get('lista') or []:
        if codigo in CATALOGO and codigo not in lista:
            lista.append(codigo)
    base = bruto.get('base') if bruto.get('base') in CATALOGO else 'es'
    if base not in lista:
        lista.insert(0, base)
    if len(lista) < 2:
        return None

    por_id = {e['id']: e for e in elementos}
    pregunta = bruto.get('pregunta')
    elegida = por_id.get(pregunta)
    if not (elegida and elegida.get('tipo') in ('opcion_unica', 'desplegable')):
        pregunta = None

    textos = {}
    crudos = bruto.get('textos') if isinstance(bruto.get('textos'), dict) else {}
    for codigo in lista:
        if codigo == base or not isinstance(crudos.get(codigo), dict):
            continue
        crudo = crudos[codigo]
        uno = {}
        for campo, maximo in (('titulo', 300), ('descripcion', 2000), ('mensaje_final', 500)):
            texto = modelo._rico(crudo.get(campo), maximo)
            if texto:
                uno[campo] = texto
        por_elemento = crudo.get('elementos') if isinstance(crudo.get('elementos'), dict) else {}
        uno['elementos'] = {}
        for ident, valor in por_elemento.items():
            if ident in por_id and ident != pregunta:
                limpio = _textos_elemento(valor, por_id[ident])
                if limpio:
                    uno['elementos'][ident] = limpio
        textos[codigo] = uno

    return {'base': base, 'lista': lista[:LIMITE_IDIOMAS], 'pregunta': pregunta,
            'textos': textos}


# ---------------------------------------------------------------------------
# Traducir para quien responde
# ---------------------------------------------------------------------------
def _idiomas(definicion):
    return definicion.get('idiomas') or None


def elegible(definicion, codigo):
    """El código si el formulario lo ofrece y no es el base; si no, None."""
    idiomas = _idiomas(definicion)
    if not idiomas or codigo not in idiomas['lista'] or codigo == idiomas['base']:
        return None
    return codigo


def _lista_traducida(base, traducida):
    traducida = traducida or []
    return [(traducida[i] if i < len(traducida) and traducida[i] else original)
            for i, original in enumerate(base)]


def traducir(definicion, codigo):
    """Copia de la definición en ese idioma. Con un idioma que no ofrece, la
    misma definición. Lo que falte de traducir queda en el idioma base."""
    codigo = elegible(definicion, codigo)
    if not codigo:
        return definicion
    textos = _idiomas(definicion)['textos'].get(codigo) or {}
    nueva = copy.deepcopy(definicion)
    for campo in ('titulo', 'descripcion', 'mensaje_final'):
        if textos.get(campo):
            nueva[campo] = textos[campo]
    for elemento in nueva.get('elementos', []):
        propio = (textos.get('elementos') or {}).get(elemento['id'])
        if not propio:
            continue
        for campo in _RICOS + _ETIQUETAS:
            if propio.get(campo) and campo in elemento:
                elemento[campo] = propio[campo]
        for campo in _LISTAS:
            if elemento.get(campo):
                antes = elemento[campo]
                elemento[campo] = _lista_traducida(antes, propio.get(campo))
                if campo == 'opciones':
                    # Los saltos van por el TEXTO de la opción: hay que
                    # renombrarlos con la opción traducida o se pierden.
                    cambio = dict(zip(antes, elemento[campo]))
                    if elemento.get('saltos'):
                        elemento['saltos'] = {cambio.get(o, o): d
                                              for o, d in elemento['saltos'].items()}
    nueva['_idioma'] = codigo
    return nueva


def para_publico(definicion):
    """Lo que la página necesita para ofrecer el cambio de idioma."""
    idiomas = _idiomas(definicion)
    if not idiomas:
        return None
    return {
        'base': idiomas['base'],
        'actual': definicion.get('_idioma') or idiomas['base'],
        'pregunta': idiomas['pregunta'],
        'lista': [{'codigo': c, 'nombre': CATALOGO[c]} for c in idiomas['lista']],
    }


# ---------------------------------------------------------------------------
# Respuestas: del idioma de quien responde al base, y al revés
# ---------------------------------------------------------------------------
def codigo_de_respuestas(definicion, enviado):
    """En qué idioma viene un envío: lo dice la pregunta «Idioma»."""
    idiomas = _idiomas(definicion)
    if not idiomas or not idiomas['pregunta'] or not isinstance(enviado, dict):
        return None
    elegido = enviado.get(idiomas['pregunta'])
    for codigo in idiomas['lista']:
        if elegido == CATALOGO[codigo]:
            return elegible(definicion, codigo)
    return None


def _mapear(valor, mapa):
    if isinstance(valor, list):
        return [mapa.get(v, v) if isinstance(v, str) else v for v in valor]
    return mapa.get(valor, valor) if isinstance(valor, str) else valor


def _convertir(definicion, codigo, respuestas, al_base):
    if not codigo or not isinstance(respuestas, dict):
        return respuestas
    textos = (_idiomas(definicion)['textos'].get(codigo) or {}).get('elementos') or {}
    salida = dict(respuestas)
    for pregunta in modelo.preguntas(definicion):
        propio = textos.get(pregunta['id'])
        if not propio or pregunta['id'] not in salida:
            continue
        mapas = {}
        for campo in _LISTAS:
            base = pregunta.get(campo) or []
            traducida = _lista_traducida(base, propio.get(campo))
            pares = zip(traducida, base) if al_base else zip(base, traducida)
            mapas[campo] = dict(pares)
        valor = salida[pregunta['id']]
        if isinstance(valor, dict):          # cuadrícula: {fila: columna(s)}
            salida[pregunta['id']] = {
                mapas['filas'].get(fila, fila): _mapear(elegido, mapas['columnas'])
                for fila, elegido in valor.items()}
        elif mapas.get('opciones'):
            salida[pregunta['id']] = _mapear(valor, mapas['opciones'])
    return salida


def al_base(definicion, enviado):
    """Las respuestas de un envío, escritas como en el idioma base.

    Se hace ANTES de validar: así la validación, los saltos, la calificación y la
    hoja trabajan con el formulario de siempre. Lo escrito a mano (respuestas
    abiertas, «Otro») se queda como vino.
    """
    return _convertir(definicion, codigo_de_respuestas(definicion, enviado),
                      enviado, al_base=True)


def al_idioma(definicion, codigo, respuestas):
    """Al revés: para «modificar mi respuesta» en el idioma en que se dio."""
    return _convertir(definicion, elegible(definicion, codigo), respuestas,
                      al_base=False)
