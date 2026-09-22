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
