# -*- coding: utf-8 -*-
"""
Almacén Maquita — servicio para el WEBMAIL (aplicación independiente).
======================================================================
Fábrica Flask que publica el motor del Almacén junto al webmail:

- API bajo `/api/almacen/*` (mismo contrato que docs/CONTRATO-API.md).
- Página del editor OnlyOffice en `/archivos-almacen/editar?ruta=...`.
- Autenticación: la cookie `access_token` del webmail (ver auth_webmail.py).
- `/api/almacen/onlyoffice/download|callback` van exentos de la cookie:
  los llama el Document Server con su propio token firmado (JWT).

Correr con gunicorn (ver deploy/maquita-almacen.service):
    gunicorn -w 4 -b 127.0.0.1:8788 'app_webmail:crear_app_webmail()'
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# La "nómina" del motor ES la propia BD del Almacén en el webmail (tabla
# usuarios local). Debe fijarse ANTES de importar config_almacen.
for _var in ('HOST', 'NAME', 'USER', 'PASSWORD', 'PORT'):
    _valor = os.getenv(f'ALMACEN_DB_{_var}')
    if _valor and not os.getenv(f'NOMINA_DB_{_var}'):
        os.environ[f'NOMINA_DB_{_var}'] = _valor

from flask import Flask, jsonify, request

from almacen_bd import asegurar_esquema
from auth_webmail import asegurar_tablas_webmail, usuario_webmail
from config_almacen import CLAVE_SESION, TAMANO_MAX_SUBIDA

# Rutas que NO exigen la cookie del webmail (autenticación propia por token
# firmado del Document Server, o diagnóstico sin datos).
_EXENTAS = (
    '/api/almacen/onlyoffice/download',
    '/api/almacen/onlyoffice/callback',
    '/api/almacen/publico/',    # descarga por enlace compartido (token propio)
    '/almacen-s/',              # página del enlace compartido
    '/healthz',
)


def crear_app_webmail() -> Flask:
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    app = Flask('almacen_webmail')
    app.secret_key = CLAVE_SESION
    app.config['MAX_CONTENT_LENGTH'] = TAMANO_MAX_SUBIDA

    asegurar_esquema()          # esquema del motor (idempotente)
    asegurar_tablas_webmail()   # directorio local de usuarios
    from alias_correo import asegurar_tabla_alias
    asegurar_tabla_alias()      # alias: varios buzones -> una identidad

    from api_archivos import bp_archivos
    from api_compartir import bp_compartir
    from api_extras import bp_extras
    from api_admin import bp_admin
    from api_versiones import bp_versiones
    from api_onlyoffice import bp_onlyoffice, bp_onlyoffice_web
    from api_unidades import bp_unidades
    from api_actividad import bp_actividad
    from api_almacenamiento import bp_almacenamiento
    from api_alias import bp_alias

    for bp in (bp_archivos, bp_compartir, bp_extras, bp_admin, bp_versiones,
               bp_onlyoffice, bp_unidades, bp_actividad, bp_almacenamiento,
               bp_alias):
        app.register_blueprint(bp, url_prefix='/api/almacen')
    app.register_blueprint(bp_onlyoffice_web)   # /archivos-almacen/editar

    @app.before_request
    def _candado_webmail():
        # NUNCA confiar en la cabecera si viene del cliente: se limpia siempre
        # y solo este candado la fija tras validar la cookie del webmail.
        request.environ.pop('HTTP_X_ALMACEN_USUARIO_ID', None)
        ruta = request.path
        if ruta.startswith(_EXENTAS):
            return None
        uid, rol = usuario_webmail()
        if not uid:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        # Las rutas administrativas exigen master (los endpoints además lo
        # re-validan por su cuenta vía es_master: defensa en profundidad).
        if '/admin/' in ruta and rol not in ('master', 'master_admin'):
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        request.environ['HTTP_X_ALMACEN_USUARIO_ID'] = str(uid)
        return None

    @app.get('/almacen-s/<token>')
    def enlace_publico(token):
        """Página del enlace compartido: pide la clave si hace falta y descarga.
        La seguridad real vive en /api/almacen/publico/<token> (token, clave,
        expiración, permite_descarga) — esto es solo la cara amable."""
        import re as _re
        if not _re.fullmatch(r'[A-Za-z0-9_-]{10,64}', token):
            return jsonify({'success': False, 'error': 'Enlace inválido'}), 404
        html = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archivo compartido</title>
<style>
 body{font-family:'Segoe UI',system-ui,sans-serif;background:#f3f2f1;display:flex;
      align-items:center;justify-content:center;min-height:100vh;margin:0}
 .tarjeta{background:#fff;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);
      padding:32px;max-width:380px;width:90%;text-align:center}
 h1{font-size:18px;color:#323130;margin:0 0 6px}
 p{font-size:13px;color:#605e5c;margin:0 0 18px}
 input{width:100%;box-sizing:border-box;padding:9px;border:1px solid #8a8886;
      border-radius:6px;font-size:14px;margin-bottom:12px;display:none}
 button{width:100%;padding:10px;background:#0078d4;color:#fff;border:0;
      border-radius:6px;font-size:14px;font-weight:600;cursor:pointer}
 button:hover{background:#106ebe}
 #mensaje{font-size:13px;color:#d13438;margin-top:12px;min-height:18px}
</style></head><body>
<div class="tarjeta">
  <div style="font-size:42px">📎</div>
  <h1>Archivo compartido contigo</h1>
  <p>Este enlace fue generado desde el Almacén. Si tiene clave, se pedirá.</p>
  <input id="clave" type="password" placeholder="Clave del enlace" autocomplete="off">
  <button onclick="descargar()">Descargar archivo</button>
  <div id="mensaje"></div>
</div>
<script>
 const TOKEN = location.pathname.split('/').pop();
 async function descargar(){
   const clave = document.getElementById('clave').value;
   const m = document.getElementById('mensaje');
   m.textContent = 'Verificando…'; m.style.color = '#605e5c';
   const url = '/api/almacen/publico/' + encodeURIComponent(TOKEN)
             + (clave ? '?clave=' + encodeURIComponent(clave) : '');
   const r = await fetch(url);
   if (r.ok){
     m.textContent = '';
     const blob = await r.blob();
     const cd = r.headers.get('Content-Disposition') || '';
     const nombre = decodeURIComponent((cd.match(/filename\*?=(?:UTF-8''|\"?)([^\";]+)/i)||[])[1]||'archivo');
     const a = document.createElement('a');
     a.href = URL.createObjectURL(blob); a.download = nombre; a.click();
     URL.revokeObjectURL(a.href);
     return;
   }
   m.style.color = '#d13438';
   if (r.status === 401){
     document.getElementById('clave').style.display = 'block';
     m.textContent = clave ? 'Clave incorrecta' : 'Este enlace tiene clave: escríbela';
   } else if (r.status === 410){ m.textContent = 'Este enlace ya expiró'; }
   else if (r.status === 403){ m.textContent = 'Este enlace no permite descargar'; }
   else { m.textContent = 'El enlace no existe o fue retirado'; }
 }
</script></body></html>"""
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

    @app.get('/healthz')
    def healthz():
        return jsonify({'success': True, 'servicio': 'almacen-webmail'})

    # Cualquier endpoint del contrato aún no implementado responde JSON 404
    # (nunca HTML: el frontend hace .json() sobre la respuesta).
    @app.route('/api/almacen/<path:faltante>')
    def _no_implementado(faltante):
        return jsonify({'success': False,
                        'error': f'Función no disponible: /{faltante}'}), 404

    @app.errorhandler(401)
    def _sin_sesion(_e):
        return jsonify({'success': False, 'error': 'No autenticado'}), 401

    @app.errorhandler(403)
    def _sin_permiso(_e):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    @app.errorhandler(404)
    def _no_encontrado(_e):
        return jsonify({'success': False, 'error': 'No encontrado'}), 404

    @app.errorhandler(413)
    def _muy_grande(_e):
        return jsonify({'success': False, 'error': 'Archivo demasiado grande'}), 413

    return app
