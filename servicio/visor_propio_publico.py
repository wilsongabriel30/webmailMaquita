"""Los PDF y las imágenes de un enlace público se ven en el visor propio del Drive (14/10/2026).

El Drive muestra los PDF con PDF.js (/static/pdfjs) y las imágenes tal cual, en la vista
pública /almacen-s/<token>. Los enlaces de edición (/e/<token> y
/archivos-almacen/editar-publico?t=) los mandaban a OnlyOffice aunque fueran un PDF o una
imagen. Este módulo los redirige a la vista propia. Nunca lanza: si algo falla, el enlace
sigue su camino de siempre.
"""

from urllib.parse import quote, urlencode

from flask import redirect, request

EXT_VISOR_PROPIO = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}


def redireccion_visor_propio(token):
    """Redirección a /almacen-s/<token>[/<sub>] si el enlace es de un PDF o una imagen; si no, None."""
    try:
        if not token:
            return None
        from enlaces_siguen_archivo import reparar_por_token
        reparar_por_token(token)
        from almacen_bd import consultar
        filas = consultar('SELECT ruta FROM compartidos WHERE token = %s', (token,))
        if not filas:
            return None
        sub = (request.args.get('sub') or '').strip('/')
        nombre = (sub or filas[0]['ruta']).rstrip('/').rsplit('/', 1)[-1]
        extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
        if extension not in EXT_VISOR_PROPIO:
            return None
        destino = '/almacen-s/' + quote(token, safe='') + ('/' + quote(sub) if sub else '')
        if request.args.get('clave'):
            destino += '?' + urlencode({'clave': request.args['clave']})
        return redirect(destino, 302)
    except Exception:
        return None
