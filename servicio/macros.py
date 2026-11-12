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
# digitales en vbaProjectSignature*.bin.
PARTES_MACRO_OOXML = re.compile(
    r'(^|/)(vbaProject\.bin|vbaProjectSignature[^/]*\.bin|vbaData\.xml)$',
    re.IGNORECASE)

# ODF: los módulos Basic viven bajo Basic/ y se declaran en el manifiesto.
PARTES_MACRO_ODF = re.compile(r'^Basic/', re.IGNORECASE)

# OnlyOffice: sus macros JavaScript se guardan dentro del documento, en
# xl/jsaProject.bin (word/ y ppt/ en texto y presentaciones), enlazadas desde
# las relaciones con el tipo http://schemas.onlyoffice.com/jsaProject. Pueden
# ir en un .xlsx normal, sin ningún VBA (comprobado el 13/10/2026 con el SIGTH).
PARTES_MACRO_ONLYOFFICE = re.compile(
    r'(^|/)(jsaProject\.bin|macros?\.(json|xml|bin)|documentMacros[^/]*)$',
    re.IGNORECASE)

# Tipos de contenido propios de una macro (VBA y sus firmas).
TIPO_CONTENIDO_MACRO = re.compile(r'vbaProject|vbaData', re.IGNORECASE)

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


# Función de serie que OnlyOffice (complemento de IA, DS 9.x/10.x) escribe por su
# cuenta en xl/jsaProject.bin de las hojas que se editan en el Drive, aunque la
# persona no haya creado ninguna macro. No es lógica de nadie: es la fórmula
# =AI(...) del propio editor. Se reconoce por la huella EXACTA de su código
# (comprobada el 04/11/2026: 100 de 100 archivos, mismo guid y misma huella);
# una función que solo se LLAME «AI» pero cambie un byte sigue siendo macro.
FUNCIONES_DE_SERIE_ONLYOFFICE = {
    ('AI', '42109f0b4a24e403db220325831067588ce92f7320d8691153cc502950f37564'),
}
TOPE_JSA_DE_SERIE = 64 * 1024     # el de serie pesa ~1,7 KB


def _jsa_solo_de_serie(info, paquete):
    """¿Este jsaProject.bin no trae nada salvo funciones de serie del editor?

    Falla cerrado: si pesa demasiado, no es JSON, trae alguna macro de usuario
    (macrosArray no vacío) o alguna función que no sea de serie, devuelve False
    y el archivo se trata como CON macros.
    """
    import hashlib
    import json
    try:
        if info.file_size > TOPE_JSA_DE_SERIE:
            return False
        datos = json.loads(paquete.read(info).decode('utf-8'))
        if not isinstance(datos, dict) or datos.get('macrosArray'):
            return False
        funciones = (datos.get('customFunctions') or {}).get('macrosArray') or []
        for funcion in funciones:
            huella = hashlib.sha256(
                (funcion.get('value') or '').encode('utf-8')).hexdigest()
            if (funcion.get('name'), huella) not in FUNCIONES_DE_SERIE_ONLYOFFICE:
                if funcion.get('name') == 'AI':
                    # Casi seguro: una versión nueva de OnlyOffice cambió su
                    # función de serie. Se sigue bloqueando (falla cerrado),
                    # pero avisa para añadir la huella nueva a la lista.
                    registro.warning(
                        'MACROS: función AI con huella desconocida %s (guid %s). '
                        'Si es la de serie de una versión nueva de OnlyOffice, '
                        'añadirla a FUNCIONES_DE_SERIE_ONLYOFFICE en macros.py',
                        huella, funcion.get('guid'))
                return False
        return True
    except Exception:
        return False


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
            for info in paquete.infolist():
                parte = info.filename
                if _es_parte_de_macro(parte):
                    # 04/11/2026: el jsaProject.bin que solo lleva la función
                    # de serie =AI() de OnlyOffice no es una macro (caso
                    # ATS.FOR.023 de u59: no se podía compartir).
                    if (parte.rsplit('/', 1)[-1].lower() == 'jsaproject.bin'
                            and _jsa_solo_de_serie(info, paquete)):
                        continue
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
    texto = re.sub(r'<Override[^>]*(vbaProject|vbaData|jsaProject)[^>]*/>',
                   '', texto, flags=re.IGNORECASE)
    # La entrada genérica de .bin solo se quita si declara el tipo VBA: en
    # muchos libros declara printerSettings*.bin, y quitarla dejaría esas
    # partes sin tipo y el archivo dañado para Excel.
    texto = re.sub(r'<Default[^>]*Extension="bin"[^>]*/>',
                   lambda m: '' if TIPO_CONTENIDO_MACRO.search(m.group(0))
                   else m.group(0), texto, flags=re.IGNORECASE)
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
    """Quita las relaciones que apuntaban a la macro (VBA u OnlyOffice)."""
    texto = datos.decode('utf-8', 'replace')
    texto = re.sub(r'<Relationship[^>]*(vbaProject|jsaProject)[^>]*/>', '',
                   texto, flags=re.IGNORECASE)
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
