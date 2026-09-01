# -*- coding: utf-8 -*-
"""
CLI interno de conversiones pesadas del Editor PDF.

Las operaciones CPU-intensivas (pdf2docx, OpenCV, tesseract/OCR, compresión
con garbage collection, python-pptx) NO deben correr dentro del worker
eventlet de gunicorn: congelan el event loop, el master deja de recibir
latidos, mata al worker a los 300 s (timeout de gunicorn_nomina.conf.py) y
nginx devuelve 504 — además de dejar colgadas las demás peticiones de ese
worker mientras dura la operación.

Este script se ejecuta como PROCESO APARTE desde la API, vía
`cliente_conversiones.en_subproceso()`.

Uso: conversor_cli.py <operacion> <archivo_salida> <params_json> <entrada1> [<entrada2>]
En error: el mensaje para el usuario queda en la última línea de stderr, exit 1.

Operaciones: pdf-a-word | pdf-a-excel | pdf-a-ppt | comparar | comprimir | ocr
            | ocr-a-texto (escaneo → PDF de texto real, para editar en Word)
(comprimir usa params {"calidad"}; ocr usa {"idioma", "pagina"} y su salida es JSON)
"""

import json
import os
import sys

RUTA_MODULO = os.path.dirname(os.path.abspath(__file__))
# Raíz del proyecto (…/Maquita) para poder importar el paquete completo
# (cliente_pymupdf usa imports relativos del módulo pdf_editor)
RAIZ_PROYECTO = os.path.abspath(os.path.join(RUTA_MODULO, '..', '..', '..', '..'))


def main():
    sys.path.insert(0, RUTA_MODULO)      # cliente_conversiones / cliente_comparador (sueltos)
    sys.path.insert(0, RAIZ_PROYECTO)    # modulos.pdf_editor.… (paquete)
    import cliente_conversiones as conv

    if len(sys.argv) < 5:
        print('Uso: conversor_cli.py <operacion> <salida> <params_json> <entrada...>', file=sys.stderr)
        return 2

    operacion, ruta_salida = sys.argv[1], sys.argv[2]
    try:
        params = json.loads(sys.argv[3])
    except ValueError:
        params = {}
    entradas = []
    for ruta in sys.argv[4:]:
        with open(ruta, 'rb') as f:
            entradas.append(f.read())

    try:
        if operacion == 'pdf-a-word':
            salida = conv.pdf_a_word(entradas[0])
        elif operacion == 'pdf-a-word-sencillo':
            # Respaldo: cuando pdf2docx no puede con el documento, se saca el texto y
            # las tablas y se monta un Word sencillo. Import SUELTO por lo mismo que
            # abajo: por el paquete entra media aplicación y el arranque cuesta ~7 s.
            import word_sencillo
            salida = word_sencillo.construir(entradas[0])
        elif operacion == 'pdf-a-excel':
            salida = conv.pdf_a_excel(entradas[0])
        elif operacion == 'pdf-a-ppt':
            salida = conv.pdf_a_ppt(entradas[0])
        elif operacion == 'comparar':
            import cliente_comparador
            salida = cliente_comparador.comparar(entradas[0], entradas[1])
        elif operacion == 'comprimir':
            # Por la vía corta (ver carga_ligera.py): importar esta clase por el
            # paquete arrastraba FARO entero y costaba ~4,5 s de arranque.
            import carga_ligera
            salida = carga_ligera.cliente_pdf().comprimir_desde_bytes(
                entradas[0], params.get('calidad', 'media'))
        elif operacion == 'ocr-a-texto':
            # Escaneo → PDF de texto REAL, para poder convertirlo a Word.
            # Aquí, y no en el worker: tesseract es CPU pura y reparte páginas
            # entre varios procesos (ver ocr_pagina_texto.py).
            # Import SUELTO (no `modulos.pdf_editor.…`) a propósito: por el
            # paquete entra media aplicación FARO y el arranque del proceso
            # costaba ~7 s, más que el propio OCR. Medido el 27-jul-2026.
            from ocr_pagina_texto import rehacer_con_texto
            salida = rehacer_con_texto(entradas[0], params.get('idioma', 'spa'))
            if salida is None:
                salida = entradas[0]      # no se reconoció nada: el original
        elif operacion == 'ocr':
            # Lo mismo: 4,54 s de arranque -> 0,21 s. En un OCR de 12 hojas eso era
            # más de la mitad de lo que esperaba el usuario (31-jul-2026).
            import carga_ligera
            if params.get('area'):
                # Un recuadro elegido a mano: solo esa zona, y respetando cómo está
                # escrita (ver texto_area.py). Pedido del usuario el 31-jul-2026.
                area = carga_ligera.importar(
                    'modulos.pdf_editor.infraestructura.externos.texto_area')
                resultado = area.extraer_como_resultado(
                    entradas[0], params.get('pagina') or 1, params['area'],
                    params.get('idioma', 'spa'))
            else:
                resultado = carga_ligera.cliente_pdf().extraer_texto_desde_bytes(
                    entradas[0], params.get('pagina'), idioma=params.get('idioma', 'spa'))
            salida = json.dumps(resultado, ensure_ascii=False).encode('utf-8')
        else:
            print('Operación desconocida: %s' % operacion, file=sys.stderr)
            return 2
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    with open(ruta_salida, 'wb') as f:
        f.write(salida)
    return 0


if __name__ == '__main__':
    sys.exit(main())
