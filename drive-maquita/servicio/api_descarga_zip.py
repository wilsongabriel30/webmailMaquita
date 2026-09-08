"""
Descarga de CARPETAS y de VARIOS elementos como un solo ZIP (Drive Maquita).

Por qué existe: «Descargar» sobre una carpeta llamaba a /archivos/descargar,
que solo entrega archivos, y el navegador terminaba en una página con el JSON
{"error": "Archivo no encontrado"} (reportado 2026-09-03). En Google Drive una
carpeta se baja como ZIP; aquí igual.

Rutas (montadas sobre bp_archivos, mismo prefijo /api/almacen):
  GET /archivos/descargar-zip?ruta=A&ruta=B[&comprobar=1]
    - comprobar=1 → JSON {success, nombre, total_bytes, archivos} sin generar
      nada. El explorador lo usa ANTES de navegar, para avisar con un diálogo
      en vez de mandar al usuario a una página de texto.
    - sin comprobar → el ZIP como adjunto.

Permisos: cada ruta pedida pasa por la misma validación que /archivos/descargar
(_permiso_unidad + _efectivo + ruta_fisica). Límite: _ZIP_MAXIMO (2 GB), el
mismo del ZIP de enlaces compartidos en integracion_faro.
"""
import logging
import os
import tempfile
import zipfile

from flask import after_this_request, jsonify, request, send_file

import api_archivos as _api
from seguridad_rutas import RutaInvalida, ruta_fisica

log = logging.getLogger('almacen.api.zip')

ZIP_MAXIMO = 2 * 1024 ** 3   # 2 GB por descarga (igual que integracion_faro)


def _resolver(usuario, rutas):
    """Devuelve [(ruta_virtual, fisica)] o lanza ValueError/PermissionError."""
    resueltas = []
    for ruta in rutas:
        ruta = (ruta or '').strip()
        if not ruta:
            continue
        if not _api._permiso_unidad(usuario, ruta, escritura=False):
            raise PermissionError('No tienes acceso a «%s»' % os.path.basename(ruta))
        usuario_ef, ruta_ef = _api._efectivo(usuario, ruta)
        fisica = ruta_fisica(usuario_ef, ruta_ef)
        if not os.path.exists(fisica):
            raise FileNotFoundError('No se encontró «%s»' % os.path.basename(ruta))
        resueltas.append((ruta, fisica))
    if not resueltas:
        raise ValueError('No se indicó qué descargar')
    return resueltas


def _inventario(resueltas):
    """[(ruta_en_zip, fisica)] de todo lo que entra, más el total de bytes."""
    entradas = []
    total = 0
    for ruta, fisica in resueltas:
        base = os.path.basename(fisica.rstrip('/')) or 'archivo'
        if os.path.isfile(fisica):
            entradas.append((base, fisica))
            total += _tamano(fisica)
            continue
        for carpeta, _dirs, archivos in os.walk(fisica):
            rel_carpeta = os.path.relpath(carpeta, fisica)
            if not archivos and not _dirs:
                # carpeta vacía: que aparezca en el ZIP igual que en el Drive
                entradas.append((os.path.join(base, rel_carpeta).rstrip('/.') + '/', None))
            for nombre in archivos:
                completo = os.path.join(carpeta, nombre)
                if not os.path.isfile(completo):
                    continue
                entradas.append((os.path.normpath(os.path.join(base, rel_carpeta, nombre)), completo))
                total += _tamano(completo)
    return entradas, total


def _tamano(fisica):
    try:
        return os.path.getsize(fisica)
    except OSError:
        return 0


def _nombre_zip(resueltas):
    if len(resueltas) == 1:
        return (os.path.basename(resueltas[0][1].rstrip('/')) or 'descarga') + '.zip'
    return 'Drive Maquita - %d elementos.zip' % len(resueltas)


@_api.bp_archivos.route('/archivos/descargar-zip', methods=['GET'])
def descargar_zip():
    usuario = _api.usuario_actual()
    try:
        resueltas = _resolver(usuario, request.args.getlist('ruta'))
    except PermissionError as excepcion:
        return _api.error(str(excepcion), 403)
    except FileNotFoundError as excepcion:
        return _api.error(str(excepcion), 404)
    except (ValueError, RutaInvalida) as excepcion:
        return _api.error(str(excepcion), 400)

    entradas, total = _inventario(resueltas)
    nombre = _nombre_zip(resueltas)
    if total > ZIP_MAXIMO:
        return _api.error('La descarga supera el límite de 2 GB por ZIP. '
                          'Entra en la carpeta y descarga por partes.', 413)

    if request.args.get('comprobar') == '1':
        return jsonify({'success': True, 'nombre': nombre, 'total_bytes': total,
                        'archivos': sum(1 for _r, f in entradas if f)})

    token = _token_seguro(request.args.get('token', ''))
    progreso = _Progreso(token, total)
    temporal = tempfile.NamedTemporaryFile(prefix='almacen_zip_', suffix='.zip', delete=False)
    temporal.close()
    try:
        with zipfile.ZipFile(temporal.name, 'w', zipfile.ZIP_DEFLATED) as z:
            for ruta_zip, fisica in entradas:
                if fisica is None:
                    z.writestr(ruta_zip, b'')
                else:
                    _agregar_por_bloques(z, fisica, ruta_zip, progreso)
        progreso.terminar()
    except Exception:
        log.exception('descargar-zip: fallo armando %s para usuario %s', nombre, usuario)
        progreso.limpiar()
        try:
            os.unlink(temporal.name)
        except OSError:
            pass
        return _api.error('No se pudo preparar el ZIP', 500)

    @after_this_request
    def _borrar(respuesta):
        try:
            os.unlink(temporal.name)
        except OSError:
            pass
        progreso.limpiar()
        return respuesta

    log.info('descargar-zip: usuario %s, %d elementos, %d bytes → %s',
             usuario, len(resueltas), total, nombre)
    respuesta = send_file(temporal.name, mimetype='application/zip',
                          as_attachment=True, download_name=nombre)
    # Aviso «preparando la descarga» del explorador: el navegador no avisa
    # cuando una navegación empieza a descargar, así que el cliente manda un
    # token y vigila esta cookie para saber que el ZIP ya está saliendo.
    if token:
        respuesta.set_cookie('almacen_descarga_' + token, '1', max_age=120,
                             path='/', samesite='Lax', secure=True)
    return respuesta


def _token_seguro(token):
    token = (token or '')[:40]
    return token if token.isalnum() else ''


# ── progreso del armado (porcentaje en la tarjeta del explorador) ────────────
# Cada worker de gunicorn es un proceso distinto: el que arma el ZIP y el que
# atiende la consulta de progreso pueden no ser el mismo. Por eso el avance se
# escribe en un archivo pequeño en /tmp identificado por el token del cliente.
_BLOQUE = 1024 * 1024          # 1 MB por escritura al ZIP
_DIR_PROGRESO = tempfile.gettempdir()


def _archivo_progreso(token):
    return os.path.join(_DIR_PROGRESO, 'almacen_zip_progreso_%s.json' % token)


class _Progreso:
    """Lleva bytes procesados / total y lo vuelca a disco como mucho 4 veces
    por segundo (para no castigar el NFS ni el disco con miles de escrituras)."""

    def __init__(self, token, total):
        import time
        self.token = token
        self.total = max(total, 1)
        self.hechos = 0
        self._ultimo = 0.0
        self._reloj = time.monotonic
        if token:
            self._escribir(forzar=True)

    def avanzar(self, n):
        self.hechos += n
        if self.token:
            self._escribir()

    def terminar(self):
        self.hechos = self.total
        if self.token:
            self._escribir(forzar=True, listo=True)

    def _escribir(self, forzar=False, listo=False):
        ahora = self._reloj()
        if not forzar and ahora - self._ultimo < 0.25:
            return
        self._ultimo = ahora
        import json
        datos = {'hechos': self.hechos, 'total': self.total,
                 'porcentaje': min(100, int(self.hechos * 100 / self.total)),
                 'listo': listo}
        ruta = _archivo_progreso(self.token)
        try:
            with open(ruta + '.tmp', 'w') as f:
                json.dump(datos, f)
            os.replace(ruta + '.tmp', ruta)   # atómico: nunca se lee a medias
        except OSError:
            pass

    def limpiar(self):
        if not self.token:
            return
        for sufijo in ('', '.tmp'):
            try:
                os.unlink(_archivo_progreso(self.token) + sufijo)
            except OSError:
                pass


def _agregar_por_bloques(z, fisica, ruta_zip, progreso):
    """Como z.write(), pero avisando el avance cada bloque: así el porcentaje
    también se mueve dentro de un archivo grande (un video de 800 MB)."""
    info = zipfile.ZipInfo.from_file(fisica, ruta_zip)
    info.compress_type = zipfile.ZIP_DEFLATED
    with open(fisica, 'rb') as origen, z.open(info, 'w') as destino:
        while True:
            bloque = origen.read(_BLOQUE)
            if not bloque:
                break
            destino.write(bloque)
            progreso.avanzar(len(bloque))


@_api.bp_archivos.route('/archivos/descargar-zip/progreso', methods=['GET'])
def progreso_zip():
    """GET /archivos/descargar-zip/progreso?token= → {success, porcentaje, hechos, total, listo}.
    Solo lee el archivo de su propio token; sin token válido no devuelve nada."""
    import json
    _api.usuario_actual()
    token = _token_seguro(request.args.get('token', ''))
    if not token:
        return _api.error('Token inválido', 400)
    try:
        with open(_archivo_progreso(token)) as f:
            datos = json.load(f)
    except (OSError, ValueError):
        # aún no empezó (o ya terminó y se limpió): el cliente lo trata como 0 %
        return jsonify({'success': True, 'porcentaje': 0, 'hechos': 0, 'total': 0,
                        'listo': False, 'sin_datos': True})
    datos['success'] = True
    return jsonify(datos)
