# -*- coding: utf-8 -*-
"""
Permisos del espacio «Compartido conmigo» del Almacén Maquita.
==============================================================
Cuando alguien comparte una carpeta (o un archivo) con una persona de la casa,
esa persona debe poder ENTRAR a la carpeta desde su propio Drive y trabajar
dentro con el permiso que le dieron — igual que en Google Drive. Hasta ahora
solo existían dos espacios: «Mi unidad» (lo propio) y «/unidades/<id>» (las
unidades compartidas), así que lo compartido por una persona a otra solo se
podía mirar por el enlace público, en solo lectura.

Este módulo añade el tercer espacio, con la misma forma que el de unidades:

    /compartido/<propietario_id>/<subruta>

La traducción es directa: esa ruta virtual equivale a `<subruta>` dentro del
espacio del propietario. Por eso `resolver()` devuelve el par
(usuario_efectivo, ruta_efectiva): la API valida el permiso con la identidad
REAL de quien pide, y luego llama al núcleo con la identidad del DUEÑO. Así el
índice de búsqueda, las versiones, la papelera y la cuota siguen siendo los del
dueño del contenido, que es lo correcto: el archivo no cambia de manos porque
alguien lo edite.

Regla de acceso: hay permiso si existe un compartido VIGENTE dirigido a esa
persona (por nombre de usuario o por correo) cuya ruta sea la pedida o una
carpeta por encima de ella. Escribir exige además `puede_editar`.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import logging
import re

from almacen_bd import consultar
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.compartidos')

# Una ruta del espacio compartido se ve así: /compartido/<propietario_id>/<subruta>
_RE_COMPARTIDO = re.compile(r'^/compartido/(\d+)(/.*)?$')

PREFIJO = '/compartido'


def compartido_de_ruta(ruta_virtual: str):
    """Si la ruta es del espacio «Compartido conmigo» devuelve
    (propietario_id, subruta); si no, devuelve (None, ruta normalizada)."""
    limpia = normalizar_ruta_virtual(ruta_virtual)
    coincidencia = _RE_COMPARTIDO.match(limpia)
    if coincidencia:
        return int(coincidencia.group(1)), (coincidencia.group(2) or '/')
    return None, limpia


def ruta_compartida(propietario_id: int, subruta: str = '/') -> str:
    """Arma la ruta virtual del espacio compartido a partir de la ruta real
    del dueño. Es la inversa de `compartido_de_ruta`."""
    limpia = normalizar_ruta_virtual(subruta)
    if limpia == '/':
        return f'{PREFIJO}/{int(propietario_id)}'
    return f'{PREFIJO}/{int(propietario_id)}{limpia}'


def es_ruta_compartida(ruta_virtual: str) -> bool:
    """¿La ruta pertenece al espacio «Compartido conmigo»?"""
    try:
        propietario, _ = compartido_de_ruta(ruta_virtual)
    except RutaInvalida:
        return False
    return propietario is not None


def identidad(usuario_id: int):
    """(nombre de usuario, correo en minúsculas) de la persona. Los compartidos
    guardan el destinatario de las dos formas según cómo se compartiera."""
    filas = consultar('SELECT username, email FROM usuarios WHERE id = %s',
                      (int(usuario_id),), nomina=True)
    if not filas:
        return '', ''
    fila = filas[0]
    return (fila.get('username') or '').strip(), (fila.get('email') or '').strip().lower()


def concesiones(usuario_id: int) -> list:
    """Compartidos VIGENTES dirigidos a esta persona, sean carpetas o archivos.

    Vigente = sin fecha de caducidad o con una que aún no ha pasado. Se excluye
    lo que la propia persona compartió (no tiene sentido vérselo a uno mismo) y
    los enlaces sueltos sin destinatario, que no conceden espacio propio: esos
    se abren por su enlace.
    """
    usuario_id = int(usuario_id)
    nombre_usuario, correo = identidad(usuario_id)
    if not nombre_usuario and not correo:
        return []
    filas = consultar("""
        SELECT id, propietario_id, ruta, token, puede_editar, permite_descarga,
               permisos, clave_hash, expira_en, creado_en, modo
        FROM compartidos
        WHERE propietario_id <> %s
          AND (expira_en IS NULL OR expira_en > NOW())
          AND (LOWER(email) = %s OR destinatario = %s)
        ORDER BY creado_en DESC
    """, (usuario_id, correo, nombre_usuario))
    return [dict(f) for f in filas]


def _cubre(ruta_concedida: str, ruta_pedida: str) -> bool:
    """¿La ruta compartida cubre la ruta pedida? La cubre si es la misma o si
    es una carpeta por encima. La comparación es por segmentos completos para
    que «/Cacao» no conceda acceso a «/Cacao Privado»."""
    concedida = normalizar_ruta_virtual(ruta_concedida)
    pedida = normalizar_ruta_virtual(ruta_pedida)
    if concedida == '/':
        return True
    return pedida == concedida or pedida.startswith(concedida + '/')


def permiso_compartido(usuario_id: int, ruta_virtual: str, escritura: bool = False):
    """¿Puede esta persona leer (o escribir) esta ruta del espacio compartido?

    Devuelve True/False si la ruta ES del espacio compartido, y None si no lo
    es (para que quien pregunte siga con sus propias comprobaciones).
    """
    propietario, subruta = compartido_de_ruta(ruta_virtual)
    if propietario is None:
        return None
    usuario_id = int(usuario_id)
    if propietario == usuario_id:
        return True   # su propio contenido visto por el camino largo
    for concesion in concesiones(usuario_id):
        if int(concesion['propietario_id']) != propietario:
            continue
        if not _cubre(concesion['ruta'], subruta):
            continue
        if concesion.get('clave_hash'):
            # Enlace protegido con clave: el acceso se gana en la vista del
            # enlace, no por el explorador. No concede espacio propio.
            continue
        if not escritura or concesion.get('puede_editar'):
            return True
    return False


def resolver(usuario_id: int, ruta_virtual: str):
    """(usuario_efectivo, ruta_efectiva) con los que hay que llamar al núcleo.

    Para una ruta normal devuelve lo mismo que entró. Para una ruta del espacio
    compartido devuelve el DUEÑO y la ruta real dentro de su espacio. No valida
    permisos: eso es cosa de `permiso_compartido`, que se llama antes.
    """
    propietario, subruta = compartido_de_ruta(ruta_virtual)
    if propietario is None:
        return int(usuario_id), subruta
    return propietario, subruta


def prefijo_de(ruta_virtual: str) -> str:
    """Prefijo que hay que devolver al frontend para que siga navegando dentro
    del espacio compartido ('' si la ruta es normal)."""
    propietario, _ = compartido_de_ruta(ruta_virtual)
    return '' if propietario is None else f'{PREFIJO}/{propietario}'
