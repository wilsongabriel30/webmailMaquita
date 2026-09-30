# -*- coding: utf-8 -*-
"""
Formularios del Almacén — pregunta «Colaborador», enlazada con nómina
====================================================================
Quien responde elige a una persona de la nómina y sus datos de trabajo (cargo,
departamento, ciudad…) se rellenan solos: «cuando elija a Gissela Jaya, que me
salga en qué departamento trabaja» (28/09/2026).

Cómo se guarda
--------------
La respuesta es una FOTO de ese momento, tomada por el servidor:

    {"id": 62, "nombre": "GISSELA FERNANDA JAYA SANTIANA",
     "cargo": "Analista de…", "departamento": "Planificación y Procesos", …}

Del navegador solo se cree el `id`: todo lo demás se lee de nómina al recibir la
respuesta. Si la persona cambia después de departamento, las respuestas ya
dadas conservan el que tenía.

En la hoja de cálculo cada dato ocupa SU columna («Colaborador»,
«Colaborador · Cargo»…): `desplegar` convierte la pregunta en varias columnas.

Qué NO sale nunca de aquí: cédula, sueldo, teléfonos, domicilio, banco, salud.
La lista de campos es cerrada (`CAMPOS`) y la consulta solo pide esas columnas.

Solo personal ACTIVO y en su versión vigente. La lista se guarda 5 minutos en
memoria: son ~125 personas y se pregunta en cada tecla del buscador.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging
import re
import time
import unicodedata

log = logging.getLogger('almacen.encuestas.colaboradores')

TIPO = 'colaborador'

# Clave → nombre visible. El orden es el de las columnas de la hoja.
CAMPOS = (
    ('cargo', 'Cargo'),
    ('departamento', 'Departamento'),
    ('area', 'Área'),
    ('sucursal', 'Sucursal'),
    ('ciudad', 'Ciudad'),
    ('centro_costo', 'Centro de costo'),
    ('empresa', 'Empresa'),
)
ETIQUETAS = dict(CAMPOS)
CLAVES = tuple(c for c, _ in CAMPOS)

SEPARADOR_ID = '::'          # id de las columnas desplegadas: «<pregunta>::cargo»
MINIMO_LETRAS = 2
LIMITE_RESULTADOS = 20
SEGUNDOS_MEMORIA = 300

_SQL = """
    SELECT t.id,
           trim(coalesce(t.nombres, '') || ' ' || coalesce(t.apellidos, '')) AS nombre,
           c.nombre  AS cargo,
           d.nombre  AS departamento,
           d.area_general AS area,
           s.nombre  AS sucursal,
           coalesce(nullif(trim(s.ciudad), ''), initcap(t.canton_laboral)) AS ciudad,
           cc.nombre AS centro_costo,
           t.empresa_social AS empresa
      FROM trabajadores t
      LEFT JOIN cargos c                ON c.id = t.cargo_id
      LEFT JOIN departamentos_empresa d ON d.id = t.departamento_id
      LEFT JOIN sucursales s            ON s.id = t.sucursal_id
      LEFT JOIN centros_costo cc        ON cc.id = t.centro_costo_id
     WHERE coalesce(t.es_version_actual, TRUE)
       AND t.estado = 'Activo'
     ORDER BY 2
"""

_memoria = {'hasta': 0, 'lista': []}


def _plano(texto):
    sin = unicodedata.normalize('NFKD', str(texto or ''))
    sin = ''.join(c for c in sin if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sin).strip().lower()


def _todos():
    """El personal activo, con lo justo. Nunca lanza: sin nómina, lista vacía."""
    if _memoria['hasta'] > time.time():
        return _memoria['lista']
    try:
        import almacen_bd as bd
        lista = []
        for fila in bd.consultar(_SQL, nomina=True):
            ficha = {'id': int(fila['id']), 'nombre': fila['nombre'] or ''}
            for clave in CLAVES:
                ficha[clave] = (fila.get(clave) or '').strip()
            ficha['_buscar'] = _plano(ficha['nombre'])
            lista.append(ficha)
        _memoria.update(hasta=time.time() + SEGUNDOS_MEMORIA, lista=lista)
    except Exception as excepcion:
        log.warning('no se pudo leer la nómina: %s', excepcion)
        return _memoria['lista']
    return _memoria['lista']


def buscar(texto, limite=LIMITE_RESULTADOS):
    """Personas cuyo nombre contiene TODAS las palabras escritas (sin tildes ni
    mayúsculas). Devuelve nombre y cargo: el cargo distingue a dos tocayas.
    Primero quien empieza su nombre por lo escrito, luego quien tiene otro
    nombre o apellido que empieza así, y al final quien solo lo contiene."""
    palabras = _plano(texto).split()
    if sum(len(p) for p in palabras) < MINIMO_LETRAS:
        return []
    encontradas = []
    for ficha in _todos():
        trozos, puntos = ficha['_buscar'].split(), 0
        for palabra in palabras:
            if trozos and trozos[0].startswith(palabra):
                puntos += 3
            elif any(t.startswith(palabra) for t in trozos):
                puntos += 2
            elif palabra in ficha['_buscar']:
                puntos += 1
            else:
                puntos = 0
                break
        if puntos:
            encontradas.append((-puntos, ficha['nombre'], ficha))
    encontradas.sort(key=lambda e: e[:2])
    return [{'id': f['id'], 'nombre': f['nombre'], 'cargo': f['cargo']}
            for _, _, f in encontradas[:limite]]


def lista():
    """Todo el personal activo con lo mínimo (id, nombre, cargo). La página la
    pide UNA vez y sugiere al instante mientras se escribe, sin una petición
    por tecla: importa en conexiones lentas (28/09/2026)."""
    return [{'id': f['id'], 'nombre': f['nombre'], 'cargo': f['cargo']}
            for f in _todos()]


def uno(trabajador_id):
    try:
        buscado = int(trabajador_id)
    except (TypeError, ValueError):
        return None
    return next((f for f in _todos() if f['id'] == buscado), None)


# ── la pregunta ──────────────────────────────────────────────────────────
def campos_validos(bruto):
    """Los campos elegidos, en el orden de CAMPOS. Sin la clave (una pregunta
    recién creada), todos."""
    if not isinstance(bruto, list):
        return list(CLAVES)
    return [c for c in CLAVES if c in bruto]


def campos_de(pregunta):
    return campos_validos((pregunta or {}).get('colaborador_campos'))


# Textos que quien arma el formulario puede cambiar (28/09/2026): el del campo
# de búsqueda, la nota de debajo y el nombre visible de cada dato.
LARGO_BUSCAR, LARGO_NOTA, LARGO_ETIQUETA = 120, 300, 60


def completar(pregunta, bruto, recortar):
    """Deja en `pregunta` lo propio de este tipo, saneado. `recortar(texto,
    largo)` es el limpiador de textos del modelo."""
    pregunta['colaborador_campos'] = campos_validos(bruto.get('colaborador_campos'))
    # Una sola respuesta por colaborador (28/09/2026). Activado salvo que se
    # diga lo contrario: quien responde ES el colaborador, y sin este límite la
    # misma persona puede aparecer dos veces.
    pregunta['colaborador_unica'] = bruto.get('colaborador_unica') is not False
    pregunta['colaborador_buscar'] = recortar(bruto.get('colaborador_buscar'), LARGO_BUSCAR)
    # La nota distingue «no se ha tocado» (None: se escribe sola, con los datos
    # elegidos) de «se dejó vacía a propósito» (''): no se muestra.
    nota = bruto.get('colaborador_nota')
    pregunta['colaborador_nota'] = None if nota is None else recortar(nota, LARGO_NOTA)
    etiquetas = bruto.get('colaborador_etiquetas')
    etiquetas = etiquetas if isinstance(etiquetas, dict) else {}
    limpias = {}
    for clave in CLAVES:
        texto = recortar(etiquetas.get(clave), LARGO_ETIQUETA)
        if texto and texto != ETIQUETAS[clave]:
            limpias[clave] = texto
    pregunta['colaborador_etiquetas'] = limpias


def etiqueta(pregunta, clave):
    """El nombre visible de un dato: el que puso quien armó el formulario, o el
    de siempre."""
    propias = (pregunta or {}).get('colaborador_etiquetas')
    propia = propias.get(clave) if isinstance(propias, dict) else None
    return propia or ETIQUETAS[clave]


def ficha_publica(pregunta, trabajador_id):
    """Lo que ve quien responde al elegir: nombre y SOLO los campos que la
    pregunta pide."""
    persona = uno(trabajador_id)
    if not persona:
        return None
    salida = {'id': persona['id'], 'nombre': persona['nombre']}
    for clave in campos_de(pregunta):
        salida[clave] = persona[clave]
    return salida


def valor_limpio(pregunta, bruto):
    """(respuesta, error). Del navegador solo se cree el id."""
    identificador = bruto.get('id') if isinstance(bruto, dict) else bruto
    ficha = ficha_publica(pregunta, identificador)
    if not ficha:
        return None, 'Elige a una persona de la lista en «%s».' % _titulo(pregunta)
    return ficha, None


def _titulo(pregunta):
    sin_etiquetas = re.sub(r'<[^>]+>', '', str((pregunta or {}).get('titulo') or ''))
    return sin_etiquetas.strip() or 'Colaborador'


def texto(valor, pregunta=None):
    """La respuesta en una línea (correo de copia, tablas)."""
    if not isinstance(valor, dict):
        return str(valor or '')
    datos = ['%s: %s' % (etiqueta(pregunta, c), valor[c]) for c in CLAVES if valor.get(c)]
    return (valor.get('nombre') or '') + (' — ' + ' · '.join(datos) if datos else '')


def unica(pregunta):
    return (pregunta or {}).get('colaborador_unica') is not False


def limita(definicion):
    """¿El formulario tiene una pregunta «Colaborador» que admite una sola
    respuesta por persona? Entonces ya se sabe quién responde sin pedirle
    correo ni sesión."""
    return any(e.get('clase') == 'pregunta' and e.get('tipo') == TIPO and unica(e)
               for e in (definicion or {}).get('elementos') or [])


def ya_respondio(encuesta_id, pregunta_id, trabajador_id, excepto=None):
    """¿Hay ya una respuesta de este formulario con esa persona elegida en esa
    pregunta? `excepto`: id de la respuesta que se está modificando. Las
    respuestas borradas no cuentan. Si la consulta falla, se dice que no: no
    se bloquea a nadie por un error nuestro."""
    try:
        import almacen_bd as bd
        filas = bd.consultar(
            "SELECT id FROM encuesta_respuestas WHERE encuesta_id = %s "
            "AND (datos -> %s ->> 'id') = %s AND id <> %s LIMIT 1",
            (encuesta_id, pregunta_id, str(int(trabajador_id)), int(excepto or 0)))
        return bool(filas)
    except Exception as excepcion:
        log.warning('no se pudo comprobar la respuesta única: %s', excepcion)
        return False


def repetido(definicion, respuestas, excepto=None):
    """El mensaje para quien intenta responder por un colaborador que ya tiene
    respuesta, o '' si puede responder."""
    for elemento in (definicion or {}).get('elementos') or []:
        if elemento.get('clase') != 'pregunta' or elemento.get('tipo') != TIPO \
                or not unica(elemento):
            continue
        valor = (respuestas or {}).get(elemento.get('id'))
        if isinstance(valor, dict) and valor.get('id') and ya_respondio(
                definicion['id'], elemento['id'], valor['id'], excepto):
            return ('Ya hay una respuesta registrada de %s. Este formulario admite '
                    'una sola respuesta por colaborador.' % (valor.get('nombre') or 'esa persona'))
    return ''


def quien_responde(definicion, datos):
    """El colaborador elegido en la respuesta, que es quien responde cuando el
    formulario lleva esta pregunta (28/09/2026): sin sesión no hay otra forma
    de saber de quién es la respuesta. Con varias preguntas «Colaborador»,
    cuenta la primera del formulario. '' si no hay ninguna respondida."""
    if not isinstance(datos, dict):
        return ''
    for elemento in (definicion or {}).get('elementos') or []:
        if elemento.get('clase') == 'pregunta' and elemento.get('tipo') == TIPO:
            valor = datos.get(elemento.get('id'))
            if isinstance(valor, dict) and valor.get('nombre'):
                return str(valor['nombre'])
    return ''


# ── la hoja de cálculo: una columna por dato ─────────────────────────────
def desplegar(listado):
    """El listado de preguntas con cada «Colaborador» convertida en varias
    columnas: la suya (el nombre) y una por campo."""
    salida = []
    for pregunta in listado:
        if pregunta.get('tipo') != TIPO:
            salida.append(pregunta)
            continue
        titulo = _titulo(pregunta)
        salida.append({'id': pregunta['id'], 'clase': 'pregunta', 'tipo': 'texto_corto',
                       'titulo': titulo})
        for clave in campos_de(pregunta):
            salida.append({'id': pregunta['id'] + SEPARADOR_ID + clave,
                           'clase': 'pregunta', 'tipo': 'texto_corto',
                           'titulo': '%s · %s' % (titulo, etiqueta(pregunta, clave))})
    return salida


def desplegar_respuesta(listado, respuesta):
    """La respuesta con los datos de cada «Colaborador» repartidos en las
    claves de sus columnas desplegadas."""
    if not any(p.get('tipo') == TIPO for p in listado):
        return respuesta
    salida = dict(respuesta or {})
    for pregunta in listado:
        if pregunta.get('tipo') != TIPO:
            continue
        valor = salida.get(pregunta['id'])
        if not isinstance(valor, dict):
            continue
        salida[pregunta['id']] = valor.get('nombre') or ''
        for clave in campos_de(pregunta):
            salida[pregunta['id'] + SEPARADOR_ID + clave] = valor.get(clave) or ''
    return salida
