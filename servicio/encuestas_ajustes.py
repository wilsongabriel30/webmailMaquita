# -*- coding: utf-8 -*-
"""
Formularios del Almacén — ajustes de la pestaña «Configuración»

Los tres ajustes históricos (abierta, solo_internos, una_por_persona) siguen en
sus columnas. El resto vive en una columna JSONB: son muchos y van a seguir
creciendo, y así no hace falta un ALTER TABLE por cada opción nueva.

Aquí está la lista cerrada de lo que se admite y, sobre todo, **las
dependencias entre opciones**. Se resuelven en un solo sitio y se aplican en el
servidor, no en la pantalla: una opción que se deja marcar pero no se cumple es
peor que no tenerla.

Autoría: Equipo de Tecnología Maquita — 2026-08-25
"""

import re
from datetime import datetime

# --- opciones de lista -------------------------------------------------------
CORREO_NO = 'no'
CORREO_ESCRITO = 'entrada'
# 27/08/2026 — quedan DOS formas de recoger el correo, no tres:
#
#   'no'       no se pide
#   'entrada'  se pide y se comprueba que la dirección esté bien escrita
#              (es lo que la pantalla llama «Verificadas»)
#
# «Verificadas» significaba antes «tomarlo de la cuenta de FARO», lo que obligaba
# a cerrar el formulario a la gente de la casa. Esa tercera vía se retira: quien
# la tenía activada pasa a la de pedirlo escrito, que hace lo mismo para quien
# rellena el formulario —le piden su correo— y además funciona para gente de
# fuera, que es a quien se reparte el enlace y el QR.
CORREO_VERIFICADO = 'verificadas'      # solo para traducir lo ya guardado
CORREOS = (CORREO_NO, CORREO_ESCRITO)

NOTA_INMEDIATA = 'inmediata'
NOTA_MANUAL = 'manual'
NOTAS = (NOTA_INMEDIATA, NOTA_MANUAL)

COPIA_NO = 'no'
COPIA_SOLICITUD = 'solicitud'
COPIA_SIEMPRE = 'siempre'
COPIAS = (COPIA_NO, COPIA_SOLICITUD, COPIA_SIEMPRE)

# --- valores por defecto -----------------------------------------------------
# `enlace_otra_respuesta` arranca activado, como en Google.
POR_DEFECTO = {
    'recopilar_correo': CORREO_NO,
    'copia_respuesta': COPIA_NO,
    'permitir_editar': False,
    'barra_progreso': False,
    'preguntas_aleatorias': False,
    'enlace_otra_respuesta': True,
    'ver_resumen': False,
    'sin_autoguardado': False,
    # Anónimo de verdad: no se guarda NI el usuario NI el correo, aunque quien
    # responda tenga la sesión abierta.
    'anonimo': False,
    # Plazo para responder. Cadenas 'AAAA-MM-DDTHH:MM' o '' si no hay límite.
    'abre_en': '',
    'cierra_en': '',
    # Modo cuestionario
    'cuestionario': False,
    'publicar_nota': NOTA_INMEDIATA,
    'ver_falladas': True,
    'ver_correctas': True,
    'ver_puntuacion': True,
}

# Preferencias del usuario: se aplican a los formularios que cree a partir de
# ahora, no a los que ya existen.
PREFERENCIAS_POR_DEFECTO = {
    'pred_recopilar_correo': CORREO_NO,
    'pred_obligatorias': False,
}


# Formato del <input type="datetime-local">: 'AAAA-MM-DDTHH:MM'. Se guarda tal
# cual, en hora local de Ecuador, que es la que la persona escribe y la que le
# van a leer. Guardarlo en UTC obligaría a convertir en cinco sitios y a que
# quien mire la base de datos hiciera la cuenta de cabeza.
_MOMENTO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')


def _fecha(bruto):
    """Un momento válido, o cadena vacía si no lo es."""
    texto = str(bruto or '').strip()[:16]
    if not texto or not _MOMENTO.match(texto):
        return ''
    try:
        datetime.strptime(texto, '%Y-%m-%dT%H:%M')
    except ValueError:
        return ''            # 2026-02-31, por ejemplo
    return texto


def momento(texto):
    """El texto convertido a `datetime`, o None."""
    texto = _fecha(texto)
    if not texto:
        return None
    return datetime.strptime(texto, '%Y-%m-%dT%H:%M')


def estado_plazo(ajustes, ahora=None):
    """¿Se puede responder ahora mismo, según el plazo?

    Devuelve ('antes'|'dentro'|'despues', apertura, cierre). El plazo se
    comprueba SIEMPRE en el servidor: la hora del navegador la pone quien
    responde, así que no sirve para decidir nada.
    """
    ahora = ahora or datetime.now()
    apertura = momento(ajustes.get('abre_en'))
    cierre = momento(ajustes.get('cierra_en'))
    if apertura and ahora < apertura:
        return 'antes', apertura, cierre
    if cierre and ahora > cierre:
        return 'despues', apertura, cierre
    return 'dentro', apertura, cierre


def limpiar(bruto):
    """Deja solo lo conocido, con el tipo correcto."""
    bruto = bruto if isinstance(bruto, dict) else {}
    limpio = dict(POR_DEFECTO)

    correo = bruto.get('recopilar_correo')
    if correo == CORREO_VERIFICADO:
        correo = CORREO_ESCRITO      # ver la nota de las constantes
    if correo in CORREOS:
        limpio['recopilar_correo'] = correo

    copia = bruto.get('copia_respuesta')
    if copia in COPIAS:
        limpio['copia_respuesta'] = copia

    nota = bruto.get('publicar_nota')
    if nota in NOTAS:
        limpio['publicar_nota'] = nota

    for clave in ('abre_en', 'cierra_en'):
        limpio[clave] = _fecha(bruto.get(clave))

    for clave in ('permitir_editar', 'barra_progreso', 'preguntas_aleatorias',
                  'enlace_otra_respuesta', 'ver_resumen', 'sin_autoguardado',
                  'anonimo',
                  'cuestionario', 'ver_falladas', 'ver_correctas',
                  'ver_puntuacion'):
        if clave in bruto:
            limpio[clave] = bool(bruto[clave])

    return limpio


def limpiar_preferencias(bruto):
    bruto = bruto if isinstance(bruto, dict) else {}
    limpio = dict(PREFERENCIAS_POR_DEFECTO)
    if bruto.get('pred_recopilar_correo') in CORREOS:
        limpio['pred_recopilar_correo'] = bruto['pred_recopilar_correo']
    if 'pred_obligatorias' in bruto:
        limpio['pred_obligatorias'] = bool(bruto['pred_obligatorias'])
    return limpio


def coherentes(ajustes, solo_internos, una_por_persona, abriendo=False,
               quitando_correo=False):
    """Aplica las dependencias reales entre opciones.

    Devuelve (ajustes, solo_internos, una_por_persona) ya cuadrados, y la lista
    de ajustes que se han tenido que forzar, para poder decirlo en pantalla.

    `abriendo` (27/08/2026) es la clave de en qué DIRECCIÓN se resuelve un
    choque. Dos opciones pueden ser incompatibles y hay que ceder por algún
    lado; el problema es elegir por cuál:

    - Sin `abriendo`, gana la restricción: si el formulario recoge el correo
      verificado, se exige la sesión. Es lo correcto mientras nadie diga otra
      cosa, porque una opción activada tiene que cumplirse de verdad.
    - Con `abriendo` —la persona acaba de DESMARCAR «solo para personas de
      Maquita»—, gana su decisión y cede la otra opción: el correo verificado
      pasa a pedirse escrito y el límite de una respuesta por persona se quita.

    Antes solo existía la primera dirección, y el resultado era que quitar «solo
    para personas de Maquita» no servía de nada: se volvía a activar solo y el
    enlace y el QR seguían pidiendo iniciar sesión, sin que se entendiera por
    qué. Deshacer una restricción tiene que poder hacerse desde la opción que se
    está mirando.
    """
    ajustes = dict(ajustes)
    solo_internos = bool(solo_internos)
    una_por_persona = bool(una_por_persona)
    forzados = []

    # 1) Anónimo manda sobre todo lo que identifique. No es una preferencia
    #    que se pueda combinar: o no se sabe quién respondió, o se sabe. Si se
    #    dejaran juntas, el formulario prometería anonimato mientras guarda el
    #    correo o el usuario, que es la peor de las mentiras posibles aquí.
    #
    #    Va PRIMERO a propósito: apaga cosas de las que dependen las reglas de
    #    abajo. Si fuera al final, «una respuesta por persona» ya habría
    #    activado la sesión obligatoria por un motivo que el anonimato acaba de
    #    eliminar, y quedaría una restricción sin razón que la sostenga.
    if ajustes['anonimo']:
        if ajustes['recopilar_correo'] != CORREO_NO:
            ajustes['recopilar_correo'] = CORREO_NO
            forzados.append('Se dejó de pedir el correo: la encuesta es anónima.')
        if ajustes['copia_respuesta'] != COPIA_NO:
            ajustes['copia_respuesta'] = COPIA_NO
            forzados.append('No se envía copia por correo: sin correo no hay '
                            'a dónde mandarla, y pedirlo rompería el anonimato.')
        if ajustes['permitir_editar']:
            ajustes['permitir_editar'] = False
            forzados.append('No se pueden modificar las respuestas: haría falta '
                            'reconocer quién las envió.')
        if una_por_persona:
            una_por_persona = False
            forzados.append('Se quitó el límite de una respuesta por persona: '
                            'para aplicarlo habría que saber quién responde.')
        if solo_internos:
            # Exigir la sesión en una encuesta anónima no aporta nada: no se va
            # a guardar quién respondió, así que lo único que consigue es dejar
            # fuera a la gente de fuera (27/08/2026).
            solo_internos = False
            forzados.append('Se quitó «Solo personas de Maquita»: en una '
                            'encuesta anónima no hace falta iniciar sesión.')

    # 2) Para saber quién ya respondió hay que saber quién es, y hay DOS formas
    #    de saberlo: la sesión de FARO o el correo que el formulario recoge.
    #    Antes solo valía la primera, así que el límite obligaba a que quien
    #    respondiera fuera de la casa; con el correo vale también para gente de
    #    fuera, que es a quien se le reparte el enlace o el QR (27/08/2026).
    if una_por_persona and not solo_internos and \
            ajustes['recopilar_correo'] == CORREO_NO:
        if quitando_correo:
            una_por_persona = False
            forzados.append('Se quitó el límite de una respuesta por persona: '
                            'sin correo ni sesión no hay forma de reconocer a '
                            'quien responde.')
        elif abriendo:
            una_por_persona = False
            forzados.append('Se quitó el límite de una respuesta por persona: '
                            'sin sesión iniciada no hay forma de saber quién ya '
                            'respondió.')
        else:
            # Se pide el correo, no la sesión: es lo que menos cierra el
            # formulario de las dos formas de identificar a quien responde.
            ajustes['recopilar_correo'] = CORREO_ESCRITO
            forzados.append('Se pide el correo a quien responde: hace falta '
                            'reconocerlo para admitir una sola respuesta por '
                            'persona.')

    # 3) Pedir el correo y exigir la sesión de Maquita son incompatibles
    #    (27/08/2026). Si se pide el correo es porque va a responder gente de
    #    fuera —a quien se le manda el enlace o el QR—; para quien entra con su
    #    cuenta ya se sabe quién es sin preguntárselo. Dejar las dos juntas
    #    obliga a la misma persona a identificarse dos veces y cierra el
    #    formulario a quien iba dirigido.
    #
    #    Manda la opción de correo: es la que se acaba de elegir en el
    #    desplegable, y «solo personas de Maquita» queda apagada y sin poder
    #    marcarse mientras el correo se pida.
    if ajustes['recopilar_correo'] != CORREO_NO and solo_internos:
        solo_internos = False
        forzados.append('Se quitó «Solo personas de Maquita»: el formulario '
                        'pide el correo, así que puede responderlo cualquiera.')

    # 4) No se puede mandar copia a un correo que no se ha pedido.
    if (ajustes['copia_respuesta'] != COPIA_NO and
            ajustes['recopilar_correo'] == CORREO_NO):
        if quitando_correo:
            ajustes['copia_respuesta'] = COPIA_NO
            forzados.append('Ya no se envía copia de la respuesta: sin correo '
                            'no hay a dónde mandarla.')
        else:
            ajustes['recopilar_correo'] = CORREO_ESCRITO
            forzados.append('Se pide el correo a quien responde porque se le '
                            'envía una copia de su respuesta.')

    # 5) Editar la respuesta enviada exige poder reconocer a quien la envió.
    if ajustes['permitir_editar'] and not solo_internos and \
            ajustes['recopilar_correo'] == CORREO_NO:
        if quitando_correo:
            ajustes['permitir_editar'] = False
            forzados.append('Ya no se pueden modificar las respuestas: sin '
                            'correo ni sesión no hay forma de saber de quién '
                            'es cada una.')
        else:
            ajustes['recopilar_correo'] = CORREO_ESCRITO
            forzados.append('Se pide el correo porque, para poder modificar una '
                            'respuesta, hay que saber de quién es.')

    # 6) «Publicar la nota más tarde» significa justo eso: al entregar no se
    #    enseña ni la puntuación ni qué se falló, o no habría nada que publicar
    #    después. Google se comporta igual.
    if ajustes['cuestionario'] and ajustes['publicar_nota'] == NOTA_MANUAL:
        if ajustes['ver_puntuacion'] or ajustes['ver_falladas'] or \
                ajustes['ver_correctas']:
            ajustes['ver_puntuacion'] = False
            ajustes['ver_falladas'] = False
            ajustes['ver_correctas'] = False
            forzados.append('Como la calificación se publica más tarde, al '
                            'entregar no se muestra ni la nota ni las '
                            'respuestas correctas.')

    # 7) Un cierre anterior a la apertura dejaría el formulario inaccesible
    #    para siempre sin que se vea el motivo por ninguna parte.
    apertura = momento(ajustes.get('abre_en'))
    cierre = momento(ajustes.get('cierra_en'))
    if apertura and cierre and cierre <= apertura:
        ajustes['cierra_en'] = ''
        forzados.append('Se quitó la fecha de cierre porque era anterior a la '
                        'de apertura: así el formulario no se habría podido '
                        'responder nunca.')

    return ajustes, solo_internos, una_por_persona, forzados
