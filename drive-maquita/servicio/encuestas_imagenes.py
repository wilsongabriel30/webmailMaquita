# -*- coding: utf-8 -*-
"""
Imágenes de los formularios `.forma` (encabezado y preguntas).
==============================================================
Las imágenes viven FUERA del árbol de archivos del usuario, en
`<raiz>/_formularios/<encuesta_id>/<imagen_id>.<ext>`. La razón es que hay que
servirlas SIN sesión —quien responde el formulario no es de la casa— y un
endpoint público que leyera del Drive del usuario sería una vía para pedir
cualquier ruta suya. Aquí, en cambio, lo único que se puede pedir es una imagen
que pertenece a ese formulario, y el nombre lo pone el servidor.

Reglas que se aplican a todo lo que entra:

  - Se acepta solo PNG, JPEG, GIF y WEBP. **SVG no**: es XML y puede llevar
    scripts dentro, de modo que servirlo sería un XSS con nuestro dominio.
  - El tipo NO se cree por la extensión ni por el `Content-Type` que manda el
    navegador: se abre con Pillow y se comprueba lo que realmente es.
  - La imagen se reconstruye a partir de sus PÍXELES, no se limita a volver a
    guardarse: así no sobreviven comentarios, EXIF ni perfiles incrustados, y lo
    que queda en disco es una imagen hecha por nosotros. (Un GIF animado sí se
    guarda tal cual; ver `guardar()`.)
  - Los nombres los genera el servidor (UUID); nada del cliente toca la ruta.
  - Límite de tamaño y de dimensiones, para que una imagen enorme no llene el
    disco ni tumbe la memoria al recodificarla.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import io
import logging
import os
import re
import uuid

log = logging.getLogger('almacen.encuestas.imagenes')

CARPETA = '_formularios'
LIMITE_BYTES = 8 * 1024 * 1024        # 8 MB de archivo entrante
LADO_MAXIMO = 2000                    # se reduce si viene más grande
PIXELES_MAXIMOS = 50 * 1000 * 1000    # descarta la «bomba de descompresión»

# formato de Pillow -> (extensión, tipo MIME)
FORMATOS = {
    'PNG':  ('png',  'image/png'),
    'JPEG': ('jpg',  'image/jpeg'),
    'GIF':  ('gif',  'image/gif'),
    'WEBP': ('webp', 'image/webp'),
}

_ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
                 r'[0-9a-f]{4}-[0-9a-f]{12}$')


class ImagenInvalida(Exception):
    """Lo que llegó no es una imagen que podamos servir con tranquilidad."""


# ---------------------------------------------------------------------------
# Rutas en disco
# ---------------------------------------------------------------------------
def _raiz():
    from config_almacen import raiz_datos
    return os.path.join(raiz_datos(), CARPETA)


def _validar_id(valor, que='identificador'):
    """Los ids son UUID y se comprueban ANTES de tocar el disco: es lo que
    impide que un `../..` en la URL se convierta en una ruta."""
    texto = str(valor or '').lower()
    if not _ID.match(texto):
        raise ImagenInvalida('%s inválido' % que.capitalize())
    return texto


def carpeta_de(encuesta_id):
    return os.path.join(_raiz(), _validar_id(encuesta_id, 'formulario'))


def buscar(encuesta_id, imagen_id):
    """Ruta física de la imagen, o None si no está.

    Se busca por extensión conocida en vez de aceptar la que venga en la URL:
    así la URL nunca decide qué archivo se abre.
    """
    try:
        carpeta = carpeta_de(encuesta_id)
        limpio = _validar_id(imagen_id, 'imagen')
    except ImagenInvalida:
        return None
    for extension, _mime in FORMATOS.values():
        camino = os.path.join(carpeta, limpio + '.' + extension)
        if os.path.isfile(camino):
            return camino
    return None


def tipo_de(camino):
    """MIME según la extensión que puso el servidor al guardar."""
    extension = os.path.splitext(camino)[1].lstrip('.').lower()
    for ext, mime in FORMATOS.values():
        if ext == extension:
            return mime
    return 'application/octet-stream'


# ---------------------------------------------------------------------------
# Guardar
# ---------------------------------------------------------------------------
def guardar(encuesta_id, flujo):
    """Valida, recodifica y guarda la imagen. Devuelve su ficha para el `.forma`.

    `flujo` es el archivo que subió el navegador.
    """
    from PIL import Image

    datos = flujo.read(LIMITE_BYTES + 1)
    if not datos:
        raise ImagenInvalida('El archivo llegó vacío')
    if len(datos) > LIMITE_BYTES:
        raise ImagenInvalida('La imagen supera los %d MB'
                             % (LIMITE_BYTES // (1024 * 1024)))

    # Lo que decide si es una imagen es Pillow, no la extensión ni el navegador.
    try:
        Image.MAX_IMAGE_PIXELS = PIXELES_MAXIMOS
        imagen = Image.open(io.BytesIO(datos))
        imagen.verify()                      # detecta archivos corrompidos
        imagen = Image.open(io.BytesIO(datos))   # verify() agota el archivo
    except Exception:
        raise ImagenInvalida('El archivo no es una imagen que podamos usar')

    formato = (imagen.format or '').upper()
    if formato not in FORMATOS:
        raise ImagenInvalida(
            'Formato no admitido. Usa PNG, JPG, GIF o WEBP.')

    extension, _mime = FORMATOS[formato]
    animada = getattr(imagen, 'is_animated', False)

    if animada:
        # Un GIF animado se guarda tal cual: recodificarlo cuadro a cuadro se
        # cargaría la animación. Pillow ya confirmó que es un GIF válido y el
        # formato no admite scripts, así que servirlo es seguro; lo que no se
        # puede prometer de él es que vaya sin metadatos.
        salida = datos
        ancho, alto = imagen.size
    else:
        if max(imagen.size) > LADO_MAXIMO:
            imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
        if imagen.mode in ('P', 'PA'):
            imagen = imagen.convert('RGBA' if 'transparency' in imagen.info
                                    else 'RGB')
        if formato == 'JPEG' and imagen.mode not in ('RGB', 'L'):
            imagen = imagen.convert('RGB')

        # La imagen se reconstruye a partir de SOLO sus píxeles. No basta con
        # volver a guardarla: Pillow arrastra `info` al archivo nuevo, y con eso
        # sobreviven el comentario JPEG, el EXIF y los perfiles incrustados.
        # Copiando los píxeles a una imagen nueva no queda nada de eso.
        limpia = Image.frombytes(imagen.mode, imagen.size, imagen.tobytes())
        memoria = io.BytesIO()
        limpia.save(memoria, format=formato)
        salida = memoria.getvalue()
        ancho, alto = limpia.size

    carpeta = carpeta_de(encuesta_id)
    os.makedirs(carpeta, exist_ok=True)
    imagen_id = str(uuid.uuid4())
    destino = os.path.join(carpeta, imagen_id + '.' + extension)
    temporal = destino + '.parcial'
    with open(temporal, 'wb') as f:
        f.write(salida)
    os.replace(temporal, destino)        # publicación atómica

    return {'id': imagen_id, 'ancho': ancho, 'alto': alto}


def borrar(encuesta_id, imagen_id):
    """Elimina la imagen. Silencioso si ya no estaba."""
    camino = buscar(encuesta_id, imagen_id)
    if not camino:
        return False
    try:
        os.remove(camino)
        return True
    except OSError as excepcion:
        log.warning('No se pudo borrar la imagen %s: %s', imagen_id, excepcion)
        return False


def ids_en_uso(definicion):
    """Ids de imagen que el formulario referencia ahora mismo."""
    usados = set()
    cabecera = definicion.get('cabecera')
    if isinstance(cabecera, dict) and cabecera.get('id'):
        usados.add(str(cabecera['id']))
    for elemento in definicion.get('elementos', []):
        imagen = elemento.get('imagen')
        if isinstance(imagen, dict) and imagen.get('id'):
            usados.add(str(imagen['id']))
    return usados


def limpiar_huerfanas(encuesta_id, definicion):
    """Borra del disco las imágenes que el formulario ya no usa.

    Se llama al guardar: si alguien quita una imagen de una pregunta, el archivo
    no se queda ocupando sitio para siempre.
    """
    try:
        carpeta = carpeta_de(encuesta_id)
    except ImagenInvalida:
        return 0
    if not os.path.isdir(carpeta):
        return 0
    usados = ids_en_uso(definicion)
    borradas = 0
    for nombre in os.listdir(carpeta):
        base = os.path.splitext(nombre)[0]
        if base in usados or nombre.endswith('.parcial'):
            continue
        try:
            os.remove(os.path.join(carpeta, nombre))
            borradas += 1
        except OSError:
            pass
    return borradas
