"""Eliminar una carpeta con todo lo que tiene dentro, subcarpetas incluidas (15/11/2026).

Informe de Andes: al eliminar una carpeta con subcarpetas, la primera vez la pantalla decía
«Carpeta eliminada» y la carpeta seguía ahí; las siguientes, 400 «Failed to delete folder».

Por qué: IMAP no borra en cascada. Con `DELETE Padre`, si la carpeta tiene hijas, el servidor
borra sus correos, responde OK y deja el nombre como contenedor de las hijas (RFC 3501, 6.3.4),
así que sigue en la lista. El segundo intento ya responde NO: «Padre» no existe como buzón, pero
tampoco desaparece mientras tenga hijas. Comprobado con Dovecot 2.4.1.

Aquí se borra primero lo de dentro, de la subcarpeta más profunda a la raíz, quitando antes cada
suscripción, con el separador que diga el servidor. El éxito no se deduce de las respuestas a
DELETE (un contenedor que quedó de un intento anterior responde NO y aun así desaparece al
quedarse sin hijas): se comprueba al final que no queda nada con ese nombre. Si queda algo, se
dice qué y por qué, y la interfaz no anuncia un borrado que no ocurrió.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.mail.clients.imap_client import _imap_utf7_decode, _imap_utf7_encode
from app.mail.services.cuentas_delegadas import carpeta_real

# Carpetas de uso especial: no se borran aunque estén dentro de la carpeta pedida.
_USO_ESPECIAL = frozenset({"sent", "drafts", "trash", "junk", "archive", "all"})
_RE_LISTA = re.compile(
    r'^\((?P<marcas>[^)]*)\)\s+(?:"(?P<sep>(?:\\.|[^"\\])*)"|NIL)\s+(?P<nombre>.+)$'
)


class NoSePudoBorrar(Exception):
    """El borrado no se completó. `estado` es el código HTTP que le corresponde."""

    def __init__(self, mensaje: str, estado: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado = estado


@dataclass(frozen=True)
class Carpeta:
    nombre: str  # tal como lo da el servidor (UTF-7 modificado)
    separador: str
    marcas: frozenset[str]

    @property
    def legible(self) -> str:
        return _imap_utf7_decode(self.nombre)


def citar(nombre: str) -> str:
    """Un nombre de buzón ya codificado, siempre entre comillas (RFC 3501)."""
    return '"' + nombre.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _texto(linea) -> str:
    if isinstance(linea, (bytes, bytearray)):
        return bytes(linea).decode("utf-8", errors="replace")
    return str(linea)


def leer_lista(lineas) -> list[Carpeta]:
    """Las carpetas de una respuesta a LIST (se ignoran la línea final y lo que no se entienda)."""
    carpetas: list[Carpeta] = []
    for linea in lineas:
        m = _RE_LISTA.match(_texto(linea).strip())
        if not m:
            continue
        nombre = m.group("nombre").strip()
        if nombre.startswith('"') and nombre.endswith('"') and len(nombre) >= 2:
            nombre = re.sub(r"\\(.)", r"\1", nombre[1:-1])
        if not nombre:
            continue
        marcas = frozenset(
            x.strip().lower() for x in m.group("marcas").split("\\") if x.strip()
        )
        separador = re.sub(r"\\(.)", r"\1", m.group("sep") or "")
        carpetas.append(Carpeta(nombre, separador, marcas))
    return carpetas


def orden_de_borrado(raiz: str, hijas: list[Carpeta], separador: str) -> list[str]:
    """De la más profunda a la raíz; la raíz, la última."""
    nombres = {h.nombre for h in hijas if h.nombre != raiz}
    profundas = sorted(nombres, key=lambda n: (-n.count(separador), n))
    return profundas + [raiz]


def _motivo(resp) -> str:
    """Lo que respondió el servidor, sin los tiempos entre paréntesis del final."""
    for linea in getattr(resp, "lines", None) or []:
        texto = re.sub(r"\s*\([\d.+ ]+secs?\)\.?$", "", _texto(linea).strip())
        if texto:
            return texto[:200]
    return ""


async def _listar(imap, patron: str) -> list[Carpeta]:
    resp = await imap.list('""', citar(patron))
    if getattr(resp, "result", "") != "OK":
        raise NoSePudoBorrar(
            "El servidor de correo no pudo consultar la carpeta. Inténtelo de nuevo."
        )
    return leer_lista(resp.lines)


async def borrar_con_subcarpetas(imap, carpeta: str) -> dict:
    """Borra `carpeta` (nombre legible) y sus subcarpetas. Lanza `NoSePudoBorrar` si no se completa.

    Devuelve {"subcarpetas": cuántas se borraron además de la pedida}.
    """
    raiz = _imap_utf7_encode(carpeta_real(carpeta))
    propias = [c for c in await _listar(imap, raiz) if c.nombre == raiz]
    if not propias:
        raise NoSePudoBorrar("La carpeta ya no existe.", 404)
    separador = propias[0].separador
    hijas = (
        [
            c
            for c in await _listar(imap, raiz + separador + "*")
            if c.nombre.startswith(raiz + separador)
        ]
        if separador
        else []
    )
    for hija in hijas:
        if hija.marcas & _USO_ESPECIAL:
            raise NoSePudoBorrar(
                f"La carpeta contiene «{hija.legible}», que es una carpeta del sistema y no se "
                "puede eliminar. Muévala fuera e inténtelo de nuevo."
            )

    motivos: dict[str, str] = {}
    for nombre in orden_de_borrado(raiz, hijas, separador):
        citado = citar(nombre)
        try:
            await imap.unsubscribe(citado)
        except Exception:
            pass  # sin suscripción no hay nada que quitar
        resp = await imap.delete(citado)
        if getattr(resp, "result", "") != "OK":
            motivos[nombre] = _motivo(resp)

    quedan = [c for c in await _listar(imap, raiz) if c.nombre == raiz]
    if separador:
        quedan += [
            c
            for c in await _listar(imap, raiz + separador + "*")
            if c.nombre.startswith(raiz + separador)
        ]
    if quedan:
        # Se nombra la que el servidor se negó a borrar; las demás quedan por ser sus madres.
        primera = next((c for c in quedan if motivos.get(c.nombre)), quedan[0])
        motivo = motivos.get(primera.nombre, "")
        detalle = f" El servidor respondió: {motivo}." if motivo else ""
        if len(quedan) == 1:
            que = f"No se pudo eliminar «{primera.legible}»."
        else:
            que = (
                f"No se pudo eliminar la carpeta completa: quedan {len(quedan)} carpetas "
                f"(entre ellas «{primera.legible}»)."
            )
        raise NoSePudoBorrar(que + detalle)
    return {"subcarpetas": len({h.nombre for h in hijas})}
