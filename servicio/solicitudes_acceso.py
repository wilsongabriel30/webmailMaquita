"""Solicitudes de acceso a un enlace compartido.

Responsabilidad ÚNICA: registrar que alguien pidió acceso a un archivo cuyo
enlace ya no le sirve, y avisar a quien lo comparte.

Por qué existe: hasta ahora, quien abría un enlace caducado se topaba con una
pantalla de error **sin ninguna salida**: ni sabía a quién pedirle acceso, ni
tenía forma de hacerlo. En Drive esa pantalla ofrece un formulario para
solicitarlo. Esto es el equivalente propio.
"""

import logging
import re

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.solicitudes')

CORREO = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')

# Para que nadie use el formulario como buzón de correo ajeno.
MAX_POR_HORA = 3


def _valido(email):
    return bool(email) and bool(CORREO.fullmatch(email))


def compartido_de_token(token):
    """El compartido al que apunta el token, AUNQUE esté caducado. None si el
    token no existe: en ese caso no sabemos a quién avisar."""
    filas = consultar(
        'SELECT id, propietario_id, ruta, email FROM compartidos WHERE token = %s',
        (token,))
    return dict(filas[0]) if filas else None


def demasiadas(token, email):
    """¿Se está abusando del formulario? Cuenta el último tramo de una hora."""
    filas = consultar(
        "SELECT COUNT(*) AS n FROM solicitudes_acceso "
        "WHERE token = %s AND LOWER(email_solicitante) = %s "
        "AND creado_en > NOW() - INTERVAL '1 hour'",
        (token, (email or '').lower()))
    return bool(filas) and filas[0]['n'] >= MAX_POR_HORA


def registrar(token, email, nombre='', mensaje=''):
    """(ok: bool, mensaje: str). Nunca lanza."""
    try:
        email = (email or '').strip().lower()[:255]
        if not _valido(email):
            return False, 'Escribe un correo válido.'

        comp = compartido_de_token(token)
        if not comp:
            # No se revela si el token existió alguna vez.
            return False, 'Este enlace ya no existe. Pídele uno nuevo a quien te lo compartió.'

        if demasiadas(token, email):
            return False, 'Ya enviamos tu solicitud. Espera a que te respondan.'

        ejecutar(
            'INSERT INTO solicitudes_acceso '
            '(token, compartido_id, propietario_id, ruta, email_solicitante, '
            ' nombre_solicitante, mensaje) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (token, comp['id'], comp['propietario_id'], comp['ruta'], email,
             (nombre or '').strip()[:255], (mensaje or '').strip()[:1000]))

        avisado = _avisar(comp, email, nombre, mensaje)
        log.info('Solicitud de acceso ruta=%s de %s (avisado=%s)',
                 comp['ruta'], email, avisado)
        return True, ('Listo. Le avisamos a quien puede darte acceso.' if avisado
                      else 'Registramos tu solicitud. Le llegará a quien puede darte acceso.')
    except Exception as excepcion:
        log.warning('Solicitud de acceso falló: %s', excepcion)
        return False, 'No pudimos registrar tu solicitud. Inténtalo más tarde.'


def _avisar(comp, email, nombre, mensaje, clave=None):
    """Correo al dueño. Best-effort: si falla, la solicitud queda igual guardada."""
    try:
        destino = consultar('SELECT email FROM usuarios WHERE id = %s',
                            (comp['propietario_id'],), nomina=True)
        if not destino or not destino[0]['email']:
            log.warning('Aviso de solicitud: el dueno %s no tiene correo',
                        comp.get('propietario_id'))
            return False
        import html as _html
        archivo = (comp['ruta'] or '').rstrip('/').rsplit('/', 1)[-1] or comp['ruta']
        archivo_e = _html.escape(archivo or '')
        quien = ('%s (%s)' % (nombre, email)) if nombre else email
        quien_e = _html.escape(quien or '')
        mensaje_e = _html.escape(mensaje or '')
        boton = ''
        if clave:
            # Un solo clic: se abre, se comprueba que eres tú, y queda dado.
            try:
                from config_almacen import URL_LINKS as _base
            except Exception:
                _base = 'https://drive.maquita.com.ec'
            enlace = '%s/dar-acceso/%s' % (_base.rstrip('/'), clave)
            boton = (
                '<p style="margin:24px 0;">'
                '<a href="%s" style="background:#1a73e8;color:#fff;'
                'text-decoration:none;padding:12px 24px;border-radius:6px;'
                'display:inline-block;font-family:Arial,sans-serif;">'
                'Dar acceso</a></p>'
                '<p style="color:#5f6368;font-size:12px;">Al pulsarlo se le da '
                'acceso de lectura y podrá entrar enseguida. Si prefieres no '
                'darlo, ignora este correo.</p>' % enlace)

        cuerpo = (
            '<p><b>%s</b> pide acceso a <b>%s</b>.</p>' % (quien_e, archivo_e) +
            ('<p>Mensaje:<br><i>%s</i></p>' % mensaje_e if mensaje else '') +
            boton +
            ('' if boton else
             '<p>Para dárselo, abre el archivo en Drive Maquita y compártelo con '
             'ese correo. Si no reconoces a esta persona, ignora este aviso.</p>'))
        # Por el servicio de FARO y, si no puede, directamente: el aviso no
        # puede perderse en silencio (01/09/2026).
        from correo_almacen import enviar
        return enviar(destino[0]['email'], 'Piden acceso a "%s"' % archivo, cuerpo)
    except Exception as excepcion:
        log.warning('Aviso de solicitud no enviado: %s', excepcion)
        return False


def pendientes(propietario_id):
    """Solicitudes sin atender de los archivos de esta persona."""
    return [dict(f) for f in consultar(
        "SELECT * FROM solicitudes_acceso WHERE propietario_id = %s "
        "AND estado = 'pendiente' ORDER BY creado_en DESC", (int(propietario_id),))]


# ── Enlaces internos (sin token) ─────────────────────────────────────────────
def _pendiente_de(ruta, email):
    """La solicitud que ya hizo esta persona sobre esa ruta, si sigue viva."""
    filas = consultar(
        # El respiro se cuenta desde el ULTIMO AVISO, no desde que se pidio:
        # si no, insistir mandaria un correo cada vez.
        "SELECT id, clave_respuesta, creado_en, "
        "       (COALESCE(ultimo_aviso, creado_en) > NOW() - INTERVAL '5 minutes') "
        "        AS muy_reciente "
        "FROM solicitudes_acceso "
        "WHERE ruta = %s AND email_solicitante = %s AND estado = 'pendiente' "
        "ORDER BY creado_en DESC LIMIT 1",
        (ruta, email))
    return dict(filas[0]) if filas else None


def registrar_por_ruta(propietario_id, ruta, email, nombre='', mensaje=''):
    """Solicitud de acceso a una ruta concreta, sin enlace de por medio.

    (ok: bool, mensaje: str). Nunca lanza.
    """
    try:
        email = (email or '').strip().lower()[:255]
        if not _valido(email):
            return False, 'No tenemos tu correo. Vuelve a entrar y prueba otra vez.'
        if not ruta or not propietario_id:
            return False, 'No sabemos a quién pedirle el acceso.'

        import secrets as _secretos

        # Si ya lo pidió y sigue sin respuesta, se REENVÍA el aviso: no se
        # crea otra solicitud, pero tampoco se deja a la persona esperando un
        # correo que nunca sale.
        antes = _pendiente_de(ruta, email)
        if antes:
            if antes['muy_reciente']:
                return True, ('Tu solicitud ya salió hace un momento. '
                              'Espera un poco antes de volver a pedirla.')
            clave = antes['clave_respuesta']
            if not clave:
                # Las de antes del botón no tenían clave: se les pone ahora.
                clave = _secretos.token_urlsafe(32)
                ejecutar('UPDATE solicitudes_acceso SET clave_respuesta = %s '
                         'WHERE id = %s', (clave, antes['id']))
            avisado = _avisar({'propietario_id': int(propietario_id), 'ruta': ruta},
                              email, nombre, mensaje, clave)
            if avisado:
                ejecutar('UPDATE solicitudes_acceso SET ultimo_aviso = NOW() '
                         'WHERE id = %s', (antes['id'],))
            log.info('Solicitud de acceso REENVIADA ruta=%s a %s (avisado=%s)',
                     ruta, email, avisado)
            return True, ('Volvimos a avisarle a quien puede darte acceso.' if avisado
                          else 'Tu solicitud sigue registrada. Le llegará el aviso.')

        clave = _secretos.token_urlsafe(32)
        ejecutar(
            'INSERT INTO solicitudes_acceso '
            '(token, compartido_id, propietario_id, ruta, email_solicitante, '
            ' nombre_solicitante, mensaje, clave_respuesta) '
            'VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)',
            ('', int(propietario_id), ruta, email,
             (nombre or '').strip()[:255], (mensaje or '').strip()[:1000], clave))

        avisado = _avisar({'propietario_id': int(propietario_id), 'ruta': ruta},
                          email, nombre, mensaje, clave)
        if avisado:
            ejecutar('UPDATE solicitudes_acceso SET ultimo_aviso = NOW() '
                     'WHERE clave_respuesta = %s', (clave,))
        log.info('Solicitud de acceso (enlace interno) ruta=%s de %s (avisado=%s)',
                 ruta, email, avisado)
        return True, ('Listo. Le avisamos a quien puede darte acceso.' if avisado
                      else 'Registramos tu solicitud. Le llegará a quien puede darte acceso.')
    except Exception as excepcion:
        log.warning('Solicitud de acceso por ruta falló: %s', excepcion)
        return False, 'No pudimos registrar tu solicitud. Inténtalo más tarde.'


# ── Dar el acceso desde el correo ────────────────────────────────────────────
def por_clave(clave):
    """La solicitud que corresponde a esa clave, o None."""
    if not clave:
        return None
    filas = consultar(
        'SELECT * FROM solicitudes_acceso WHERE clave_respuesta = %s LIMIT 1',
        (clave,))
    return dict(filas[0]) if filas else None


def conceder(clave, quien_concede, puede_editar=False):
    """Da el acceso pedido. (ok: bool, mensaje: str, solicitud|None).

    Solo puede concederlo el DUEÑO: la clave sirve para encontrar la solicitud,
    no para saltarse quién es quien entra.
    """
    try:
        solicitud = por_clave(clave)
        if not solicitud:
            return False, 'Esta solicitud ya no existe.', None
        if int(solicitud['propietario_id'] or 0) != int(quien_concede):
            return False, 'Esta solicitud no es tuya.', None

        ruta = solicitud['ruta']
        correo = (solicitud['email_solicitante'] or '').strip().lower()
        if not ruta or not correo:
            return False, 'A esta solicitud le faltan datos.', solicitud

        # El nombre de usuario de quien pide: los compartidos guardan el
        # destinatario de las dos formas, según cómo se compartiera.
        usuario = consultar('SELECT id, username FROM usuarios WHERE LOWER(email) = %s',
                            (correo,), nomina=True)
        nombre_usuario = (usuario[0]['username'] if usuario else '') or ''

        ya = consultar(
            'SELECT id FROM compartidos WHERE propietario_id = %s AND ruta = %s '
            '  AND (LOWER(email) = %s OR destinatario = %s) LIMIT 1',
            (int(quien_concede), ruta, correo, nombre_usuario))
        if not ya:
            ejecutar(
                'INSERT INTO compartidos '
                '(propietario_id, ruta, tipo, destinatario, permisos, '
                ' permite_descarga, email, puede_editar, modo) '
                "VALUES (%s, %s, 0, %s, %s, TRUE, %s, %s, %s)",
                (int(quien_concede), ruta, nombre_usuario or None,
                 3 if puede_editar else 1, correo, bool(puede_editar),
                 'editar' if puede_editar else 'descargar'))
        elif puede_editar:
            ejecutar("UPDATE compartidos SET puede_editar = TRUE, permisos = 3, "
                     "modo = 'editar' WHERE id = %s", (ya[0]['id'],))

        ejecutar("UPDATE solicitudes_acceso SET estado = 'aceptada' WHERE id = %s",
                 (solicitud['id'],))
        log.info('Acceso concedido a %s sobre %s por %s (editar=%s)',
                 correo, ruta, quien_concede, puede_editar)
        return True, 'Listo.', solicitud
    except Exception as excepcion:
        log.warning('No se pudo conceder el acceso: %s', excepcion)
        return False, 'No se pudo dar el acceso. Inténtalo de nuevo.', None
