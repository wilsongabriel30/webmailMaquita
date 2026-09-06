# -*- coding: utf-8 -*-
"""
T-43 · Ficha del compañero (31/08/2026, pedido de la gente).

`GET /api/chat/personas/<usuario_id>/ficha` → datos del directorio de nómina para
mostrar la tarjeta al hacer clic en la foto de alguien.

Criterio de privacidad (por defecto, revisable por la dirección):
  * LO INSTITUCIONAL lo ve todo el personal: foto, nombres completos, cargo, área,
    sede, correo institucional, teléfono institucional y extensión.
  * LO PERSONAL (cédula, teléfono personal, correo personal) solo lo ven los
    perfiles de Talento Humano / administración, y cada quien en su propia ficha.
Si la dirección decide abrirlo a todos, se cambia PERSONALES_PARA_TODOS a True.

Autor: Wilson Arguello
"""
import os

from flask import Blueprint, jsonify, session

bp_ficha = Blueprint('ficha_persona', __name__, url_prefix='/api/chat/personas')

PERSONALES_PARA_TODOS = os.getenv('FICHA_DATOS_PERSONALES_PARA_TODOS', '0') == '1'
ROLES_RRHH = ('master', 'master_admin', 'admin', 'talento_humano', 'rrhh', 'nomina')
AREAS_RRHH = ('talento humano', 'recursos humanos', 'gestion del talento humano')

SQL = """
SELECT t.id, t.nombres, t.apellidos, t.cedula,
       COALESCE(c.nombre, '')  AS cargo,
       COALESCE(d.nombre, '')  AS area,
       COALESCE(s.nombre, '')  AS sede,
       COALESCE(t.email_institucional, '') AS correo_institucional,
       COALESCE(t.email_personal, '')      AS correo_personal,
       COALESCE(t.telefono_movil_institucional, '') AS telefono_institucional,
       COALESCE(t.extension_telefono, '')  AS extension,
       COALESCE(t.telefono_movil, '')      AS telefono_personal,
       COALESCE(t.telefono_fijo, '')       AS telefono_fijo,
       COALESCE(t.foto_perfil, '')         AS foto,
       u.id AS usuario_id
FROM usuarios u
JOIN trabajadores t ON t.id = u.trabajador_id
LEFT JOIN cargos c        ON c.id = t.cargo_id
LEFT JOIN departamentos_empresa d ON d.id = t.departamento_id
LEFT JOIN sucursales s    ON s.id = t.sucursal_id
WHERE u.id = %s
"""

SQL_QUIEN = """
SELECT COALESCE(u.role, ''), COALESCE(d.nombre, '')
FROM usuarios u
LEFT JOIN trabajadores t  ON t.id = u.trabajador_id
LEFT JOIN departamentos_empresa d ON d.id = t.departamento_id
WHERE u.id = %s
"""


def _conexion():
    import psycopg2
    return psycopg2.connect(os.getenv('USERS_DB_URL') or os.getenv('DATABASE_URL'))


def _puede_ver_personales(cur, quien, de_quien):
    if PERSONALES_PARA_TODOS or str(quien) == str(de_quien):
        return True          # cada quien ve su propia ficha completa
    cur.execute(SQL_QUIEN, (quien,))
    fila = cur.fetchone()
    if not fila:
        return False
    rol, area = (fila[0] or '').lower(), (fila[1] or '').lower()
    return rol in ROLES_RRHH or any(a in area for a in AREAS_RRHH)


def _url_foto(foto):
    if not foto:
        return ''
    if foto.startswith('http') or foto.startswith('/'):
        return foto
    if foto.startswith('uploads/'):
        return 'https://datos.maquita.com.ec/static/' + foto
    return 'https://datos.maquita.com.ec/static/uploads/profiles/' + foto


@bp_ficha.route('/<int:usuario_id>/ficha', methods=['GET'])
def ficha(usuario_id):
    """Ficha del compañero. Solo datos del directorio institucional; los personales,
    según el perfil de quien pregunta."""
    quien = session.get('usuario_id')
    if not quien:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    try:
        con = _conexion()
        try:
            with con.cursor() as cur:
                cur.execute(SQL, (usuario_id,))
                f = cur.fetchone()
                if not f:
                    return jsonify({'success': False,
                                    'error': 'Esta persona todavía no está en el directorio'}), 404
                ver_personales = _puede_ver_personales(cur, quien, usuario_id)
        finally:
            con.close()
    except Exception:
        return jsonify({'success': False, 'error': 'No se pudo consultar el directorio'}), 200

    (_id, nombres, apellidos, cedula, cargo, area, sede, correo_inst, correo_pers,
     tel_inst, extension, tel_pers, tel_fijo, foto, uid) = f

    datos = {
        'usuario_id': uid,
        'nombre': ('%s %s' % (nombres or '', apellidos or '')).strip(),
        'cargo': cargo, 'area': area, 'sede': sede,
        'correo_institucional': correo_inst,
        'telefono_institucional': tel_inst,
        'extension': extension,
        'foto': _url_foto(foto),
    }
    if ver_personales:
        datos.update({'cedula': cedula or '', 'telefono_personal': tel_pers,
                      'telefono_fijo': tel_fijo, 'correo_personal': correo_pers})
    # T-48: el estado de presencia, con la misma regla que el resto del chat
    try:
        from interfaces.websocket import estado_presencia as _ep
        datos['estado'] = _ep.estado_de(usuario_id)
    except Exception:
        datos['estado'] = 'ausente'

    return jsonify({'success': True, 'persona': datos,
                    'incluye_personales': bool(ver_personales)}), 200
