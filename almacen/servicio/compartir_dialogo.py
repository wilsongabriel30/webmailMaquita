# -*- coding: utf-8 -*-
"""
Compatibilidad del diálogo «Compartir» del explorador con la API del Almacén.
=============================================================================
El diálogo (`explorador-compartir.js`) heredó el contrato de la Nube anterior:
envía `destinatario` (usuario de Raíces), `password` y `fecha_expiracion`, espera
la lista del archivo en `shares` y cambia permisos con `PUT /compartidos/<id>`.
La API del Almacén usa `con_quien`/`email`, `clave`, `expira_dias` y `compartidos`.
Este módulo traduce entre ambos sin tocar el resto del motor.

- Compartir con una persona guarda su CORREO (sale del directorio de Raíces):
  así le aparece en «Compartidos conmigo», que busca por correo.

Autoría: Equipo de Tecnología Maquita — 2026-10-28
"""
from datetime import date

from flask import jsonify, request

from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual
from clave_enlace import hash_clave
from config_almacen import URL_PUBLICA

TIPO_USUARIO, TIPO_ENLACE, TIPO_CORREO = 0, 3, 4
PERMISO_EDITOR = 15


def _correo_de_usuario(username: str) -> str:
    filas = consultar("""
        SELECT COALESCE(email, '') AS email FROM usuarios
        WHERE LOWER(username) = LOWER(%s) AND active = TRUE LIMIT 1
    """, (username,), nomina=True)
    return (filas[0]['email'] or '').strip().lower() if filas else ''


def _dias_hasta(fecha: str) -> int:
    """'AAAA-MM-DD' → días desde hoy (el día elegido incluido). 0 = sin vencimiento."""
    try:
        return max((date.fromisoformat(fecha[:10]) - date.today()).days + 1, 0)
    except (TypeError, ValueError):
        return 0


def adaptar_peticion(datos: dict):
    """Traduce el cuerpo del diálogo al de POST /compartir. Devuelve un mensaje de
    error (texto) si no se puede, o None si quedó listo."""
    if datos.get('password') and not datos.get('clave'):
        datos['clave'] = datos['password']
    if datos.get('fecha_expiracion') and not datos.get('expira_dias'):
        datos['expira_dias'] = _dias_hasta(datos['fecha_expiracion'])
    destinatario = (datos.get('destinatario') or '').strip()
    if not destinatario or datos.get('con_quien') or datos.get('email'):
        return None
    tipo = int(datos.get('tipo', TIPO_USUARIO))
    correo = destinatario.lower() if '@' in destinatario and tipo == TIPO_CORREO else _correo_de_usuario(destinatario)
    if not correo and '@' in destinatario:
        correo = destinatario.lower()
    if not correo:
        return 'Esa persona no tiene correo registrado en Raíces; pide a Tecnología que lo agregue.'
    datos['con_quien'] = destinatario
    datos['email'] = correo
    datos['rol'] = 'editor' if int(datos.get('permisos') or 1) == PERMISO_EDITOR else 'lector'
    return None


def shares_de_ruta(usuario: int, ruta: str):
    """GET /shares?ruta= — quién tiene acceso a ESTE archivo, en el formato del diálogo."""
    filas = consultar("""
        SELECT id, tipo, destinatario, email, token, permisos, puede_editar,
               expira_en, clave_hash
        FROM compartidos
        WHERE propietario_id = %s AND ruta = %s
          AND (expira_en IS NULL OR expira_en > NOW())
        ORDER BY creado_en
    """, (usuario, ruta))
    usuarios = {f['destinatario'] for f in filas if f['destinatario']}
    nombres = {}
    if usuarios:
        for n in consultar("""
            SELECT u.username, COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.username IN %s
        """, (tuple(usuarios),), nomina=True):
            nombres[n['username']] = n['nombre']
    shares = []
    for f in filas:
        if f['email'] or f['destinatario']:
            tipo = TIPO_USUARIO if f['destinatario'] and f['tipo'] != TIPO_CORREO and f['destinatario'] in nombres else TIPO_CORREO
            correo = f['email'] or f['destinatario']
            nombre = nombres.get(f['destinatario']) or correo
        else:
            tipo, correo, nombre = TIPO_ENLACE, None, None
        shares.append({
            'id': f['id'], 'tipo': tipo,
            'compartido_con': correo, 'compartido_con_nombre': nombre,
            'permisos': PERMISO_EDITOR if f['puede_editar'] else (f['permisos'] or 1),
            'token': f['token'],
            'url': f"{URL_PUBLICA}/almacen-s/{f['token']}" if f['token'] else None,
            'expira_en': f['expira_en'].isoformat() if f['expira_en'] else None,
            'con_clave': bool(f['clave_hash']),
        })
    return jsonify({'success': True, 'shares': shares, 'total': len(shares)})


def registrar(bp):
    @bp.route('/compartidos/<int:compartido_id>', methods=['PUT'])
    def actualizar_compartido(compartido_id):
        """PUT /compartidos/<id> — {permisos} | {password} | {fecha_expiracion}."""
        usuario = usuario_actual()
        datos = request.get_json() or {}
        cambios, valores = [], []
        if 'permisos' in datos:
            permisos = int(datos.get('permisos') or 1)
            cambios += ['permisos = %s', 'puede_editar = %s']
            valores += [permisos, permisos == PERMISO_EDITOR]
        if 'password' in datos:
            clave = (datos.get('password') or '').strip()
            cambios.append('clave_hash = %s')
            valores.append(hash_clave(clave) if clave else None)
        if 'fecha_expiracion' in datos:
            dias = _dias_hasta(datos.get('fecha_expiracion') or '')
            cambios.append("expira_en = CASE WHEN %s > 0 THEN NOW() + make_interval(days => %s) END")
            valores += [dias, dias]
        if not cambios:
            return error('Nada que cambiar', 400)
        fila = ejecutar(
            'UPDATE compartidos SET ' + ', '.join(cambios) +
            ' WHERE id = %s AND propietario_id = %s RETURNING id',
            tuple(valores) + (compartido_id, usuario))
        if not fila:
            return error('Compartido no encontrado', 404)
        return jsonify({'success': True})
