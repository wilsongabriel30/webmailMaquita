"""Correo propio verificado: remitente de un dominio de la casa que llegó por un camino de confianza.

Caso real (14/09/2026): direccion@maquita.com.ec escribió a gerencia@maquitaturismo.com y el
correo cayó en Junk por «exceso-links(16)(+3)»: una firma con muchos enlaces bastó para llegar
al umbral (3) aunque la red neuronal dijera «ham 0,99». El correo venía de nuestro propio
Zimbra (193.16.0.18): no era un desconocido.

Aquí se decide si un correo es «propio verificado»: el dominio del remitente es de la casa Y
llegó por un relé interno de confianza, o por una sesión autenticada (ESMTPSA). Con eso el
filtro le aplica el mismo descuento que a un dominio de confianza (no lo exime: un correo
propio con virus o palabras de estafa sigue puntuando).

Ojo: la cabecera From no está autenticada. Por eso NO basta con que el dominio sea propio;
hace falta además el camino de confianza. Un externo que escriba «From: direccion@maquita.com.ec»
entra por internet, no por el relé, y no recibe el descuento (además rspamd lo rechaza por
anti-spoofing).

Listas (una entrada por línea, «#» comenta):
  /etc/maquita-mail/dominios-propios.txt   dominios de la casa (si falta, se usan los conocidos)
  /etc/maquita-mail/reles-confianza.txt    IPs o redes CIDR de relés internos (si falta, Zimbra y este servidor)
"""

import ipaddress
import re

DOMINIOS_PROPIOS_PATH = "/etc/maquita-mail/dominios-propios.txt"
RELES_CONFIANZA_PATH = "/etc/maquita-mail/reles-confianza.txt"

DOMINIOS_POR_OMISION = (
    "maquita.org", "maquita.com.ec", "mcch.com.ec", "fundmcch.com.ec",
    "maquitaturismo.com", "invertiagro.com", "maquitaagro.com", "maquitaagro.com.ec",
    "alimentaelcambio.com.ec", "relacc-la.org", "productoresdema.com",
)
RELES_POR_OMISION = ("193.16.0.18", "193.16.0.21", "127.0.0.1")

RAZON = "propio-verificado"


def _leer_lista(ruta, por_omision):
    try:
        with open(ruta, encoding="utf-8") as fh:
            valores = [l.strip().lower() for l in fh if l.strip() and not l.lstrip().startswith("#")]
        return valores or list(por_omision)
    except Exception:
        return list(por_omision)


def es_dominio_propio(sender_domain, dominios=None):
    d = (sender_domain or "").strip().lower()
    if not d:
        return False
    for propio in dominios or _leer_lista(DOMINIOS_PROPIOS_PATH, DOMINIOS_POR_OMISION):
        if d == propio or d.endswith("." + propio):
            return True
    return False


def ip_en_reles(ip, reles=None):
    if not ip:
        return False
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entrada in reles or _leer_lista(RELES_CONFIANZA_PATH, RELES_POR_OMISION):
        try:
            if "/" in entrada:
                if direccion in ipaddress.ip_network(entrada, strict=False):
                    return True
            elif direccion == ipaddress.ip_address(entrada):
                return True
        except ValueError:
            continue
    return False


_AUTENTICADO = re.compile(r"\bwith\s+ESMTPSA\b|\(Authenticated sender:", re.IGNORECASE)


def llego_autenticado(msg):
    """Alguna cabecera Received de ESTE servidor dice que el remitente se autenticó."""
    try:
        for recibido in msg.get_all("Received", []) or []:
            if _AUTENTICADO.search(str(recibido)[:600]):
                return True
    except Exception:
        pass
    return False


def es_correo_propio_verificado(sender_domain, sender_ip, msg):
    """(True, razón) si el remitente es de la casa y llegó por relé interno o autenticado."""
    if not es_dominio_propio(sender_domain):
        return False, ""
    if ip_en_reles(sender_ip):
        return True, f"{RAZON}:rele({sender_ip})"
    if llego_autenticado(msg):
        return True, f"{RAZON}:autenticado"
    return False, ""
