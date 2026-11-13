"""Mensaje a la persona de una alerta: la redacción, en lenguaje llano y de usted.

Cuando los intentos fallidos de entrar a una cuenta vienen todos del país o de la red interna, lo
más probable es que sea un celular (u otro programa de correo) de la propia persona con una
contraseña vieja guardada. Aquí se decide en qué alertas procede escribirle y se redacta el texto
que el administrador verá ya escrito y podrá corregir antes de enviarlo.

Funciones puras: sin base de datos y sin envío (eso está en mensajes.py). El texto no nombra
protocolos ni direcciones de red: la persona no tiene por qué conocerlos.
"""

from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

FIRMA = "Tecnología"
LARGO_ASUNTO = 150
LARGO_CUERPO = 4000
ASUNTO = "Revise el correo en su celular: la contraseña guardada no está funcionando"


def procede(
    ataque: dict, existe: bool, protegida: bool, pais_propio: str = "EC"
) -> bool:
    """Solo si la cuenta existe, sigue abierta a sus equipos y ningún intento viene del exterior.

    Con intentos desde otros países es un ataque: decirle a la persona que revise su celular sería
    engañarla. Y si la cuenta ya está protegida (solo webmail), el acceso ya está cerrado.
    """
    fuera = [
        p
        for p in ataque.get("paises", [])
        if p.upper() not in (pais_propio.upper(), "LAN")
    ]
    return bool(existe and not protegida and not fuera and ataque.get("direcciones"))


def _cuando(ultimo: datetime | None, zona=None) -> str:
    """Los accesos se guardan por horas: se dice la franja, no un minuto que no se conoce."""
    if not ultimo:
        return ""
    local = ultimo.astimezone(zona) if zona and ultimo.tzinfo else ultimo
    fin = local + timedelta(hours=1)
    return f"el {local:%d/%m/%Y}, entre las {local:%H}:00 y las {fin:%H}:00"


def redactar(
    cuenta: str,
    nombre: str = "",
    ultimo: datetime | None = None,
    desde_red_interna: bool = False,
    url_correo: str = "",
    enlace_app: str = "",
    zona=None,
) -> dict:
    """Asunto y cuerpo por defecto. `enlace_app` vacío (lo normal hoy): no se menciona la aplicación."""
    saludo = f"Buen día, {nombre.strip()}:" if nombre.strip() else "Buen día:"
    cuando = _cuando(ultimo, zona)
    detectado = (
        f"Le escribimos de Tecnología. El servidor de correo detectó que un celular u otro programa "
        f"de correo intenta entrar a su cuenta {cuenta} una y otra vez con una contraseña equivocada."
    )
    if cuando:
        detectado += f" El último intento fue {cuando}."
    if desde_red_interna:
        detectado += " Ese equipo estaba conectado a la red de la institución."
    web = f" ({url_correo})" if url_correo else ""
    parrafos = [
        saludo,
        detectado,
        "Casi siempre pasa porque en el celular quedó guardada una contraseña anterior.",
        "Qué le pedimos hacer:\n"
        "1. Abra el correo en su celular y en cualquier otro programa donde lo tenga configurado.\n"
        "2. Actualice la contraseña guardada. Si no encuentra dónde cambiarla, quite la cuenta y "
        "vuelva a agregarla.\n"
        "3. Si no reconoce ese celular o programa, o no tiene su correo configurado en ningún "
        "equipo, avise de inmediato a Tecnología respondiendo a este mensaje.",
        "Si no lo corrige, Tecnología desactivará el acceso a su correo desde ese celular o "
        f"programa hasta que quede arreglado. Su correo por la web{web} seguirá funcionando con "
        "normalidad.",
    ]
    if enlace_app.strip():
        parrafos.append(
            "También puede usar la aplicación de correo de la institución en su celular: "
            f"{enlace_app.strip()}"
        )
    parrafos.append("Si necesita ayuda, responda a este mensaje.")
    parrafos.append(FIRMA)
    return {"asunto": ASUNTO, "cuerpo": "\n\n".join(parrafos)}


def limpiar_asunto(asunto: str) -> str:
    """Una sola línea: un salto de línea en el asunto abriría una cabecera nueva."""
    return " ".join((asunto or "").split())[:LARGO_ASUNTO]


def limpiar_cuerpo(cuerpo: str) -> str:
    return (
        (cuerpo or "").replace("\r\n", "\n").replace("\r", "\n").strip()[:LARGO_CUERPO]
    )


def direccion(remitente: str) -> str:
    """'Tecnología <a@example.org>' -> 'a@example.org' (la dirección del sobre)."""
    return parseaddr(remitente or "")[1]


def componer(
    remitente: str, responder_a: str, destinatario: str, asunto: str, cuerpo: str
) -> EmailMessage:
    """El correo listo para entregar. Si el remitente no trae nombre, firma como Tecnología."""
    nombre, correo = parseaddr(remitente)
    mensaje = EmailMessage()
    mensaje["From"] = formataddr((nombre or FIRMA, correo))
    mensaje["To"] = destinatario
    if responder_a:
        mensaje["Reply-To"] = responder_a
    mensaje["Subject"] = limpiar_asunto(asunto)
    mensaje.set_content(limpiar_cuerpo(cuerpo) + "\n")
    return mensaje
