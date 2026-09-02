# -*- coding: utf-8 -*-
"""
Puente del enlace compartido a la sesión — Almacén Maquita.
===========================================================
Un enlace dirigido a una persona DE LA CASA no debe abrirse como si fuera
público: así se entraba de invitado, en solo lectura, aunque a esa persona le
hubieran dado permiso de editor. Estilo Drive: el enlace pide iniciar sesión y
lleva a la carpeta de verdad, donde manda el permiso que tiene, no el enlace.

Reglas:
  · Enlace sin destinatario (abierto a cualquiera) → no se toca: sigue público.
  · Destinatario que NO es usuario de FARO (persona externa) → sigue público,
    con su clave o su código al correo como siempre.
  · Destinatario de la casa → pide sesión y entra al espacio compartido.
  · El dueño abriendo su propio enlace → entra directo a su carpeta.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import logging
from urllib.parse import quote

from almacen_bd import consultar

log = logging.getLogger('almacen.compartidos')


def _usuario_en_sesion():
    """ID de la persona con sesión abierta, o None."""
    try:
        from flask import session
        usuario = session.get('usuario_id') or session.get('_user_id')
        if usuario:
            return int(usuario)
        from flask_login import current_user
        if getattr(current_user, 'is_authenticated', False):
            return int(current_user.id)
    except Exception:
        pass
    return None


def _destinatario_interno(comp):
    """ID del usuario de FARO al que va dirigido el enlace, o None si va a una
    persona externa (o a nadie en concreto)."""
    correo = (comp.get('email') or '').strip().lower()
    nombre_usuario = (comp.get('destinatario') or '').strip()
    if not correo and not nombre_usuario:
        return None
    try:
        filas = consultar("""
            SELECT id FROM usuarios
            WHERE LOWER(email) = %s OR username = %s
            LIMIT 1
        """, (correo, nombre_usuario), nomina=True)
    except Exception as excepcion:
        log.warning('No se pudo comprobar el destinatario del enlace: %s', excepcion)
        return None
    return int(filas[0]['id']) if filas else None


def puente_a_sesion(comp, subruta=''):
    """Redirección al explorador si el enlace es para alguien de la casa; None
    si el enlace debe seguir su camino público de siempre."""
    from flask import redirect, request

    destinatario = _destinatario_interno(comp)
    if destinatario is None:
        return None

    from permisos_compartidos import ruta_compartida
    ruta = comp.get('ruta') or '/'
    cola = ('/' + subruta.strip('/')) if subruta else ''
    usuario = _usuario_en_sesion()

    if usuario is None:
        # Sin sesión: al login y de vuelta a este mismo enlace, que ya sabrá
        # llevarla a su sitio.
        volver = request.full_path.rstrip('?') if request.full_path else request.path
        return redirect('/auth/iniciar-sesion?next=' + quote(volver), 302)

    if usuario == int(comp['propietario_id']):
        return redirect('/archivos-almacen' + quote(ruta + cola), 302)

    if usuario == destinatario:
        return redirect('/archivos-almacen'
                        + quote(ruta_compartida(comp['propietario_id'], ruta) + cola), 302)

    # Otra persona con sesión abierta: no es su enlace. Sigue el camino público
    # (que ya pide clave o código si el enlace los tiene).
    return None
