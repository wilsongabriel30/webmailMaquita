# -*- coding: utf-8 -*-
"""
OTP por correo + auditoría de accesos externos del Almacén (fase C).
====================================================================
Cuando un enlace compartido se crea con `requiere_otp`, el invitado debe
validar un código de 6 dígitos que le llega a SU correo (el del share) antes
de ver/editar. Una vez validado queda recordado en la sesión del navegador
(igual que la clave). Todo acceso externo queda auditado en `accesos_externos`.

Endpoints SIN sesión (los usa el invitado; exentos del candado maestro por el
prefijo /api/almacen/publico-otp/):
  POST /publico-otp/enviar  {token}          → envía el código al correo del share
  POST /publico-otp/validar {token, codigo}  → valida y marca la sesión

Endpoint del DUEÑO (con sesión):
  GET /compartidos/<id>/accesos              → auditoría de ese enlace

Seguridad: código hasheado (sha256), expira en 10 min, máx 5 intentos,
reenvío mínimo cada 60 s, un solo código activo por enlace.

Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, session

from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual

log = logging.getLogger('almacen.otp')

bp_acceso_externo = Blueprint('almacen_acceso_externo', __name__)

MINUTOS_CODIGO = 10
MAX_INTENTOS = 5
SEGUNDOS_REENVIO = 60


# ── auditoría ────────────────────────────────────────────────────────────
def registrar_acceso(compartido_id, token, evento, email='', detalle=''):
    """Anota un evento de acceso externo (best-effort, nunca lanza)."""
    try:
        ejecutar("""
            INSERT INTO accesos_externos
                (compartido_id, token, email, evento, detalle, ip, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (compartido_id, token, (email or '')[:255], evento, detalle,
              (request.headers.get('X-Real-IP') or request.remote_addr or '')[:64],
              (request.headers.get('User-Agent') or '')[:500]))
    except Exception as excepcion:
        log.warning('auditoría no registrada (%s): %s', evento, excepcion)


# ── helpers OTP ──────────────────────────────────────────────────────────
def _mascara(email: str) -> str:
    """f***a@gma**.com — para mostrar sin revelar el correo completo."""
    try:
        usuario, dominio = email.split('@', 1)
        u = usuario[0] + '***' + (usuario[-1] if len(usuario) > 1 else '')
        d = dominio[:3] + '**' + dominio[dominio.rfind('.'):]
        return f'{u}@{d}'
    except Exception:
        return '***'


def otp_ok(token: str, comp: dict) -> bool:
    """¿Este navegador ya validó el OTP del enlace (o el enlace no lo pide)?"""
    if not comp.get('requiere_otp'):
        return True
    return bool(session.get(f'almacen_otp_ok_{token}'))


def _share(token: str):
    filas = consultar("""
        SELECT id, propietario_id, ruta, token, email, requiere_otp, expira_en
        FROM compartidos WHERE token = %s
    """, (token,))
    if not filas:
        return None
    comp = dict(filas[0])
    if comp['expira_en'] is not None and comp['expira_en'] < datetime.now(timezone.utc):
        return None
    return comp


# ── endpoints del invitado (sin sesión FARO) ─────────────────────────────
@bp_acceso_externo.route('/publico-otp/enviar', methods=['POST'])
def otp_enviar():
    datos = request.get_json(silent=True) or {}
    comp = _share((datos.get('token') or '').strip())
    if not comp:
        return error('Enlace inválido o expirado', 404)
    if not comp['requiere_otp']:
        return jsonify({'success': True, 'otp_requerido': False})
    email = (comp.get('email') or '').strip()
    if not email:
        return error('Este enlace no tiene un correo asociado', 400)

    # rate-limit de reenvío
    ultimo = consultar("""
        SELECT creado_en FROM otp_codigos WHERE compartido_id = %s
        ORDER BY creado_en DESC LIMIT 1
    """, (comp['id'],))
    if ultimo:
        espera = (datetime.now(timezone.utc) - ultimo[0]['creado_en']).total_seconds()
        if espera < SEGUNDOS_REENVIO:
            return error(f'Espera {int(SEGUNDOS_REENVIO - espera)} s para reenviar', 429)

    codigo = f'{secrets.randbelow(1000000):06d}'
    ejecutar("UPDATE otp_codigos SET usado = TRUE WHERE compartido_id = %s", (comp['id'],))
    ejecutar("""
        INSERT INTO otp_codigos (compartido_id, email, codigo_hash, expira_en)
        VALUES (%s, %s, %s, %s)
    """, (comp['id'], email, hashlib.sha256(codigo.encode()).hexdigest(),
          datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_CODIGO)))

    enviado = False
    try:
        from compartido.servicios.email_service import email_service
        if email_service.puede_enviar():
            nombre = comp['ruta'].rsplit('/', 1)[-1]
            enviado = email_service.enviar_correo(
                destinatario=email,
                asunto=f'Tu código de acceso: {codigo}',
                html_content=(
                    '<div style="font-family:Arial,sans-serif;max-width:420px;margin:0 auto;'
                    'text-align:center;border:1px solid #dadce0;border-radius:12px;padding:26px;">'
                    f'<p style="font-size:14px;color:#3c4043;">Código para abrir '
                    f'<b>{nombre}</b> en Maquita:</p>'
                    f'<p style="font-size:34px;letter-spacing:8px;font-weight:700;'
                    f'color:#0061a1;margin:12px 0;">{codigo}</p>'
                    f'<p style="font-size:12px;color:#9aa0a6;">Vence en {MINUTOS_CODIGO} minutos. '
                    'Si no lo pediste, ignora este correo.</p></div>'),
                text_content=f'Tu código de acceso Maquita: {codigo} (vence en {MINUTOS_CODIGO} min)',
                remitente_nombre='Almacenamiento Maquita',
            )
    except Exception as excepcion:
        log.warning('OTP no enviado a %s: %s', email, excepcion)
    registrar_acceso(comp['id'], comp['token'], 'otp_enviado', email,
                     'enviado' if enviado else 'fallo_envio')
    if not enviado:
        return error('No se pudo enviar el código, intenta más tarde', 502)
    return jsonify({'success': True, 'email_mascara': _mascara(email),
                    'vence_minutos': MINUTOS_CODIGO})


@bp_acceso_externo.route('/publico-otp/validar', methods=['POST'])
def otp_validar():
    datos = request.get_json(silent=True) or {}
    comp = _share((datos.get('token') or '').strip())
    if not comp:
        return error('Enlace inválido o expirado', 404)
    codigo = (datos.get('codigo') or '').strip()
    if not codigo:
        return error('Código requerido', 400)
    filas = consultar("""
        SELECT id, codigo_hash, intentos, usado, expira_en
        FROM otp_codigos WHERE compartido_id = %s
        ORDER BY creado_en DESC LIMIT 1
    """, (comp['id'],))
    vigente = filas and not filas[0]['usado'] \
        and filas[0]['expira_en'] > datetime.now(timezone.utc) \
        and filas[0]['intentos'] < MAX_INTENTOS
    if not vigente:
        registrar_acceso(comp['id'], comp['token'], 'otp_fallo', comp.get('email'),
                         'sin_codigo_vigente')
        return error('Código vencido: pide uno nuevo', 410)
    fila = filas[0]
    if hashlib.sha256(codigo.encode()).hexdigest() != fila['codigo_hash']:
        ejecutar("UPDATE otp_codigos SET intentos = intentos + 1 WHERE id = %s",
                 (fila['id'],))
        registrar_acceso(comp['id'], comp['token'], 'otp_fallo', comp.get('email'),
                         f'intento_{fila["intentos"] + 1}')
        return error('Código incorrecto', 401)
    ejecutar("UPDATE otp_codigos SET usado = TRUE WHERE id = %s", (fila['id'],))
    session[f'almacen_otp_ok_{comp["token"]}'] = True
    session.permanent = False
    registrar_acceso(comp['id'], comp['token'], 'otp_ok', comp.get('email'))
    return jsonify({'success': True})


# ── auditoría para el DUEÑO del enlace (con sesión) ──────────────────────
@bp_acceso_externo.route('/compartidos/<int:compartido_id>/accesos', methods=['GET'])
def accesos_de_compartido(compartido_id):
    usuario = usuario_actual()
    dueno = consultar("""
        SELECT id FROM compartidos WHERE id = %s AND propietario_id = %s
    """, (compartido_id, usuario))
    if not dueno:
        return error('Compartido no encontrado', 404)
    filas = consultar("""
        SELECT evento, email, detalle, ip, user_agent, creado_en
        FROM accesos_externos WHERE compartido_id = %s
        ORDER BY creado_en DESC LIMIT 200
    """, (compartido_id,))
    accesos = [{
        'evento': f['evento'], 'email': f['email'], 'detalle': f['detalle'],
        'ip': f['ip'], 'user_agent': (f['user_agent'] or '')[:120],
        'creado_en': f['creado_en'].isoformat(),
    } for f in filas]
    return jsonify({'success': True, 'accesos': accesos, 'total': len(accesos)})
