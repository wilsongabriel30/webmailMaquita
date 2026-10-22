"""Alcance de las fichas de API del portal: qué puede pedir una ficha según el método y la ruta. Sin base de datos.

Una ficha lleva una lista de alcances:
  «lectura»                         ver (GET) en las áreas de abajo
  «cuentas», «alias», «reenvios»,   además, cambiar en esa área (cualquier método)
  «grupos», «dns», «sitios»

Lo que no está en AREAS no se puede pedir con una ficha, ni para ver (falla cerrado). Nunca, con ninguna ficha: la
propia cuenta (contraseña, segundo factor, sesiones) ni las fichas de API (una ficha no crea otras ni se renueva
sola). El intermediario de los sitios vuelve a comprobar el alcance de cada orden (deploy/sitios/portal/lib/fichas.py).
"""

PREFIJO = "mqd_"
AREAS = {
    "cuentas": "Cuentas de correo",
    "alias": "Alias",
    "reenvios": "Reenvíos",
    "grupos": "Grupos y listas",
    "dns": "Zonas DNS",
    "sitios": "Sitios web",
}
ALCANCES = ("lectura", *AREAS)
# Prefijo de la ruta → área (el más largo primero). «resumen» solo se puede ver.
_RUTAS = (
    ("/api/sitios/dns", "dns"),
    ("/api/sitios", "sitios"),
    ("/api/dns", "dns"),
    ("/api/cuentas", "cuentas"),
    ("/api/asignaciones", "cuentas"),
    ("/api/alias", "alias"),
    ("/api/reenvios", "reenvios"),
    ("/api/grupos", "grupos"),
    ("/api/resumen", "resumen"),
)
LECTURA = ("GET", "HEAD")
DIAS_MAXIMOS = 365
MAXIMO_POR_CUENTA = 10


def area_de(ruta: str) -> str | None:
    for prefijo, area in _RUTAS:
        if ruta == prefijo or ruta.startswith(prefijo + "/"):
            return area
    return None


def permitido(alcances, metodo: str, ruta: str) -> bool:
    if not isinstance(alcances, (list, tuple)) or ".." in ruta or "//" in ruta:
        return False
    if ruta == "/api/acceso/yo" and metodo in LECTURA:
        return True  # quién soy y qué dominios tengo: lo mínimo para usar la API
    area = area_de(ruta)
    if area is None:
        return False
    if metodo in LECTURA:
        return "lectura" in alcances or area in alcances
    return area in AREAS and area in alcances


def validar_alcances(valor) -> list[str] | None:
    """Lista limpia (en el orden de ALCANCES) o None si no vale."""
    if not isinstance(valor, list) or not valor or len(valor) > len(ALCANCES):
        return None
    if any(not isinstance(a, str) or a not in ALCANCES for a in valor):
        return None
    return [a for a in ALCANCES if a in valor]
