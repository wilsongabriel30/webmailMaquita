"""Registros DNS que el administrador de dominio ve pero no puede crear, cambiar ni borrar.

Son los que sostienen el correo del dominio (y su certificado): servidores de nombres, MX, SPF, DKIM,
DMARC, MTA-STS, TLS-RPT, autoconfiguración, los nombres del correo, TLSA, los SRV de correo y
calendario y CAA (una CAA mal puesta impide renovar el certificado del correo). Un cambio en
cualquiera de ellos deja al dominio sin correo o lo manda a otro servidor.
"""

TIPOS = {"NS", "SOA", "MX", "TLSA", "CAA"}
# Nombres (relativos a la zona) del correo; también protegen los que van debajo (_imaps._tcp…).
NOMBRES = {"mail", "imap", "smtp", "pop3", "webmail", "correo", "autoconfig", "autodiscover", "mta-sts",
           "_mta-sts", "_dmarc", "_smtp._tls"}
SRV_CORREO = ("_imap.", "_imaps.", "_pop3.", "_pop3s.", "_submission.", "_submissions.", "_smtp.",
              "_autodiscover.", "_caldav.", "_caldavs.", "_carddav.", "_carddavs.")


def nombre_relativo(nombre, zona):
    """Como lo guarda maquita-dns: «@» para la zona y sin el sufijo de la zona."""
    nombre = str(nombre or "@").strip().lower().rstrip(".") or "@"
    if nombre == zona:
        return "@"
    if nombre.endswith("." + zona):
        nombre = nombre[: -len(zona) - 1]
    return nombre


def es_protegido(registro, zona):
    tipo = str(registro.get("tipo", "")).upper()
    nombre = nombre_relativo(registro.get("nombre"), zona)
    valor = str(registro.get("valor", "")).strip().strip('"').lower()
    if tipo in TIPOS:
        return True
    if tipo == "TXT" and valor.startswith("v=spf1"):
        return True
    if nombre in NOMBRES or "_domainkey" in nombre.split("."):
        return True
    # Lo que cuelga de ellos con «_» (_25._tcp.mail, x._dmarc) también; «blog.mail» no: es otro nombre.
    if nombre.startswith("_") and any(nombre.endswith("." + p) for p in NOMBRES):
        return True
    return (nombre + ".").startswith(SRV_CORREO)


def marcar(datos, zona):
    """La respuesta de `maquita-dns ver` con "protegido" en cada registro."""
    for r in datos.get("registros", []):
        r["protegido"] = es_protegido(r, zona)
    return datos
