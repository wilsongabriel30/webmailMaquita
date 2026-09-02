# -*- coding: utf-8 -*-
"""
Formularios del Almacén — copia de la respuesta por correo

Cuando el formulario lo pide, a quien responde se le manda una copia de lo que
envió. Dos reglas que gobiernan todo este módulo:

1. **El correo nunca puede tumbar la respuesta.** La respuesta ya está guardada
   cuando esto se ejecuta; si el servidor de correo no contesta, se registra el
   fallo y se sigue. Perder una respuesta por un problema de SMTP sería mucho
   peor que no enviar el aviso.
2. **Se envía en un hilo aparte.** Un SMTP lento dejaría a la persona mirando
   una rueda después de haber pulsado «Enviar».

La configuración (servidor, puerto, remitente) se lee de `system_config`, la
misma que usa el resto del sistema; no se guardan credenciales aquí.

Autoría: Equipo de Tecnología Maquita — 2026-08-25
"""
import logging
import smtplib
import threading
from email.message import EmailMessage
from email.utils import parseaddr

import almacen_bd as bd

log = logging.getLogger('almacen.encuestas.correo')

TIEMPO_LIMITE = 20          # segundos por intento


def _configuracion():
    """SMTP tal como lo tiene configurado el sistema. None si no lo está."""
    try:
        with bd.conexion(nomina=True) as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT smtp_host, smtp_port, smtp_username, smtp_password,
                           smtp_use_tls, smtp_use_ssl, smtp_sender_name,
                           smtp_sender_email
                    FROM system_config LIMIT 1
                """)
                fila = cur.fetchone()
    except Exception as excepcion:
        log.warning('No se pudo leer la configuración de correo: %s', excepcion)
        return None

    if not fila or not fila[0]:
        return None
    return {
        'host': fila[0], 'puerto': int(fila[1] or 587),
        'usuario': fila[2], 'clave': fila[3],
        'tls': bool(fila[4]), 'ssl': bool(fila[5]),
        'nombre': fila[6] or 'Fundación Maquita',
        'remitente': fila[7] or fila[2],
    }


def disponible():
    """¿Se puede enviar? Lo consulta la pantalla para no ofrecer un imposible."""
    return _configuracion() is not None


def correo_valido(texto):
    """Validación deliberadamente simple: hay una cuenta y un dominio con punto.

    No se intenta adivinar si la dirección existe —eso solo lo dice el envío—,
    pero sí se descartan los errores de escritura evidentes.
    """
    if not texto or len(texto) > 254:
        return None
    direccion = parseaddr(str(texto).strip())[1]
    if not direccion or direccion.count('@') != 1:
        return None
    cuenta, dominio = direccion.split('@')
    if not cuenta or '.' not in dominio or dominio.startswith('.') \
            or dominio.endswith('.') or ' ' in direccion:
        return None
    # «gmail..com» pasaba: tiene punto, no empieza ni acaba en punto. Es un
    # error de tecleo de los frecuentes y ningún dominio real lo tiene.
    if '..' in direccion:
        return None
    return direccion


def enviar_copia(destino, titulo, lineas, enlace_edicion=None):
    """Lanza el envío en segundo plano. No devuelve nada ni lanza errores."""
    destino = correo_valido(destino)
    if not destino:
        return
    hilo = threading.Thread(
        target=_enviar, args=(destino, titulo, list(lineas), enlace_edicion),
        daemon=True)
    hilo.start()


def _enviar(destino, titulo, lineas, enlace_edicion):
    configuracion = _configuracion()
    if not configuracion:
        log.info('Copia no enviada a %s: no hay correo configurado', destino)
        return

    mensaje = EmailMessage()
    mensaje['Subject'] = 'Copia de tu respuesta: ' + (titulo or 'Formulario')
    mensaje['From'] = '%s <%s>' % (configuracion['nombre'],
                                   configuracion['remitente'])
    mensaje['To'] = destino
    mensaje.set_content(_cuerpo(titulo, lineas, enlace_edicion))

    try:
        if configuracion['ssl']:
            servidor = smtplib.SMTP_SSL(configuracion['host'],
                                        configuracion['puerto'],
                                        timeout=TIEMPO_LIMITE)
        else:
            servidor = smtplib.SMTP(configuracion['host'],
                                    configuracion['puerto'],
                                    timeout=TIEMPO_LIMITE)
            if configuracion['tls']:
                servidor.starttls()
        with servidor:
            if configuracion['usuario']:
                servidor.login(configuracion['usuario'], configuracion['clave'])
            servidor.send_message(mensaje)
        log.info('Copia de respuesta enviada a %s', destino)
    except Exception as excepcion:
        # A propósito no se reintenta ni se propaga: la respuesta ya está
        # guardada y quien la envió no debe enterarse de un fallo de correo.
        log.warning('No se pudo enviar la copia a %s: %s', destino, excepcion)


def _cuerpo(titulo, lineas, enlace_edicion):
    partes = ['Esta es la copia de la respuesta que enviaste'
              + (' a «%s»' % titulo if titulo else '') + '.', '']
    for pregunta, respuesta in lineas:
        partes.append('%s\n    %s' % (pregunta, respuesta or '(sin responder)'))
        partes.append('')
    if enlace_edicion:
        partes.append('Si necesitas cambiar algo, puedes modificar tu '
                      'respuesta aquí:')
        partes.append(enlace_edicion)
        partes.append('')
    partes.append('Este mensaje es automático; no hace falta contestarlo.')
    return '\n'.join(partes)
