"""
ZIP reanudable en flujo (Drive Maquita): se envía mientras se lee, sin tocar
el disco, y si la descarga se corta continúa desde donde quedó.

Sustituye a zip_en_flujo.py (28/09/2026). Aquel comprimía sobre la marcha: el
tamaño final no se conocía, el navegador no podía mostrar cuánto faltaba y un
corte obligaba a empezar de cero — justo lo que más castiga a quien descarga
por ADSL rural o satélite. Aquí nada se comprime (casi todo lo que hay en el
Drive ya viene comprimido: PDF, Office, fotos, vídeo), así que:
  - se anuncia el tamaño exacto (Content-Length): el navegador muestra el
    avance y el tiempo restante;
  - se acepta «dame desde el byte N» (Range): el navegador reanuda solo;
  - el ETag asegura que lo que se continúa es el mismo ZIP; si algo cambió en
    la carpeta, la descarga empieza de nuevo en vez de entregar un ZIP roto.

Uso:
    plan = zip_reanudable_plan.obtener(firma, construir)
    return zip_reanudable.respuesta(plan, 'Carpeta.zip')
"""
import bisect
import logging
import zlib
from urllib.parse import quote

from flask import Response, request

import zip_reanudable_plan as planes
from compartido_medios import _en_hilo
from zip_reanudable_formato import cierre

log = logging.getLogger('almacen.zip_reanudable')

_BLOQUE = 4 * 1024 * 1024   # 4 MB por lectura


def _rango(total, etag):
    """(inicio, fin, parcial) con fin exclusivo; None si el rango pedido no
    existe. Sin Range válido —o si el ZIP ya no es el mismo— va completo."""
    completo = (0, total, False)
    pedido = (request.headers.get('Range') or '').strip()
    if not pedido.startswith('bytes=') or ',' in pedido:
        return completo
    condicion = (request.headers.get('If-Range') or '').strip()
    if condicion and condicion != etag:
        return completo
    desde, _, hasta = pedido[6:].partition('-')
    try:
        if desde.strip() == '':
            inicio, fin = max(total - int(hasta), 0), total
        else:
            inicio = int(desde)
            fin = int(hasta) + 1 if hasta.strip() else total
    except ValueError:
        return completo
    fin = min(fin, total)
    if inicio < 0 or inicio >= fin:
        return None
    return inicio, fin, True


def _trozo(datos, base, inicio, fin):
    """La parte de `datos` (que empieza en el byte `base` del ZIP) que cae
    dentro de [inicio, fin)."""
    a = max(inicio - base, 0)
    b = min(fin - base, len(datos))
    return datos[a:b] if a < b else b''


def _leer(archivo, cantidad, crc):
    """Solo disco y CPU: apto para tpool."""
    bloque = archivo.read(cantidad)
    if crc is not None and bloque:
        crc = zlib.crc32(bloque, crc)
    return bloque, crc


def _datos(entrada, desde, hasta):
    """Bytes [desde, hasta) del contenido. Devuelve el CRC si se envió el
    contenido entero (si no, None)."""
    if entrada.tipo == 'm':
        yield entrada.memoria[desde:hasta]
        return None
    entero = desde == 0 and hasta == entrada.tam
    crc = 0 if entero else None
    falta = hasta - desde
    with open(entrada.origen, 'rb') as archivo:
        if desde:
            archivo.seek(desde)
        while falta:
            bloque, crc = _en_hilo(_leer, archivo, min(_BLOQUE, falta), crc)
            if not bloque:
                raise IOError('cambió durante la descarga: %s' % entrada.origen)
            falta -= len(bloque)
            yield bloque
    return crc


def generar(plan, inicio, fin, al_avanzar=None, al_terminar=None, al_cerrar=None):
    """Generador con los bytes [inicio, fin) del ZIP."""
    entradas = plan.entradas
    conocidos = planes.crcs_guardados(plan.etag)

    def crc_de(indice):
        entrada = entradas[indice]
        if entrada.crc is not None:
            return entrada.crc
        if indice not in conocidos:
            conocidos[indice] = _en_hilo(planes.crc_de, entrada.origen, entrada.tam)
            planes.guardar_crc(plan.etag, indice, conocidos[indice])
        return conocidos[indice]

    def salida(datos):
        if al_avanzar:
            al_avanzar(len(datos))
        return datos

    try:
        if inicio < plan.inicio_central:
            posiciones = [e.desplazamiento for e in entradas]
            primero = max(bisect.bisect_right(posiciones, inicio) - 1, 0)
            for indice in range(primero, len(entradas)):
                entrada = entradas[indice]
                if entrada.desplazamiento >= fin:
                    break
                base = entrada.desplazamiento
                parte = _trozo(entrada.cabecera(), base, inicio, fin)
                if parte:
                    yield salida(parte)
                base += entrada.largo_cabecera()
                desde = max(inicio - base, 0)
                hasta = min(fin - base, entrada.tam)
                if desde < hasta:
                    lector = _datos(entrada, desde, hasta)
                    while True:
                        try:
                            yield salida(next(lector))
                        except StopIteration as final:
                            if final.value is not None and entrada.crc is None:
                                conocidos[indice] = final.value
                                planes.guardar_crc(plan.etag, indice, final.value)
                            break
                base += entrada.tam
                if entrada.con_descriptor and base < fin and base + entrada.largo_descriptor() > inicio:
                    parte = _trozo(entrada.descriptor(crc_de(indice)), base, inicio, fin)
                    if parte:
                        yield salida(parte)

        base = plan.inicio_central
        if fin > base:
            acumulado = []
            for indice, entrada in enumerate(entradas):
                largo = entrada.largo_central()
                if base < fin and base + largo > inicio:
                    acumulado.append(_trozo(entrada.central(crc_de(indice)), base, inicio, fin))
                    if sum(len(x) for x in acumulado) >= _BLOQUE:
                        yield salida(b''.join(acumulado))
                        acumulado = []
                base += largo
            acumulado.append(_trozo(cierre(len(entradas), plan.inicio_central, plan.tam_central),
                                    base, inicio, fin))
            resto = b''.join(acumulado)
            if resto:
                yield salida(resto)
        if al_terminar and fin == plan.total:
            al_terminar()
    except GeneratorExit:
        log.info('zip reanudable: descarga interrumpida por el cliente')
        raise
    except Exception:
        log.exception('zip reanudable: fallo a mitad del envío')
        raise
    finally:
        if al_cerrar:
            try:
                al_cerrar()
            except Exception:
                log.exception('zip reanudable: fallo en la limpieza')


def _disposicion(nombre):
    """Content-Disposition con el nombre en UTF-8 (tildes, eñes) y una
    alternativa ASCII para navegadores antiguos."""
    simple = nombre.encode('ascii', 'ignore').decode().replace('"', '').replace('\\', '')
    return 'attachment; filename="%s"; filename*=UTF-8\'\'%s' % (
        simple.strip() or 'descarga.zip', quote(nombre))


def respuesta(plan, nombre, al_avanzar=None, al_terminar=None, al_cerrar=None):
    """Respuesta Flask: 200 con el ZIP entero o 206 con el tramo pedido."""
    rango = _rango(plan.total, plan.etag)
    if rango is None:
        resp = Response(status=416)
        resp.headers['Content-Range'] = 'bytes */%d' % plan.total
        return resp
    inicio, fin, parcial = rango
    if inicio and al_avanzar:
        al_avanzar(inicio)      # lo ya descargado cuenta en el porcentaje
    resp = Response(generar(plan, inicio, fin, al_avanzar, al_terminar, al_cerrar),
                    status=206 if parcial else 200, mimetype='application/zip')
    resp.headers['Content-Length'] = str(fin - inicio)
    if parcial:
        resp.headers['Content-Range'] = 'bytes %d-%d/%d' % (inicio, fin - 1, plan.total)
    resp.headers['Accept-Ranges'] = 'bytes'
    resp.headers['ETag'] = plan.etag
    resp.headers['Content-Disposition'] = _disposicion(nombre)
    resp.headers['Cache-Control'] = 'private, no-cache'
    # nginx no debe acumular el ZIP: el envío sigue el ritmo de quien descarga
    # (también con satélite o ADSL) y el porcentaje refleja lo que ya salió.
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp
