# -*- coding: utf-8 -*-
"""
Formularios del Almacén — código QR del enlace público

El QR NO es una puerta aparte: codifica exactamente el mismo enlace
`/formulario/<token>`, así que hereda todas las restricciones configuradas
—acepta o no respuestas, solo gente con la sesión iniciada, una respuesta por
persona— y deja de funcionar en cuanto se revoca el enlace. Por eso no se
genera si el formulario todavía no está publicado: un QR sin token sería un
cartel que lleva a un 404.

Se reutiliza el mismo criterio que el generador de QR del sistema
(`interfaces/api/herramientas/qr.py`): corrección de errores H (30 %), que
tolera que el cartel se manche o se despegue una esquina.

Autoría: Equipo de Tecnología Maquita — 2026-08-25
"""
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.svg import SvgPathImage

TAMANO_MIN, TAMANO_MAX, TAMANO_DEFECTO = 128, 2048, 720
FORMATOS = ('png', 'svg')


def _construir(enlace, factory=None):
    qr = qrcode.QRCode(
        version=None,               # el tamaño lo decide el contenido
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,                   # zona de silencio estándar; sin ella no lee
        image_factory=factory,
    )
    qr.add_data(enlace)
    qr.make(fit=True)
    return qr


def png(enlace, tamano=TAMANO_DEFECTO):
    """PNG cuadrado del tamaño pedido. Para pegar en un cartel o un correo."""
    from PIL import Image

    tamano = min(max(int(tamano or TAMANO_DEFECTO), TAMANO_MIN), TAMANO_MAX)
    imagen = _construir(enlace).make_image(
        fill_color='black', back_color='white').get_image()
    # NEAREST y no un remuestreo suave: un QR difuminado pierde legibilidad.
    imagen = imagen.resize((tamano, tamano), Image.NEAREST)

    memoria = io.BytesIO()
    imagen.save(memoria, format='PNG')
    memoria.seek(0)
    return memoria


def svg(enlace):
    """SVG vectorial: es lo que hay que mandar a imprenta para un cartel."""
    memoria = io.BytesIO()
    _construir(enlace, factory=SvgPathImage).make_image().save(memoria)
    memoria.seek(0)
    return memoria


def _corto(momento):
    """«12/09/2026 a las 17:30», para caber en un aviso de una línea."""
    return momento.strftime('%d/%m/%Y a las %H:%M') if momento else ''


def restricciones(fila):
    """Frases que describen a qué lleva este QR, para avisar ANTES de imprimir.

    Un cartel es difícil de recoger: quien lo pega tiene que saber si el
    formulario está cerrado o si pide sesión iniciada, porque el QR se lo va a
    encontrar la gente en la pared.
    """
    if not fila:
        return ['Este formulario todavía no tiene enlace.']

    avisos = []

    # El plazo, lo primero: un cartel con QR se pega y se olvida, y si la
    # encuesta cierra el viernes hay que saberlo ANTES de mandarlo a imprimir.
    import encuestas_ajustes as ajustes_mod
    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    estado, apertura, cierre = ajustes_mod.estado_plazo(ajustes)
    if estado == 'antes':
        avisos.append('TODAVÍA NO ESTÁ ABIERTO: quien escanee antes del %s '
                      'verá un aviso.' % _corto(apertura))
    elif estado == 'despues':
        avisos.append('EL PLAZO YA TERMINÓ (%s): el código no sirve para '
                      'responder.' % _corto(cierre))
    elif cierre:
        avisos.append('Deja de aceptar respuestas el %s.' % _corto(cierre))

    if not fila.get('abierta'):
        avisos.append('AHORA MISMO NO ACEPTA RESPUESTAS: quien escanee verá un '
                      'aviso de formulario cerrado.')
    if fila.get('solo_internos'):
        avisos.append('Solo responde quien tenga la sesión iniciada: no sirve para '
                      'público externo.')
    if fila.get('una_por_persona'):
        avisos.append('Una respuesta por persona.')
    if not avisos:
        avisos.append('Abierto a cualquiera que escanee el código.')
    return avisos
