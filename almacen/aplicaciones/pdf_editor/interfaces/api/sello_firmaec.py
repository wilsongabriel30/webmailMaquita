# -*- coding: utf-8 -*-
"""
Sello visible de la firma electrónica, dibujado con trazos y texto reales (12/11/2026)

El sello se generaba como una IMAGEN de alta resolución (QR + texto). Al ver o imprimir el PDF a
tamaño normal, el visor reduce esa imagen y la suaviza: el QR y las letras salían grises y borrosos,
«con una mancha gris alrededor», al lado del sello nítido que pone FirmaEC.

Aquí el sello es un pequeño PDF vectorial que se incrusta en la firma, igual que hace FirmaEC:
  - el QR son rectángulos negros (un solo trazo relleno: sin uniones visibles entre módulos);
  - el texto es texto de verdad, en Courier y Courier negrita (fuentes estándar de PDF).
No hay ninguna imagen que reducir: se ve negro y definido a cualquier tamaño y al imprimir.

El contenido del QR y los textos son los mismos de antes (formato de FirmaEC).

Fecha: 2026-11-12
"""

import binascii
import io
import uuid

LINEA_1 = "Validar únicamente en FirmaEC."
LINEA_2 = "Firmado electrónicamente por:"
FUENTE = "cour"          # Courier
FUENTE_NEGRITA = "cobo"  # Courier-Bold
PROPORCION_NOMBRE = 1.28
TAMANO_MINIMO = 3.0


def contenido_qr(nombre, razon, ubicacion, fecha_iso):
    return (
        "FIRMADO POR: %s\nRAZON: %s\nLOCALIZACION: %s\nFECHA: %s\n"
        "VALIDAR CON: https://www.firmadigital.gob.ec\n"
        "Firmado digitalmente con FirmaEC 5.1.0"
    ) % (nombre, razon or "", ubicacion or "", fecha_iso)


def _partir(texto, fuente, tamano, ancho, medir):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if medir(prueba, fontname=fuente, fontsize=tamano) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def sello_pdf(nombre, razon, ubicacion, fecha_iso, ancho_pt, alto_pt):
    """Devuelve los bytes de un PDF de una página (ancho_pt x alto_pt) con el sello vectorial."""
    import fitz
    import qrcode

    ancho_pt, alto_pt = float(ancho_pt), float(alto_pt)
    doc = fitz.open()
    pagina = doc.new_page(width=ancho_pt, height=alto_pt)

    # --- QR: un rectángulo por tramo horizontal de módulos negros, todos en UN solo trazo ---
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=1, border=0)
    qr.add_data(contenido_qr(nombre, razon, ubicacion, fecha_iso))
    qr.make(fit=True)
    matriz = qr.get_matrix()
    n = len(matriz)
    lado = min(alto_pt, ancho_pt * 0.45)
    modulo = lado / n
    y0 = (alto_pt - lado) / 2.0
    trazo = pagina.new_shape()
    for fila, celdas in enumerate(matriz):
        col = 0
        while col < n:
            if celdas[col]:
                inicio = col
                while col < n and celdas[col]:
                    col += 1
                trazo.draw_rect(fitz.Rect(inicio * modulo, y0 + fila * modulo, col * modulo, y0 + (fila + 1) * modulo))
            else:
                col += 1
    trazo.finish(fill=(0, 0, 0), color=None, width=0, even_odd=False)
    trazo.commit()

    # --- Texto: tamaño que quepa en el ancho libre, nombre en negrita y algo mayor ---
    medir = fitz.get_text_length
    x = lado + alto_pt * 0.08
    # Un pequeño margen a la derecha: el ancho medido incluye el avance de la última letra.
    libre = max(10.0, ancho_pt - x - max(1.5, ancho_pt * 0.015))
    referencia = LINEA_1 if medir(LINEA_1, fontname=FUENTE, fontsize=10) >= medir(LINEA_2, fontname=FUENTE, fontsize=10) else LINEA_2
    tamano = alto_pt * 0.16
    while tamano > TAMANO_MINIMO and medir(referencia, fontname=FUENTE, fontsize=tamano) > libre:
        tamano -= 0.25
    tamano_nombre = tamano * PROPORCION_NOMBRE
    nombre_mayus = (nombre or "").upper()
    lineas_nombre = _partir(nombre_mayus, FUENTE_NEGRITA, tamano_nombre, libre, medir)
    while len(lineas_nombre) > 3 and tamano_nombre > TAMANO_MINIMO:
        tamano_nombre -= 0.25
        lineas_nombre = _partir(nombre_mayus, FUENTE_NEGRITA, tamano_nombre, libre, medir)
    bloques = [(LINEA_1, FUENTE, tamano), (LINEA_2, FUENTE, tamano)] + [(l, FUENTE_NEGRITA, tamano_nombre) for l in lineas_nombre]
    interlinea = alto_pt * 0.035
    alto_total = sum(t for _, _, t in bloques) + interlinea * (len(bloques) - 1)
    y = max(0.0, (alto_pt - alto_total) / 2.0)
    for texto, fuente, t in bloques:
        y += t
        pagina.insert_text(fitz.Point(x, y - t * 0.2), texto, fontname=fuente, fontsize=t, color=(0, 0, 0))
        y += interlinea
    datos = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return datos


def estilo(nombre, razon, ubicacion, fecha_iso, ancho_pt, alto_pt):
    """Estilo de sello de pyHanko con el dibujo vectorial. Lanza excepción si no se puede generar."""
    from pyhanko.pdf_utils.content import PdfContent
    from pyhanko.pdf_utils.layout import AxisAlignment, BoxConstraints, Margins, SimpleBoxLayoutRule
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.stamp import StaticStampStyle

    datos = sello_pdf(nombre, razon, ubicacion, fecha_iso, ancho_pt, alto_pt)

    class _PaginaEnMemoria(PdfContent):
        """Como ImportedPdfPage de pyHanko, pero desde memoria: sin archivos temporales que limpiar."""

        def render(self):
            objeto = self._ensure_writer.import_page_as_xobject(PdfFileReader(io.BytesIO(datos)), page_ix=0)
            nombre_recurso = b"/Sello" + binascii.hexlify(uuid.uuid4().bytes)
            self.resources.xobject[nombre_recurso.decode("ascii")] = objeto
            x1, y1, x2, y2 = objeto.get_object()["/BBox"]
            self.box = BoxConstraints(width=abs(x1 - x2), height=abs(y1 - y2))
            return nombre_recurso + b" Do"

    return StaticStampStyle(
        border_width=0,
        background=_PaginaEnMemoria(),
        background_layout=SimpleBoxLayoutRule(
            x_align=AxisAlignment.ALIGN_MIN, y_align=AxisAlignment.ALIGN_MIN, margins=Margins(0, 0, 0, 0)
        ),
        background_opacity=1,
    )
