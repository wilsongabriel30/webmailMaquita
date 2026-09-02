# -*- coding: utf-8 -*-
"""Mandar un correo desde el Almacén, pase lo que pase.

Responsabilidad ÚNICA: entregar un correo y **decir qué ocurrió**.

POR QUÉ EXISTE (01/09/2026)
Los avisos de «piden acceso» no llegaban. El servidor de correo estaba bien
—se comprobó enviando a mano— y la configuración también, pero el aviso se
apoyaba solo en `email_service` de FARO, y cuando ese servicio no puede enviar
devuelve False sin más: el aviso se perdía en silencio y nadie se enteraba.

Ahora hay dos caminos y un rastro:
  1. `email_service` de FARO, que es el de siempre.
  2. Si no puede, se envía **directamente** por SMTP con la misma configuración
     (tabla `system_config`), que es exactamente lo que hace FARO por dentro.

Y en los dos casos queda escrito en el registro del Almacén qué pasó, para no
volver a quedarnos a ciegas.
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr

log = logging.getLogger('almacen.correo')


def _config_smtp():
    """La configuración de correo de la casa, la misma que usa FARO."""
    from almacen_bd import consultar
    filas = consultar("""
        SELECT smtp_host, smtp_port, smtp_username, smtp_password,
               smtp_use_tls, smtp_use_ssl, smtp_sender_name, smtp_sender_email
        FROM system_config LIMIT 1
    """, (), nomina=True)
    if not filas or not filas[0].get('smtp_host'):
        return None
    fila = filas[0]
    return {
        'host': fila['smtp_host'],
        'puerto': int(fila['smtp_port'] or 587),
        'usuario': fila['smtp_username'],
        'clave': fila['smtp_password'],
        'tls': bool(fila['smtp_use_tls']),
        'ssl': bool(fila['smtp_use_ssl']),
        'nombre': fila['smtp_sender_name'] or 'Drive Maquita',
        'remitente': fila['smtp_sender_email'] or fila['smtp_username'],
    }


def _por_faro(destino, asunto, cuerpo):
    try:
        from compartido.servicios.email_service import email_service
        if not email_service.puede_enviar():
            log.info('Correo: el servicio de FARO dice que no puede enviar')
            return False
        return bool(email_service.enviar_correo(destino, asunto, cuerpo))
    except Exception as excepcion:
        log.info('Correo: el servicio de FARO no se pudo usar (%s)', excepcion)
        return False


def _directo(destino, asunto, cuerpo):
    """El mismo servidor, hablado directamente. Es el plan B."""
    config = _config_smtp()
    if not config or not config['host'] or not config['usuario']:
        log.warning('Correo: no hay configuracion de envio en system_config')
        return False
    mensaje = MIMEText(cuerpo, 'html', 'utf-8')
    mensaje['Subject'] = asunto
    mensaje['From'] = formataddr((config['nombre'], config['remitente']))
    mensaje['To'] = destino
    try:
        if config['ssl']:
            servidor = smtplib.SMTP_SSL(config['host'], config['puerto'], timeout=20)
        else:
            servidor = smtplib.SMTP(config['host'], config['puerto'], timeout=20)
            if config['tls']:
                servidor.starttls(context=ssl.create_default_context())
        if config['clave']:
            servidor.login(config['usuario'], config['clave'])
        servidor.sendmail(config['remitente'], [destino], mensaje.as_string())
        servidor.quit()
        return True
    except Exception as excepcion:
        log.warning('Correo: no se pudo enviar a %s (%s)', destino, excepcion)
        return False


def enviar(destino, asunto, cuerpo_html):
    """Devuelve True si el correo salió. Nunca lanza."""
    destino = (destino or '').strip()
    if not destino:
        log.warning('Correo: no hay a quien enviar «%s»', asunto)
        return False
    if _por_faro(destino, asunto, cuerpo_html):
        log.info('Correo enviado a %s por el servicio de FARO: %s', destino, asunto)
        return True
    if _directo(destino, asunto, cuerpo_html):
        log.info('Correo enviado a %s directamente: %s', destino, asunto)
        return True
    log.warning('Correo NO enviado a %s: %s', destino, asunto)
    return False
