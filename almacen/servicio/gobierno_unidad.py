# -*- coding: utf-8 -*-
"""Gobierno de una unidad compartida (F-11, tercera revisión).

Una unidad no puede quedarse sin manager: degradar o quitar al último (incluido uno
mismo) se rechaza. La comprobación y el cambio van en UNA transacción con las membresías
de la unidad bloqueadas (FOR UPDATE), para que dos peticiones simultáneas no dejen la
unidad huérfana. Módulo sin Flask: recibe el `conexion()` del almacén.
"""


class UltimoManager(Exception):
    """La operación dejaría la unidad sin ningún manager."""


def managers_restantes(miembros: dict, excepto: int) -> int:
    """Cuántos managers quedarían sin contar a `excepto`."""
    return sum(1 for uid, rol in miembros.items() if rol == "manager" and uid != excepto)


def _miembros_bloqueados(cur, unidad_id: int) -> dict:
    cur.execute("SELECT usuario_id, rol FROM unidad_miembros WHERE unidad_id = %s FOR UPDATE", (unidad_id,))
    return {int(f[0]): f[1] for f in cur.fetchall()}


def asignar_rol(conexion, unidad_id: int, usuario_id: int, rol: str) -> None:
    """Agrega o cambia el rol de un miembro. Lanza UltimoManager si degradaría al último."""
    with conexion() as con, con.cursor() as cur:
        actuales = _miembros_bloqueados(cur, unidad_id)
        if rol != "manager" and actuales.get(usuario_id) == "manager":
            if managers_restantes(actuales, excepto=usuario_id) == 0:
                raise UltimoManager()
        cur.execute(
            """INSERT INTO unidad_miembros (unidad_id, usuario_id, rol) VALUES (%s, %s, %s)
               ON CONFLICT (unidad_id, usuario_id) DO UPDATE SET rol = EXCLUDED.rol""",
            (unidad_id, usuario_id, rol),
        )


def quitar(conexion, unidad_id: int, usuario_id: int) -> None:
    """Quita a un miembro. Lanza UltimoManager si era el último manager."""
    with conexion() as con, con.cursor() as cur:
        actuales = _miembros_bloqueados(cur, unidad_id)
        if actuales.get(usuario_id) == "manager" and managers_restantes(actuales, excepto=usuario_id) == 0:
            raise UltimoManager()
        cur.execute("DELETE FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s", (unidad_id, usuario_id))
