# -*- coding: utf-8 -*-
"""
Correo de invitación al compartir del Almacén Maquita (fase B).
===============================================================
Cuando se comparte un archivo/carpeta a una PERSONA por correo (interno o
externo), se le envía la invitación con el enlace correcto:
  - documento office editable con rol editor → enlace de EDICIÓN en línea
    (/archivos-almacen/editar-publico?t=) — el invitado edita sin cuenta FARO;
  - cualquier otro caso → enlace de vista/descarga (/almacen-s/<token>).

Reglas:
  - BEST-EFFORT: si el correo falla, el compartir NO falla (se registra en log).
  - La CLAVE nunca viaja en el correo (se avisa que el remitente la entregará
    por otro medio) — misma práctica que los enlaces protegidos de Drive.
  - Emisor único: email_service de FARO (SMTP configurado en system_config).
    Import perezoso: en modo servicio independiente (sin FARO) simplemente
    no se envía y se registra el motivo.

Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import logging

from almacen_bd import consultar
from config_almacen import URL_LINKS

log = logging.getLogger('almacen.correo')

# Extensiones que abren en el editor en línea (mismas de api_onlyoffice)
_EDITABLES = {'docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp', 'txt', 'csv'}


def _nombre_remitente(usuario_id: int) -> str:
    try:
        filas = consultar("""
            SELECT COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id = %s
        """, (usuario_id,), nomina=True)
        if filas and filas[0]['nombre']:
            return filas[0]['nombre']
    except Exception:
        pass
    return 'Un compañero de Maquita'


def _enlace(compartido: dict) -> str:
    """Enlace correcto según destinatario, tipo de archivo y permiso."""
    token = compartido.get('token') or ''
    if not token:
        # Compartido con una persona DE Maquita (sin enlace público): el
        # correo la lleva a la ruta DENTRO de la app; si no tiene sesión,
        # el login la devuelve aquí (12/08/2026). Nunca un enlace de
        # descarga directa para el personal.
        from urllib.parse import quote
        return URL_LINKS + '/archivos-almacen' + quote(compartido.get('ruta') or '/')
    nombre = (compartido.get('ruta') or '').rsplit('/', 1)[-1]
    ext = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    if compartido.get('puede_editar') and ext in _EDITABLES:
        return f'{URL_LINKS}/e/{token}'
    return f'{URL_LINKS}/s/{token}'


def enviar_invitacion(compartido: dict, remitente_id: int) -> bool:
    """Envía la invitación del share `compartido` (dict de api_compartir).
    Devuelve True si salió el correo; False (sin lanzar) en cualquier fallo."""
    email = (compartido.get('email') or '').strip()
    # 12/08/2026: también se invita al compartir con una persona interna
    # (tipo usuario, sin token): el enlace va a la app con inicio de sesión.
    if not email:
        return False
    try:
        # Import perezoso: solo disponible cuando el motor corre dentro de FARO
        from compartido.servicios.email_service import email_service
        if not email_service.puede_enviar():
            log.warning('Invitación no enviada a %s: SMTP no configurado', email)
            return False
    except Exception as excepcion:
        log.warning('Invitación no enviada a %s: sin email_service (%s)', email, excepcion)
        return False

    remitente = _nombre_remitente(remitente_id)
    nombre = (compartido.get('ruta') or '').rsplit('/', 1)[-1] or 'un archivo'
    rol = 'editar' if compartido.get('puede_editar') else 'ver'
    enlace = _enlace(compartido)
    expira = compartido.get('expira_en')
    con_clave = bool(compartido.get('con_clave'))

    avisos = ''
    if expira:
        avisos += (f'<p style="color:#5f6368;font-size:13px;margin:6px 0 0;">'
                   f'El enlace caduca el {str(expira)[:10]}.</p>')
    if con_clave:
        avisos += ('<p style="color:#5f6368;font-size:13px;margin:6px 0 0;">'
                   'Este documento está protegido: la persona que lo compartió '
                   'te dará la clave por otro medio.</p>')

    asunto = f'{remitente} compartió "{nombre}" contigo'
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;
                border:1px solid #dadce0;border-radius:12px;overflow:hidden;">
      <div style="background:#0061a1;color:#fff;padding:16px 22px;font-size:16px;font-weight:600;">
        Almacenamiento Maquita
      </div>
      <div style="padding:22px;">
        <p style="font-size:15px;color:#202124;margin:0 0 6px;">
          <b>{remitente}</b> compartió contigo:</p>
        <p style="font-size:16px;color:#0061a1;font-weight:600;margin:0 0 14px;">📄 {nombre}</p>
        <p style="font-size:14px;color:#3c4043;margin:0 0 18px;">
          Puedes <b>{rol}</b> este documento en línea desde tu navegador,
          sin instalar nada.</p>
        <p style="text-align:center;margin:0 0 10px;">
          <a href="{enlace}" style="background:#0061a1;color:#fff;text-decoration:none;
             padding:12px 26px;border-radius:8px;font-size:14px;display:inline-block;">
             Abrir documento</a></p>
        {avisos}
        <p style="color:#9aa0a6;font-size:12px;margin:18px 0 0;">
          Si no esperabas este correo puedes ignorarlo. Enviado automáticamente
          por la plataforma de Maquita.</p>
      </div>
    </div>"""
    texto = (f'{remitente} compartió "{nombre}" contigo.\n'
             f'Abrir ({rol}): {enlace}\n')

    try:
        enviado = email_service.enviar_correo(
            destinatario=email,
            asunto=asunto,
            html_content=html,
            text_content=texto,
            remitente_nombre='Almacenamiento Maquita',
        )
        (log.info if enviado else log.warning)(
            'Invitación a %s (share %s): %s', email, compartido.get('id'),
            'enviada' if enviado else 'NO enviada')
        return bool(enviado)
    except Exception as excepcion:
        log.warning('Invitación a %s falló: %s', email, excepcion)
        return False
