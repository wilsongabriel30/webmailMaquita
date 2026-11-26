"""Formularios del Almacén — pregunta «Repetición» (Fase 1, paso 2b, 10/11/2026).

Un grupo de preguntas que se responde varias veces: los miembros del hogar, las
parcelas, los cultivos. Como el `begin repeat` de ODK, pero dentro de UNA
pregunta, para no tocar el resto del modelo.

  campos         subpreguntas: texto_corto, numero, cedula, opcion_unica,
                 desplegable, casillas, fecha (cada una con su `nombre`)
  rep_min/max    cuántas filas se piden / admiten
  rep_etiqueta   cómo se llama cada fila («Miembro», «Parcela»)

La respuesta es una lista de filas `[{id_subpregunta: valor}]`. En las reglas,
`${miembros}` es la lista de filas (count(${miembros}) = cuántas) y
`${edad}` —el nombre de una subpregunta— es la columna entera
(sum(${edad}), max(${edad})).
"""
import re
import uuid

SUBTIPOS = ('texto_corto', 'numero', 'cedula', 'opcion_unica', 'desplegable', 'casillas', 'fecha')
CON_OPCIONES = ('opcion_unica', 'desplegable', 'casillas')
CAMPOS_MAX = 30
FILAS_MAX = 200
FILAS_DEFECTO = 20
OPCIONES_MAX = 1000
TEXTO_MAX = 2000
_UUID = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
_NOMBRE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
_FECHA = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _plano(texto, maximo=300):
    return re.sub(r'<[^>]+>', '', texto or '').strip()[:maximo] if isinstance(texto, str) else ''


def _entero(valor, defecto, minimo, maximo):
    try:
        return min(max(int(valor), minimo), maximo)
    except (TypeError, ValueError):
        return defecto


def _campo(bruto):
    import encuestas_tipos_campo as tipos_campo
    if not isinstance(bruto, dict) or bruto.get('tipo') not in SUBTIPOS:
        return None
    ident = bruto.get('id') if isinstance(bruto.get('id'), str) and _UUID.match(bruto['id']) else str(uuid.uuid4())
    nombre = bruto.get('nombre').strip() if isinstance(bruto.get('nombre'), str) else ''
    campo = {'id': ident, 'nombre': nombre if _NOMBRE.match(nombre) else None, 'tipo': bruto['tipo'],
             'titulo': _plano(bruto.get('titulo')) or 'Pregunta sin título',
             'obligatoria': bool(bruto.get('obligatoria'))}
    if campo['tipo'] in CON_OPCIONES:
        opciones, vistos = [], set()
        for o in (bruto.get('opciones') or [])[:OPCIONES_MAX]:
            t = _plano(o, 300) if isinstance(o, str) else ''
            if t and t not in vistos:
                vistos.add(t)
                opciones.append(t)
        campo['opciones'] = opciones or ['Opción 1']
    if campo['tipo'] in ('numero', 'cedula'):
        tipos_campo.completar(campo, bruto)
    return campo


def completar(pregunta, bruto):
    campos = []
    for c in (bruto.get('campos') or [])[:CAMPOS_MAX]:
        limpio = _campo(c)
        if limpio:
            campos.append(limpio)
    if not campos:
        campos = [{'id': str(uuid.uuid4()), 'nombre': None, 'tipo': 'texto_corto',
                   'titulo': 'Nombre', 'obligatoria': True}]
    pregunta['campos'] = campos
    pregunta['rep_max'] = _entero(bruto.get('rep_max'), FILAS_DEFECTO, 1, FILAS_MAX)
    pregunta['rep_min'] = _entero(bruto.get('rep_min'), 0, 0, pregunta['rep_max'])
    pregunta['rep_etiqueta'] = _plano(bruto.get('rep_etiqueta'), 40) or 'Registro'
    return pregunta


def _vacio(v):
    return v is None or v == '' or v == []


def _sub_valor(campo, bruto, etiqueta):
    """(valor, error) de una subpregunta en una fila."""
    import encuestas_tipos_campo as tipos_campo
    if _vacio(bruto) or (isinstance(bruto, str) and not bruto.strip()):
        return None, None
    tipo, titulo = campo['tipo'], campo['titulo']
    if tipo in ('numero', 'cedula'):
        valor, error = tipos_campo.valor_limpio(campo, bruto)
        return valor, (f'{etiqueta}: {error}' if error else None)
    if tipo == 'casillas':
        lista = bruto if isinstance(bruto, list) else [bruto]
        malas = [v for v in lista if v not in campo['opciones']]
        if malas:
            return None, f'{etiqueta}: «{malas[0]}» no es una opción de «{titulo}».'
        return [v for v in campo['opciones'] if v in lista] or None, None
    if tipo in ('opcion_unica', 'desplegable'):
        if bruto not in campo['opciones']:
            return None, f'{etiqueta}: «{bruto}» no es una opción de «{titulo}».'
        return bruto, None
    if tipo == 'fecha':
        t = str(bruto).strip()
        return (t, None) if _FECHA.match(t) else (None, f'{etiqueta}: «{titulo}» no es una fecha válida.')
    return str(bruto).strip()[:TEXTO_MAX], None


def valor_limpio(pregunta, bruto):
    """(filas, error). Las filas en blanco se descartan."""
    titulo = _plano(pregunta.get('titulo'), 80)
    if bruto is None or bruto == []:
        filas_brutas = []
    elif isinstance(bruto, list):
        filas_brutas = bruto
    else:
        return None, f'«{titulo}»: la respuesta no tiene la forma esperada.'
    if len(filas_brutas) > pregunta['rep_max']:
        return None, f'«{titulo}» admite como mucho {pregunta["rep_max"]}.'
    filas = []
    for n, fila in enumerate(filas_brutas, 1):
        if not isinstance(fila, dict):
            continue
        etiqueta = f'«{titulo}», {pregunta["rep_etiqueta"]} {n}'
        limpia = {}
        for campo in pregunta['campos']:
            valor, error = _sub_valor(campo, fila.get(campo['id']), etiqueta)
            if error:
                return None, error
            if valor is not None:
                limpia[campo['id']] = valor
        if not limpia:
            continue
        for campo in pregunta['campos']:
            if campo['obligatoria'] and campo['id'] not in limpia:
                return None, f'{etiqueta}: falta «{campo["titulo"]}».'
        filas.append(limpia)
    if filas and len(filas) < pregunta['rep_min']:
        return None, f'«{titulo}» pide al menos {pregunta["rep_min"]}.'
    return (filas or None), None


def valores_para_reglas(pregunta, filas):
    """{nombre: valor} que la repetición aporta a las reglas: las filas y cada columna."""
    filas = filas if isinstance(filas, list) else []
    # Las filas en blanco no cuentan, igual que al guardar.
    filas = [f for f in filas if isinstance(f, dict) and any(not _vacio(v) and v != '' for v in f.values())]
    salida = {}
    if pregunta.get('nombre'):
        salida[pregunta['nombre']] = [{c['nombre'] or c['id']: f.get(c['id']) for c in pregunta['campos']}
                                      for f in filas]
    for c in pregunta['campos']:
        if c.get('nombre'):
            columna = [f.get(c['id']) for f in filas]
            if c['tipo'] == 'numero':
                import encuestas_tipos_campo as tipos_campo
                columna = [tipos_campo.a_numero(v) if isinstance(v, str) else v for v in columna]
            salida[c['nombre']] = columna
    return salida


def texto(pregunta, filas):
    if not isinstance(filas, list):
        return ''
    partes = []
    for n, fila in enumerate(filas, 1):
        datos = []
        for c in pregunta.get('campos') or []:
            v = fila.get(c['id']) if isinstance(fila, dict) else None
            if v in (None, '', []):
                continue
            datos.append(f'{c["titulo"]}: {", ".join(map(str, v)) if isinstance(v, list) else v}')
        partes.append(f'{pregunta.get("rep_etiqueta") or "Registro"} {n} — ' + ' · '.join(datos))
    return ' | '.join(partes)
