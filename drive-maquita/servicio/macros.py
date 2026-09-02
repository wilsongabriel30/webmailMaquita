"""Control de macros del Almacén Maquita.

POLÍTICA (definida por la dirección el 29/07/2026)
--------------------------------------------------
Un archivo con macros es de USO INTERNO de los trabajadores de Maquita y de
nadie más. No sale de la organización con la macro dentro. Cuando hay que
enviarlo fuera se entrega una COPIA LIMPIA: el MISMO formato, con todos los
datos, fórmulas y formato intactos, pero sin la macro.

Se descartó entregar un PDF: perdía las fórmulas y la posibilidad de seguir
trabajando el archivo sin necesidad, porque las macros de OnlyOffice son
JavaScript y el Excel de quien lo recibe no las ejecutaría de todos modos.

POR QUÉ IMPORTA
---------------
OnlyOffice NO ejecuta VBA: tiene su propio motor de macros en JavaScript, así
que una macro de Excel viaja dentro del archivo pero aquí nunca corre. El
riesgo no es que se ejecute en Maquita, es que el archivo SALGA de Maquita con
la macro dentro y se ejecute en el Excel de quien lo reciba, junto con la
lógica de negocio que contenga.

CÓMO SE DETECTA
---------------
Por CONTENIDO, nunca por extensión: renombrar un .xlsm a .xlsx lo dejaría
pasar. Los formatos modernos (OOXML y ODF) son archivos ZIP, así que basta con
mirar su listado interno. Los formatos antiguos (.doc/.xls/.ppt) son
contenedores OLE y se detectan por la firma del flujo de VBA.

REGLA DE SEGURIDAD: si un archivo no se puede analizar, SE TRATA COMO SI
TUVIERA MACROS. Se falla cerrado, igual que en permisos_referencia.py.
"""

import logging
import os
import posixpath
import re
import shutil
import zipfile

registro = logging.getLogger(__name__)

# ── Partes internas que delatan una macro ────────────────────────────────────
# OOXML: el proyecto VBA va siempre en <carpeta>/vbaProject.bin y sus firmas
# digitales en vbaProjectSignature*.bin. OnlyOffice guarda SUS macros (las de
# JavaScript) en la parte docProps/ como un documento aparte.
PARTES_MACRO_OOXML = re.compile(
    r'(^|/)(vbaProject\.bin|vbaProjectSignature[^/]*\.bin|vbaData\.xml)$',
    re.IGNORECASE)

# ODF: los módulos Basic viven bajo Basic/ y se declaran en el manifiesto.
PARTES_MACRO_ODF = re.compile(r'^Basic/', re.IGNORECASE)

# OnlyOffice: sus macros JavaScript se guardan dentro del documento.
PARTES_MACRO_ONLYOFFICE = re.compile(
    r'(^|/)(macros?\.(json|xml|bin)|documentMacros[^/]*)$', re.IGNORECASE)

# Extensiones que declaran macros de entrada, y su equivalente SIN macros.
# Al limpiar se cambia la extensión: un .xlsm sin vbaProject.bin es exactamente
# un .xlsx, y dejarlo como .xlsm haría que Excel avisara de una macro ausente.
EQUIVALENTE_SIN_MACROS = {
    'xlsm': 'xlsx', 'xltm': 'xltx',
    'docm': 'docx', 'dotm': 'dotx',
    'pptm': 'pptx', 'potm': 'potx', 'ppsm': 'ppsx',
}

# Formatos antiguos: son contenedores OLE, no ZIP. No se les puede quitar la
# macro reescribiendo el envase; hay que CONVERTIRLOS al formato moderno, que
# es lo que hace desaparecer el proyecto VBA.
FORMATOS_ANTIGUOS = {'xls': 'xlsx', 'doc': 'docx', 'ppt': 'pptx',
                     'xlt': 'xltx', 'dot': 'dotx', 'pot': 'potx'}

# Formato binario de Excel: tampoco es ZIP.
FORMATOS_BINARIOS = {'xlsb': 'xlsx'}

# Todo lo que el editor abre como documento de ofimática. Si un archivo lleva
# una de estas extensiones y NO se puede analizar, se considera peligroso: o
# está corrupto, o alguien lo disfrazó para colar una macro.
EXTENSIONES_OFIMATICA = (
    set(EQUIVALENTE_SIN_MACROS) | set(EQUIVALENTE_SIN_MACROS.values())
    | set(FORMATOS_ANTIGUOS) | set(FORMATOS_ANTIGUOS.values())
    | set(FORMATOS_BINARIOS) | set(FORMATOS_BINARIOS.values())
    | {'ods', 'odt', 'odp', 'ots', 'ott', 'otp'}
)

# Firma del contenedor OLE (Compound File Binary Format).
FIRMA_OLE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'


def _es_parte_de_macro(nombre):
    """¿Esta parte interna del ZIP es una macro?"""
    return bool(PARTES_MACRO_OOXML.search(nombre)
                or PARTES_MACRO_ODF.match(nombre)
                or PARTES_MACRO_ONLYOFFICE.search(nombre))


def extension_de(nombre):
    return nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''


def tiene_macros(ruta_fisica, nombre=None):
    """¿El archivo contiene macros?

    Mira el CONTENIDO, no la extensión. Ante cualquier duda —archivo ilegible,
    corrupto o de un formato que no se sabe analizar— devuelve True: es
    preferible tratar como peligroso algo inofensivo que al revés.
    """
    nombre = nombre or os.path.basename(ruta_fisica)
    extension = extension_de(nombre)

    try:
        if not os.path.isfile(ruta_fisica):
            return False
        if os.path.getsize(ruta_fisica) == 0:
            return False

        # Formatos antiguos (OLE) y binarios: no son ZIP.
        with open(ruta_fisica, 'rb') as flujo:
            cabecera = flujo.read(8)

        if cabecera == FIRMA_OLE:
            return _ole_tiene_vba(ruta_fisica)

        if not zipfile.is_zipfile(ruta_fisica):
            # Ni ZIP ni OLE. Hay dos casos MUY distintos:
            #  - Un formato que sencillamente no puede llevar macros (texto
            #    plano, PDF, imágenes): es seguro, se deja pasar.
            #  - Un archivo que DICE ser de ofimática pero no se puede abrir:
            #    está corrupto o disfrazado. No se puede afirmar que esté
            #    limpio, así que se trata como peligroso.
            if extension in EXTENSIONES_OFIMATICA:
                registro.warning('%s dice ser %s pero no se puede abrir; se '
                                 'trata como CON macros', nombre, extension)
                return True
            return False

        with zipfile.ZipFile(ruta_fisica) as paquete:
            for parte in paquete.namelist():
                if _es_parte_de_macro(parte):
                    return True
            # ODF declara los módulos en el manifiesto aunque no haya carpeta.
            if 'META-INF/manifest.xml' in paquete.namelist():
                manifiesto = paquete.read('META-INF/manifest.xml')
                if b'Basic' in manifiesto or b'script' in manifiesto.lower():
                    return True
        return False

    except Exception as excepcion:
        registro.warning('No se pudo analizar %s en busca de macros (%s); '
                         'se trata como CON macros', nombre, excepcion)
        return True


def _ole_tiene_vba(ruta_fisica):
    """Busca la firma del proyecto VBA en un contenedor OLE (.doc/.xls/.ppt).

    No se interpreta la estructura OLE completa: los nombres de los flujos se
    guardan en UTF-16, así que basta con buscar 'VBA' y '_VBA_PROJECT' de esa
    forma. Es una comprobación conservadora, y para estos formatos da igual:
    la copia limpia se genera CONVIRTIENDO a formato moderno, que elimina la
    macro exista o no.
    """
    try:
        with open(ruta_fisica, 'rb') as flujo:
            contenido = flujo.read(4 * 1024 * 1024)   # cabecera y directorio
        return (b'V\x00B\x00A\x00' in contenido
                or b'_\x00V\x00B\x00A' in contenido
                or b'vbaProject' in contenido)
    except Exception:
        return True


def limpiar(ruta_origen, nombre, ruta_destino):
    """Escribe en `ruta_destino` una copia SIN macros de `ruta_origen`.

    Devuelve el nombre que debe llevar la copia (con la extensión cambiada si
    correspondía), o None si el archivo no se puede limpiar aquí y necesita
    conversión por el Document Server (formatos antiguos y .xlsb).

    Se conserva TODO lo demás: datos, fórmulas, formato, gráficos, hojas y
    vínculos internos. Solo se quitan las partes de macro y las referencias
    que apuntaban a ellas.
    """
    extension = extension_de(nombre)

    if extension in FORMATOS_ANTIGUOS or extension in FORMATOS_BINARIOS:
        return None      # necesita conversión, no se puede reescribir el ZIP

    if not zipfile.is_zipfile(ruta_origen):
        # Sin macros posibles: se copia tal cual.
        shutil.copy2(ruta_origen, ruta_destino)
        return nombre

    quitadas = []
    with zipfile.ZipFile(ruta_origen) as origen:
        partes = origen.namelist()
        macros = [p for p in partes if _es_parte_de_macro(p)]

        with zipfile.ZipFile(ruta_destino, 'w', zipfile.ZIP_DEFLATED) as salida:
            for info in origen.infolist():
                if info.filename in macros:
                    quitadas.append(info.filename)
                    continue

                datos = origen.read(info.filename)

                # Las partes que APUNTAN a la macro quedarían rotas: el
                # archivo abriría con un aviso de error. Hay que depurarlas.
                if info.filename == '[Content_Types].xml':
                    datos = _limpiar_content_types(datos)
                elif info.filename.endswith('.rels'):
                    datos = _limpiar_relaciones(datos)
                elif info.filename == 'META-INF/manifest.xml':
                    datos = _limpiar_manifiesto_odf(datos)

                salida.writestr(info, datos)

    if quitadas:
        registro.info('Copia sin macros de %s: quitadas %s', nombre, quitadas)

    nueva_extension = EQUIVALENTE_SIN_MACROS.get(extension)
    if nueva_extension:
        return nombre[: -len(extension)] + nueva_extension
    return nombre


def _limpiar_content_types(datos):
    """Quita del catálogo de tipos la entrada del proyecto VBA.

    Si se deja, el archivo declara un contenido que ya no existe y Excel lo
    da por dañado al abrirlo.
    """
    texto = datos.decode('utf-8', 'replace')
    texto = re.sub(r'<Override[^>]*vbaProject[^>]*/>', '', texto,
                   flags=re.IGNORECASE)
    texto = re.sub(r'<Default[^>]*Extension="bin"[^>]*/>', '', texto,
                   flags=re.IGNORECASE)
    # El tipo con macros pasa a ser el tipo sin macros.
    texto = texto.replace('.sheet.macroEnabled.main+xml',
                          '.sheet.main+xml')
    texto = texto.replace('.document.macroEnabled.main+xml',
                          '.document.main+xml')
    texto = texto.replace('.presentation.macroEnabled.main+xml',
                          '.presentation.main+xml')
    texto = texto.replace('.template.macroEnabled.main+xml',
                          '.template.main+xml')
    return texto.encode('utf-8')


def _limpiar_relaciones(datos):
    """Quita las relaciones que apuntaban al proyecto VBA."""
    texto = datos.decode('utf-8', 'replace')
    texto = re.sub(r'<Relationship[^>]*vbaProject[^>]*/>', '', texto,
                   flags=re.IGNORECASE)
    return texto.encode('utf-8')


def _limpiar_manifiesto_odf(datos):
    """Quita del manifiesto ODF las entradas de los módulos Basic."""
    texto = datos.decode('utf-8', 'replace')
    texto = re.sub(r'<manifest:file-entry[^>]*Basic[^>]*/>', '', texto,
                   flags=re.IGNORECASE)
    return texto.encode('utf-8')


def nombre_copia_limpia(nombre):
    """Nombre que llevará la copia sin macros, sin generarla."""
    extension = extension_de(nombre)
    destino = (EQUIVALENTE_SIN_MACROS.get(extension)
               or FORMATOS_ANTIGUOS.get(extension)
               or FORMATOS_BINARIOS.get(extension))
    if destino:
        return nombre[: -len(extension)] + destino
    return nombre


def necesita_conversion(nombre):
    """¿Hace falta el Document Server para limpiarlo?"""
    extension = extension_de(nombre)
    return extension in FORMATOS_ANTIGUOS or extension in FORMATOS_BINARIOS
