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
    '/api/almacen/publico-info/',           # datos del enlace (misma seguridad)
    '/api/almacen/onlyoffice/config-public',  # editor por enlace (token + clave)
    '/almacen-s/',              # página del enlace compartido
    '/archivos-almacen',        # páginas del explorador (redirigen a login solas)
    '/drive',                   # acceso corto del producto
    '/almacen-static/',         # css/js del explorador
    '/healthz',
)


_CONTACTO_SOPORTE = os.getenv('ALMACEN_CONTACTO_SOPORTE', '')


def _mensaje_sin_enlace(correo, motivo):
    """Mensaje de ayuda cuando el buzón entra pero la cuenta no está enlazada
    al directorio institucional (o la fase piloto no lo incluye aún)."""
    if motivo == 'piloto':
        base = ('El módulo de Archivos está en fase de pruebas y tu cuenta '
                'aún no está incluida.')
    else:
        base = (f'Tu buzón ({correo}) todavía no está conectado a tu '
                'identidad institucional.')
    if _CONTACTO_SOPORTE:
        return (f'{base} Escríbenos a {_CONTACTO_SOPORTE} y lo activamos: '
                'creamos o conectamos tu cuenta y te avisamos por correo.')
    return f'{base} Comunícate con el administrador del sistema para activarla.'


def _pagina_ayuda_enlace(correo, motivo):
    """Página amigable para el usuario con buzón pero sin identidad enlazada."""
    mensaje = _mensaje_sin_enlace(correo, motivo)
    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Un paso más — Archivos</title>
<style>
 body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f3f2f1;display:flex;
      align-items:center;justify-content:center;min-height:100vh;margin:0}}
 .tarjeta{{background:#fff;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);
      padding:36px;max-width:440px;width:90%;text-align:center}}
 h1{{font-size:18px;color:#323130;margin:0 0 10px}}
 p{{font-size:14px;color:#605e5c;line-height:1.5;margin:0 0 20px}}
 a.boton{{display:inline-block;padding:10px 22px;background:#0078d4;color:#fff;
      border-radius:6px;text-decoration:none;font-weight:600;font-size:14px}}
 a.boton:hover{{background:#106ebe}}
</style></head><body>
<div class="tarjeta">
  <div style="font-size:46px">🔗</div>
  <h1>Falta un paso para activar tus Archivos</h1>
  <p>{mensaje}</p>
  <a class="boton" href="/webmail">Volver al correo</a>
</div>
</body></html>"""
    return html, 403, {'Content-Type': 'text/html; charset=utf-8'}


def crear_app_webmail() -> Flask:
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    base = os.path.dirname(os.path.abspath(__file__))
    app = Flask('almacen_webmail',
                template_folder=os.path.join(base, 'plantillas'),
                static_folder=os.path.join(base, 'estaticos'),
                static_url_path='/almacen-static')
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

    # El template del explorador viene del sistema mayor y enlaza a modulos
    # que aqui no existen (helpdesk, etc.): esos enlaces van al correo en vez
    # de tumbar el render con BuildError.
    from flask import url_for as _url_for_real

    @app.context_processor
    def _url_for_tolerante():
        def url_for(endpoint, **valores):
            try:
                return _url_for_real(endpoint, **valores)
            except Exception:
                return '/webmail'
        return {'url_for': url_for}

    @app.before_request
    def _candado_webmail():
        # NUNCA confiar en la cabecera si viene del cliente: se limpia siempre
        # y solo este candado la fija tras validar la cookie del webmail.
        request.environ.pop('HTTP_X_ALMACEN_USUARIO_ID', None)
        ruta = request.path
        if ruta.startswith(_EXENTAS):
            return None
        from auth_webmail import sesion_actual
        uid, rol, correo, motivo = sesion_actual()
        if not uid:
            if motivo in ('sin_enlace', 'piloto'):
                return jsonify({
                    'success': False,
                    'error': 'cuenta_sin_enlace',
                    'mensaje': _mensaje_sin_enlace(correo, motivo),
                }), 403
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
      padding:32px;max-width:400px;width:90%;text-align:center}
 h1{font-size:17px;color:#323130;margin:0 0 4px;word-break:break-word}
 p{font-size:13px;color:#605e5c;margin:0 0 16px}
 input{width:100%;box-sizing:border-box;padding:9px;border:1px solid #8a8886;
      border-radius:6px;font-size:14px;margin-bottom:12px;display:none}
 button{width:100%;padding:10px;border:0;border-radius:6px;font-size:14px;
      font-weight:600;cursor:pointer;margin-bottom:8px}
 .principal{background:#0078d4;color:#fff}.principal:hover{background:#106ebe}
 .secundario{background:#fff;color:#0078d4;border:1px solid #0078d4;display:none}
 .secundario:hover{background:#deecf9}
 #mensaje{font-size:13px;color:#d13438;margin-top:8px;min-height:18px}
</style></head><body>
<div class="tarjeta">
  <div style="font-size:42px" id="icono">📎</div>
  <h1 id="titulo">Archivo compartido contigo</h1>
  <p id="detalle">Verificando el enlace…</p>
  <input id="clave" type="password" placeholder="Clave del enlace" autocomplete="off">
  <button id="btnAbrir" class="secundario" onclick="abrir()">✏️ Abrir en línea</button>
  <button id="btnBajar" class="principal" onclick="descargar()">⬇️ Descargar archivo</button>
  <div id="mensaje"></div>
</div>
<script>
 const TOKEN = location.pathname.split('/').filter(Boolean).pop();
 const $ = id => document.getElementById(id);
 function claveQS(){ const c = $('clave').value; return c ? '&clave=' + encodeURIComponent(c) : ''; }

 async function cargarInfo(){
   const r = await fetch('/api/almacen/publico-info/' + encodeURIComponent(TOKEN) + '?x=1' + claveQS());
   if (!r.ok){
     const d = await r.json().catch(() => ({}));
     $('detalle').textContent = d.error || 'El enlace no existe o fue retirado';
     $('btnBajar').style.display = 'none';
     return;
   }
   const d = await r.json();
   if (d.requiere_clave && !d.clave_valida){
     $('clave').style.display = 'block';
     $('detalle').textContent = 'Este enlace tiene clave: escríbela y pulsa un botón';
     $('btnAbrir').style.display = 'block';   // se re-valida al pulsar
     return;
   }
   $('titulo').textContent = d.nombre || 'Archivo compartido';
   $('detalle').textContent = (d.tamano_bytes != null ? (d.tamano_bytes/1048576).toFixed(2) + ' MB · ' : '')
                            + (d.puede_editar ? 'puedes editarlo en línea' : d.abre_en_linea ? 'puedes verlo en línea' : 'listo para descargar');
   if (d.abre_en_linea) $('btnAbrir').style.display = 'block';
   $('btnBajar').style.display = d.permite_descarga ? 'block' : 'none';
   if (!d.permite_descarga && !d.abre_en_linea) $('detalle').textContent = 'Este enlace es de solo lectura';
 }

 function abrir(){
   location.href = '/almacen-s/' + encodeURIComponent(TOKEN) + '/editar' + ($('clave').value ? '?clave=' + encodeURIComponent($('clave').value) : '');
 }

 async function descargar(){
   const m = $('mensaje');
   m.textContent = 'Verificando…'; m.style.color = '#605e5c';
   const r = await fetch('/api/almacen/publico/' + encodeURIComponent(TOKEN) + '?x=1' + claveQS());
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
   if (r.status === 401){ $('clave').style.display = 'block'; m.textContent = $('clave').value ? 'Clave incorrecta' : 'Este enlace tiene clave: escríbela'; }
   else if (r.status === 410){ m.textContent = 'Este enlace ya expiró'; }
   else if (r.status === 403){ m.textContent = 'Este enlace no permite descargar'; }
   else { m.textContent = 'El enlace no existe o fue retirado'; }
 }
 cargarInfo();
</script></body></html>"""
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

    # ── Explorador web (el template estilo Drive del equipo) ─────────────
    # El menú lateral del template enlaza a /archivos-almacen/<vista>; /drive
    # es el acceso corto de producto (nginx: mail.dominio/drive llega aquí).
    _VISTAS_ESPECIALES = ('compartidos', 'recientes', 'favoritos', 'papelera')

    @app.route('/drive')
    @app.route('/drive/', endpoint='drive_barra')
    def drive():
        from flask import redirect
        return redirect('/archivos-almacen', code=302)

    # El template trae {{ url_for('home') }} (volver al inicio): aquí el
    # inicio es el correo.
    @app.route('/webmail-inicio', endpoint='home')
    def _home():
        from flask import redirect
        return redirect('/webmail', code=302)

    class _UsuarioPlantilla:
        """current_user mínimo que consume el template del explorador."""
        def __init__(self, correo, rol):
            self.username = correo
            self.nombre = correo.split('@')[0].replace('.', ' ').title()
            self.email = correo
            self.role = rol or 'user'
            self.profile_picture = ''
            self.is_authenticated = True

    @app.route('/archivos-almacen')
    @app.route('/archivos-almacen/<path:ruta>')
    def explorador_web(ruta=''):
        from flask import render_template
        from auth_webmail import sesion_actual
        uid, rol, correo, motivo = sesion_actual()
        if not uid:
            from flask import redirect
            if motivo == 'sin_sesion':
                return redirect('/webmail/login', code=302)
            return _pagina_ayuda_enlace(correo, motivo)
        ruta = (ruta or '').strip('/')
        primera = ruta.split('/')[0] if ruta else ''
        if primera in _VISTAS_ESPECIALES:
            vista, ruta_inicial = primera, '/'
        elif primera == 'mi-unidad':
            vista, ruta_inicial = 'archivos', '/'
        else:
            vista, ruta_inicial = 'archivos', '/' + ruta
        subperms = {k: True for k in ('mi_unidad', 'compartidos', 'recientes',
                                      'favoritos', 'papelera')}
        return render_template(
            'nextcloud/explorador.html',
            ruta_inicial=ruta_inicial,
            vista=vista,
            usuario_nextcloud='',
            modulos_disponibles={},
            nube_subperms=subperms,
            almacen_modo=True,
            current_user=_UsuarioPlantilla(correo, rol),
            usuario=_UsuarioPlantilla(correo, rol),
        )

    @app.get('/almacen-s/<token>/editar')
    def editor_publico(token):
        """Editor OnlyOffice para un enlace compartido (sin sesión). Pide la
        configuración a /api/almacen/onlyoffice/config-public con el token del
        enlace (+clave si viaja en el query)."""
        import re as _re
        if not _re.fullmatch(r'[A-Za-z0-9_-]{10,64}', token):
            return jsonify({'success': False, 'error': 'Enlace inválido'}), 404
        html = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Editor — archivo compartido</title>
<style>
 html,body{height:100%;margin:0;background:#f3f2f1;font-family:'Segoe UI',system-ui,sans-serif}
 #contenedor{height:100%}
 #estado{position:absolute;top:40%;left:0;right:0;text-align:center;color:#605e5c;font-size:14px}
</style></head><body>
<div id="estado">Cargando el editor…</div>
<div id="contenedor"><div id="editor"></div></div>
<script>
 const partes = location.pathname.split('/').filter(Boolean);   // almacen-s, <token>, editar
 const TOKEN = partes[1];
 const CLAVE = new URLSearchParams(location.search).get('clave') || '';
 const estado = document.getElementById('estado');
 function fallo(m){ estado.innerHTML = '<b>No se pudo abrir el editor</b><br>' + m; }

 (async () => {
   const r = await fetch('/api/almacen/onlyoffice/config-public?token=' + encodeURIComponent(TOKEN)
                       + (CLAVE ? '&clave=' + encodeURIComponent(CLAVE) : ''));
   const d = await r.json().catch(() => ({}));
   if (!r.ok || !d.success){ fallo(d.error || 'Enlace inválido'); return; }
   document.title = d.nombre + ' — compartido';
   const s = document.createElement('script');
   s.src = d.api_js_url;
   s.onerror = () => fallo('No se pudo cargar el servidor de documentos');
   s.onload = () => {
     d.config.events = { onAppReady: () => { estado.style.display = 'none'; } };
     new DocsAPI.DocEditor('editor', d.config);
   };
   document.head.appendChild(s);
 })();
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
