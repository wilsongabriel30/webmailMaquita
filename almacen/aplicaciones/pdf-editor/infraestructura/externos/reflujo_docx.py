# -*- coding: utf-8 -*-
"""
Agregar una fila DESPLAZANDO todo el documento (y creando páginas).
====================================================================
«necesito que si yo agrego una fila el texto se desplace hacia abajo de todo el
documento no importa que se agreguen más páginas» — el usuario, 27-jul-2026.

Un PDF **no tiene flujo**: son renglones clavados en coordenadas de cada
página. Para que el documento entero se recorra y nazcan páginas nuevas hay que
reconstruirlo: pasarlo a un formato con flujo (Word), insertar la fila ahí
—donde una tabla sí es una tabla— y volver a PDF. El usuario no ve ningún Word
en ningún momento; es una tubería interna.

El precio, que se le avisa antes de hacerlo: al reconstruirlo el aspecto
general puede variar un poco (márgenes, saltos de página, alguna imagen). Por
eso el editor **pregunta** cada vez que no hay sitio en la página, en vez de
decidir por su cuenta: "solo aquí" (rápido y fiel) o "desplazar todo".

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import copy
import io
import logging

logger = logging.getLogger(__name__)


def _tabla_del_docx(documento, indice):
    tablas = documento.tables
    if indice < 0 or indice >= len(tablas):
        raise ValueError('No se encontró esa tabla al reconstruir el documento.')
    return tablas[indice]


def _fila_vacia_como(tabla, modelo):
    """Una fila igual que `modelo` (mismos bordes y anchos) pero sin texto."""
    nueva = copy.deepcopy(modelo._tr)
    # Vaciar el texto de cada celda, conservando el formato del primer párrafo
    for celda in nueva.findall(
            '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
        parrafos = celda.findall(
            '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        for sobrante in parrafos[1:]:
            celda.remove(sobrante)
        for parrafo in parrafos[:1]:
            for run in parrafo.findall(
                    '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
                parrafo.remove(run)
    return nueva


def indice_de_tabla(contenido_pdf, numero_pagina, indice_en_pagina):
    """Qué número de tabla es, contando desde el principio del documento.

    En el .docx las tablas van seguidas, sin páginas; hay que traducir "la
    tabla 0 de la página 3" a "la tabla 5 del documento".
    """
    import fitz
    from . import tablas_pdf

    documento = fitz.open(stream=contenido_pdf, filetype='pdf')
    try:
        total = 0
        for numero in range(int(numero_pagina) - 1):
            tablas, _ = tablas_pdf._tablas_de(documento[numero])
            total += len(tablas)
        return total + int(indice_en_pagina)
    finally:
        documento.close()


def agregar_fila(contenido_pdf, numero_pagina, indice_en_pagina, posicion):
    """Inserta una fila y devuelve el PDF entero recompuesto. (pdf, aviso)."""
    from docx import Document

    from . import cliente_conversiones as conv

    indice = indice_de_tabla(contenido_pdf, numero_pagina, indice_en_pagina)
    logger.info('reflujo: tabla %d de la página %s (la %d del documento)',
                indice_en_pagina, numero_pagina, indice)

    docx = conv.en_subproceso('pdf-a-word', [contenido_pdf], timeout=900)
    if not docx:
        raise ValueError('No se pudo reconstruir el documento para desplazar el texto.')

    documento = Document(io.BytesIO(docx))
    tabla = _tabla_del_docx(documento, indice)
    filas = tabla.rows
    if not filas:
        raise ValueError('Esa tabla llegó vacía al reconstruir el documento.')

    posicion = max(0, min(int(posicion), len(filas)))
    # Se copia una fila de datos (no la de encabezados) para heredar bordes y anchos
    modelo = filas[min(len(filas) - 1, max(1, posicion if posicion < len(filas) else len(filas) - 1))]
    nueva = _fila_vacia_como(tabla, modelo)
    if posicion >= len(filas):
        tabla._tbl.append(nueva)
    else:
        filas[posicion]._tr.addprevious(nueva)

    salida = io.BytesIO()
    documento.save(salida)
    pdf = conv.oficina_a_pdf('documento.docx', salida.getvalue(), timeout=600)
    if not pdf:
        raise ValueError('No se pudo volver a PDF tras insertar la fila.')

    import fitz
    antes = fitz.open(stream=contenido_pdf, filetype='pdf')
    despues = fitz.open(stream=pdf, filetype='pdf')
    paginas_antes, paginas_despues = antes.page_count, despues.page_count
    antes.close()
    despues.close()

    aviso = ('el documento se recompuso entero para hacer sitio; '
             'repasa que todo siga en su lugar')
    if paginas_despues != paginas_antes:
        aviso += ' (ahora tiene %d páginas, antes %d)' % (paginas_despues, paginas_antes)
    return pdf, aviso
