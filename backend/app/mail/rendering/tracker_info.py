"""
Catálogo de servicios de rastreo de correo y detección en mensajes.

PARA QUÉ
--------
Complementa a `link_unwrap.py`. Aquel **quita** el rastreador cuando puede;
este **informa** de lo que queda, para que el usuario sepa qué está pasando.

Hay servicios cuyos enlaces NO se pueden limpiar porque usan identificadores
opacos: el destino real solo lo conoce el servidor del tercero (Mailchimp,
HubSpot...). En esos casos el enlace debe dejarse intacto —romperlo sería
peor—, pero sí conviene avisar al usuario:

  · Si es **publicidad**  → ofrecerle marcarlo como spam.
  · Si es **transaccional** (una factura, una clave) → decirle que el enlace
    pasa por un intermediario y que compruebe el destino antes de entrar.

CLASIFICACIÓN
-------------
- "publicidad"    : plataformas de marketing y boletines masivos.
- "transaccional" : envíos operativos (claves, facturas, confirmaciones).

La distinción importa: NO se debe sugerir marcar como spam un correo
transaccional, porque el usuario puede estar esperándolo.

Ver: 07-INCIDENTES/20260824-zimbra-comprometido-cryptominer-devshm.md y
     03-INFRAESTRUCTURA/RED-MIKROTIK/fix-dns-bloqueaba-awstrack-enlaces-correo-20260824.md
"""

from typing import List, Dict

# dominio_marca -> (nombre visible, tipo, se_puede_desenvolver)
# Para añadir un servicio: una línea aquí. Si además se puede desenvolver,
# hay que sumar su función en link_unwrap.py y poner True.
CATALOGO = {
    # --- Transaccionales (SÍ se desenvuelven) ---
    "awstrack.me":      ("Amazon SES",       "transaccional", True),
    "pstmrk.it":        ("Postmark",         "transaccional", True),

    # --- Transaccionales (NO se pueden desenvolver: identificador opaco) ---
    "sendgrid.net":     ("SendGrid",         "transaccional", False),
    "mailgun.org":      ("Mailgun",          "transaccional", False),
    "sparkpostmail.com":("SparkPost",        "transaccional", False),

    # --- Publicidad / marketing (NO se pueden desenvolver) ---
    "list-manage.com":  ("Mailchimp",        "publicidad",    False),
    "mailchi.mp":       ("Mailchimp",        "publicidad",    False),
    "hubspotlinks.com": ("HubSpot",          "publicidad",    False),
    "rs6.net":          ("Constant Contact", "publicidad",    False),
    "klclick.com":      ("Klaviyo",          "publicidad",    False),
    "sendibm1.com":     ("Brevo",            "publicidad",    False),
    "activehosted.com": ("ActiveCampaign",   "publicidad",    False),
}


def detectar_rastreadores(html: str) -> List[Dict]:
    """
    Devuelve los servicios de rastreo presentes en el HTML.

    Cada elemento: {"servicio": str, "tipo": str, "desenvolvible": bool}
    Lista vacía si no hay ninguno. Nunca lanza excepciones.

    Se llama DESPUÉS de desenvolver, así que lo que aparezca aquí es lo que
    NO se pudo limpiar (salvo que el correo mezcle varios servicios).
    """
    if not html or not isinstance(html, str):
        return []

    encontrados = {}
    try:
        for marca, (nombre, tipo, desenvolvible) in CATALOGO.items():
            if marca in html:
                # Se agrupa por nombre: un mismo servicio puede aparecer con
                # varios dominios (p. ej. Mailchimp).
                encontrados[nombre] = {
                    "servicio": nombre,
                    "tipo": tipo,
                    "desenvolvible": desenvolvible,
                }
    except Exception:
        return []

    return list(encontrados.values())


def resumen_para_usuario(rastreadores: List[Dict]) -> Dict:
    """
    Traduce la detección a algo que la interfaz pueda mostrar directamente.

    Devuelve:
      {
        "hay_rastreo": bool,
        "es_publicidad": bool,      # sugerir marcar como spam
        "servicios": ["Mailchimp", ...],
        "mensaje": "texto ya redactado para el usuario"
      }
    """
    if not rastreadores:
        return {"hay_rastreo": False, "es_publicidad": False,
                "servicios": [], "mensaje": ""}

    servicios = sorted({r["servicio"] for r in rastreadores})
    es_publicidad = any(r["tipo"] == "publicidad" for r in rastreadores)
    lista = ", ".join(servicios)

    if es_publicidad:
        mensaje = (
            f"Los enlaces de este correo pasan por {lista}, una plataforma de "
            "envíos publicitarios que registra quién hace clic. "
            "Si no esperabas este correo, puedes marcarlo como spam para no "
            "volver a recibirlo."
        )
    else:
        mensaje = (
            f"Los enlaces de este correo pasan por {lista} antes de llevarte "
            "al destino real. Comprueba a dónde te dirige antes de entrar, "
            "sobre todo si te pide contraseñas o datos bancarios."
        )

    return {"hay_rastreo": True, "es_publicidad": es_publicidad,
            "servicios": servicios, "mensaje": mensaje}
