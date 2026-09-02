# -*- coding: utf-8 -*-
"""
Nombres de archivo del Almacén Maquita.
=======================================
La extensión de un archivo NO es parte del nombre que la persona edita: es lo
que decide con qué programa se abre. Si al cambiar el nombre se pierde, el
archivo deja de abrirse aunque su contenido esté intacto — pasó el 31/08/2026
con «BIBLIOTECA PROCESOS FORMATIVOS», un .xlsx que quedó como .xls y OnlyOffice
dejó de ofrecer la barra de edición.

Por eso, igual que en Google Drive, al renombrar se CONSERVA SIEMPRE la
extensión original. Aquí vive esa regla, en un solo sitio, para que valga para
todas las vías de renombrado (menú contextual, lápiz de la fila, WebDAV, API).

Autoría: Equipo de Tecnología Maquita — 2026-08-31
"""

# Extensiones compuestas: hay que conservarlas enteras o el archivo pierde
# la mitad de su identidad (un .tar.gz que queda en .gz ya no dice que dentro
# hay un tar).
EXTENSIONES_COMPUESTAS = ('.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst')

# Un tramo tras el último punto solo es extensión si es corto y sin espacios.
# «Informe final v1.2» no tiene extensión: «2» no lo es, y «Acta 2026.borrador
# final» tampoco. Diez caracteres cubren de sobra .xlsx, .pptx o .drawio.
LARGO_MAXIMO_EXTENSION = 10


def extension_de(nombre: str) -> str:
    """Extensión de un nombre de archivo, CON el punto y tal como está escrita.

    Devuelve '' cuando no hay extensión reconocible. Un archivo oculto sin más
    puntos (.gitignore) no tiene extensión: el punto inicial es parte del
    nombre.
    """
    nombre = (nombre or '').strip()
    if not nombre:
        return ''
    minusculas = nombre.lower()
    for compuesta in EXTENSIONES_COMPUESTAS:
        if minusculas.endswith(compuesta) and len(nombre) > len(compuesta):
            return nombre[-len(compuesta):]
    # El corte tiene que caer a partir del segundo carácter: en «.gitignore» el
    # punto inicial es parte del nombre, no el separador de una extensión.
    corte = nombre.rfind('.')
    if corte < 1:
        return ''
    extension = nombre[corte:]
    cuerpo = extension[1:]
    if not cuerpo or ' ' in cuerpo or len(cuerpo) > LARGO_MAXIMO_EXTENSION:
        return ''
    if not cuerpo.replace('_', '').replace('-', '').isalnum():
        return ''
    # Toda extensión de formato lleva alguna letra (.7z, .mp4, .xlsx). Un tramo
    # de solo dígitos es parte del nombre: «Informe final v1.2» acaba en «.2»
    # y ese «.2» no se le puede pegar al nombre nuevo.
    if not any(caracter.isalpha() for caracter in cuerpo):
        return ''
    return extension


def cuerpo_de(nombre: str) -> str:
    """El nombre sin su extensión — lo único que la persona debería editar."""
    extension = extension_de(nombre)
    return nombre[:-len(extension)] if extension else nombre


def conservar_extension(nombre_actual: str, nombre_nuevo: str,
                        es_carpeta: bool = False) -> str:
    """Nombre nuevo con la extensión ORIGINAL puesta de vuelta si se perdió.

    - Las carpetas no tienen extensión que proteger: pasan tal cual.
    - Si el original no tenía extensión, no hay nada que conservar.
    - Si el nombre nuevo ya termina en la misma extensión (sin mirar
      mayúsculas), se respeta lo que la persona escribió.
    - En cualquier otro caso se le añade la extensión original al final. Es
      deliberado que «archivo.xlsx» renombrado a «archivo.xls» quede como
      «archivo.xls.xlsx»: el archivo sigue abriéndose, que es lo que importa,
      y el nombre deja ver lo que se intentó hacer.
    """
    nombre_nuevo = (nombre_nuevo or '').strip()
    if es_carpeta or not nombre_nuevo:
        return nombre_nuevo
    extension = extension_de(nombre_actual)
    if not extension:
        return nombre_nuevo
    if nombre_nuevo.lower().endswith(extension.lower()):
        return nombre_nuevo
    return nombre_nuevo + extension


def nombre_libre(existe, nombre: str) -> str:
    """Un nombre que no choque con nada, al estilo de «informe (1).xlsx».

    `existe` es una función que dice si un nombre ya está ocupado; así esto no
    necesita saber nada del disco y se puede probar solo.

    El número va ANTES de la extensión, no al final: «informe.xlsx (1)» dejaría
    de ser un Excel para el sistema, que es justo el problema que se arregló
    esta misma mañana.
    """
    if not existe(nombre):
        return nombre
    extension = extension_de(nombre)
    cuerpo = nombre[:-len(extension)] if extension else nombre
    numero = 1
    while True:
        candidato = '%s (%d)%s' % (cuerpo, numero, extension)
        if not existe(candidato):
            return candidato
        numero += 1
        if numero > 9999:        # no se cuelga aunque haya un caso absurdo
            raise ValueError('No se encontró un nombre libre para %r' % nombre)
