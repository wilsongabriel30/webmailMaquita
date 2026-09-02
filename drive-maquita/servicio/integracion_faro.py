# -*- coding: utf-8 -*-
"""
Integración del Almacén Maquita dentro de FARO (modo pruebas, SOLO master).
===========================================================================
Monta el motor propio bajo el prefijo `/api/almacen` y sirve el MISMO explorador
en `/archivos-almacen`, apuntándolo al motor. Así el equipo prueba el desarrollo
desde el frontend SIN chocar con la Nube en producción (`/api/nextcloud`).

Todo lo de `/api/almacen*` y `/archivos-almacen*` queda restringido a usuarios
master. Es un puente TEMPORAL de desarrollo; en producción el Almacén correrá
como servicio propio detrás de nginx.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import os
import sys
import logging

from flask import Blueprint, make_response, render_template, session, abort, request
from flask_login import login_required, current_user

log = logging.getLogger('almacen.integracion')

# Carpeta del servicio del Almacén (para importar sus módulos por nombre)
_DIR_SERVICIO = os.path.dirname(os.path.abspath(__file__))

bp_almacen_web = Blueprint('almacen_web', __name__)

def _uid_actual():
    """ID de usuario de la petición (sesión de FARO o flask_login)."""
    uid = session.get('usuario_id')
    if not uid and getattr(current_user, 'is_authenticated', False):
        uid = current_user.id
    return int(uid) if uid else None


def _es_master_actual() -> bool:
    """Master según la BD (autoritativo), no según el rol de sesión que a veces
    llega vacío. Reutiliza es_master() del motor (consulta nómina, cacheado)."""
    uid = _uid_actual()
    if not uid:
        return False
    try:
        from almacen_bd import es_master
        return es_master(uid)
    except Exception:
        return False


# Usuarios de PILOTO (además de los master) con acceso al Almacén en esta fase de pruebas.
# Wilson Argüello (14) y Alejandra Calvache (187, pasante). Ampliar aquí para sumar testers.
_PILOTO_IDS = {14, 187}


def _acceso_almacen() -> bool:
    """¿Puede entrar al Almacén? Cualquier master, un piloto de la lista, o un usuario
    con el permiso del módulo FARO almacen (asignable desde /admin/modulos-permisos).
    NO otorga permisos de admin: las rutas /admin/* siguen exigiendo master (ver el candado
    y los propios endpoints con _exigir_master/_master)."""
    # CORTE 2026-07-23 (decisión de Wilson): Drive Maquita abierto a TODOS los
    # usuarios autenticados de FARO (reemplaza a la Nube/Nextcloud, que queda
    # solo para master/admin). Las rutas /admin/* siguen exigiendo master.
    if _uid_actual():
        return True
    if _es_master_actual():
        return True
    if _uid_actual() in _PILOTO_IDS:
        return True
    try:
        from services.modulos_permisos_service import modulos_permisos_service
        rol = getattr(current_user, "role", "") or ""
        return bool(modulos_permisos_service.user_has_module_access(_uid_actual(), rol, "almacen"))
    except Exception as e:
        log.warning("almacen: fallo consultando permiso de modulo: %s", e)
        return False


def _es_ruta_admin_almacen(ruta: str) -> bool:
    """Rutas administrativas del motor: reservadas a master aunque el usuario sea piloto."""
    return '/admin/' in ruta or ruta.endswith('/admin')


# Vistas especiales del explorador (mismas que la Nube): no son carpetas, son secciones.
_VISTAS_ESPECIALES = ('principal', 'compartidos', 'recientes', 'favoritos', 'papelera',
                      'ordenadores', 'unidades')


# `strict_slashes=False`: «/archivos-almacen/» —con la barra final y nada
# detrás— no coincidía con ninguna de las dos rutas y devolvía la página «Página
# no encontrada» de FARO. Lo generaba cualquier enlace armado a partir de una
# carpeta que resultara ser la raíz (27/08/2026).
@bp_almacen_web.route('/archivos-almacen', strict_slashes=False)
@bp_almacen_web.route('/archivos-almacen/<path:ruta>')
@login_required
def explorador_almacen(ruta=''):
    """Explorador conectado al motor propio (solo master, para pruebas).
    Reconoce las vistas especiales (compartidos/recientes/favoritos/papelera) igual
    que la Nube, para que el menú lateral funcione DENTRO del motor y no salte a Nextcloud."""
    if not _acceso_almacen():
        abort(403)

    ruta = (ruta or '').strip('/')
    primer = ruta.split('/')[0] if ruta else ''
    if primer in _VISTAS_ESPECIALES:
        # «Unidades compartidas» es la UNICA vista especial que tiene contenido
        # debajo: /unidades es el listado, pero /unidades/3/Contratos es una
        # carpeta de verdad. Sin esto se descartaba el resto de la ruta y al
        # entrar en una unidad se volvia al listado, sin poder abrir nada.
        resto = ruta[len(primer):].strip('/')
        if primer == 'unidades' and resto:
            vista = 'archivos'
            ruta_inicial = '/unidades/' + resto
        else:
            vista = primer
            ruta_inicial = '/'
    else:
        vista = 'archivos'
        ruta_inicial = '/' + ruta

        # Un enlace interno apunta a esa ruta EN EL ESPACIO DE QUIEN ENTRA. Si
        # la carpeta es de otra persona, aquí no existe y el explorador devolvía
        # a «Mi unidad» diciendo que el enlace ya no existe —siendo que la
        # carpeta está ahí, solo que es de otro— (01/09/2026).
        try:
            from resolver_enlace import resolver as _resolver_enlace
            _destino = _resolver_enlace(int(current_user.id), ruta_inicial)
        except Exception as _exc_resolver:
            log.warning('No se pudo resolver el enlace %s: %s', ruta_inicial, _exc_resolver)
            _destino = None
        if _destino and _destino.get('ir_a'):
            # Se lo compartieron: se le lleva por el camino que sí le abre.
            from flask import redirect as _redirigir
            from urllib.parse import quote as _codificar
            return _redirigir('/archivos-almacen' + _codificar(_destino['ir_a']), 302)
        if _destino and _destino.get('pedir_acceso'):
            # Existe, pero es de otra persona: se le enseña de quién es y un
            # botón para pedírselo, como en Google Drive.
            return _pagina_pedir_acceso(_destino['pedir_acceso'])

    # En modo Almacén el menú se muestra completo (permisos de la Nube no aplican aquí)
    subperms = {k: True for k in ('mi_unidad', 'compartidos', 'recientes', 'favoritos', 'papelera')}

    pagina = render_template(
        'nextcloud/explorador.html',
        ruta_inicial=ruta_inicial,
        vista=vista,
        usuario=current_user,
        usuario_nextcloud='',
        modulos_disponibles={},
        nube_subperms=subperms,
        almacen_modo=True,          # activa window.ALMACEN_OVERRIDE + rutas del motor
    )

    # La pagina NO se guarda en cache. No es una precaucion de mas: sin esto,
    # el navegador se la quedaba por heuristica propia y seguia pidiendo los
    # `?v=` VIEJOS de los JS y CSS. Como en drive.maquita.com.ec los estaticos
    # van con `Cache-Control: public, immutable` y un ano de caducidad, esos
    # archivos quedan congelados y NUNCA se revalidan: el cambio esta en el
    # servidor, se sirve bien, y aun asi la persona ve lo anterior.
    #
    # Ademas se mezclaban versiones -- HTML nuevo con JavaScript viejo--, y esa
    # combinacion deja la interfaz incoherente: acciones del menu contextual
    # que dejan de responder, modulos que no se cargan. Verificado el
    # 29/07/2026 con una auditoria externa que midio codigo antiguo mientras el
    # servidor ya servia el nuevo.
    #
    # La pagina lleva la sesion de la persona dentro: no debe cachearse nunca.
    respuesta = make_response(pagina)
    respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    respuesta.headers['Pragma'] = 'no-cache'
    return respuesta


# ---------------------------------------------------------------------------
# Acceso PUBLICO por enlace (personas externas). Reusa las MISMAS plantillas
# que la Nube para que el externo vea la interfaz de siempre, estilo Drive.
# Solo lectura: ver, navegar carpetas y descargar.
# ---------------------------------------------------------------------------
_EXT_IMAGEN = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}
_ZIP_MAXIMO = 2 * 1024 ** 3   # 2 GB por descarga completa


def _tam_humano(n):
    """Tamano legible, igual que lo muestra la Nube."""
    n = float(n or 0)
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or u == 'TB':
            return ('%d %s' % (n, u)) if u == 'B' else ('%.1f %s' % (n, u))
        n /= 1024



def _bloqueo_restringido(comp):
    """Si el enlace está en modo «restringido», responde por él (12/08/2026).

    Devuelve None cuando el enlace NO es restringido (sigue el flujo normal).
    Restringido = contenido de una unidad compartida cuyo enlace dejó de ser
    público: el miembro con sesión entra directo a la unidad; el resto ve a
    quién pedirle acceso. El enlace jamás entrega contenido.
    """
    if (comp or {}).get('modo') != 'restringido':
        return None
    from urllib.parse import quote
    from flask import session, redirect
    from almacen_bd import consultar

    ruta = comp.get('ruta') or '/'
    destino = '/archivos-almacen' + quote(ruta)
    unidad_id = None
    try:
        from api_unidades import unidad_de_ruta, rol_en_unidad
        unidad_id, _sub = unidad_de_ruta(ruta)
        usuario = session.get('usuario_id') or session.get('_user_id')
        if usuario and unidad_id is not None \
                and rol_en_unidad(int(usuario), unidad_id) is not None:
            return redirect(destino)
    except Exception:
        pass

    administradores = []
    try:
        if unidad_id is not None:
            filas = consultar(
                "SELECT usuario_id FROM unidad_miembros "
                "WHERE unidad_id = %s AND rol = 'manager'", (unidad_id,))
            ids = tuple(int(f['usuario_id']) for f in filas)
            if ids:
                personas = consultar("""
                    SELECT COALESCE(t.nombres || ' ' || t.apellidos,
                                    u.full_name, u.username) AS nombre
                    FROM usuarios u
                    LEFT JOIN trabajadores t ON u.trabajador_id = t.id
                    WHERE u.id IN %s ORDER BY 1
                """, (ids,), nomina=True)
                administradores = [p['nombre'] for p in personas]
    except Exception:
        pass

    import html as _html
    lista = ''.join('<li>%s</li>' % _html.escape(a) for a in administradores) \
        or '<li>El equipo de Tecnología</li>'
    login = '/auth/iniciar-sesion?next=' + quote(destino, safe='')
    pagina = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>Acceso restringido — Drive Maquita</title>'
              '<style>body{font-family:system-ui,Segoe UI,Roboto,sans-serif;'
              'background:#f8f9fa;color:#202124;display:flex;align-items:center;'
              'justify-content:center;min-height:100vh;margin:0}'
              '.caja{background:#fff;border:1px solid #dadce0;border-radius:12px;'
              'padding:32px;max-width:460px;width:92%%;text-align:center}'
              '.icono{font-size:44px}h1{font-size:1.2rem;margin:12px 0 6px}'
              'p{font-size:.92rem;color:#5f6368;margin:6px 0}'
              'ul{list-style:none;padding:0;margin:10px 0;font-size:.92rem}'
              'li{padding:2px 0}'
              'a.boton{display:inline-block;margin-top:14px;background:#1a73e8;'
              'color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;'
              'font-size:.95rem}</style></head><body><div class="caja">'
              '<div class="icono">🔒</div>'
              '<h1>Este contenido es de una unidad compartida de Maquita</h1>'
              '<p>El enlace ya no es de acceso público. Si trabajas en Maquita, '
              'inicia sesión y, si eres miembro de la unidad, entrarás directo.</p>'
              '<a class="boton" href="%s">Iniciar sesión</a>'
              '<p style="margin-top:16px">Si no tienes acceso, solicítalo a '
              'quienes administran la unidad:</p><ul>%s</ul>'
              '</div></body></html>') % (login, lista)
    return pagina, 403


def _compartido(token):
    """Devuelve la fila del enlace o None.

    El token se limpia de espacios: al copiar un enlace de un correo o de un
    documento se arrastra a veces un espacio o un salto de linea al final, y
    eso hacia que un enlace perfectamente valido respondiera «no existe».
    """
    from almacen_bd import consultar
    token = (token or '').strip()
    filas = consultar("""
        SELECT id, propietario_id, ruta, expira_en, clave_hash, permite_descarga,
               email, requiere_otp, puede_editar, modo
        FROM compartidos WHERE token = %s
    """, (token,))
    return filas[0] if filas else None


def _abre_en_onlyoffice(extension):
    """¿Este tipo de archivo se puede abrir en línea con OnlyOffice? (P-13)

    Se pregunta a la propia tabla de OnlyOffice para no mantener dos listas que
    se desincronicen. Si el módulo no está disponible se responde que NO, para
    caer al comportamiento de siempre (descarga) en vez de dar un error."""
    try:
        from api_onlyoffice import TIPOS_DOCUMENTO
        return extension in TIPOS_DOCUMENTO
    except Exception:
        return False


def _entregar_sin_macros(comp, destino, subruta='', adjunto=True):
    """send_file del archivo de un enlace, aplicando la política de macros.

    Un archivo con macros nunca sale por un enlace tal cual: se entrega su
    copia limpia (mismos datos, fórmulas y formato) y, si no se puede generar,
    no se entrega. Ver compartir_macros.py.
    """
    import os
    from flask import send_file
    from seguridad_rutas import normalizar_ruta_virtual, RutaInvalida
    import compartir_macros

    nombre = os.path.basename(destino)
    try:
        virtual = normalizar_ruta_virtual(comp['ruta'] + '/' + subruta) \
            if subruta else comp['ruta']
    except RutaInvalida:
        virtual = None

    ruta, nombre_final, temporal = compartir_macros.entrega_segura(
        destino, nombre, comp['propietario_id'], virtual)
    if not ruta:
        return compartir_macros.mensaje_bloqueo(nombre), 403

    respuesta = send_file(ruta, as_attachment=adjunto, download_name=nombre_final)
    if temporal:
        # La copia limpia se genera al vuelo: ni se guarda ni se cachea.
        respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'

        @respuesta.call_on_close
        def _borrar():
            try:
                os.unlink(temporal)
            except OSError:
                pass
    return respuesta


def _va_a_onlyoffice(comp, extension):
    """¿Este archivo del enlace debe abrirse en OnlyOffice? (P-13 / P-13b)

    Solo si quien compartió eligió «ver» o «editar». Los PDF y las imágenes se
    quedan en el visor propio del enlace: ya se ven bien y es más liviano."""
    # PDF e imagenes: se quedan en el visor propio del enlace (mas liviano).
    if extension == 'pdf' or extension in _EXT_IMAGEN:
        return False
    # Office (docx/xlsx/pptx/...): SIEMPRE se abre en el visor OnlyOffice EN LINEA,
    # como Google Drive, sin importar el 'modo' del enlace. La lectura vs edicion la
    # decide puede_editar del enlace (los de solo lectura abren en modo vista) y la
    # descarga DENTRO del visor respeta permite_descarga. Asi ningun enlace de solo
    # lectura fuerza la descarga del archivo.
    return _abre_en_onlyoffice(extension)


def _url_editor_publico(token, subruta='', clave=''):
    """URL del editor público del enlace. `subruta` viaja en `sub` cuando lo
    compartido es una carpeta y se abre un archivo de dentro (P-13b)."""
    from urllib.parse import quote
    url = '/archivos-almacen/editar-publico?t=%s' % quote(token)
    if subruta:
        url += '&sub=%s' % quote(subruta.strip('/'))
    if clave:
        url += '&clave=%s' % quote(clave)
    return url


def _propietario_nombre(usuario_id):
    """Nombre para mostrar del dueno del enlace (cae a la Fundacion si no hay)."""
    try:
        from almacen_bd import consultar
        filas = consultar("SELECT full_name, username FROM usuarios WHERE id = %s",
                          (usuario_id,), nomina=True)
        if filas:
            nombre = (filas[0].get('full_name') or filas[0].get('username') or '').strip()
            if nombre:
                return nombre.title() if nombre.isupper() else nombre
    except Exception as e:
        log.warning('almacen: no se pudo leer el dueno del enlace: %s', e)
    return 'Fundacion Maquita'


def _clave_ok(token, comp):
    """Valida la clave del enlace. Una vez correcta queda recordada en la sesion."""
    from flask import request as req, session
    if not comp['clave_hash']:
        return True
    marca = 'almacen_s_ok_%s' % token
    if session.get(marca):
        return True
    from hashlib import sha256
    clave = req.args.get('clave', '')
    if clave and sha256(clave.encode()).hexdigest() == comp['clave_hash']:
        session[marca] = True
        return True
    return False


def _pedir_clave(token):
    from flask import make_response, render_template_string
    return render_template_string(
        '<div style="font-family:Arial,sans-serif;max-width:360px;margin:90px auto;'
        'text-align:center;color:#202124"><h3>Contenido protegido</h3>'
        '<p style="color:#5f6368;font-size:14px">Escribe la clave para abrir este enlace.</p>'
        '<form method="get"><input type="password" name="clave" placeholder="Clave de acceso" '
        'style="padding:10px;width:100%;box-sizing:border-box;margin:8px 0;border:1px solid #dadce0;'
        'border-radius:6px"><button style="padding:10px 20px;border:0;border-radius:6px;'
        'background:#1a73e8;color:#fff;cursor:pointer">Abrir</button></form></div>'), 401


def _pagina_otp(token):
    """Pantalla de verificacion por codigo (OTP) de la vista publica."""
    from flask import render_template_string
    return render_template_string("""
<div style="font-family:Arial,sans-serif;max-width:380px;margin:80px auto;text-align:center;color:#202124">
  <h3>Verificacion por correo</h3>
  <p style="color:#5f6368;font-size:14px">Te enviaremos un codigo de 6 digitos al correo
  con el que te compartieron este enlace.</p>
  <button id="otpEnviar" style="padding:10px 20px;border:0;border-radius:6px;background:#1a73e8;color:#fff;cursor:pointer">Enviarme el codigo</button>
  <div id="otpZona" style="display:none;margin-top:14px">
    <input id="otpCodigo" maxlength="6" inputmode="numeric" placeholder="Codigo de 6 digitos"
      style="padding:10px;width:100%;box-sizing:border-box;border:1px solid #dadce0;border-radius:6px;text-align:center;font-size:20px;letter-spacing:6px">
    <button id="otpValidar" style="margin-top:10px;padding:10px 20px;border:0;border-radius:6px;background:#188038;color:#fff;cursor:pointer">Verificar</button>
  </div>
  <p id="otpMsj" style="font-size:13px;color:#5f6368;min-height:18px;margin-top:10px"></p>
<script>
var T={{ token|tojson }};
function msj(t,e){var m=document.getElementById('otpMsj');m.textContent=t;m.style.color=e?'#d93025':'#5f6368';}
document.getElementById('otpEnviar').onclick=async function(){
  msj('Enviando codigo...');
  var r=await fetch('/api/almacen/publico-otp/enviar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:T})});
  var d=await r.json();
  if(d.success){document.getElementById('otpZona').style.display='block';msj('Codigo enviado a '+(d.email_mascara||'tu correo'));}
  else msj(d.error||'No se pudo enviar',true);
};
document.getElementById('otpValidar').onclick=async function(){
  var c=document.getElementById('otpCodigo').value.trim();
  if(c.length!==6){msj('Escribe los 6 digitos',true);return;}
  var r=await fetch('/api/almacen/publico-otp/validar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:T,codigo:c})});
  var d=await r.json();
  if(d.success){msj('Verificado. Abriendo...');location.reload();}
  else msj(d.error||'Codigo incorrecto',true);
};
</script></div>""", token=token), 401


def _fisica_dentro(comp, subruta):
    """Ruta fisica de <compartido>/<subruta>, con contencion contra fugas."""
    import os
    from seguridad_rutas import ruta_fisica, normalizar_ruta_virtual, RutaInvalida
    base = ruta_fisica(comp['propietario_id'], comp['ruta'])
    if not subruta:
        return base, base
    try:
        destino = ruta_fisica(comp['propietario_id'],
                              normalizar_ruta_virtual(comp['ruta'] + '/' + subruta))
    except RutaInvalida:
        return base, None
    if not os.path.realpath(destino).startswith(os.path.realpath(base) + os.sep):
        return base, None
    # «Limitar el acceso» (CO-03): un elemento marcado deja de ser alcanzable a
    # traves del enlace de una carpeta que lo contiene. Se comprueba DESPUES de
    # la contencion de rutas para no cambiar esa garantia.
    try:
        from ajustes_compartir import bloqueado_bajo
        virtual = normalizar_ruta_virtual(comp['ruta'] + '/' + subruta)
        if bloqueado_bajo(comp['propietario_id'], comp['ruta'], virtual):
            return base, None
    except Exception:
        # Ante cualquier fallo del ajuste NO se abre el acceso: se mantiene el
        # comportamiento anterior, que es el permisivo por defecto y ya validado.
        pass
    return base, destino


def _listar(directorio, prefijo):
    """Contenido de una carpeta con los campos que espera la plantilla de la Nube."""
    import os
    items = []
    for nombre in sorted(os.listdir(directorio)):
        if nombre.startswith('.'):
            continue
        completo = os.path.join(directorio, nombre)
        rel = (prefijo + '/' + nombre).lstrip('/') if prefijo else nombre
        es_carpeta = os.path.isdir(completo)
        try:
            tam = 0 if es_carpeta else os.path.getsize(completo)
        except OSError:
            tam = 0
        items.append({
            'nombre': nombre,
            'es_carpeta': es_carpeta,
            'ruta_relativa': rel,
            'extension': '' if es_carpeta else nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else '',
            'size_formateado': '—' if es_carpeta else _tam_humano(tam),
            'tamano': tam,
        })
    return items


def _pagina_pedir_acceso(datos):
    """«Necesitas acceso», con el nombre de quien puede darlo."""
    import json as _json
    import os as _os
    from flask import Response as _Respuesta
    plantilla = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                              'plantillas', 'acceso_denegado.html')
    with open(plantilla, encoding='utf-8') as archivo:
        html = archivo.read()
    correo = ''
    try:
        correo = getattr(current_user, 'email', '') or ''
    except Exception:
        pass
    # El texto se escapa: son nombres de personas y de carpetas.
    from markupsafe import escape as _escapar
    html = (html.replace('{{ propietario }}', str(_escapar(datos['propietario'])))
                .replace('{{ nombre }}', str(_escapar(datos['nombre'])))
                .replace('{{ correo }}', str(_escapar(correo)))
                .replace('{{ ruta_json|safe }}', _json.dumps(datos['ruta'])))
    # 403 y no 200: no se tiene acceso, y así lo dicen también los registros.
    return _Respuesta(html, status=403, mimetype='text/html')


def _pagina_simple(titulo, cuerpo, estado=200):
    """Una página sobria para decir cómo fue. Sin dependencias ni plantillas."""
    from flask import Response as _Respuesta
    html = ("""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s · Drive Maquita</title><style>
:root{color-scheme:light dark}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#f8f9fa;color:#202124;font:14px/1.6 Arial,Helvetica,sans-serif;padding:24px}
.t{background:#fff;border:1px solid #dadce0;border-radius:10px;max-width:460px;width:100%%;
padding:40px;box-shadow:0 1px 4px rgba(60,64,67,.15);text-align:center}
h1{font-size:22px;font-weight:400;margin:0 0 12px}
p{color:#5f6368;margin:0 0 10px}
b{color:#202124}
a.b{display:inline-block;margin-top:20px;background:#1a73e8;color:#fff;text-decoration:none;
padding:10px 22px;border-radius:6px}
a.s{display:inline-block;margin-top:12px;color:#1a73e8;text-decoration:none;font-size:13px}
@media(prefers-color-scheme:dark){body{background:#202124;color:#e8eaed}
.t{background:#2d2d2d;border-color:#4a4a4a}b{color:#e8eaed}a.s{color:#8ab4f8}}
</style></head><body><main class="t">%s</main></body></html>""" % (titulo, cuerpo))
    return _Respuesta(html, status=estado, mimetype='text/html')


@bp_almacen_web.route('/dar-acceso/<clave>')
@login_required
def dar_acceso(clave):
    """Botón «Dar acceso» del correo: concede y avisa a quien lo pidió.

    La clave sirve para encontrar la solicitud; QUIÉN concede se comprueba con
    la sesión: solo el dueño puede darlo. Si llega sin sesión, FARO lo manda al
    login y vuelve aquí.
    """
    import html as _html
    from solicitudes_acceso import conceder, por_clave
    quiere_editar = request.args.get('editar') == '1'

    ok, mensaje, solicitud = conceder(clave, int(current_user.id), quiere_editar)
    if not ok:
        return _pagina_simple('No se pudo dar el acceso',
                              '<h1>No se pudo dar el acceso</h1><p>%s</p>'
                              '<a class="b" href="/archivos-almacen">Ir a mi Drive</a>'
                              % _html.escape(mensaje), 400)

    quien = _html.escape(solicitud.get('nombre_solicitante')
                         or solicitud.get('email_solicitante') or 'esa persona')
    que = _html.escape((solicitud.get('ruta') or '').rstrip('/').rsplit('/', 1)[-1])
    ampliar = ''
    if not quiere_editar:
        ampliar = ('<a class="s" href="/dar-acceso/%s?editar=1">'
                   'Permitir también que edite</a>' % _html.escape(clave))
    return _pagina_simple(
        'Acceso concedido',
        '<h1>Acceso concedido</h1>'
        '<p><b>%s</b> ya puede entrar en <b>%s</b>%s.</p>'
        '<a class="b" href="/archivos-almacen">Ir a mi Drive</a><br>%s'
        % (quien, que, ' y editarlo' if quiere_editar else ' (solo lectura)', ampliar))


@bp_almacen_web.route('/archivos-almacen/solicitar-acceso-interno', methods=['POST'])
@login_required
def solicitar_acceso_interno():
    """Pedir acceso a algo que se abrió por un enlace INTERNO (sin token).

    Se comprueba aquí mismo que de verdad no se tiene acceso: si se tuviera,
    no habría nada que pedir.
    """
    from flask import request as _peticion, jsonify as _json_respuesta
    datos = _peticion.get_json(silent=True) or {}
    ruta = (datos.get('ruta') or '').strip()
    if not ruta:
        return _json_respuesta({'success': False, 'mensaje': 'Falta la ruta.'}), 200
    try:
        from resolver_enlace import resolver as _resolver
        destino = _resolver(int(current_user.id), ruta)
    except Exception as _exc:
        log.warning('Solicitud de acceso interno, al resolver %s: %s', ruta, _exc)
        destino = None
    if not destino or not destino.get('pedir_acceso'):
        return _json_respuesta({'success': False,
                                'mensaje': 'Ya tienes acceso a esto.'}), 200
    ficha = destino['pedir_acceso']
    from solicitudes_acceso import registrar_por_ruta
    ok, mensaje = registrar_por_ruta(
        ficha['propietario_id'], ficha['ruta'],
        getattr(current_user, 'email', ''),
        getattr(current_user, 'full_name', '') or getattr(current_user, 'username', ''),
        datos.get('mensaje'))
    return _json_respuesta({'success': ok, 'mensaje': mensaje}), 200


@bp_almacen_web.route('/solicitar-acceso', methods=['POST'])
def solicitar_acceso():
    """Recibe la solicitud de acceso de quien abrió un enlace que ya no sirve.

    SIN sesión a propósito: quien la usa normalmente no tiene cuenta en FARO.
    La protección es el token del enlace más un límite por correo y hora.
    """
    from flask import request as req, jsonify
    from solicitudes_acceso import registrar
    datos = req.get_json(silent=True) or req.form or {}
    ok, mensaje = registrar(
        (datos.get('token') or '').strip(),
        datos.get('email'),
        datos.get('nombre'),
        datos.get('mensaje'),
    )
    # SIEMPRE 200: FARO tiene un manejador global de errores que sustituye el
    # cuerpo de cualquier 4xx por su página HTML, así que un 400 aquí llegaría
    # al navegador como HTML y el formulario no sabría qué decir. El resultado
    # va en el cuerpo, que es lo que lee la página.
    return jsonify({'success': ok, 'mensaje': mensaje}), 200


# La barra final se acepta a proposito: un enlace pegado en un correo o en un
# documento llega muchas veces como «…/s/TOKEN/» y antes eso daba un 404 seco,
# como si el enlace no existiera (05/08/2026).
@bp_almacen_web.route('/s/<token>')
@bp_almacen_web.route('/s/<token>/')
@bp_almacen_web.route('/s/<token>/<path:subruta>')
def enlace_corto_vista(token, subruta=''):
    """Enlace CORTO de compartir (drive.maquita.com.ec/s/<token>) — redirige a la
    vista real. Así el link que ve la gente es corto y de marca (estilo Drive)."""
    from flask import redirect
    destino = f'/almacen-s/{token}' + (f'/{subruta}' if subruta else '')
    return redirect(destino, 302)


@bp_almacen_web.route('/e/<token>')
def enlace_corto_editar(token):
    """Enlace CORTO de EDICIÓN externa (drive.maquita.com.ec/e/<token>)."""
    from flask import redirect
    return redirect(f'/archivos-almacen/editar-publico?t={token}', 302)


@bp_almacen_web.route('/almacen-s/<token>')
@bp_almacen_web.route('/almacen-s/<token>/')
@bp_almacen_web.route('/almacen-s/<token>/<path:subruta>')
def acceso_compartido(token, subruta=''):
    """Vista publica del enlace: misma interfaz que la Nube (carpeta o archivo)."""
    import os
    from datetime import datetime, timezone
    from urllib.parse import quote
    from flask import render_template, request as req, redirect, send_file, abort
    from almacen_bd import ejecutar

    comp = _compartido(token)
    if not comp:
        return render_template('nextcloud/compartido_error.html',
                               error='Este enlace ya no es válido.',
                               token=token, puede_solicitar=False), 404
    # Enlace dirigido a alguien de la casa: pide sesión y entra a la carpeta de
    # verdad, donde manda su permiso (editor o lector). Antes se abría como
    # invitado y quedaba en solo lectura aunque fuera editor.
    try:
        from enlace_a_sesion import puente_a_sesion
        _puente = puente_a_sesion(comp, subruta)
        if _puente is not None:
            return _puente
    except Exception as _exc_puente:
        log.warning('Puente del enlace a la sesión no aplicado: %s', _exc_puente)
    _rest = _bloqueo_restringido(comp)
    if _rest is not None:
        return _rest
    if comp['expira_en'] is not None and comp['expira_en'] < datetime.now(timezone.utc):
        # Caducado: SÍ sabemos de quién es el archivo, así que se puede pedir acceso.
        return render_template('nextcloud/compartido_error.html',
                               error='Este enlace caducó.',
                               token=token, puede_solicitar=True), 410
    if not _clave_ok(token, comp):
        return _pedir_clave(token)
    # Fase C: OTP por correo en la vista publica + auditoria
    from api_acceso_externo import otp_ok as _otp_fn, registrar_acceso as _reg_acc
    if not _otp_fn(token, comp):
        return _pagina_otp(token)
    if not subruta:
        _reg_acc(comp.get('id'), token, 'abrio_vista', comp.get('email') or '')

    # Compatibilidad con los enlaces viejos: /almacen-s/<token>?f=<archivo>
    if req.args.get('f'):
        return redirect('/almacen-s/%s/archivo/%s' % (token, req.args['f']))

    base, destino = _fisica_dentro(comp, subruta)
    if not destino or not os.path.exists(destino):
        return render_template('nextcloud/compartido_error.html',
                               error='No encontramos ese contenido.',
                               token=token, puede_solicitar=True), 404
    ejecutar("UPDATE compartidos SET accesos = accesos + 1 WHERE token = %s", (token,))

    nombre_raiz = os.path.basename(comp['ruta'].rstrip('/')) or 'Compartido'
    propietario = _propietario_nombre(comp['propietario_id'])

    # --- Archivo suelto -----------------------------------------------------
    if os.path.isfile(destino):
        ext = destino.rsplit('.', 1)[-1].lower() if '.' in destino else ''

        # ── P-13: el enlace se abre COMO eligió quien compartió ──────────────
        # 'ver' / 'editar' → OnlyOffice (el editor público ya decide vista o
        # edición según `puede_editar` del enlace). Vale tanto para el archivo
        # compartido directamente como para uno de dentro de una carpeta
        # compartida, que viaja en `sub` (P-13b). La clave (si el enlace la
        # tiene) ya se validó arriba y se arrastra para que el editor pueda
        # pedir su configuración.
        # Los PDF y las imágenes se quedan en el visor propio del enlace, que ya
        # los muestra bien y es más liviano que levantar OnlyOffice.
        if _va_a_onlyoffice(comp, ext):
            return redirect(_url_editor_publico(token, subruta,
                                                req.args.get('clave')), 302)

        visible = ext == 'pdf' or ext in _EXT_IMAGEN
        if visible:
            share = {
                'token': token,
                'nombre': os.path.basename(destino),
                'nombre_raiz': nombre_raiz,
                'es_carpeta': False,
                'ruta_archivo': subruta,
                'propietario': propietario,
                'puede_editar': False,
            }
            return render_template('nextcloud/compartido_archivo_visor.html',
                                   share=share, base_s='/almacen-s/')
        return _entregar_sin_macros(comp, destino, subruta,
                                    bool(comp['permite_descarga']))

    # --- Carpeta ------------------------------------------------------------
    contenido = _listar(destino, subruta)
    breadcrumb = [{'nombre': nombre_raiz, 'ruta': ''}]
    if subruta:
        acumulada = ''
        for parte in subruta.strip('/').split('/'):
            acumulada = (acumulada + '/' + parte).strip('/')
            breadcrumb.append({'nombre': parte, 'ruta': acumulada})

    share = {
        'token': token,
        'nombre': breadcrumb[-1]['nombre'],
        'nombre_raiz': nombre_raiz,
        'es_carpeta': True,
        'subruta': subruta,
        'contenido': contenido,
        'breadcrumb': breadcrumb,
        'propietario': propietario,
        'permisos': 1,
        'puede_editar': False,
        'puede_crear': False,
        'puede_eliminar': False,
    }
    return render_template('nextcloud/compartido_carpeta.html',
                           share=share, base_s='/almacen-s/',
                           nc_public_url='')


# Las variantes SIN ruta son para cuando el enlace apunta a UN ARCHIVO suelto
# (no a una carpeta): ahí la plantilla del visor arma «…/archivo/» con la parte
# final vacía, porque no hay subruta que poner. Sin estas rutas, Flask no
# emparejaba la petición y devolvía 404: el visor de PDF e imágenes salía en
# blanco y el enlace parecía roto (05/08/2026).
@bp_almacen_web.route('/almacen-s/<token>/archivo/<path:ruta>')
@bp_almacen_web.route('/almacen-s/<token>/ver/<path:ruta>')
@bp_almacen_web.route('/almacen-s/<token>/thumb/<path:ruta>')
def descargar_compartido(token, ruta):
    """Entrega un archivo del enlace: descarga (/archivo), vista (/ver) o miniatura (/thumb)."""
    import os
    from datetime import datetime, timezone
    from flask import send_file, request as req, render_template, abort

    comp = _compartido(token)
    if not comp:
        abort(404)
    _rest = _bloqueo_restringido(comp)
    if _rest is not None:
        return _rest
    if comp['expira_en'] is not None and comp['expira_en'] < datetime.now(timezone.utc):
        abort(410)
    if not _clave_ok(token, comp):
        return _pedir_clave(token)

    base, destino = _fisica_dentro(comp, ruta)
    if not destino or not os.path.isfile(destino):
        abort(404)

    modo = req.path.split('/')[3]  # archivo | ver | thumb
    ext = destino.rsplit('.', 1)[-1].lower() if '.' in destino else ''
    if modo == 'thumb':
        if ext not in _EXT_IMAGEN:
            abort(404)
        return send_file(destino)

    # P-13b: dentro de un enlace de CARPETA compartido en modo «ver»/«editar»,
    # abrir el documento en OnlyOffice en vez de bajarlo. Es la misma decisión
    # que toma la vista del enlace, aquí para los clics de la lista de archivos.
    if _va_a_onlyoffice(comp, ext):
        from flask import redirect
        return redirect(_url_editor_publico(token, ruta, req.args.get('clave')), 302)

    # Política de macros: lo que sale del enlace va sin macro (o no sale). Vale
    # también para /ver/, que si no sería la puerta de atrás para el original.
    adjunto = (modo == 'archivo') and bool(comp['permite_descarga'])
    return _entregar_sin_macros(comp, destino, ruta, adjunto)


@bp_almacen_web.route('/almacen-s/<token>/archivo/',
                      endpoint='compartido_archivo_directo')
def _compartido_archivo_directo(token):
    """El enlace apunta a UN ARCHIVO: la plantilla del visor arma «…/archivo/»
    con la parte final vacía porque no hay subruta. Se atiende aquí con su
    propio endpoint —en vez de un `defaults` compartido— porque con varias
    reglas apuntando a la misma función Flask no sabía cuál era la canónica y
    acababa redirigiendo /archivo/ a /thumb/ (05/08/2026)."""
    return descargar_compartido(token, '')


@bp_almacen_web.route('/almacen-s/<token>/ver/',
                      endpoint='compartido_ver_directo')
def _compartido_ver_directo(token):
    """Igual que la anterior, para la vista previa del visor."""
    return descargar_compartido(token, '')


@bp_almacen_web.route('/almacen-s/<token>/descargar')
def descargar_todo_compartido(token):
    """Descarga la carpeta compartida completa en un ZIP (como en la Nube)."""
    import os
    import zipfile
    from datetime import datetime, timezone
    from flask import send_file, request as req, abort, after_this_request

    comp = _compartido(token)
    if not comp:
        abort(404)
    _rest = _bloqueo_restringido(comp)
    if _rest is not None:
        return _rest
    if comp['expira_en'] is not None and comp['expira_en'] < datetime.now(timezone.utc):
        abort(410)
    if not _clave_ok(token, comp):
        return _pedir_clave(token)
    if not comp['permite_descarga']:
        abort(403)

    base, destino = _fisica_dentro(comp, req.args.get('subruta', ''))
    if not destino or not os.path.isdir(destino):
        abort(404)

    # Limite de cortesia: un ZIP gigante en un worker web es un riesgo para FARO.
    total = 0
    for carpeta, _dirs, archivos in os.walk(destino):
        for nombre in archivos:
            try:
                total += os.path.getsize(os.path.join(carpeta, nombre))
            except OSError:
                pass
    if total > _ZIP_MAXIMO:
        return ('<div style="font-family:Arial;max-width:420px;margin:90px auto;text-align:center">'
                '<h3>Carpeta muy grande</h3><p style="color:#5f6368">Esta carpeta supera el limite '
                'de descarga en un solo ZIP. Abre el enlace y descarga los archivos que necesites.'
                '</p></div>', 413)

    import tempfile
    temporal = tempfile.NamedTemporaryFile(prefix='almacen_zip_', suffix='.zip', delete=False)
    temporal.close()
    # Política de macros dentro del ZIP: cada archivo con macros entra como su
    # COPIA LIMPIA (mismos datos y fórmulas, sin la macro). Los que no se
    # pueden limpiar no entran, y se listan en un aviso dentro del propio ZIP
    # para que quien lo abra sepa qué falta y por qué.
    import compartir_macros
    omitidos = []
    limpiados = []
    with zipfile.ZipFile(temporal.name, 'w', zipfile.ZIP_DEFLATED) as z:
        for carpeta, _dirs, archivos in os.walk(destino):
            for nombre in archivos:
                completo = os.path.join(carpeta, nombre)
                relativo = os.path.relpath(completo, destino)
                if not compartir_macros.con_macros(completo, nombre):
                    z.write(completo, relativo)
                    continue
                virtual = None
                try:
                    from seguridad_rutas import normalizar_ruta_virtual
                    virtual = normalizar_ruta_virtual(
                        comp['ruta'] + '/' + os.path.relpath(completo, base))
                except Exception:
                    virtual = None
                ruta_ok, nombre_ok, tmp = compartir_macros.entrega_segura(
                    completo, nombre, comp['propietario_id'], virtual)
                if not ruta_ok:
                    omitidos.append(relativo)
                    continue
                destino_zip = os.path.join(os.path.dirname(relativo), nombre_ok)
                z.write(ruta_ok, destino_zip)
                limpiados.append(relativo)
                if tmp:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
        if omitidos or limpiados:
            aviso = ['Archivos con macros de la Fundación Maquita', '']
            if limpiados:
                aviso.append('Se incluyeron SIN la macro (conservan datos, '
                             'fórmulas y formato):')
                aviso += ['  - ' + x for x in limpiados] + ['']
            if omitidos:
                aviso.append('NO se incluyeron (no se pudo quitarles la macro). '
                             'Pídelos a quien te compartió el enlace:')
                aviso += ['  - ' + x for x in omitidos]
            z.writestr('LEEME - archivos con macros.txt',
                       '\n'.join(aviso).encode('utf-8'))
    titulo = os.path.basename(destino.rstrip('/')) or 'compartido'

    @after_this_request
    def _borrar(respuesta):
        try:
            os.unlink(temporal.name)
        except OSError:
            pass
        return respuesta

    return send_file(temporal.name, mimetype='application/zip', as_attachment=True,
                     download_name=titulo + '.zip')


def registrar_almacen(app):
    """
    Registra el Almacén dentro de la app FARO. Defensivo: si algo falla, FARO
    sigue funcionando (el Almacén es opcional y de desarrollo).
    """
    try:
        if _DIR_SERVICIO not in sys.path:
            sys.path.insert(0, _DIR_SERVICIO)

        from almacen_bd import asegurar_esquema
        from api_archivos import bp_archivos
        # Desplegable de sugerencias del buscador (respuesta instantánea).
        from api_busqueda_rapida import bp_busqueda_rapida
        from api_compartir import bp_compartir
        from api_extras import bp_extras
        from api_admin import bp_admin
        from api_versiones import bp_versiones
        from api_almacenamiento import bp_almacenamiento
        from api_actividad import bp_actividad
        from api_unidades import bp_unidades
        from api_onlyoffice import bp_onlyoffice, bp_onlyoffice_web
        # Control de macros: estado y descarga de la copia sin macros.
        from api_macros import bp_macros
        # Avisos de menciones en comentarios (campanita de FARO).
        from api_menciones import bp_menciones
        # Conectar equipos al Drive como disco (WebDAV).
        from api_dav import bp_dav
        # Compartir por enlace desde la app de Windows (auth por token DAV).
        from api_dav_compartir import bp_dav_compartir
        # Desconectar el equipo y enviar registros de error (P-03, P-06).
        from api_dav_equipo import bp_dav_equipo
        from api_drawio import bp_drawio, bp_drawio_web
        from api_crear import bp_crear
        from api_oo_drive import bp_oo_drive
        from api_acceso_externo import bp_acceso_externo
        from api_cad import bp_cad, bp_cad_web
        from api_orto import bp_orto
        from api_vinculos import bp_vinculos, asegurar_esquema_vinculos
        from api_monitor import bp_monitor
        from api_encuestas import bp_encuestas, bp_encuestas_web
        # Cuelga sus rutas del mismo bp_encuestas: basta con importarlo ANTES
        # de registrar el blueprint para que queden dentro.
        import api_encuestas_quiz          # noqa: F401
        from api_encuestas_publico import bp_encuestas_publico
        from api_enlace_info import bp_enlace_info
        # Buzón de diagnóstico del editor (temporal, 02/09/2026).
        from api_diagnostico_editor import bp_diag_editor
        from arreglos_editor import registrar as registrar_arreglos_editor
        from encuestas_bd import asegurar_esquema_encuestas

        # Los esquemas se aseguran BEST-EFFORT: si la base de datos esta lenta o
        # caida un instante al arrancar el worker, eso NO debe impedir que se
        # registren las rutas del Almacen. Si se impidiera, /api/almacen*
        # devolveria 404 (HTML) y el explorador se rompe para todos.
        try:
            asegurar_esquema()
            from indice_busqueda import asegurar_esquema_indice
            asegurar_esquema_indice()
            from indice_contenido import asegurar_esquema_contenido
            asegurar_esquema_contenido()
            asegurar_esquema_vinculos()
            asegurar_esquema_encuestas()
        except Exception as _exc_esquema:
            log.error('Almacen: no se pudo asegurar el esquema, se continua igual '
                      'para no dejar la API sin rutas: %s', _exc_esquema)

        # API del motor bajo /api/almacen (NO choca con /api/nextcloud)
        for bp in (bp_archivos, bp_compartir, bp_extras, bp_admin, bp_versiones, bp_almacenamiento, bp_actividad, bp_unidades, bp_onlyoffice, bp_drawio, bp_crear, bp_oo_drive, bp_acceso_externo, bp_cad, bp_orto, bp_vinculos, bp_monitor, bp_macros, bp_menciones, bp_dav, bp_dav_compartir, bp_dav_equipo, bp_encuestas, bp_busqueda_rapida, bp_enlace_info, bp_diag_editor):
            app.register_blueprint(bp, url_prefix='/api/almacen')
        # Página del explorador en modo Almacén
        app.register_blueprint(bp_almacen_web)
        # Los arreglos del editor de hojas valen para CUALQUIER archivo, se abra
        # por donde se abra: el Almacen, su enlace publico, o las tres paginas
        # de la Nube antigua. Por eso se enganchan a la aplicacion, no a una
        # plantilla (01/09/2026).
        registrar_arreglos_editor(app)
        # Las páginas públicas de este blueprint (clave del enlace, código por
        # correo, solicitud de acceso) las usa gente SIN sesión y por tanto sin
        # token CSRF: se rechazaban con un 400 que FARO convierte en su página
        # de error HTML. Su protección es el token del enlace, no la sesión.
        try:
            from flask_wtf.csrf import CSRFProtect  # noqa: F401
            ext = app.extensions.get('csrf')
            if ext:
                ext.exempt(bp_almacen_web)
                # Compartir por token (app de Windows): sin sesión → sin CSRF.
                # Su protección es el token DAV (Basic), no la cookie.
                ext.exempt(bp_dav_compartir)
                ext.exempt(bp_dav_equipo)
        except Exception as _exc:
            log.warning('No se pudo eximir bp_almacen_web de CSRF: %s', _exc)
        # Página del editor OnlyOffice del Almacén (/archivos-almacen/editar)
        app.register_blueprint(bp_onlyoffice_web)
        app.register_blueprint(bp_drawio_web)
        app.register_blueprint(bp_cad_web)
        # Formularios (.forma): el editor va bajo /archivos-almacen (candado),
        # la página para responder vive fuera de los dos prefijos porque la
        # abre gente SIN sesión y su llave es el token del enlace.
        app.register_blueprint(bp_encuestas_web)
        app.register_blueprint(bp_encuestas_publico)
        try:
            _csrf = app.extensions.get('csrf')
            if _csrf:
                _csrf.exempt(bp_encuestas_publico)
                # El buzon de diagnostico del editor lo llama el propio
                # editor por fetch, sin token CSRF. Solo escribe estado
                # tecnico en un registro (temporal, 02/09/2026).
                _csrf.exempt(bp_diag_editor)
        except Exception as _exc_enc:
            log.warning('No se pudo eximir los formularios públicos de CSRF: %s',
                        _exc_enc)

        # Candado: todo /api/almacen* y /archivos-almacen* es SOLO master.
        # Para la API respondemos JSON (nunca HTML) para que el frontend no reviente
        # con "Unexpected token '<'".
        from flask import jsonify

        # Rutas que llama el OnlyOffice Document Server (SIN sesión de usuario):
        # su seguridad es el token firmado (JWT) que valida api_onlyoffice.
        _SIN_SESION_ONLYOFFICE = ('/api/almacen/onlyoffice/download',
                                  '/api/almacen/onlyoffice/callback',
                                  '/api/almacen/onlyoffice/config-public',
                                  '/api/almacen/publico-otp/',
                                  '/api/almacen/publico-info/',
                                  '/api/almacen/publico/')

        # Página web del editor para invitados externos (sin sesión FARO): su
        # seguridad es el token del enlace + clave/expiración (los valida
        # config-public). Debe quedar exenta del candado igual que la API.
        _SIN_SESION_WEB = ('/archivos-almacen/editar-publico', '/solicitar-acceso')

        # Compartir desde la app de Windows: se autentica por token DAV (Basic),
        # no por sesión. El propio endpoint valida el token; por eso queda fuera
        # del candado de sesión (igual que OnlyOffice con su JWT).
        _SIN_SESION_TOKEN = ('/api/almacen/dav/compartir',
                             '/api/almacen/dav/revocar',
                             '/api/almacen/dav/log-cliente',
                             '/api/almacen/dav/uso')

        @app.before_request
        def _candado_almacen():
            ruta = request.path or ''
            if ruta.startswith(_SIN_SESION_ONLYOFFICE):
                return None
            if ruta.startswith(_SIN_SESION_WEB):
                return None
            if ruta.startswith(_SIN_SESION_TOKEN):
                return None
            if ruta.startswith('/api/almacen'):
                if not current_user.is_authenticated:
                    return jsonify({'success': False, 'error': 'No autorizado'}), 403
                # Rutas admin: SOLO master. El resto: master o piloto (defensa en profundidad,
                # aunque cada endpoint admin ya valida master por su cuenta).
                if _es_ruta_admin_almacen(ruta):
                    if not _es_master_actual():
                        return jsonify({'success': False, 'error': 'No autorizado'}), 403
                elif not _acceso_almacen():
                    return jsonify({'success': False, 'error': 'No autorizado'}), 403
            elif ruta.startswith('/archivos-almacen'):
                if not current_user.is_authenticated:
                    # Acceso directo estilo Drive: al login y de VUELTA aquí
                    from flask import redirect as _redir
                    from urllib.parse import quote as _q
                    return _redir('/auth/iniciar-sesion?next=' + _q(request.full_path.rstrip('?') or ruta))
                if not _acceso_almacen():
                    abort(403)

        # Catch-all: cualquier endpoint /api/almacen/* que el motor aún NO implemente
        # responde JSON 404 (no la página HTML de FARO). Los endpoints reales son más
        # específicos y ganan la resolución de ruta; esto solo atrapa lo no implementado.
        def _catchall_almacen(resto):
            return jsonify({'success': False,
                            'error': 'Función aún no disponible en el motor: /' + resto}), 404
        app.add_url_rule('/api/almacen/<path:resto>', 'almacen_api_catchall',
                         _catchall_almacen,
                         methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])

        app.logger.info('[Almacén] Puente de desarrollo montado (/api/almacen, /archivos-almacen) — solo master')
        return True
    except Exception as excepcion:
        app.logger.warning(f'[Almacén] No se pudo montar el puente de desarrollo: {excepcion}')
        return False
