# -*- coding: utf-8 -*-
"""
«Publicar en la web» — una hoja de cálculo como página ligera (Drive Maquita)
============================================================================
Como el «Publicar en la web» de Google Sheets: un enlace público que enseña
los DATOS de la hoja en una página HTML sencilla, sin abrir el editor, y que
siempre refleja la versión actual del archivo (se genera al pedirla, con una
caché por fecha de modificación).

Por qué una página propia y no el editor en solo lectura (que ya existe con
«Compartir → enlace»): el editor pesa varios MB y hace decenas de peticiones.
Para quien consulta desde el campo, con ADSL o satélite, eso no carga (regla
de sitios para conexiones lentas). Esta página es una sola petición, sin
recursos externos, y pesa lo que pesen los datos.

Lo que muestra: valores calculados (como los guardó el editor), negrita,
cursiva, colores de letra y relleno, alineación, celdas combinadas y anchos
de columna. Filas y columnas ocultas no salen. Las imágenes y los gráficos no
se muestran. También se puede bajar la hoja en CSV.

Autoría: Equipo de Tecnología Maquita — 2026-09-23
"""
import csv
import datetime as dt
import html
import io
import logging
import os
import secrets
import threading
from collections import OrderedDict

import openpyxl
from openpyxl.utils import get_column_letter

import almacen_bd as bd

log = logging.getLogger('almacen.publicar_web')

MAX_FILAS = 3000
MAX_COLUMNAS = 80
_esquema_listo = False
_cache = OrderedDict()          # (fisica, mtime, hoja, formato) → bytes
_cache_lock = threading.Lock()
_CACHE_MAX = 24


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
def asegurar_esquema():
    global _esquema_listo
    if _esquema_listo:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS publicaciones_web (
            id          SERIAL PRIMARY KEY,
            token       TEXT UNIQUE NOT NULL,
            usuario_id  INTEGER NOT NULL,
            ruta        TEXT NOT NULL,
            hoja        TEXT,                 -- NULL = todas las hojas visibles
            creado_por  INTEGER,
            creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            vistas      INTEGER NOT NULL DEFAULT 0,
            activo      BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS ix_publicaciones_ruta
            ON publicaciones_web(ruta) WHERE activo;
    """)
    _esquema_listo = True


def publicar(usuario, ruta, hoja, creado_por):
    """Crea la publicación (o devuelve la que ya hay para esa ruta y hoja)."""
    asegurar_esquema()
    filas = bd.consultar(
        'SELECT * FROM publicaciones_web WHERE activo AND ruta = %s '
        'AND usuario_id = %s AND hoja IS NOT DISTINCT FROM %s', (ruta, usuario, hoja))
    if filas:
        return dict(filas[0])
    return dict(bd.ejecutar(
        'INSERT INTO publicaciones_web (token, usuario_id, ruta, hoja, creado_por) '
        'VALUES (%s, %s, %s, %s, %s) RETURNING *',
        (secrets.token_urlsafe(18), usuario, ruta, hoja, creado_por)))


def de_ruta(usuario, ruta):
    asegurar_esquema()
    return [dict(f) for f in bd.consultar(
        'SELECT * FROM publicaciones_web WHERE activo AND ruta = %s AND usuario_id = %s '
        'ORDER BY id', (ruta, usuario))]


def por_token(token):
    asegurar_esquema()
    filas = bd.consultar('SELECT * FROM publicaciones_web WHERE activo AND token = %s',
                         (token,))
    return dict(filas[0]) if filas else None


def despublicar(publicacion_id):
    bd.ejecutar('UPDATE publicaciones_web SET activo = FALSE WHERE id = %s',
                (int(publicacion_id),))


def contar_vista(publicacion_id):
    try:
        bd.ejecutar('UPDATE publicaciones_web SET vistas = vistas + 1 WHERE id = %s',
                    (int(publicacion_id),))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Formato de los valores (es-EC: coma decimal, punto de miles)
# ---------------------------------------------------------------------------
def _decimales(formato):
    if not formato or formato == 'General':
        return None
    parte = formato.split(';')[0]
    if '.' not in parte:
        return 0
    return len([c for c in parte.split('.', 1)[1] if c in '0#'])


def _numero(valor, decimales, miles):
    texto = ('{:,.%df}' % decimales).format(valor) if miles else ('%.*f' % (decimales, valor))
    return texto.replace(',', '\0').replace('.', ',').replace('\0', '.')


def texto_de(celda):
    valor = celda.value
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return 'VERDADERO' if valor else 'FALSO'
    formato = celda.number_format or 'General'
    if isinstance(valor, dt.datetime):
        if valor.time() == dt.time(0, 0) and not any(x in formato.lower() for x in ('h', 's')):
            return valor.strftime('%d/%m/%Y')
        return valor.strftime('%d/%m/%Y %H:%M')
    if isinstance(valor, dt.date):
        return valor.strftime('%d/%m/%Y')
    if isinstance(valor, dt.time):
        return valor.strftime('%H:%M')
    if isinstance(valor, (int, float)):
        if '%' in formato:
            return _numero(valor * 100, _decimales(formato.replace('%', '')) or 0, False) + ' %'
        decimales = _decimales(formato)
        if decimales is None:
            if isinstance(valor, float) and not valor.is_integer():
                return ('%.10g' % valor).replace('.', ',')
            return str(int(valor)) if isinstance(valor, float) else str(valor)
        texto = _numero(valor, decimales, ',' in formato.split(';')[0])
        if '$' in formato:
            texto = '$ ' + texto
        return texto
    return str(valor)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def _color(c):
    """#rrggbb de un color de openpyxl (directo o de la paleta indexada)."""
    try:
        if c is None:
            return None
        if c.type == 'rgb' and isinstance(c.rgb, str) and len(c.rgb) == 8 \
                and c.rgb != '00000000':
            return '#' + c.rgb[2:]
        # El editor guarda a veces el color como índice de paleta (amarillo = 5).
        if c.type == 'indexed' and c.indexed is not None and c.indexed < 64:
            from openpyxl.styles.colors import COLOR_INDEX
            return '#' + COLOR_INDEX[c.indexed][2:]
    except Exception:
        pass
    return None


def _estilo(celda):
    reglas = []
    f = celda.font
    if f is not None:
        if f.b:
            reglas.append('font-weight:bold')
        if f.i:
            reglas.append('font-style:italic')
        if f.u:
            reglas.append('text-decoration:underline')
        col = _color(f.color)
        if col and col.upper() != '#000000':
            reglas.append('color:' + col)
        if f.sz and float(f.sz) >= 13:
            reglas.append('font-size:%dpx' % round(float(f.sz) * 1.33))
    rel = celda.fill
    if rel is not None and rel.fill_type == 'solid':
        col = _color(rel.fgColor)
        if col and col.upper() != '#FFFFFF':
            reglas.append('background:' + col)
            # Sobre un fondo de color, texto oscuro aunque la página esté en modo oscuro.
            if not any(r.startswith('color:') for r in reglas):
                reglas.append('color:#202124')
    al = celda.alignment
    if al is not None:
        if al.horizontal in ('center', 'centerContinuous'):
            reglas.append('text-align:center')
        elif al.horizontal == 'right':
            reglas.append('text-align:right')
        if al.wrap_text:
            reglas.append('white-space:normal')
    if isinstance(celda.value, (int, float)) and not isinstance(celda.value, bool) \
            and not (al is not None and al.horizontal):
        reglas.append('text-align:right')
    return ';'.join(reglas)


def hojas_visibles(libro, solo=None):
    visibles = [ws for ws in libro.worksheets if ws.sheet_state == 'visible']
    if solo:
        visibles = [ws for ws in visibles if ws.title == solo]
    return visibles


def _tabla(ws):
    """(html de la tabla, recortada?) de una hoja."""
    max_f = min(ws.max_row or 0, MAX_FILAS)
    max_c = min(ws.max_column or 0, MAX_COLUMNAS)
    recortada = (ws.max_row or 0) > MAX_FILAS or (ws.max_column or 0) > MAX_COLUMNAS
    # Quitar filas y columnas vacías del final (el «max» suele incluir formato suelto).
    filas = [list(f) for f in ws.iter_rows(min_row=1, max_row=max_f, max_col=max_c)]
    while filas and all(c.value is None for c in filas[-1]):
        filas.pop()
    if not filas:
        return '<p class="vacio">Esta hoja está vacía.</p>', False
    ultima_c = max((i + 1 for f in filas for i, c in enumerate(f) if c.value is not None), default=1)

    ocultas_c = {i for i in range(1, ultima_c + 1)
                 if ws.column_dimensions[get_column_letter(i)].hidden}
    combinadas, tapadas = {}, set()
    for rango in ws.merged_cells.ranges:
        combinadas[(rango.min_row, rango.min_col)] = (rango.max_row - rango.min_row + 1,
                                                       rango.max_col - rango.min_col + 1)
        for r in range(rango.min_row, rango.max_row + 1):
            for c in range(rango.min_col, rango.max_col + 1):
                if (r, c) != (rango.min_row, rango.min_col):
                    tapadas.add((r, c))

    clases, css = {}, []

    def clase(estilo):
        if not estilo:
            return ''
        if estilo not in clases:
            clases[estilo] = 'e%d' % len(clases)
            css.append('.%s{%s}' % (clases[estilo], estilo))
        return ' class="%s"' % clases[estilo]

    anchos = []
    for i in range(1, ultima_c + 1):
        if i in ocultas_c:
            continue
        ancho = ws.column_dimensions[get_column_letter(i)].width
        anchos.append('<col style="width:%dpx">' % max(40, min(420, round((ancho or 10) * 7.5))))
    partes = ['<table><colgroup>%s</colgroup>' % ''.join(anchos)]
    for n, fila in enumerate(filas, start=1):
        if ws.row_dimensions[n].hidden:
            continue
        celdas = []
        for i, celda in enumerate(fila[:ultima_c], start=1):
            if i in ocultas_c or (n, i) in tapadas:
                continue
            extra = ''
            if (n, i) in combinadas:
                alto, ancho = combinadas[(n, i)]
                if alto > 1:
                    extra += ' rowspan="%d"' % alto
                if ancho > 1:
                    extra += ' colspan="%d"' % len([c for c in range(i, i + ancho) if c not in ocultas_c])
            celdas.append('<td%s%s>%s</td>' % (clase(_estilo(celda)), extra,
                                                html.escape(texto_de(celda))))
        partes.append('<tr>%s</tr>' % ''.join(celdas))
    partes.append('</table>')
    return '<style>%s</style>%s' % (''.join(css), ''.join(partes)), recortada


_PAGINA = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{titulo}</title>
<style>
:root{{--fondo:#fff;--texto:#202124;--suave:#5f6368;--borde:#e0e3e7;--acento:#0061a1;--pest:#f1f3f4}}
@media (prefers-color-scheme:dark){{:root{{--fondo:#1f1f1f;--texto:#e8eaed;--suave:#9aa0a6;--borde:#3c4043;--acento:#8ab4f8;--pest:#2d2e30}}}}
body{{margin:0;background:var(--fondo);color:var(--texto);font:14px/1.35 Arial,Helvetica,sans-serif}}
header{{padding:12px 16px 0}}h1{{font-size:18px;margin:0 0 4px;word-break:break-word}}
.meta{{color:var(--suave);font-size:12px;margin-bottom:8px}}.meta a{{color:var(--acento)}}
nav{{display:flex;gap:4px;overflow-x:auto;padding:0 16px;border-bottom:1px solid var(--borde)}}
nav a{{padding:7px 12px;border-radius:6px 6px 0 0;color:var(--texto);text-decoration:none;white-space:nowrap;background:var(--pest)}}
nav a.activa{{background:var(--acento);color:#fff}}
main{{overflow:auto;padding:8px 16px 24px;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;table-layout:fixed}}
td{{border:1px solid var(--borde);padding:3px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;vertical-align:bottom}}
.vacio,.aviso{{color:var(--suave)}}
</style></head><body>
<header><h1>{titulo}</h1>
<div class="meta">Actualizado: {fecha} · <a href="?{csv}">Descargar CSV</a>{aviso}</div></header>
{pestanas}
<main>{tabla}</main>
</body></html>"""


def _leer(fisica):
    return openpyxl.load_workbook(fisica, data_only=True)


def render(fisica, nombre, solo_hoja, indice, formato='html'):
    """Bytes de la página (o del CSV). Con caché por fecha de modificación."""
    mtime = os.path.getmtime(fisica)
    clave = (fisica, mtime, solo_hoja, indice, formato)
    with _cache_lock:
        if clave in _cache:
            _cache.move_to_end(clave)
            return _cache[clave]
    libro = _leer(fisica)
    try:
        hojas = hojas_visibles(libro, solo_hoja)
        if not hojas:
            raise LookupError('La hoja publicada ya no existe en el archivo')
        try:
            indice = int(indice or 0)
        except (TypeError, ValueError):
            indice = 0
        indice = max(0, min(indice, len(hojas) - 1))
        ws = hojas[indice]
        if formato == 'csv':
            salida = io.StringIO()
            escritor = csv.writer(salida)
            for fila in ws.iter_rows(max_row=min(ws.max_row or 0, 100000),
                                     max_col=min(ws.max_column or 0, 500)):
                escritor.writerow([texto_de(c) for c in fila])
            datos = ('﻿' + salida.getvalue()).encode('utf-8')
        else:
            tabla, recortada = _tabla(ws)
            pestanas = ''
            if len(hojas) > 1:
                pestanas = '<nav>%s</nav>' % ''.join(
                    '<a href="?h=%d"%s>%s</a>' % (i, ' class="activa"' if i == indice else '',
                                                  html.escape(h.title))
                    for i, h in enumerate(hojas))
            aviso = (' · <span class="aviso">Se muestran las primeras %d filas y %d columnas.</span>'
                     % (MAX_FILAS, MAX_COLUMNAS)) if recortada else ''
            titulo = nombre.rsplit('.', 1)[0] + ('' if len(hojas) == 1 and solo_hoja is None
                                                 else ' — ' + ws.title)
            datos = _PAGINA.format(
                titulo=html.escape(titulo),
                fecha=dt.datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M'),
                csv='h=%d&formato=csv' % indice, aviso=aviso,
                pestanas=pestanas, tabla=tabla).encode('utf-8')
    finally:
        libro.close()
    with _cache_lock:
        _cache[clave] = datos
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return datos
