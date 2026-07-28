"""Lee el buzon de un usuario con doveadm: rebotes recibidos y mensaje original.

Se apoya en doveadm (mismo binario que ya usan otros modulos del panel) para no depender
del formato en disco de los buzones.
"""
import asyncio
import re
from asyncio.subprocess import PIPE

# Validacion defensiva: solo direcciones de correo con forma razonable.
_CUENTA_OK = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Campos que se extraen del cuerpo del rebote (formato DSN estandar, RFC 3464).
_DESTINATARIO_FALLIDO = re.compile(r"^Final-Recipient:.*?;\s*(\S+)", re.M)
_MOTIVO = re.compile(r"^Diagnostic-Code:\s*(.+)$", re.M)
_MESSAGE_ID = re.compile(r"^Message-ID:\s*<([^>]+)>", re.M | re.I)
# Marca donde empiezan las cabeceras del mensaje original dentro del DSN.
_INICIO_ORIGINAL = re.compile(
    r"Content-Type:\s*(?:message/rfc822|text/rfc822-headers)|Undelivered Message", re.I)
_ASUNTO = re.compile(r"^Subject:\s*(.+)$", re.M)
_FECHA_ORIGINAL = re.compile(r"^Arrival-Date:\s*(.+)$", re.M)


def _validar(cuenta: str):
    if not _CUENTA_OK.match(cuenta or ""):
        raise ValueError(f"Cuenta invalida: {cuenta}")


async def _doveadm(*args: str) -> str:
    """Ejecuta doveadm y devuelve su salida (cadena vacia si falla)."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "doveadm", *args, stdout=PIPE, stderr=PIPE
    )
    out, _ = await proc.communicate()
    return out.decode("utf-8", "ignore")


async def _uids(cuenta: str, *criterios: str) -> list[str]:
    """UIDs que cumplen un criterio de busqueda de doveadm."""
    salida = await _doveadm("search", "-u", cuenta, *criterios)
    # Cada linea es "<guid> <uid>"; nos quedamos con el uid.
    return [ln.split()[-1] for ln in salida.strip().splitlines() if ln.strip()]


async def _mensaje(cuenta: str, buzon: str, uid: str) -> str:
    """Contenido completo (cabeceras + cuerpo) de un mensaje."""
    salida = await _doveadm("fetch", "-u", cuenta, "text", "mailbox", buzon, "uid", uid)
    # doveadm antepone una linea "text:" que no forma parte del mensaje.
    return salida.split("text:", 1)[1].lstrip("\n") if "text:" in salida else salida


async def listar_rebotes(cuenta: str, dias: int = 15) -> list[dict]:
    """Rebotes recibidos por una cuenta, ya interpretados.

    Devuelve, por cada rebote: el asunto y Message-ID del correo original, los
    destinatarios que fallaron y el motivo. Con eso el panel puede ofrecer el reenvio.
    """
    _validar(cuenta)
    desde = (await _fecha_imap(dias))
    uids = await _uids(cuenta, "mailbox", "INBOX", "FROM", "MAILER-DAEMON", "SINCE", desde)

    rebotes = []
    for uid in uids:
        crudo = await _mensaje(cuenta, "INBOX", uid)
        fallidos = sorted(set(_DESTINATARIO_FALLIDO.findall(crudo)))
        if not fallidos:
            continue  # no es un DSN con destinatarios (p. ej. aviso de otro tipo)
        mid = _message_id_original(crudo)
        # El primer Subject del DSN es "Undelivered Mail..."; el segundo es el original.
        asuntos = _ASUNTO.findall(crudo)
        motivo = _MOTIVO.search(crudo)
        fecha = _FECHA_ORIGINAL.search(crudo)
        rebotes.append({
            "uid_rebote": uid,
            "message_id": mid,
            "asunto": (asuntos[1] if len(asuntos) > 1 else (asuntos[0] if asuntos else "")).strip(),
            "fecha_original": fecha.group(1).strip() if fecha else "",
            "destinatarios_fallidos": fallidos,
            "motivo": motivo.group(1).strip()[:200] if motivo else "",
            # Se puede reenviar si el rebote trae el mensaje adjunto (lo mas comun) o,
            # en su defecto, si hay Message-ID para buscarlo en Enviados.
            "trae_copia": bool(extraer_original_del_dsn(crudo)),
            "reenviable": bool(extraer_original_del_dsn(crudo)) or bool(mid),
        })
    return rebotes


def _message_id_original(dsn: str) -> str:
    """Message-ID del correo que reboto (no el del rebote).

    Un DSN lleva dos: el suyo propio en la cabecera y, al final, las cabeceras del mensaje
    original. Nos interesa el segundo. Si no se distingue la seccion, se toma el ultimo,
    que es el del original en la practica.
    """
    corte = _INICIO_ORIGINAL.search(dsn)
    zona = dsn[corte.end():] if corte else dsn
    encontrados = _MESSAGE_ID.findall(zona)
    if encontrados:
        return encontrados[0]
    todos = _MESSAGE_ID.findall(dsn)
    return todos[-1] if len(todos) > 1 else ""


async def _fecha_imap(dias: int) -> str:
    """Fecha en formato IMAP (dd-Mmm-yyyy) de hace N dias, para el criterio SINCE."""
    proc = await asyncio.create_subprocess_exec(
        "date", "-d", f"{int(dias)} days ago", "+%d-%b-%Y", stdout=PIPE, stderr=PIPE
    )
    out, _ = await proc.communicate()
    return out.decode().strip()


def extraer_original_del_dsn(dsn: str) -> str:
    """Mensaje original tal cual, extraido del propio rebote.

    Postfix adjunta el correo completo dentro del DSN (parte `message/rfc822`). Cuando esta,
    es la fuente mas fiable: es exactamente lo que no se pudo entregar, y funciona incluso
    con cuentas que no guardan copia en Enviados (por ejemplo, las que envian desde un ERP).
    Devuelve cadena vacia si el rebote solo trae las cabeceras.
    """
    marca = re.search(r"Content-Type:\s*message/rfc822", dsn, re.I)
    if not marca:
        return ""
    resto = dsn[marca.end():]
    # El mensaje adjunto empieza tras la linea en blanco que cierra las cabeceras de la parte.
    partes = resto.split("\n\n", 1)
    if len(partes) < 2:
        return ""
    cuerpo = partes[1]
    # Cortar en el delimitador MIME que cierra la parte (linea que empieza por "--").
    lineas, acumulado = cuerpo.splitlines(True), []
    for linea in lineas:
        if linea.startswith("--") and len(linea.strip()) > 10 and "@" not in linea:
            break
        acumulado.append(linea)
    return "".join(acumulado).strip()


async def obtener_rebote_crudo(cuenta: str, uid: str) -> str:
    """Contenido completo de un rebote concreto del INBOX (por su UID)."""
    _validar(cuenta)
    if not str(uid).isdigit():
        raise ValueError(f"UID invalido: {uid}")
    return await _mensaje(cuenta, "INBOX", str(uid))


async def obtener_original(cuenta: str, message_id: str) -> str:
    """Mensaje original completo, buscado por Message-ID en la carpeta de Enviados.

    Devuelve cadena vacia si no se encuentra (por ejemplo, cuentas de sistema que envian
    por SMTP sin guardar copia en Enviados).
    """
    _validar(cuenta)
    if not message_id or len(message_id) > 300:
        raise ValueError("Message-ID invalido")

    # Solo carpetas de enviados. Buscar en INBOX devolveria el propio rebote.
    for buzon in ("Sent", "Elementos enviados", "Enviados"):
        uids = await _uids(cuenta, "mailbox", buzon, "HEADER", "Message-ID", message_id)
        if uids:
            return await _mensaje(cuenta, buzon, uids[-1])
    return ""
