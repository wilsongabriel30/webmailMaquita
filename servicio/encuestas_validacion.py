# -*- coding: utf-8 -*-
"""
Formularios del Almacén — validación de respuestas
==================================================
La «Validación de respuestas» del menú ⋮ de cada pregunta, como en Google
Forms: además de exigir que se responda (obligatoria), se puede exigir QUÉ se
responde — un número entre 18 y 65, un texto que contenga «@maquita», entre 2 y
4 casillas marcadas…

POR QUÉ ESTÁ AQUÍ Y NO EN `encuestas_modelo.py`
-----------------------------------------------
Son dos cosas: el modelo dice cómo es una pregunta, y esto dice cuándo una
RESPUESTA vale. Metido allí, `_limpiar_pregunta()` habría crecido con veinte
reglas que no tienen nada que ver con la forma del formulario, y la
comprobación —que la usa la página pública, no el editor— habría quedado en un
archivo que el editor carga entero.

Este archivo no importa al modelo: recibe la pregunta ya limpia y devuelve
textos. Así se puede probar solo, y no hay import circular.

LA COMPROBACIÓN DE VERDAD ES ESTA
---------------------------------
`encuesta-validacion.js` repite estas mismas reglas en el navegador, pero eso es
para avisar mientras se responde. Quien decide si una respuesta entra es este
archivo: el JavaScript se puede saltar con la consola abierta.

Autoría: Equipo de Tecnología Maquita — 2026-09-09
"""
import re

import encuestas_identificacion as identificacion

# Qué clase de validación admite cada tipo de pregunta. Es el mismo reparto de
# Google: los números y el texto solo tienen sentido en una respuesta escrita, y
# «cuántas casillas» solo en las casillas.
CLASES_POR_TIPO = {
    'texto_corto': ('numero', 'texto', 'longitud', 'expresion',
                    'identificacion'),
    'parrafo': ('longitud', 'expresion'),
    'casillas': ('seleccion',),
}

REGLAS = {
    'numero': ('mayor', 'mayor_igual', 'menor', 'menor_igual', 'igual',
               'distinto', 'entre', 'no_entre', 'es_numero', 'es_entero'),
    'texto': ('contiene', 'no_contiene', 'correo', 'url'),
    'longitud': ('max_caracteres', 'min_caracteres'),
    'expresion': ('contiene', 'no_contiene', 'coincide', 'no_coincide'),
    'seleccion': ('al_menos', 'como_maximo', 'exactamente'),
    # Cédula y RUC de Ecuador (10/09/2026). Las reglas, en
    # `encuestas_identificacion.py`.
    'identificacion': ('cedula', 'ruc', 'cedula_o_ruc'),
}

# Las reglas que necesitan un segundo número («entre 18 y 65»).
REGLAS_CON_DOS = ('entre', 'no_entre')
# Las que no necesitan ninguno («es un número», «es un correo»).
REGLAS_SIN_VALOR = ('es_numero', 'es_entero', 'correo', 'url',
                    'cedula', 'ruc', 'cedula_o_ruc')

LIMITE_MENSAJE = 200
LIMITE_VALOR = 200
# Una expresión regular más larga que esto no es una validación de formulario,
# es otra cosa. El tope es además la primera defensa contra una expresión
# escrita para colgar al servidor (ver `_expresion_segura`).
LIMITE_EXPRESION = 200

# Correo y URL se comprueban con la misma expresión que el resto de Raíces usa
# para el correo de quien responde: dos criterios distintos para «correo válido»
# en el mismo formulario sería confuso de explicar y peor de depurar.
_CORREO = re.compile(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$')
_URL = re.compile(r'^https?://[^\s.]+\.[^\s]+$', re.IGNORECASE)

# Un cuantificador dentro de otro —`(a+)+`, `(a*)*`, `(\d+)*`— es lo que hace
# que una expresión regular tarde años en un texto de treinta caracteres. No se
# admiten: es la única forma de estar seguros sin poder poner un cronómetro al
# `re` de Python (el módulo `regex`, que sí acepta timeout, no está instalado).
_ANIDADO = re.compile(r'\([^()]*[+*]\s*\)\s*[+*{]')


def _texto(valor, tope):
    return str(valor or '').strip()[:tope]


# Un número tal como se escribe a mano: signo, cifras y, si acaso, decimales
# con coma o con punto. `float()` admitía además «1e3», «inf», «nan», «1_000» y
# cifras de otros alfabetos, y el navegador no, así que la misma respuesta
# podía valer en un lado y no en el otro (10/09/2026). Con esta forma los dos
# dicen lo mismo, y «inf» o «nan» dejan de pasar por «es un número».
_NUMERO = re.compile(r'[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)')


def _numero(valor):
    """El texto como número, o None si no lo es. Acepta la coma decimal: aquí
    se escribe «3,5» mucho más a menudo que «3.5»."""
    texto = str(valor if valor is not None else '').strip()
    if not _NUMERO.fullmatch(texto):
        return None
    return float(texto.replace(',', '.'))


def _como_texto(numero):
    """El número tal como se escribiría a mano: «18», no «18.0».

    Se guarda como texto y se enseña en el mensaje de error («Escribe un número
    entre 18 y 65»), así que el `.0` que arrastra el float se vería.
    """
    return str(int(numero)) if float(numero).is_integer() else str(numero)


def _entero(valor, defecto=1):
    try:
        return int(float(str(valor).strip().replace(',', '.')))
    except (TypeError, ValueError):
        return defecto


def _expresion_segura(patron):
    """La expresión compilada, o None si no se puede admitir.

    Se rechaza lo que no compila (una errata dejaría la pregunta imposible de
    responder) y lo que lleva un cuantificador anidado.
    """
    if not patron or _ANIDADO.search(patron):
        return None
    try:
        return re.compile(patron)
    except re.error:
        return None


# ---------------------------------------------------------------------------
# Limpieza (qué se guarda en el `.forma`)
# ---------------------------------------------------------------------------
def limpiar(bruto, tipo):
    """La validación de una pregunta, saneada, o None si no tiene.

    Se descarta entera en vez de corregirla a medias: una validación a la que
    le falta el número contra el que comparar no rechaza nada, y dejarla
    guardada haría creer que la pregunta está protegida cuando no lo está.
    """
    if not isinstance(bruto, dict):
        return None

    clases = CLASES_POR_TIPO.get(tipo)
    if not clases:
        return None

    clase = _texto(bruto.get('clase'), 20)
    if clase not in clases:
        return None

    regla = _texto(bruto.get('regla'), 20)
    if regla not in REGLAS[clase]:
        return None

    validacion = {
        'clase': clase,
        'regla': regla,
        'valor': '',
        'valor2': '',
        'mensaje': _texto(bruto.get('mensaje'), LIMITE_MENSAJE),
    }

    if regla in REGLAS_SIN_VALOR:
        return validacion

    if clase == 'expresion':
        patron = _texto(bruto.get('valor'), LIMITE_EXPRESION)
        if _expresion_segura(patron) is None:
            return None
        validacion['valor'] = patron
        return validacion

    if clase == 'texto':
        valor = _texto(bruto.get('valor'), LIMITE_VALOR)
        if not valor:
            return None
        validacion['valor'] = valor
        return validacion

    # Numéricas: número, longitud y selección.
    primero = _numero(bruto.get('valor'))
    if primero is None:
        return None
    if clase in ('longitud', 'seleccion'):
        primero = max(0, int(primero))
    validacion['valor'] = _como_texto(primero)

    if regla in REGLAS_CON_DOS:
        segundo = _numero(bruto.get('valor2'))
        if segundo is None:
            return None
        # «Entre 65 y 18» es lo mismo que «entre 18 y 65» y es un despiste
        # fácil de cometer: se ordena en vez de rechazarlo.
        if segundo < primero:
            primero, segundo = segundo, primero
            validacion['valor'] = _como_texto(primero)
        validacion['valor2'] = _como_texto(segundo)

    return validacion


# ---------------------------------------------------------------------------
# Comprobación (¿esta respuesta vale?)
# ---------------------------------------------------------------------------
def _por_defecto(validacion):
    """Qué decirle a quien responde cuando el formulario no puso su mensaje.

    Google deja un «El valor introducido no cumple los requisitos» para todo.
    Aquí se dice el requisito concreto: quien responde no ve la configuración
    de la pregunta y, sin esto, no tiene forma de saber qué se espera.
    """
    regla, uno, dos = validacion['regla'], validacion['valor'], validacion['valor2']
    textos = {
        'mayor': 'Escribe un número mayor que %s.' % uno,
        'mayor_igual': 'Escribe un número mayor o igual que %s.' % uno,
        'menor': 'Escribe un número menor que %s.' % uno,
        'menor_igual': 'Escribe un número menor o igual que %s.' % uno,
        'igual': 'El número tiene que ser %s.' % uno,
        'distinto': 'El número no puede ser %s.' % uno,
        'entre': 'Escribe un número entre %s y %s.' % (uno, dos),
        'no_entre': 'Escribe un número que no esté entre %s y %s.' % (uno, dos),
        'es_numero': 'Escribe un número.',
        'es_entero': 'Escribe un número entero, sin decimales.',
        'correo': 'Escribe un correo electrónico, del estilo nombre@dominio.com.',
        'url': 'Escribe una dirección web que empiece por http:// o https://.',
        'max_caracteres': 'Como máximo %s caracteres.' % uno,
        'min_caracteres': 'Escribe al menos %s caracteres.' % uno,
        'al_menos': 'Marca al menos %s opciones.' % uno,
        'como_maximo': 'Marca como máximo %s opciones.' % uno,
        'exactamente': 'Marca exactamente %s opciones.' % uno,
        'cedula': 'Escribe un número de cédula válido (10 dígitos).',
        'ruc': 'Escribe un RUC válido (13 dígitos).',
        'cedula_o_ruc': 'Escribe un número de cédula (10 dígitos) o de RUC '
                        '(13 dígitos) válido.',
    }
    if validacion['clase'] == 'expresion':
        return 'La respuesta no tiene el formato esperado.'
    if regla == 'contiene':
        return 'La respuesta tiene que contener «%s».' % uno
    if regla == 'no_contiene':
        return 'La respuesta no puede contener «%s».' % uno
    return textos.get(regla, 'La respuesta no cumple lo que pide la pregunta.')


def _cumple(validacion, valor):
    """El corazón de todo: ¿este valor pasa esta regla?"""
    clase, regla = validacion['clase'], validacion['regla']
    uno = validacion['valor']
    dos = validacion['valor2']

    if clase == 'seleccion':
        cuantas = len(valor) if isinstance(valor, list) else (0 if valor in (None, '') else 1)
        tope = _entero(uno)
        if regla == 'al_menos':
            return cuantas >= tope
        if regla == 'como_maximo':
            return cuantas <= tope
        return cuantas == tope

    texto = '' if valor is None else str(valor)

    if clase == 'identificacion':
        if regla == 'cedula':
            return identificacion.es_cedula(texto)
        if regla == 'ruc':
            return identificacion.es_ruc(texto)
        return identificacion.es_cedula_o_ruc(texto)

    if clase == 'longitud':
        tope = _entero(uno)
        return len(texto) <= tope if regla == 'max_caracteres' else len(texto) >= tope

    if clase == 'texto':
        if regla == 'correo':
            return bool(_CORREO.match(texto))
        if regla == 'url':
            return bool(_URL.match(texto))
        # «Contiene» sin distinguir mayúsculas: nadie que escriba una validación
        # de formulario espera que «Quito» y «quito» sean cosas distintas.
        hay = uno.lower() in texto.lower()
        return hay if regla == 'contiene' else not hay

    if clase == 'expresion':
        compilada = _expresion_segura(uno)
        if compilada is None:
            return True          # sin expresión válida no se rechaza nada
        # El texto se acota antes de pasarlo: una expresión legítima sobre un
        # texto larguísimo también puede tardar de más.
        recorte = texto[:1000]
        if regla in ('contiene', 'no_contiene'):
            hay = bool(compilada.search(recorte))
            return hay if regla == 'contiene' else not hay
        casa = bool(compilada.fullmatch(recorte))
        return casa if regla == 'coincide' else not casa

    # clase == 'numero'
    numero = _numero(texto)
    if numero is None:
        return False             # «es un número» y todas las demás lo exigen
    if regla in ('es_numero',):
        return True
    if regla == 'es_entero':
        return float(numero).is_integer()
    limite = _numero(uno)
    if limite is None:
        return True
    if regla == 'mayor':
        return numero > limite
    if regla == 'mayor_igual':
        return numero >= limite
    if regla == 'menor':
        return numero < limite
    if regla == 'menor_igual':
        return numero <= limite
    if regla == 'igual':
        return numero == limite
    if regla == 'distinto':
        return numero != limite
    limite2 = _numero(dos)
    if limite2 is None:
        return True
    dentro = limite <= numero <= limite2
    return dentro if regla == 'entre' else not dentro


def comprobar(pregunta, valor):
    """El mensaje de error, o None si la respuesta vale.

    Una pregunta sin responder NO se valida: eso lo decide `obligatoria`. Si no
    fuera así, una validación convertiría en obligatoria una pregunta que no lo
    es, que es justo lo que la gente no espera.
    """
    validacion = (pregunta or {}).get('validacion')
    if not validacion:
        return None
    if valor is None or valor == '' or valor == []:
        return None
    if _cumple(validacion, valor):
        return None
    return validacion.get('mensaje') or _por_defecto(validacion)
