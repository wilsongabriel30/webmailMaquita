# -*- coding: utf-8 -*-
"""
Índice de CONTENIDO del Almacén (buscar dentro de los documentos).
==================================================================
Complementa a `indice_busqueda` (que indexa nombres): aquí se guarda el TEXTO de
los documentos para poder encontrar "el informe de Esmeraldas" aunque el archivo
se llame `doc_final_v3.pdf`.

Cómo se extrae el texto (sin dependencias nuevas de Python, todo con programas del
sistema o con la librería estándar):
- **PDF**: `pdftotext` (poppler, escrito en C — rapidísimo).
- **PDF escaneado** (el anterior no devuelve texto): `tesseract` en español,
  acotado a las primeras páginas. Es lento, por eso corre aparte y en segundo plano.
- **Word/Excel/PowerPoint modernos** (docx/xlsx/pptx) y **ODF**: son archivos ZIP con
  XML dentro; se leen con `zipfile` de la librería estándar.
- **Texto plano** (txt, csv, md…): se lee directo.

Reglas de diseño (iguales que el índice de nombres):
- El índice es un ESPEJO reconstruible; la verdad es el disco.
- NUNCA se extrae texto durante una subida: la subida solo deja el archivo "pendiente"
  y un proceso en segundo plano lo trabaja. Así el usuario nunca espera.
- Ningún fallo de extracción puede romper una operación de archivos.

Autoría: Equipo de Tecnología Maquita — 2026-07-22
"""
import logging
import os
import re
import subprocess
import zipfile

import espacios_indice as espacios
from almacen_bd import conexion, consultar, ejecutar
from indice_busqueda import normalizar
from seguridad_rutas import ruta_fisica

log = logging.getLogger('almacen.contenido')

# Qué se indexa
EXTENSIONES_PDF = {'pdf'}
EXTENSIONES_ZIP_XML = {'docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp'}
EXTENSIONES_TEXTO = {'txt', 'csv', 'md', 'json', 'xml', 'html', 'htm', 'log', 'rtf'}
# Los formularios del Drive: el nombre del archivo lo pone el botón «+ Nuevo»
# («Nuevo Formulario 4.forma») y el título de verdad vive DENTRO. Sin indexar su
# contenido, buscar «encuesta» no encontraba la «Encuesta Diagnóstica» de nadie.
EXTENSIONES_FORMULARIO = {'forma'}
EXTENSIONES = (EXTENSIONES_PDF | EXTENSIONES_ZIP_XML | EXTENSIONES_TEXTO
               | EXTENSIONES_FORMULARIO)

MAXIMO_BYTES_ARCHIVO = 200 * 1024 * 1024   # más grande que esto no se abre
MAXIMO_CARACTERES = 400_000                # texto guardado por documento
PAGINAS_PDF = 60                           # páginas leídas por PDF
PAGINAS_OCR = 10                           # páginas escaneadas que se pasan por OCR
SEGUNDOS_EXTRACCION = 90                   # tope por documento
SEGUNDOS_OCR = 240                         # el OCR es lento por naturaleza

ESTADOS = ('pendiente', 'listo', 'sin_texto', 'ocr_pendiente', 'error')


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
def asegurar_esquema_contenido() -> None:
    """Crea la tabla del índice de contenido y sus índices. Idempotente."""
    ejecutar("""
        CREATE TABLE IF NOT EXISTS indice_contenido (
            usuario_id   INTEGER     NOT NULL,
            ruta         TEXT        NOT NULL,
            huella       TEXT        NOT NULL DEFAULT '',
            estado       TEXT        NOT NULL DEFAULT 'pendiente',
            paginas      INTEGER     NOT NULL DEFAULT 0,
            texto        TEXT,
            vector       TSVECTOR,
            extraido_en  TIMESTAMPTZ,
            PRIMARY KEY (usuario_id, ruta)
        )
    """)
    ejecutar("""CREATE INDEX IF NOT EXISTS idx_contenido_vector
                ON indice_contenido USING gin (vector)""")
    ejecutar("""CREATE INDEX IF NOT EXISTS idx_contenido_pendiente
                ON indice_contenido (estado) WHERE estado IN ('pendiente', 'ocr_pendiente')""")


def _huella(fisica: str) -> str:
    """Tamaño + fecha de modificación: si cambia, hay que volver a extraer."""
    try:
        s = os.stat(fisica)
        return '%d-%d' % (s.st_size, int(s.st_mtime))
    except OSError:
        return ''


def extension_de(ruta: str) -> str:
    return ruta.rsplit('.', 1)[-1].lower() if '.' in os.path.basename(ruta) else ''


# ---------------------------------------------------------------------------
# Cola: encolar es barato, extraer es caro (y va en segundo plano)
# ---------------------------------------------------------------------------
def encolar(usuario_id: int, ruta_virtual: str) -> None:
    """Marca un archivo como pendiente de extracción. Se llama al subir/copiar.

    La fila queda en el ESPACIO del archivo (ver `espacios_indice`). Antes
    quedaba a nombre de quien lo tocaba, y como esta tabla —a diferencia del
    índice de nombres— no se reconstruye por las noches, el texto de las
    unidades compartidas se iba acumulando bajo las personas.
    """
    try:
        if extension_de(ruta_virtual) not in EXTENSIONES:
            return
        fisica = ruta_fisica(usuario_id, ruta_virtual)
        if not os.path.isfile(fisica):
            return
        usuario_id, ruta_virtual = espacios.espacio_de(usuario_id, ruta_virtual)
        ejecutar("""
            INSERT INTO indice_contenido (usuario_id, ruta, huella, estado)
            VALUES (%s, %s, %s, 'pendiente')
            ON CONFLICT (usuario_id, ruta) DO UPDATE
               SET huella = EXCLUDED.huella, estado = 'pendiente'
        """, (usuario_id, ruta_virtual, _huella(fisica)))
    except Exception as e:
        log.warning('contenido: no se pudo encolar %s de %s: %s', ruta_virtual, usuario_id, e)


def olvidar(usuario_id: int, ruta_virtual: str) -> None:
    """Quita del índice un archivo (y lo que colgaba, si era carpeta)."""
    try:
        usuario_id, ruta_virtual = espacios.espacio_de(usuario_id, ruta_virtual)
        ejecutar("""DELETE FROM indice_contenido
                    WHERE usuario_id = %s AND (ruta = %s OR ruta LIKE %s)""",
                 (usuario_id, ruta_virtual, ruta_virtual.rstrip('/') + '/%'))
    except Exception as e:
        log.warning('contenido: no se pudo olvidar %s de %s: %s', ruta_virtual, usuario_id, e)


def encolar_faltantes(usuario_id: int = None, limite: int = 5000) -> int:
    """
    Compara el índice de NOMBRES con el de contenido y encola lo que falte o haya
    cambiado. Es la forma de ponerse al día con lo que ya estaba en el almacén.
    """
    condicion = 'AND n.usuario_id = %s' % int(usuario_id) if usuario_id else ''
    extensiones = tuple(sorted(EXTENSIONES))
    filas = consultar("""
        SELECT n.usuario_id, n.ruta
        FROM indice_nombres n
        LEFT JOIN indice_contenido c
               ON c.usuario_id = n.usuario_id AND c.ruta = n.ruta
        WHERE NOT n.es_carpeta AND n.extension IN %%s AND c.ruta IS NULL %s
        LIMIT %%s
    """ % condicion, (extensiones, limite))
    for fila in filas:
        encolar(fila['usuario_id'], fila['ruta'])
    return len(filas)


# ---------------------------------------------------------------------------
# Extracción
# ---------------------------------------------------------------------------
def _ejecutar(comando, segundos):
    """Corre un programa del sistema y devuelve su salida de texto (o '')."""
    try:
        salida = subprocess.run(comando, capture_output=True, timeout=segundos)
        return salida.stdout.decode('utf-8', 'ignore')
    except subprocess.TimeoutExpired:
        log.warning('contenido: se agotó el tiempo en %s', comando[0])
        return ''
    except Exception as e:
        log.warning('contenido: falló %s: %s', comando[0], e)
        return ''


def _texto_de_pdf(fisica: str) -> str:
    return _ejecutar(['pdftotext', '-q', '-enc', 'UTF-8', '-l', str(PAGINAS_PDF), fisica, '-'],
                     SEGUNDOS_EXTRACCION)


def _texto_por_ocr(fisica: str) -> str:
    """OCR de un PDF escaneado: se rasteriza con pdftoppm y se lee con tesseract."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='almacen_ocr_') as carpeta:
        base = os.path.join(carpeta, 'pag')
        _ejecutar(['pdftoppm', '-r', '150', '-l', str(PAGINAS_OCR), '-png', fisica, base],
                  SEGUNDOS_OCR)
        partes = []
        for nombre in sorted(os.listdir(carpeta)):
            if not nombre.endswith('.png'):
                continue
            partes.append(_ejecutar(['tesseract', os.path.join(carpeta, nombre), 'stdout',
                                     '-l', 'spa+eng'], SEGUNDOS_OCR))
            if sum(len(p) for p in partes) > MAXIMO_CARACTERES:
                break
        return '\n'.join(partes)


_ETIQUETA = re.compile(rb'<[^>]+>')


def _texto_de_zip_xml(fisica: str) -> str:
    """Word/Excel/PowerPoint y ODF: son ZIP con XML; se quitan las etiquetas."""
    partes = []
    try:
        with zipfile.ZipFile(fisica) as z:
            for interno in z.namelist():
                if not interno.endswith('.xml') or 'rels' in interno:
                    continue
                if not any(p in interno for p in ('document', 'sheet', 'slide',
                                                  'sharedStrings', 'content')):
                    continue
                crudo = z.read(interno)
                partes.append(_ETIQUETA.sub(b' ', crudo).decode('utf-8', 'ignore'))
                if sum(len(p) for p in partes) > MAXIMO_CARACTERES:
                    break
    except Exception as e:
        log.warning('contenido: no se pudo leer %s: %s', fisica, e)
    return ' '.join(partes)


def _texto_plano(fisica: str) -> str:
    try:
        with open(fisica, 'rb') as f:
            return f.read(MAXIMO_CARACTERES).decode('utf-8', 'ignore')
    except OSError:
        return ''


def _texto_de_formulario(fisica: str) -> str:
    """Textos visibles de un `.forma`: título, descripción y cada elemento.

    Un formulario se busca por lo que dice, no por cómo se llama el archivo: el
    nombre lo pone el botón «+ Nuevo» y es igual para todos. Se recogen los
    textos que una persona reconocería —el título, la descripción, el enunciado
    de cada pregunta, su ayuda y sus opciones—, no la estructura interna.

    Los títulos pueden llevar formato (HTML de una lista blanca cerrada, ver
    `encuestas_texto`), así que se quitan las etiquetas: si no, buscar «encuesta»
    fallaría en un título escrito como «<b>Encuesta</b>».
    """
    import json
    try:
        with open(fisica, encoding='utf-8') as f:
            definicion = json.load(f)
    except (OSError, ValueError):
        return ''
    if not isinstance(definicion, dict):
        return ''

    partes = []

    def recoger(valor):
        if isinstance(valor, str) and valor.strip():
            partes.append(re.sub(r'<[^>]+>', ' ', valor))

    recoger(definicion.get('titulo'))
    recoger(definicion.get('descripcion'))
    # `elementos` es el modelo actual (versión 2); `preguntas`, el de la primera
    # entrega. Se leen los dos: hay `.forma` de los dos formatos en el Drive.
    for elemento in (definicion.get('elementos')
                     or definicion.get('preguntas') or []):
        if not isinstance(elemento, dict):
            continue
        recoger(elemento.get('titulo'))
        recoger(elemento.get('ayuda'))
        recoger(elemento.get('descripcion'))
        for opcion in elemento.get('opciones') or []:
            recoger(opcion if isinstance(opcion, str) else None)
    return ' '.join(partes)


def extraer_texto(fisica: str, extension: str, con_ocr: bool = False):
    """Devuelve (texto, necesita_ocr). El texto viene ya limpio de espacios raros."""
    if extension in EXTENSIONES_FORMULARIO:
        texto = _texto_de_formulario(fisica)
    elif extension in EXTENSIONES_PDF:
        texto = _texto_de_pdf(fisica)
        if len(texto.strip()) < 40:                 # PDF escaneado: no trae texto
            if not con_ocr:
                return '', True
            texto = _texto_por_ocr(fisica)
    elif extension in EXTENSIONES_ZIP_XML:
        texto = _texto_de_zip_xml(fisica)
    elif extension in EXTENSIONES_TEXTO:
        texto = _texto_plano(fisica)
    else:
        return '', False
    return re.sub(r'\s+', ' ', texto).strip()[:MAXIMO_CARACTERES], False


# ---------------------------------------------------------------------------
# Trabajo en segundo plano
# ---------------------------------------------------------------------------
def _guardar(usuario_id, ruta, huella, estado, texto, paginas=0):
    normalizado = normalizar(texto)
    with conexion() as con:
        with con.cursor() as cur:
            cur.execute("""
                INSERT INTO indice_contenido
                       (usuario_id, ruta, huella, estado, paginas, texto, vector, extraido_en)
                VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('spanish', %s), now())
                ON CONFLICT (usuario_id, ruta) DO UPDATE
                   SET huella = EXCLUDED.huella, estado = EXCLUDED.estado,
                       paginas = EXCLUDED.paginas, texto = EXCLUDED.texto,
                       vector = EXCLUDED.vector, extraido_en = now()
            """, (usuario_id, ruta, huella, estado, paginas, texto, normalizado))


def procesar_pendientes(limite: int = 50, con_ocr: bool = False) -> dict:
    """
    Extrae el texto de los archivos en cola. Devuelve un resumen.
    `con_ocr=False` atiende la cola rápida y deja marcados los escaneados;
    `con_ocr=True` atiende justamente esos (es lento: va en su propia pasada).
    """
    estado_buscado = 'ocr_pendiente' if con_ocr else 'pendiente'
    filas = consultar("""
        SELECT usuario_id, ruta FROM indice_contenido
        WHERE estado = %s ORDER BY extraido_en NULLS FIRST LIMIT %s
    """, (estado_buscado, limite))

    resumen = {'listos': 0, 'sin_texto': 0, 'para_ocr': 0, 'errores': 0}
    for fila in filas:
        usuario_id, ruta = fila['usuario_id'], fila['ruta']
        try:
            fisica = ruta_fisica(usuario_id, ruta)
            if not os.path.isfile(fisica):
                olvidar(usuario_id, ruta)
                continue
            if os.path.getsize(fisica) > MAXIMO_BYTES_ARCHIVO:
                _guardar(usuario_id, ruta, _huella(fisica), 'sin_texto', '')
                resumen['sin_texto'] += 1
                continue
            texto, necesita_ocr = extraer_texto(fisica, extension_de(ruta), con_ocr=con_ocr)
            if necesita_ocr:
                ejecutar("""UPDATE indice_contenido SET estado = 'ocr_pendiente'
                            WHERE usuario_id = %s AND ruta = %s""", (usuario_id, ruta))
                resumen['para_ocr'] += 1
                continue
            if texto:
                _guardar(usuario_id, ruta, _huella(fisica), 'listo', texto)
                resumen['listos'] += 1
            else:
                _guardar(usuario_id, ruta, _huella(fisica), 'sin_texto', '')
                resumen['sin_texto'] += 1
        except Exception as e:
            log.warning('contenido: error con %s de %s: %s', ruta, usuario_id, e)
            try:
                ejecutar("""UPDATE indice_contenido SET estado = 'error', extraido_en = now()
                            WHERE usuario_id = %s AND ruta = %s""", (usuario_id, ruta))
            except Exception:
                pass
            resumen['errores'] += 1
    return resumen


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------
def buscar_en_contenido(usuario_id: int, termino: str, limite: int = 25,
                        espacios_permitidos: list = None) -> list:
    """
    Documentos cuyo TEXTO coincide con lo buscado. Devuelve la ruta y un fragmento
    con la palabra resaltada, para mostrarlo bajo el nombre del archivo.

    Dos cosas que hacen que esto responda rápido:

    - **El fragmento se calcula DESPUÉS de recortar.** `ts_headline` vuelve a
      leer el documento entero para resaltar la palabra; hacerlo en la misma
      consulta que el filtro significaba calcularlo para cientos de documentos y
      tirar todos menos 25. Ahora se ordena y se limita en la subconsulta y solo
      esos 25 pasan por el resaltado.
    - **El texto no se arrastra.** `texto` es una columna enorme; en la
      subconsulta solo viajan `ruta` y el ranking.

    Igual que en el índice de nombres, se buscan todos los espacios accesibles y
    el permiso se comprueba en cada búsqueda.
    """
    consulta = normalizar(termino)
    if len(consulta) < 3:
        return []
    if espacios_permitidos is None:
        espacios_permitidos = espacios.espacios_de_busqueda(usuario_id)
    condicion, parametros = espacios.condicion_sql(espacios_permitidos)
    try:
        return consultar("""
            SELECT c.usuario_id AS espacio, c.ruta,
                   ts_headline('spanish', c.texto,
                               plainto_tsquery('spanish', %%s),
                               'MaxWords=18, MinWords=6, ShortWord=3, MaxFragments=1,'
                               'StartSel=«, StopSel=»') AS fragmento,
                   elegidos.relevancia
            FROM (
                SELECT usuario_id, ruta,
                       ts_rank(vector, plainto_tsquery('spanish', %%s)) AS relevancia
                FROM indice_contenido
                WHERE %s AND estado = 'listo'
                  AND vector @@ plainto_tsquery('spanish', %%s)
                ORDER BY relevancia DESC
                LIMIT %%s
            ) AS elegidos
            JOIN indice_contenido c
              ON c.usuario_id = elegidos.usuario_id AND c.ruta = elegidos.ruta
            ORDER BY elegidos.relevancia DESC
        """ % condicion,
            (consulta, consulta) + tuple(parametros) + (consulta, limite))
    except Exception as e:
        log.warning('contenido: falló la búsqueda de "%s": %s', termino, e)
        return []


def estado_indice(usuario_id: int = None) -> list:
    """Resumen por estado, para saber cómo va la indexación."""
    if usuario_id:
        return consultar("""SELECT estado, count(*) AS cuantos FROM indice_contenido
                            WHERE usuario_id = %s GROUP BY estado ORDER BY estado""",
                         (usuario_id,))
    return consultar("""SELECT estado, count(*) AS cuantos FROM indice_contenido
                        GROUP BY estado ORDER BY estado""")
