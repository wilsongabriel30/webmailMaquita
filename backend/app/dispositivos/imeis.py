"""IMEI de un teléfono (uno por ranura: doble SIM y eSIM dan 2, 3 o 4). Validación y unión.

Sirven para bloquear el equipo en la operadora si lo roban o lo pierden. Los manda la app cuando puede
leerlos (control completo) o los escribe la persona (*#06#) o Tecnología. 14-17 dígitos; si son 15 se
exige el dígito de control de Luhn para atrapar errores de tecleo.
"""

import json
import re

MAXIMO = 4


def valido(imei: str) -> bool:
    imei = (imei or "").strip()
    if not re.fullmatch(r"\d{14,17}", imei):
        return False
    if len(imei) != 15:
        return True
    total = 0
    for i, c in enumerate(imei):
        n = int(c)
        if i % 2 == 1:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def normalizar(valores) -> list[str]:
    """Lista limpia, sin repetidos, máximo 4; descarta los inválidos. Acepta lista, JSON o texto con comas."""
    if valores is None:
        return []
    if isinstance(valores, str):
        try:
            valores = json.loads(valores) if valores.strip().startswith("[") else re.split(r"[,\s;]+", valores)
        except ValueError:
            valores = re.split(r"[,\s;]+", valores)
    salida: list[str] = []
    for v in valores:
        v = re.sub(r"\D", "", str(v or ""))
        if v and valido(v) and v not in salida:
            salida.append(v)
    return salida[:MAXIMO]


def unir(actuales, nuevos) -> list[str]:
    """Los nuevos primero (lo que reporta el teléfono es la verdad), conservando los que ya había."""
    lista = normalizar(nuevos)
    for v in normalizar(actuales):
        if v not in lista and len(lista) < MAXIMO:
            lista.append(v)
    return lista


async def ajenos(db, equipo_id: int | None, lista: list[str]) -> list[str]:
    """IMEI de la lista que ya pertenecen a OTRO equipo registrado (no dado de baja)."""
    if not lista:
        return []
    filas = await db.fetch(
        "SELECT DISTINCT i FROM disp_equipos e, jsonb_array_elements_text(e.imeis) AS i "
        "WHERE e.estado <> 'baja' AND ($1::int IS NULL OR e.id <> $1) AND i = ANY($2::text[])",
        equipo_id, lista,
    )
    return [f["i"] for f in filas]


def origenes(actuales, nuevos: list[str], origen: str) -> dict:
    """Mapa imei → origen ('sistema' leído por Android, 'persona' escrito a mano, 'tecnologia' panel).
    Lo que reporta el sistema manda: si un IMEI ya estaba como 'persona' y ahora llega del sistema, pasa a 'sistema'."""
    if isinstance(actuales, str):
        try:
            actuales = json.loads(actuales)
        except ValueError:
            actuales = {}
    mapa = dict(actuales or {})
    for v in nuevos:
        if origen == "sistema" or v not in mapa:
            mapa[v] = origen
    return mapa
