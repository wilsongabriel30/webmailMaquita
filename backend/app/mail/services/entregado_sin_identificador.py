"""Recuperar un correo que salió SIN identificador propio (enviado desde otra aplicación de correo).

Caso del 19/11/2026: una aplicación de correo de teléfono entregó el mensaje sin cabecera
`Message-ID`. El servidor le puso uno al recibirlo (`<AAAAMMDDHHMMSS.COLA@servidor>`), y la copia
que la aplicación guardó en «Enviados» lleva otro distinto. La recuperación busca por ese
identificador, así que no encontraba el correo en ningún buzón de destino.

Aquí se localiza la copia entregada cuando el identificador de «Enviados» no aparece en el buzón
del destinatario. Como el resultado se usa para QUITAR un correo de un buzón ajeno, solo se acepta
una coincidencia inequívoca; deben cumplirse todas estas condiciones:

- el correo del buzón de destino viene de la misma cuenta que pide recuperar y llegó hace poco;
- su identificador es de los que pone ESTE servidor a los mensajes que llegan sin uno;
- la hora de ese identificador está a pocos minutos de la hora del correo de «Enviados»
  (la de su cabecera `Date` o la de guardado en la carpeta);
- el asunto es el mismo;
- y queda un solo identificador candidato. Con cero o con varios, no se recupera nada.

La parte que decide (`elegir`) no llama a nada externo, para poder probarla sin servidor.
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from app.mail.services import plazo_recuperacion

logger = logging.getLogger(__name__)

MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"
# Margen entre la hora del correo de «Enviados» y la hora en que el servidor recibió el mensaje.
TOLERANCIA = timedelta(minutes=5)
# Margen añadido al plazo de recuperación al buscar en el buzón de destino.
MARGEN_BUSQUEDA_MINUTOS = 10
_RE_ID_SERVIDOR = re.compile(r"^<(\d{14})\.[0-9A-Fa-f]{5,20}@([^>\s]+)>$")
_RE_ESPACIOS = re.compile(r"\s+")


def asunto_normalizado(crudo: str | None) -> str:
    """Asunto decodificado, sin diferencias de espacios ni de mayúsculas."""
    texto = crudo or ""
    try:
        texto = str(make_header(decode_header(texto)))
    except Exception:
        pass
    return _RE_ESPACIOS.sub(" ", texto).strip().casefold()


def hora_del_identificador(message_id: str, servidor: str) -> datetime | None:
    """Hora (UTC) de un identificador puesto por este servidor; None si no es de los suyos."""
    m = _RE_ID_SERVIDOR.match((message_id or "").strip())
    if not m or m.group(2).lower() != (servidor or "").lower():
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def fecha_de_cabecera(crudo: str | None) -> datetime | None:
    """Cabecera `Date` como fecha UTC (None si no se entiende o no trae zona horaria)."""
    try:
        fecha = parsedate_to_datetime((crudo or "").strip())
    except (TypeError, ValueError):
        return None
    if fecha is None or fecha.tzinfo is None:
        return None
    return fecha.astimezone(timezone.utc)


def registros(salida: str) -> list[dict]:
    """Parte la salida de `doveadm fetch` en registros {campo: valor}, uniendo cabeceras plegadas."""
    lista: list[dict] = []
    for bloque in (salida or "").split("\f"):
        registro: dict = {}
        ultimo = None
        for linea in bloque.split("\n"):
            if not linea.strip():
                continue
            if linea[0] in " \t" and ultimo:
                registro[ultimo] += " " + linea.strip()
                continue
            campo, sep, valor = linea.partition(":")
            if not sep:
                continue
            ultimo = campo.strip()
            registro[ultimo] = valor.strip()
        if registro:
            lista.append(registro)
    return lista


def elegir(
    enviado: dict,
    entregados: list[dict],
    servidor: str,
    tolerancia: timedelta = TOLERANCIA,
) -> str | None:
    """Identificador de la copia entregada, o None si no hay UNA coincidencia inequívoca.

    `enviado`: {"asunto", "fechas": [fechas UTC del correo de «Enviados»]}.
    `entregados`: [{"message_id", "asunto"}] del buzón de destino, ya filtrados por remitente.
    """
    asunto = asunto_normalizado(enviado.get("asunto"))
    fechas = [f for f in enviado.get("fechas") or () if f is not None]
    if not fechas:
        return None
    candidatos: set[str] = set()
    for correo in entregados:
        identificador = (correo.get("message_id") or "").strip()
        hora = hora_del_identificador(identificador, servidor)
        if hora is None:
            continue
        if asunto_normalizado(correo.get("asunto")) != asunto:
            continue
        if any(abs(hora - f) <= tolerancia for f in fechas):
            candidatos.add(identificador)
    return candidatos.pop() if len(candidatos) == 1 else None


def _doveadm_fetch(buzon: str, campos: str, *consulta: str) -> str | None:
    try:
        r = subprocess.run(
            [
                "sudo",
                "-n",
                MAQUITA_SUDO,
                "doveadm",
                "fetch",
                "-u",
                buzon,
                campos,
                *consulta,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def datos_del_enviado(remitente: str, message_id: str) -> dict | None:
    """Asunto y fechas del correo en «Enviados» del remitente (None si no está o no se puede leer)."""
    salida = _doveadm_fetch(
        remitente,
        "hdr.date hdr.subject date.received",
        "mailbox",
        "Sent",
        "header",
        "message-id",
        message_id,
    )
    encontrados = registros(salida or "")
    if not encontrados:
        return None
    r = encontrados[-1]
    guardado = plazo_recuperacion.interpretar_fecha(r.get("date.received"))
    return {
        "asunto": r.get("hdr.subject", ""),
        "fechas": [
            fecha_de_cabecera(r.get("hdr.date")),
            # `date.received` viene en la hora local del servidor.
            guardado.astimezone(timezone.utc) if guardado else None,
        ],
    }


def identificador_entregado(
    remitente: str,
    destinatario: str,
    message_id: str,
    servidor: str,
    enviado: dict | None = None,
) -> str | None:
    """Identificador con el que el correo está en el buzón del destinatario, o None.

    Solo se llama cuando `message_id` (el de «Enviados») NO aparece en ese buzón.
    """
    enviado = (
        enviado if enviado is not None else datos_del_enviado(remitente, message_id)
    )
    if not enviado:
        return None
    minutos = plazo_recuperacion.minutos_maximos() + MARGEN_BUSQUEDA_MINUTOS
    salida = _doveadm_fetch(
        destinatario,
        "hdr.message-id hdr.subject",
        "from",
        remitente,
        "savedsince",
        f"{minutos}mins",
    )
    entregados = [
        {"message_id": r.get("hdr.message-id", ""), "asunto": r.get("hdr.subject", "")}
        for r in registros(salida or "")
    ]
    hallado = elegir(enviado, entregados, servidor)
    if hallado:
        logger.info(
            "recuperación: %s envió sin identificador propio; en el buzón de %s el correo %s es %s",
            remitente,
            destinatario,
            message_id,
            hallado,
        )
    return hallado


_servidor_cache: list[str] = []


def nombre_servidor() -> str:
    """Nombre con el que este servidor firma los identificadores que asigna (`myhostname`)."""
    if not _servidor_cache:
        nombre = ""
        try:
            r = subprocess.run(
                ["/usr/sbin/postconf", "-h", "myhostname"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            nombre = r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            nombre = ""
        if not nombre:
            # Sin nombre comprobado no se reconoce ningún identificador: no se recupera por esta vía.
            return ""
        _servidor_cache.append(nombre)
    return _servidor_cache[0]


class Localizador:
    """Busca la copia entregada en varios buzones leyendo «Enviados» una sola vez."""

    _SIN_LEER = object()

    def __init__(self, remitente: str, message_id: str):
        self.remitente = remitente
        self.message_id = message_id
        self._enviado = self._SIN_LEER

    def en_buzon(self, destinatario: str) -> str | None:
        servidor = nombre_servidor()
        if not servidor:
            return None
        if self._enviado is self._SIN_LEER:
            self._enviado = datos_del_enviado(self.remitente, self.message_id)
        if not self._enviado:
            return None
        return identificador_entregado(
            self.remitente, destinatario, self.message_id, servidor, self._enviado
        )
