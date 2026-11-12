"""Pedir archivos a una persona de fuera (15/10/2026).

Quien comparte una carpeta escribe el CORREO de una persona externa (sin
usuario en Raíces) y las fechas DESDE y HASTA en que podrá subir. Se crea un
acceso solo para esa persona:
  - tipo 4 (por correo), rol lector, `permite_subir = true`;
  - `requiere_otp = true`: al abrir el enlace le llega un código de 6 dígitos
    a ESE correo; sin el código no ve ni sube nada;
  - plazo obligatorio (`subida_desde`/`subida_hasta`, máx. 30 días); el acceso
    entero caduca al terminar el plazo.
La subida en sí la hace `subida_por_enlace.py` (con las barreras de
`protecciones_subida.py`: plazo, tipos, tope y antivirus). Un correo de la casa
no puede recibir esto: esa persona entra con su cuenta.
"""
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

bp_subida_externa = Blueprint('subida_externa', __name__)

TIPO_CORREO = 4
DIAS_DEFECTO, DIAS_MAX = 7, 30


def _fallo(mensaje, codigo):
    return jsonify({'success': False, 'error': mensaje}), codigo


def _carpeta_del_usuario(usuario, ruta):
    """Valida que `ruta` sea una carpeta que el usuario puede publicar."""
    from seguridad_rutas import normalizar_ruta_virtual, ruta_fisica
    ruta = normalizar_ruta_virtual(ruta)
    if ruta == '/':
        raise ValueError('Elige una carpeta, no la raíz de tu Drive.')
    if ruta.startswith('/unidades/'):
        from api_unidades import rol_en_unidad
        if rol_en_unidad(usuario, int(ruta.split('/')[2])) != 'manager':
            raise PermissionError('Solo el administrador de la unidad puede pedir archivos a personas de fuera.')
    if not os.path.isdir(ruta_fisica(usuario, ruta, escritura=True)):
        raise ValueError('Esa carpeta ya no está en tu Drive. Actualiza la vista (F5).')
    return ruta


def _plazo(datos):
    """Fechas «desde» y «hasta» (AAAA-MM-DD, hora de Ecuador) → instantes UTC.
    Desde: inicio del día (hoy por defecto). Hasta: fin del día (7 días por
    defecto). Máximo DIAS_MAX días de plazo y hasta 90 días por delante."""
    from protecciones_subida import ECUADOR
    hoy = datetime.now(ECUADOR).date()
    try:
        desde = datetime.strptime(datos.get('desde') or hoy.isoformat(), '%Y-%m-%d').date()
        hasta = datetime.strptime(datos.get('hasta') or (desde + timedelta(days=DIAS_DEFECTO)).isoformat(),
                                  '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Fechas no válidas.')
    if desde < hoy:
        raise ValueError('La fecha «desde» no puede ser anterior a hoy.')
    if hasta < desde:
        raise ValueError('La fecha «hasta» debe ser igual o posterior a «desde».')
    if (hasta - desde).days > DIAS_MAX:
        raise ValueError('El plazo para subir no puede pasar de %d días.' % DIAS_MAX)
    if (hasta - hoy).days > 90:
        raise ValueError('El plazo debe terminar dentro de los próximos 90 días.')
    inicio = datetime.combine(desde, datetime.min.time(), ECUADOR)
    fin = datetime.combine(hasta, datetime.max.time().replace(microsecond=0), ECUADOR)
    return inicio.astimezone(timezone.utc), fin.astimezone(timezone.utc)


def _enviar_invitacion(usuario, fila, nombre_carpeta, desde, hasta, con_macros=False):
    from config_almacen import URL_LINKS
    from correo_compartir import _nombre_remitente
    try:
        from compartido.servicios.email_service import email_service
        if not email_service.puede_enviar():
            return False
    except Exception as excepcion:
        log.warning('Invitación de subida sin email_service: %s', excepcion)
        return False
    remitente = escape(_nombre_remitente(usuario))
    carpeta = escape(nombre_carpeta)
    enlace = f"{URL_LINKS}/s/{fila['token']}"
    from protecciones_subida import ECUADOR
    # Fecha Y hora exactas: el plazo puede ser de horas (p. ej. 24 h), y decir
    # solo el día haría creer que hay hasta el final de ese día (15/10/2026).
    hora = lambda m: m.astimezone(ECUADOR).strftime('%d/%m/%Y a las %H:%M')
    vence = (f'Podrás subir desde el {hora(desde)} hasta el {hora(hasta)} (hora de Ecuador); '
             'después el enlace deja de funcionar. Es personal: no lo reenvíes.')
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;
                border:1px solid #dadce0;border-radius:12px;overflow:hidden;">
      <div style="background:#0061a1;color:#fff;padding:16px 22px;font-size:16px;font-weight:600;">
        Almacenamiento Maquita</div>
      <div style="padding:22px;font-size:14px;color:#3c4043;">
        <p style="font-size:15px;color:#202124;margin:0 0 6px;"><b>{remitente}</b> te pide que subas archivos a:</p>
        <p style="font-size:16px;color:#0061a1;font-weight:600;margin:0 0 14px;">📁 {carpeta}</p>
        <p style="margin:0 0 8px;">Al abrir el enlace te llegará a este correo un <b>código de 6 dígitos</b>.
          Escríbelo y podrás subir archivos o carpetas enteras desde tu navegador, sin crear cuenta.</p>
        <p style="text-align:center;margin:18px 0;">
          <a href="{enlace}" style="background:#0061a1;color:#fff;text-decoration:none;
             padding:12px 26px;border-radius:8px;display:inline-block;">Subir archivos</a></p>
        <p style="color:#5f6368;font-size:13px;margin:0;">{vence} Máximo 2 GB por archivo; cada archivo
          pasa por el antivirus y no se admiten programas{'' if con_macros else ' ni documentos con macros'}.</p>
        <p style="color:#9aa0a6;font-size:12px;margin:18px 0 0;">Si no esperabas este correo puedes ignorarlo.
          Enviado automáticamente por la plataforma de Maquita.</p>
      </div></div>"""
    texto = (f'{_nombre_remitente(usuario)} te pide que subas archivos a «{nombre_carpeta}».\n'
             f'Abre {enlace} ; te llegará un código a este correo. {vence}\n')
    try:
        return bool(email_service.enviar_correo(
            destinatario=fila['email'], asunto=f'{_nombre_remitente(usuario)} te pide archivos: «{nombre_carpeta}»',
            html_content=html, text_content=texto, remitente_nombre='Almacenamiento Maquita'))
    except Exception as excepcion:
        log.warning('Invitación de subida a %s falló: %s', fila['email'], excepcion)
        return False


@bp_subida_externa.route('/compartir/subida-externa', methods=['POST'])
def invitar():
    """{ruta, email, desde, hasta} → acceso de subida para esa persona."""
    from almacen_bd import consultar, ejecutar
    from api_archivos import usuario_actual
    from enlace_a_sesion import _destinatario_interno
    from registro import registrar_actividad
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    email = (datos.get('email') or '').strip().lower()[:255]
    if not re.fullmatch(r'[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+', email):
        return _fallo('Correo no válido.', 400)
    if _destinatario_interno({'email': email}) is not None:
        return _fallo('Ese correo es de una persona de Maquita: compártele la carpeta como siempre, '
                      'con su cuenta.', 409)
    try:
        desde, hasta = _plazo(datos)
        ruta = _carpeta_del_usuario(usuario, datos.get('ruta', ''))
    except PermissionError as excepcion:
        return _fallo(str(excepcion), 403)
    except Exception as excepcion:
        return _fallo(str(excepcion), 400)

    # El acceso entero (ver y subir) termina con el plazo: solo vino a entregar.
    previo = consultar("""SELECT id, token FROM compartidos WHERE propietario_id = %s AND ruta = %s
                          AND tipo = %s AND LOWER(email) = %s ORDER BY id LIMIT 1""",
                       (usuario, ruta, TIPO_CORREO, email))
    if previo:
        fila = ejecutar("""UPDATE compartidos SET permite_subir = TRUE, requiere_otp = TRUE, expira_en = %s,
                               subida_desde = %s, subida_hasta = %s, permisos = permisos | 1
                           WHERE id = %s RETURNING id, token, email""", (hasta, desde, hasta, previo[0]['id']))
    else:
        fila = ejecutar("""INSERT INTO compartidos (propietario_id, ruta, tipo, token, permisos, expira_en,
                               permite_descarga, email, puede_editar, requiere_otp, modo, permite_subir,
                               subida_desde, subida_hasta)
                           VALUES (%s, %s, %s, %s, 1, %s, TRUE, %s, FALSE, TRUE, 'descargar', TRUE, %s, %s)
                           RETURNING id, token, email""",
                        (usuario, ruta, TIPO_CORREO, secrets.token_urlsafe(24), hasta, email, desde, hasta))
    enviado = _enviar_invitacion(usuario, fila, ruta.rsplit('/', 1)[-1], desde, hasta)
    from protecciones_subida import ECUADOR
    registrar_actividad(usuario, 'pidio_archivos', ruta, '%s · %s a %s' % (
        email, desde.astimezone(ECUADOR).date().isoformat(), hasta.astimezone(ECUADOR).date().isoformat()))
    log.info('Subida externa: compartido %s, %s, %s (%s a %s)', fila['id'], ruta, email, desde, hasta)
    return jsonify({'success': True, 'id': fila['id'], 'email': email, 'subida_desde': desde.isoformat(),
                    'subida_hasta': hasta.isoformat(), 'correo_enviado': enviado}), 201


@bp_subida_externa.route('/compartir/subida-externa', methods=['GET'])
def listar():
    """Invitaciones de subida vigentes de una carpeta (para el diálogo)."""
    from almacen_bd import consultar
    from api_archivos import usuario_actual
    from seguridad_rutas import normalizar_ruta_virtual
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except Exception:
        return _fallo('Ruta no válida.', 400)
    # Todas las que tienen plazo vigente: las de esta sección y las de externos
    # con rol Editor del compartir de siempre.
    filas = consultar("""SELECT id, email, subida_desde, subida_hasta, subida_bytes, accesos, permite_macros
                         FROM compartidos
                         WHERE propietario_id = %s AND ruta = %s AND email IS NOT NULL
                           AND subida_hasta > NOW() ORDER BY id""",
                      (usuario, ruta))
    iso = lambda m: m.isoformat() if m else None
    return jsonify({'success': True, 'invitaciones': [
        {'id': f['id'], 'email': f['email'], 'accesos': f['accesos'], 'subido_bytes': f['subida_bytes'],
         'desde': iso(f['subida_desde']), 'hasta': iso(f['subida_hasta']),
         'macros': bool(f['permite_macros'])} for f in filas]})


# ---------------------------------------------------------------------------
# Compartir de siempre («Personas con acceso»): un correo EXTERNO con rol Editor
# sobre una CARPETA puede subir, siempre con código al correo. Así funciona por
# donde la gente comparte de verdad, sin una sección aparte.
# ---------------------------------------------------------------------------
def externo_editor_de_carpeta(fila):
    """¿Es un acceso por correo, externo, con rol Editor, sobre una carpeta?"""
    from enlace_a_sesion import _destinatario_interno
    from seguridad_rutas import ruta_fisica
    email = (fila.get('email') or '').strip()
    if int(fila.get('tipo') or 0) != TIPO_CORREO or not email:
        return False
    if not (int(fila.get('permisos') or 0) & 2):
        return False
    if _destinatario_interno({'email': email}) is not None:
        return False
    try:
        return os.path.isdir(ruta_fisica(fila['propietario_id'], fila['ruta']))
    except Exception:
        return False


def ajustar_externo_editor(usuario, compartido, datos=None):
    """Gancho de api_compartir.crear_compartido: si es un externo Editor de una
    carpeta, el código al correo pasa a ser obligatorio y se fija su plazo de
    subida: las fechas elegidas en el diálogo (`subida_desde`/`subida_hasta`)
    o, si no vienen, DIAS_DEFECTO días (se conserva el plazo vigente si lo
    hay). Con rol Lector no hace nada: solo ve, como en Google Drive. Nunca lanza."""
    try:
        from almacen_bd import ejecutar
        fila = dict(compartido, propietario_id=usuario)
        if not externo_editor_de_carpeta(fila):
            return
        datos = datos or {}
        elegido = None
        if datos.get('subida_desde') or datos.get('subida_hasta'):
            try:
                elegido = _plazo({'desde': datos.get('subida_desde'), 'hasta': datos.get('subida_hasta')})
            except ValueError as excepcion:
                log.warning('Plazo de subida no válido (%s): se usan %s días', excepcion, DIAS_DEFECTO)
        if elegido:
            r = ejecutar("""UPDATE compartidos SET requiere_otp = TRUE, subida_desde = %s, subida_hasta = %s
                            WHERE id = %s AND propietario_id = %s RETURNING subida_desde, subida_hasta""",
                         (elegido[0], elegido[1], compartido['id'], usuario))
        else:
            r = ejecutar("""UPDATE compartidos SET requiere_otp = TRUE,
                                subida_desde = CASE WHEN subida_hasta > NOW() THEN subida_desde ELSE NOW() END,
                                subida_hasta = CASE WHEN subida_hasta > NOW() THEN subida_hasta
                                                    ELSE NOW() + make_interval(days => %s) END
                            WHERE id = %s AND propietario_id = %s RETURNING subida_desde, subida_hasta""",
                         (DIAS_DEFECTO, compartido['id'], usuario))
        # Opción avanzada «Permitir documentos con macros»: se fija en cada
        # invitación (si no se marca, queda apagada). Solo levanta esa barrera.
        con_macros = datos.get('subida_macros') is True
        ejecutar('UPDATE compartidos SET permite_macros = %s WHERE id = %s AND propietario_id = %s',
                 (con_macros, compartido['id'], usuario))
        compartido.update(requiere_otp=True, sube_archivos=True, permite_macros=con_macros,
                          subida_desde=r['subida_desde'], subida_hasta=r['subida_hasta'])
    except Exception as excepcion:
        log.warning('ajustar_externo_editor(%s): %s', compartido.get('id'), excepcion)


def invitacion_subida(compartido, remitente_id):
    """Invitación para quien puede subir (sustituye a la de «ver/editar»)."""
    nombre = (compartido.get('ruta') or '').rstrip('/').rsplit('/', 1)[-1] or 'una carpeta'
    return _enviar_invitacion(remitente_id, compartido, nombre, compartido['subida_desde'],
                              compartido['subida_hasta'], compartido.get('permite_macros'))


def registrar(app):
    app.register_blueprint(bp_subida_externa, url_prefix='/api/almacen')
    csrf = app.extensions.get('csrf')
    if csrf:
        csrf.exempt(bp_subida_externa)   # como el resto de la API del Almacén
