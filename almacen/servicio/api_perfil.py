# -*- coding: utf-8 -*-
"""
«Mi perfil» del explorador: el nombre con el que los demás ven a la persona.
=============================================================================
`GET  /api/almacen/mi-perfil` → {nombre_nomina, nombre_visible, email, foto_url, editable}
`POST /api/almacen/mi-perfil` — {nombre_visible} → guarda el nombre (vacío = el predeterminado).

La ruta figura en el contrato (docs/CONTRATO-API.md, n.º 14) y el menú «Mi perfil» la
llama, pero el Almacén del webmail no la tenía: la petición caía en el comodín
`/api/almacen/<path>` (404 «Función no disponible») y la pantalla no cambiaba.

- Directorio LOCAL (instalación autocontenida): el nombre vive en `usuarios.full_name`,
  el mismo campo que ya muestran «Compartido por» y el diálogo «Compartir». Se puede editar.
- Directorio central o cuenta externa: el nombre lo administra ese directorio; aquí solo
  se muestra (`editable: false`) y el POST responde 403.

`nombre_nomina` es el nombre predeterminado (se conserva el nombre de campo del contrato).
"""
import re

from flask import Blueprint, jsonify, request

import auth_webmail
from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual

bp_perfil = Blueprint('almacen_perfil', __name__)

LARGO_MAXIMO = 80
# Igual que los nombres de archivo [A-13]: el explorador pinta nombres de personas dentro de
# atributos onclick, así que comillas y barra invertida no se admiten (lo ven otras personas).
_NO_PERMITIDOS = re.compile(r'[<>"\'\\\x00-\x1f\x7f]')


def nombre_predeterminado(correo: str) -> str:
    """'ana.perez@dominio' → 'Ana Perez' (igual que al crear el usuario local)."""
    return (correo or '').split('@')[0].replace('.', ' ').title()


def limpiar_nombre(texto):
    """Nombre visible saneado (espacios colapsados). None si no es admisible."""
    if texto is not None and not isinstance(texto, str):
        return None
    if _NO_PERMITIDOS.search(texto or ''):
        return None
    nombre = ' '.join((texto or '').split())
    return nombre if len(nombre) <= LARGO_MAXIMO else None


def _es_local() -> bool:
    return auth_webmail._MODO == 'local'


def perfil_de(usuario: int):
    """Datos del perfil del usuario, o None si no está en ningún directorio."""
    if usuario >= auth_webmail._OFFSET_EXTERNOS:
        filas = consultar('SELECT email, full_name FROM usuarios_externos WHERE id = %s',
                          (usuario - auth_webmail._OFFSET_EXTERNOS,))
        if not filas:
            return None
        correo = (filas[0]['email'] or '').strip().lower()
        nombre = (filas[0]['full_name'] or '').strip() or nombre_predeterminado(correo)
        return {'email': correo, 'nombre_nomina': nombre, 'nombre_visible': nombre,
                'foto_url': None, 'editable': False}
    filas = consultar("""
        SELECT u.username, COALESCE(u.email, '') AS email, COALESCE(u.full_name, '') AS full_name,
               COALESCE(t.nombres || ' ' || t.apellidos, '') AS nombre_directorio
        FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.id = %s
    """, (usuario,), nomina=True)
    if not filas:
        return None
    fila = filas[0]
    correo = (fila['email'] or fila['username'] or '').strip().lower()
    propio = (fila['full_name'] or '').strip()
    if _es_local():
        predeterminado = nombre_predeterminado(correo)
        visible = propio or predeterminado
    else:
        predeterminado = (fila['nombre_directorio'] or '').strip() or propio or fila['username']
        visible = predeterminado
    return {'email': correo, 'nombre_nomina': predeterminado, 'nombre_visible': visible,
            'foto_url': None, 'editable': _es_local()}


@bp_perfil.route('/mi-perfil', methods=['GET'])
def ver_mi_perfil():
    """GET /mi-perfil — cómo ven los demás a quien tiene la sesión."""
    perfil = perfil_de(usuario_actual())
    if perfil is None:
        return error('Perfil no encontrado', 404)
    return jsonify(dict(perfil, success=True))


@bp_perfil.route('/mi-perfil', methods=['POST'])
def guardar_mi_perfil():
    """POST /mi-perfil — {nombre_visible}. Vacío restablece el nombre predeterminado."""
    usuario = usuario_actual()
    perfil = perfil_de(usuario)
    if perfil is None:
        return error('Perfil no encontrado', 404)
    if not perfil['editable']:
        return error('Su nombre lo administra el directorio de la institución; '
                     'solicite el cambio al área de Tecnología.', 403)
    datos = request.get_json(silent=True) or {}
    nombre = limpiar_nombre(datos.get('nombre_visible'))
    if nombre is None:
        return error('El nombre no es válido: use hasta %d caracteres, sin < > comillas ni \\.'
                     % LARGO_MAXIMO, 400)
    nombre = nombre or perfil['nombre_nomina']
    fila = ejecutar('UPDATE usuarios SET full_name = %s WHERE id = %s RETURNING id',
                    (nombre, usuario))
    if not fila:
        return error('Perfil no encontrado', 404)
    return jsonify({'success': True, 'nombre_visible': nombre})
