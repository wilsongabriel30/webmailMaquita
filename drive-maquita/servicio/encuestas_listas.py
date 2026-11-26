"""Formularios del Almacén — pregunta «Lista desde archivo», con cascada (Fase 1, paso 2b, 10/11/2026).

Para listas que no caben a mano (comunidades, parroquias, productores): un CSV o
Excel del Drive de quien arma el formulario, como el `select_one_from_file` de
ODK. La pregunta dice:
  · lista_ruta     el archivo, ruta del Drive del dueño (p. ej. /Catalogos/dpa.csv)
  · lista_columna  la columna de la que se elige
  · lista_filtros  [{columna, pregunta}]: la cascada. Solo se ofrecen las filas
                   cuya `columna` es igual a lo respondido en `pregunta` (su nombre).
                   Provincia → Cantón → Parroquia → Comunidad.

El archivo se lee una vez y queda en memoria hasta que cambia en disco. Quien
responde nunca recibe el archivo: pide sugerencias (como mucho LIMITE_SUGERENCIAS)
y el servidor comprueba al recibir que lo elegido existe con esos filtros.
"""
import csv
import io
import os
import re
import threading
import unicodedata

FILAS_MAX = 100000
BYTES_MAX = 20 * 1024 * 1024
COLUMNAS_MAX = 60
LIMITE_SUGERENCIAS = 50
FILTROS_MAX = 6
EXTENSIONES = ('.csv', '.txt', '.xlsx')

_cache = {}
_candado = threading.Lock()


class ListaNoDisponible(ValueError):
    pass


def _plano(texto):
    return re.sub(r'<[^>]+>', '', texto or '').strip()[:80]


def normal(texto):
    """Para comparar y buscar sin tildes ni mayúsculas."""
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', t).strip().lower()


def _texto(valor, maximo):
    return valor.strip()[:maximo] if isinstance(valor, str) else ''


# ---------------------------------------------------------------------------
# Configuración en la definición
# ---------------------------------------------------------------------------
def completar(pregunta, bruto):
    ruta = _texto(bruto.get('lista_ruta'), 500)
    pregunta['lista_ruta'] = ruta if ruta.lower().endswith(EXTENSIONES) and '..' not in ruta else ''
    pregunta['lista_columna'] = _texto(bruto.get('lista_columna'), 100)
    filtros = []
    for f in (bruto.get('lista_filtros') or [])[:FILTROS_MAX]:
        if isinstance(f, dict):
            col, preg = _texto(f.get('columna'), 100), _texto(f.get('pregunta'), 64)
            if col and preg:
                filtros.append({'columna': col, 'pregunta': preg})
    pregunta['lista_filtros'] = filtros
    return pregunta


def referencias(pregunta):
    return [f['pregunta'] for f in pregunta.get('lista_filtros') or []]


# ---------------------------------------------------------------------------
# Lectura del archivo
# ---------------------------------------------------------------------------
def _leer_csv(crudo):
    texto = crudo.decode('utf-8-sig', errors='replace')
    muestra = texto[:5000]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=',;\t|')
    except csv.Error:
        dialecto = csv.excel
    return list(csv.reader(io.StringIO(texto), dialecto))


def _leer_xlsx(fisica):
    import openpyxl
    libro = openpyxl.load_workbook(fisica, read_only=True, data_only=True)
    try:
        hoja = libro.worksheets[0]
        return [['' if c is None else (str(int(c)) if isinstance(c, float) and c.is_integer() else str(c))
                 for c in fila] for fila in hoja.iter_rows(values_only=True)]
    finally:
        libro.close()


def cargar(fisica):
    """{'columnas': [...], 'filas': [[...]], 'normales': [[...]]} del archivo, con caché por fecha."""
    try:
        estado = os.stat(fisica)
    except OSError:
        raise ListaNoDisponible('El archivo de la lista no existe.')
    if estado.st_size > BYTES_MAX:
        raise ListaNoDisponible('El archivo de la lista pasa de 20 MB.')
    clave = (fisica, estado.st_mtime_ns, estado.st_size)
    with _candado:
        if clave in _cache:
            return _cache[clave]
    if fisica.lower().endswith('.xlsx'):
        filas = _leer_xlsx(fisica)
    else:
        with open(fisica, 'rb') as f:
            filas = _leer_csv(f.read())
    filas = [f for f in filas if any(str(c).strip() for c in f)]
    if not filas:
        raise ListaNoDisponible('El archivo de la lista está vacío.')
    columnas = [str(c).strip()[:100] for c in filas[0][:COLUMNAS_MAX]]
    cuerpo = [[str(c).strip() for c in (f + [''] * len(columnas))[:len(columnas)]]
              for f in filas[1:FILAS_MAX + 1]]
    datos = {'columnas': columnas, 'filas': cuerpo,
             'normales': [[normal(c) for c in f] for f in cuerpo]}
    with _candado:
        for k in [k for k in _cache if k[0] == fisica]:
            del _cache[k]
        _cache[clave] = datos
    return datos


def _fisica(propietario, ruta):
    from seguridad_rutas import ruta_fisica
    try:
        return ruta_fisica(int(propietario), ruta)
    except Exception:
        raise ListaNoDisponible('El archivo de la lista no está en el Drive.')


def datos_de(pregunta, propietario):
    if not pregunta.get('lista_ruta') or not pregunta.get('lista_columna'):
        raise ListaNoDisponible('La lista no tiene archivo o columna elegidos.')
    datos = cargar(_fisica(propietario, pregunta['lista_ruta']))
    if pregunta['lista_columna'] not in datos['columnas']:
        raise ListaNoDisponible(f'El archivo ya no tiene la columna «{pregunta["lista_columna"]}».')
    return datos


def opciones(pregunta, propietario, padres, buscar='', limite=LIMITE_SUGERENCIAS):
    """Valores distintos de la columna con los filtros de la cascada.

    `padres`: {nombre_pregunta: valor respondido}. Si falta algún padre, no hay
    opciones (primero se elige la provincia, luego el cantón)."""
    datos = datos_de(pregunta, propietario)
    cols = datos['columnas']
    i = cols.index(pregunta['lista_columna'])
    condiciones = []
    for f in pregunta.get('lista_filtros') or []:
        if f['columna'] not in cols:
            raise ListaNoDisponible(f'El archivo ya no tiene la columna «{f["columna"]}».')
        valor = padres.get(f['pregunta'])
        if valor in (None, ''):
            return [], True
        condiciones.append((cols.index(f['columna']), normal(valor)))
    q = normal(buscar)
    vistos, salida, completo = set(), [], True
    for fila, nfila in zip(datos['filas'], datos['normales']):
        if not fila[i] or any(nfila[c] != v for c, v in condiciones):
            continue
        if q and q not in nfila[i]:
            continue
        if nfila[i] in vistos:
            continue
        vistos.add(nfila[i])
        if len(salida) >= limite:
            completo = False
            break
        salida.append(fila[i])
    if q:      # lo que empieza por lo buscado, primero
        salida.sort(key=lambda v: (not normal(v).startswith(q), normal(v)))
    return salida, completo


def valor_limpio(pregunta, bruto, padres, propietario):
    """(valor, error). Lo elegido tiene que existir en el archivo con los filtros."""
    if bruto is None or not str(bruto).strip():
        return None, None
    texto = str(bruto).strip()[:300]
    titulo = _plano(pregunta.get('titulo'))
    try:
        encontrados, _ = opciones(pregunta, propietario, padres, texto, limite=FILAS_MAX)
    except ListaNoDisponible as e:
        return None, f'«{titulo}»: {e}'
    for v in encontrados:
        if normal(v) == normal(texto):
            return v, None
    return None, f'«{titulo}»: «{texto}» no está en la lista' + (
        ' para lo elegido antes.' if pregunta.get('lista_filtros') else '.')
