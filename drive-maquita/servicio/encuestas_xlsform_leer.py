"""Formularios del Almacén — lectura de un XLSForm (Excel de ODK y Kobo) (Fase 1, paso 6, 10/11/2026).

Solo LEE el Excel y lo deja en estructuras simples; qué pregunta sale de cada
fila lo decide `encuestas_importar_xlsform.py`.

  · Hojas `survey`, `choices` y `settings` (sin importar mayúsculas).
  · Columnas con idioma (`label::Español (es)`): se usa el idioma por omisión de
    `settings`, si no la columna sin idioma, y si no la primera que haya.
  · Alias habituales: `calculate`/`calculation`, `relevance`/`relevant`,
    `constraint message`/`constraint_message`, `list name`/`list_name`.
  · Los números que Excel guarda como 3.0 vuelven a ser «3» (nombres de opción).
"""
import io
import re

import openpyxl

TAMANO_MAX = 10 * 1024 * 1024      # un XLSForm normal pesa decenas de KB
FILAS_MAX = 5000

_ALIAS = {
    'calculate': 'calculation', 'relevance': 'relevant', 'constraint message': 'constraint_message',
    'constraint_msg': 'constraint_message', 'jr:constraintmsg': 'constraint_message',
    'list name': 'list_name', 'choice filter': 'choice_filter', 'repeat count': 'repeat_count',
    'required message': 'required_message', 'jr:requiredmsg': 'required_message',
    'read only': 'read_only', 'readonly': 'read_only', 'media::image': 'media_image', 'image': 'media_image',
}
_CON_IDIOMA = ('label', 'hint', 'constraint_message', 'required_message', 'media_image')


class XLSFormInvalido(ValueError):
    pass


def _celda(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _columna(nombre):
    """('label', 'Español (es)') / ('type', None)."""
    texto = re.sub(r'\s+', ' ', _celda(nombre)).strip()
    base, _, idioma = texto.partition('::')
    base = base.strip().lower()
    base = _ALIAS.get(base, base)
    return base, (idioma.strip() or None)


def _hoja(libro, nombre):
    for h in libro.sheetnames:
        if h.strip().lower() == nombre:
            return libro[h]
    return None


def _filas(hoja):
    """[(número de fila en Excel, {columna: texto})], con las columnas por idioma."""
    if hoja is None:
        return [], set()
    filas = list(hoja.iter_rows(values_only=True))
    if not filas:
        return [], set()
    if len(filas) > FILAS_MAX:
        raise XLSFormInvalido(f'La hoja «{hoja.title}» tiene {len(filas)} filas; el máximo es {FILAS_MAX}.')
    cabecera = [_columna(c) for c in filas[0]]
    idiomas = {i for _, i in cabecera if i}
    salida = []
    for numero, fila in enumerate(filas[1:], start=2):
        d = {}
        for (base, idioma), valor in zip(cabecera, fila):
            if not base:
                continue
            clave = f'{base}::{idioma}' if idioma else base
            texto = _celda(valor)
            if texto and not d.get(clave):
                d[clave] = texto
        if any(d.values()):
            salida.append((numero, d))
    return salida, idiomas


def _elegir_idioma(idiomas, por_defecto):
    if not idiomas:
        return None
    if por_defecto:
        for i in idiomas:
            if i == por_defecto or i.lower().startswith(por_defecto.lower()):
                return i
    for i in sorted(idiomas):
        if 'es' in i.lower() or 'españ' in i.lower():
            return i
    return sorted(idiomas)[0]


def _con_idioma(fila, idioma):
    """La fila con `label`, `hint`… ya resueltos al idioma elegido."""
    d = {k: v for k, v in fila.items() if '::' not in k}
    for base in _CON_IDIOMA:
        valor = fila.get(f'{base}::{idioma}') if idioma else None
        if not valor:
            valor = fila.get(base)
        if not valor:
            valor = next((v for k, v in fila.items() if k.startswith(base + '::') and v), '')
        d[base] = valor or ''
    return d


def leer(contenido):
    """{'survey': [(fila, {...})], 'choices': {lista: [(nombre, etiqueta)]}, 'settings': {...}}."""
    if not contenido:
        raise XLSFormInvalido('El archivo está vacío.')
    if len(contenido) > TAMANO_MAX:
        raise XLSFormInvalido('El archivo pasa de 10 MB: no parece un XLSForm.')
    try:
        libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        raise XLSFormInvalido('No se pudo abrir el archivo: tiene que ser un Excel (.xlsx) de ODK o Kobo.')
    try:
        survey, idiomas = _filas(_hoja(libro, 'survey'))
        if not survey:
            raise XLSFormInvalido('El Excel no tiene la hoja «survey» (o está vacía): no es un XLSForm.')
        ajustes_filas, _ = _filas(_hoja(libro, 'settings'))
        settings = ajustes_filas[0][1] if ajustes_filas else {}
        opciones_filas, idiomas_op = _filas(_hoja(libro, 'choices'))
    finally:
        libro.close()
    idioma = _elegir_idioma(idiomas | idiomas_op, settings.get('default_language'))
    choices = {}
    for _, fila in opciones_filas:
        fila = _con_idioma(fila, idioma)
        lista, nombre = fila.get('list_name', ''), fila.get('name', '')
        if lista and nombre:
            choices.setdefault(lista, []).append((nombre, fila.get('label') or nombre))
    return {
        'survey': [(n, _con_idioma(f, idioma)) for n, f in survey],
        'choices': choices,
        'settings': settings,
        'idioma': idioma,
    }
