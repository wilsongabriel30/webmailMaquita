"""Alcance de las fichas de API del panel general («mqa_…»): qué puede pedir una ficha según el método y la ruta.

Sin dependencias del resto del panel (las pruebas lo cargan suelto). Una ficha lleva una lista de alcances:
  «lectura»   ver (GET) en las áreas de AREAS
  <área>      además, cambiar en esa área (cualquier método)

Falla cerrado: lo que no está en AREAS no se puede pedir con una ficha, ni para ver. Así quedan fuera, entre otras,
la propia cuenta y el segundo factor (/api/auth, /api/segundo-factor), los administradores (/api/admin…), las fichas
(/api/fichas-api), leer o recuperar correo ajeno (/api/mailviewer, /api/recovery, /api/quarantine, /api/ediscovery…),
el cortafuegos del servidor y las actualizaciones. Además, la ficha no lleva segundo factor: lo que lo exige en la
interfaz (p. ej. entrar a un buzón) sigue sin poderse hacer con ella.
"""

PREFIJO = "mqa_"
AREAS = {
    "dominios": ("Dominios", ("/api/domains", "/api/dominio-nuevo", "/api/dnscheck")),
    "buzones": ("Buzones, firmas y respuestas automáticas", ("/api/mailboxes", "/api/shared", "/api/signatures",
                                                              "/api/autoresponder")),
    "alias": ("Alias", ("/api/aliases",)),
    "reenvios": ("Reenvíos", ("/api/forwarding",)),
    "grupos": ("Grupos y listas", ("/api/groups",)),
    "dns": ("Zonas DNS", ("/api/dns",)),
    "sitios": ("Sitios web", ("/api/sitios",)),
    "cola": ("Cola y seguimiento de envíos", ("/api/queue", "/api/tracking", "/api/resend")),
    "respaldos": ("Respaldos", ("/api/respaldos",)),
    "estado": ("Estado del servidor y servicios", ("/api/health", "/api/dashboard", "/api/services", "/api/connections")),
}
ALCANCES = ("lectura", *AREAS)
LECTURA = ("GET", "HEAD")
DIAS_MAXIMOS = 365
MAXIMO_POR_CUENTA = 10


def area_de(ruta: str) -> str | None:
    for area, (_titulo, prefijos) in AREAS.items():
        if any(ruta == p or ruta.startswith(p + "/") for p in prefijos):
            return area
    return None


def permitido(alcances, metodo: str, ruta: str) -> bool:
    if not isinstance(alcances, (list, tuple)) or ".." in ruta or "//" in ruta:
        return False
    if ruta == "/api/auth/me" and metodo in LECTURA:
        return True  # quién soy: lo mínimo para usar la API
    area = area_de(ruta)
    if area is None:
        return False
    if metodo in LECTURA:
        return "lectura" in alcances or area in alcances
    return area in alcances


def validar_alcances(valor) -> list[str] | None:
    if not isinstance(valor, list) or not valor or len(valor) > len(ALCANCES):
        return None
    if any(not isinstance(a, str) or a not in ALCANCES for a in valor):
        return None
    return [a for a in ALCANCES if a in valor]
