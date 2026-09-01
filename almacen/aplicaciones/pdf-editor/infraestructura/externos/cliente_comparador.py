# -*- coding: utf-8 -*-
"""
Comparador de PDFs del Editor.

Genera un PDF-reporte con las diferencias entre dos versiones de un documento:
- Página de resumen al inicio: páginas cambiadas (con % de cambio), agregadas,
  eliminadas, y el diff de texto (líneas quitadas/añadidas).
- Una página por cada página CON CAMBIOS: la versión modificada renderizada con
  recuadros rojos sobre las zonas que difieren (diff visual por píxeles con OpenCV).

Función pura bytes→bytes, reutilizable desde la API o desde scripts.
"""

import difflib
import io
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class ErrorComparacion(Exception):
    """Error con mensaje apto para mostrar al usuario."""


def _pixmap_a_matriz(pagina, dpi):
    """Renderiza la página a una matriz numpy BGR (para OpenCV)."""
    import numpy as np
    pix = pagina.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return img[:, :, ::-1].copy()  # RGB → BGR


def _igualar_tamanos(img_a, img_b):
    """Rellena con blanco para que ambas imágenes tengan el mismo alto/ancho."""
    import numpy as np
    alto = max(img_a.shape[0], img_b.shape[0])
    ancho = max(img_a.shape[1], img_b.shape[1])

    def rellenar(img):
        lienzo = np.full((alto, ancho, 3), 255, dtype=np.uint8)
        lienzo[:img.shape[0], :img.shape[1]] = img
        return lienzo

    return rellenar(img_a), rellenar(img_b)


def comparar(pdf_original, pdf_modificado, dpi=100, umbral=30):
    """Compara dos PDFs y devuelve los bytes del PDF-reporte.

    Args:
        pdf_original / pdf_modificado: bytes de cada versión
        dpi: resolución del diff visual (100 equilibra precisión y peso)
        umbral: diferencia mínima de gris (0-255) para considerar un píxel cambiado
    """
    import numpy as np
    import cv2

    try:
        doc_a = fitz.open(stream=pdf_original, filetype='pdf')
    except Exception as e:
        raise ErrorComparacion('El PDF original es inválido: %s' % e)
    try:
        doc_b = fitz.open(stream=pdf_modificado, filetype='pdf')
    except Exception as e:
        doc_a.close()
        raise ErrorComparacion('El PDF modificado es inválido: %s' % e)

    reporte = fitz.open()
    cambios = []   # (num_pagina, estado, pct)
    ESCALA = 72.0 / dpi  # px del render → puntos PDF

    try:
        total = max(len(doc_a), len(doc_b))
        for i in range(total):
            num = i + 1
            if i >= len(doc_a) or i >= len(doc_b):
                # Página agregada (solo en modificado) o eliminada (solo en original)
                agregada = i >= len(doc_a)
                origen = doc_b[i] if agregada else doc_a[i]
                img = _pixmap_a_matriz(origen, dpi)
                estado = 'agregada' if agregada else 'eliminada'
                color = (0, 150, 0) if agregada else (0, 0, 200)  # BGR
                cv2.rectangle(img, (2, 2), (img.shape[1] - 3, img.shape[0] - 3), color, 6)
                cambios.append((num, estado, 100.0))
                _agregar_pagina_reporte(reporte, img, dpi,
                                        'Página %d — %s' % (num, estado.upper()))
                continue

            img_a = _pixmap_a_matriz(doc_a[i], dpi)
            img_b = _pixmap_a_matriz(doc_b[i], dpi)
            img_a, img_b = _igualar_tamanos(img_a, img_b)

            gris_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
            gris_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gris_a, gris_b)
            _, mascara = cv2.threshold(diff, umbral, 255, cv2.THRESH_BINARY)
            pct = 100.0 * cv2.countNonZero(mascara) / mascara.size

            if pct == 0:
                continue  # página idéntica: no va al reporte

            # Agrupar zonas cambiadas y dibujar recuadros rojos sobre la versión nueva
            mascara = cv2.dilate(mascara, np.ones((9, 9), np.uint8))
            contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            marcada = img_b.copy()
            for c in contornos:
                x, y, w, h = cv2.boundingRect(c)
                if w * h < 60:
                    continue  # ruido
                cv2.rectangle(marcada, (x - 3, y - 3), (x + w + 3, y + h + 3), (0, 0, 220), 2)

            cambios.append((num, 'modificada', pct))
            _agregar_pagina_reporte(reporte, marcada, dpi,
                                    'Página %d — %.1f%% del área cambió (recuadros rojos)' % (num, pct))

        # ---- Diff de texto (líneas añadidas/quitadas) ----
        texto_a = [l for p in doc_a for l in p.get_text().split('\n') if l.strip()]
        texto_b = [l for p in doc_b for l in p.get_text().split('\n') if l.strip()]
        dif_texto = [l for l in difflib.unified_diff(texto_a, texto_b, lineterm='', n=0)
                     if l[:1] in '+-' and l[:3] not in ('+++', '---')]

        # ---- Página de resumen (al inicio) ----
        _agregar_resumen(reporte, len(doc_a), len(doc_b), total, cambios, dif_texto)
        if reporte.page_count > 1:
            reporte.move_page(reporte.page_count - 1, 0)

        buf = io.BytesIO()
        reporte.save(buf, garbage=3, deflate=True)
        return buf.getvalue()
    finally:
        doc_a.close()
        doc_b.close()
        reporte.close()


def _agregar_pagina_reporte(reporte, img_bgr, dpi, titulo):
    """Inserta una imagen marcada como página del reporte, con banda de título."""
    import cv2
    ESCALA = 72.0 / dpi
    ancho_pt = img_bgr.shape[1] * ESCALA
    alto_pt = img_bgr.shape[0] * ESCALA
    BANDA = 26  # puntos para el título

    pagina = reporte.new_page(width=ancho_pt, height=alto_pt + BANDA)
    pagina.draw_rect(fitz.Rect(0, 0, ancho_pt, BANDA), color=None, fill=(0.12, 0.12, 0.12))
    pagina.insert_text((8, 17), titulo, fontsize=11, color=(1, 1, 1))
    ok, png = cv2.imencode('.png', img_bgr)
    if ok:
        pagina.insert_image(fitz.Rect(0, BANDA, ancho_pt, alto_pt + BANDA), stream=png.tobytes())


def _agregar_resumen(reporte, pags_a, pags_b, total, cambios, dif_texto, max_lineas=40):
    """Arma la página de resumen del reporte."""
    pagina = reporte.new_page(width=595, height=842)  # A4
    y = 60
    pagina.insert_text((50, y), 'Comparación de PDFs — Resumen', fontsize=18)
    y += 26
    pagina.insert_text((50, y), 'Original: %d páginas | Modificado: %d páginas' % (pags_a, pags_b), fontsize=11)
    y += 24

    if not cambios:
        pagina.insert_text((50, y), 'Los documentos son visualmente IDÉNTICOS.', fontsize=13, color=(0, 0.5, 0))
        y += 24
    else:
        pagina.insert_text((50, y), 'Páginas con diferencias (%d de %d):' % (len(cambios), total), fontsize=13)
        y += 18
        for num, estado, pct in cambios[:35]:
            if estado == 'modificada':
                linea = '  • Página %d: modificada (%.1f%% del área)' % (num, pct)
                color = (0.75, 0.3, 0)
            else:
                linea = '  • Página %d: %s' % (num, estado)
                color = (0, 0.45, 0) if estado == 'agregada' else (0.8, 0, 0)
            pagina.insert_text((50, y), linea, fontsize=10, color=color)
            y += 14
        if len(cambios) > 35:
            pagina.insert_text((50, y), '  … y %d páginas más' % (len(cambios) - 35), fontsize=10)
            y += 14

    y += 12
    pagina.insert_text((50, y), 'Cambios de texto (— quitado / + añadido):', fontsize=13)
    y += 18
    if not dif_texto:
        pagina.insert_text((50, y), '  (sin cambios de texto detectables)', fontsize=10, color=(0.4, 0.4, 0.4))
    for linea in dif_texto[:max_lineas]:
        color = (0, 0.45, 0) if linea.startswith('+') else (0.8, 0, 0)
        pagina.insert_text((50, y), ('  ' + linea)[:110], fontsize=9, color=color)
        y += 12
        if y > 800:
            pagina.insert_text((50, y), '  … (diff truncado)', fontsize=9)
            break
    if len(dif_texto) > max_lineas and y <= 800:
        pagina.insert_text((50, y), '  … y %d líneas más' % (len(dif_texto) - max_lineas), fontsize=9)
