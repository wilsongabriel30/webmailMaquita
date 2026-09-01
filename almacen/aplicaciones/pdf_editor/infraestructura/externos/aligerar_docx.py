# -*- coding: utf-8 -*-
"""
Aligerar el .docx que sale de pdf2docx (imágenes).
==================================================
`pdf2docx` extrae TODAS las imágenes del PDF como PNG sin comprimir. En la
proforma real del usuario (31 páginas, 27-jul-2026) eso daba un Word de
**16,2 MB, de los cuales 15,4 MB eran 44 imágenes PNG**. Ese peso se paga tres
veces —al generar, al descargarlo el Document Server y al abrirlo el
navegador— y es la causa principal de que la herramienta "tardara mucho".

Las fotos se guardan como JPEG (medido: **15,4 MB → 1,7 MB en 0,6 s**, nueve
veces menos) y se renombran, actualizando las referencias del documento. Lo que
NO se toca:

- las imágenes pequeñas (logos, iconos, viñetas): comprimirlas no ahorra nada
  y sí se les nota la pérdida;
- las que tienen transparencia de verdad: JPEG no la soporta y se vería un
  recuadro blanco donde antes no había nada;
- ninguna otra parte del documento: texto, tablas, estilos y fuentes viajan
  byte a byte como estaban.

Si algo falla se devuelve el documento original: un Word pesado es un problema,
un Word roto es otro mucho peor.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import io
import logging
import os
import zipfile

logger = logging.getLogger(__name__)

# Por debajo de esto no compensa: son logos y viñetas
MINIMO_BYTES = 40 * 1024
# Ninguna imagen necesita más para verse bien en un documento de oficina
LADO_MAXIMO = 1600
CALIDAD = 82

CARPETA = 'word/media/'
EXTENSIONES = ('.png', '.bmp', '.tiff', '.tif')


def _tiene_transparencia(imagen):
    """¿Usa la transparencia de verdad, o solo trae el canal por costumbre?"""
    if imagen.mode not in ('RGBA', 'LA', 'P'):
        return False
    if imagen.mode == 'P':
        if 'transparency' not in imagen.info:
            return False
        imagen = imagen.convert('RGBA')
    alfa = imagen.getchannel('A')
    return alfa.getextrema()[0] < 255


def _a_jpeg(datos):
    """(bytes JPEG, True) o (None, False) si esta imagen no se debe tocar."""
    from PIL import Image

    imagen = Image.open(io.BytesIO(datos))
    imagen.load()
    if _tiene_transparencia(imagen):
        return None, False
    if max(imagen.size) > LADO_MAXIMO:
        imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
    if imagen.mode != 'RGB':
        imagen = imagen.convert('RGB')
    salida = io.BytesIO()
    imagen.save(salida, 'JPEG', quality=CALIDAD, optimize=True)
    return salida.getvalue(), True


def aligerar(contenido_docx):
    """Devuelve el .docx con las fotos comprimidas (o el original si falla)."""
    try:
        entrada = zipfile.ZipFile(io.BytesIO(contenido_docx))
        elementos = entrada.infolist()

        # 1. decidir qué imágenes se convierten
        nuevas = {}      # nombre viejo -> (nombre nuevo, bytes)
        for elemento in elementos:
            nombre = elemento.filename
            if not nombre.startswith(CARPETA) or elemento.file_size < MINIMO_BYTES:
                continue
            if not nombre.lower().endswith(EXTENSIONES):
                continue
            try:
                datos, convertida = _a_jpeg(entrada.read(nombre))
            except Exception as excepcion:
                logger.warning('no se pudo comprimir %s: %s', nombre, excepcion)
                continue
            # Solo si de verdad se gana algo
            if convertida and len(datos) < elemento.file_size * 0.9:
                nuevas[nombre] = (os.path.splitext(nombre)[0] + '.jpeg', datos)

        if not nuevas:
            return contenido_docx

        # 2. reescribir el paquete
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as destino:
            for elemento in elementos:
                nombre = elemento.filename
                if nombre in nuevas:
                    destino.writestr(nuevas[nombre][0], nuevas[nombre][1])
                    continue
                datos = entrada.read(nombre)
                # Las referencias a las imágenes viven en los .rels y en el XML
                if nombre.endswith(('.rels', '.xml')):
                    texto = datos.decode('utf-8', 'replace')
                    original = texto
                    for viejo, (nuevo, _bytes) in nuevas.items():
                        texto = texto.replace(os.path.basename(viejo),
                                              os.path.basename(nuevo))
                    if nombre == '[Content_Types].xml' and 'Extension="jpeg"' not in texto:
                        texto = texto.replace(
                            '<Types ',
                            '<Types ', 1).replace(
                            '>', '><Default Extension="jpeg" ContentType="image/jpeg"/>', 1)
                    if texto != original:
                        datos = texto.encode('utf-8')
                destino.writestr(elemento, datos)

        resultado = salida.getvalue()
        logger.info('docx aligerado: %.1f → %.1f MB (%d imagen(es))',
                    len(contenido_docx) / 1048576, len(resultado) / 1048576, len(nuevas))
        return resultado
    except Exception as excepcion:
        logger.warning('no se pudo aligerar el documento (%s): se deja como estaba',
                       excepcion)
        return contenido_docx
