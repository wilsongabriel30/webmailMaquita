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
(_permiso_unidad + _efectivo + ruta_fisica).

Sin límite de tamaño y reanudable (2026-09-28): el ZIP ya no se arma en /tmp,
se envía en flujo y, si la descarga se corta, el navegador la continúa desde
donde quedó (zip_reanudable.py). Antes había un tope de 2 GB.
"""
import logging
import os
import tempfile
import time

from flask import jsonify, request

import api_archivos as _api
import zip_reanudable
import zip_reanudable_plan
from seguridad_rutas import RutaInvalida, ruta_fisica

log = logging.getLogger('almacen.api.zip')

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


def _pares_virtuales(resueltas):
    """[(ruta_virtual, fisica)] de los ARCHIVOS que entran al ZIP —también
    los de dentro de las carpetas—, para poder pedirle al editor que guarde
    los que alguien tenga abiertos antes de empaquetarlos."""
    pares = []
    for ruta, fisica in resueltas:
        if os.path.isfile(fisica):
            pares.append((ruta, fisica))
            continue
        for carpeta, _dirs, archivos in os.walk(fisica):
            rel = os.path.relpath(carpeta, fisica)
            for nombre in archivos:
                completo = os.path.join(carpeta, nombre)
                virtual = os.path.normpath(
                    os.path.join(ruta, rel, nombre)).replace(os.sep, '/')
                pares.append((virtual, completo))
    return pares


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

    nombre = _nombre_zip(resueltas)

    if request.args.get('comprobar') == '1':
        entradas, total = _inventario(resueltas)
        return jsonify({'success': True, 'nombre': nombre, 'total_bytes': total,
                        'archivos': sum(1 for _r, f in entradas if f)})

    # (2026-09-04) Lo que esté abierto en el editor se guarda ANTES de
    # empaquetar; si no, el ZIP se llevaría la versión anterior. Al REANUDAR
    # no: cambiaría los archivos y la descarga tendría que empezar de nuevo.
    if not request.headers.get('Range'):
        try:
            import guardado_forzado
            guardado_forzado.guardar_lote(usuario, _pares_virtuales(resueltas))
        except Exception:
            pass

    entradas, total = _inventario(resueltas)
    try:
        plan = zip_reanudable_plan.obtener(zip_reanudable_plan.firma_de(entradas),
                                           lambda: _construir(entradas))
    except Exception:
        log.exception('descargar-zip: fallo preparando %s para usuario %s', nombre, usuario)
        return _api.error('No se pudo preparar el ZIP', 500)

    token = _token_seguro(request.args.get('token', ''))
    _limpiar_progresos_viejos()
    progreso = _Progreso(token, plan.total)

    def _al_cerrar():
        # Cancelada o fallida: el aviso desaparece. Si terminó bien, el
        # archivo de progreso queda con listo=true para que la tarjeta lo vea.
        if not progreso.listo:
            progreso.limpiar()

    log.info('descargar-zip: usuario %s, %d elementos, %d bytes → %s',
             usuario, len(resueltas), total, nombre)
    respuesta = zip_reanudable.respuesta(
        plan, nombre, al_avanzar=progreso.avanzar,
        al_terminar=progreso.terminar, al_cerrar=_al_cerrar)
    # La tarjeta del explorador vigila esta cookie para saber que el ZIP ya
    # está saliendo (el navegador no avisa cuando una navegación pasa a ser
    # descarga). Con el envío en flujo llega enseguida.
    if token:
        respuesta.set_cookie('almacen_descarga_' + token, '1', max_age=120,
                             path='/', samesite='Lax', secure=True)
    return respuesta


def _copia_compatible(fisica):
    """Las hojas salen con las listas y los colores en forma clásica, para
    que se vean fuera del Drive. Devuelve un temporal o None."""
    try:
        import compatibilidad_xlsx
        return compatibilidad_xlsx.copia_compatible(fisica)
    except Exception:
        return None


def _construir(entradas):
    """Lo que entra al ZIP, para el plan: (entradas, temporales). Las hojas
    que necesitan traducción entran como su copia compatible, con la fecha
    del original; las copias pasan a ser del plan."""
    try:
        from compatibilidad_xlsx import EXTENSIONES
    except Exception:
        EXTENSIONES = ()
    hojas = [f for _r, f in entradas if f and EXTENSIONES and f.lower().endswith(EXTENSIONES)]
    copias = dict(zip(hojas, zip_reanudable_plan.en_paralelo(_copia_compatible, hojas)))
    crudas, temporales = [], []
    for ruta_zip, fisica in entradas:
        copia = copias.get(fisica) if fisica else None
        if copia:
            temporales.append(copia)
            crudas.append((copia, ruta_zip, int(_fecha(fisica))))
        else:
            crudas.append((fisica, ruta_zip))
    return crudas, temporales


def _fecha(fisica):
    try:
        return os.path.getmtime(fisica)
    except OSError:
        return time.time()


def _token_seguro(token):
    token = (token or '')[:40]
    return token if token.isalnum() else ''


# ── progreso del armado (porcentaje en la tarjeta del explorador) ────────────
# Cada worker de gunicorn es un proceso distinto: el que envía el ZIP y el que
# atiende la consulta de progreso pueden no ser el mismo. Por eso el avance se
# escribe en un archivo pequeño en /tmp identificado por el token del cliente.
_DIR_PROGRESO = tempfile.gettempdir()
_PROGRESO_VIDA = 3600          # segundos sin cambios para darlo por abandonado


def _limpiar_progresos_viejos():
    ahora = time.time()
    try:
        nombres = os.listdir(_DIR_PROGRESO)
    except OSError:
        return
    for nombre in nombres:
        if not nombre.startswith('almacen_zip_progreso_'):
            continue
        ruta = os.path.join(_DIR_PROGRESO, nombre)
        try:
            if ahora - os.path.getmtime(ruta) > _PROGRESO_VIDA:
                os.unlink(ruta)
        except OSError:
            pass


def _archivo_progreso(token):
    return os.path.join(_DIR_PROGRESO, 'almacen_zip_progreso_%s.json' % token)


class _Progreso:
    """Lleva bytes procesados / total y lo vuelca a disco como mucho 4 veces
    por segundo (para no castigar el NFS ni el disco con miles de escrituras)."""

    def __init__(self, token, total):
        self.token = token
        self.total = max(total, 1)
        self.hechos = 0
        self.listo = False
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
        self.listo = True
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
