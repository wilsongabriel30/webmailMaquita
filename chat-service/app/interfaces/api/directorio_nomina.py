# -*- coding: utf-8 -*-
"""Traducir una ficha de NÓMINA a la cuenta del chat (N-25).

La lista de personas del chat sale de la tabla `trabajadores` de nómina, pero el chat no sabe
nada de nómina: conversaciones, no leídos y presencia van por `usuarios.id`. La versión anterior
devolvía el id de NÓMINA como si fuera el del chat, y no coinciden: con la lista llena se habría
escrito a la persona equivocada. Además filtraba por `estado = 'ACTIVO'` cuando en nómina el
valor está escrito `Activo`, así que la lista salía siempre vacía y el fallo no se notaba.

Aquí queda la parte que se puede razonar y probar sin base de datos: qué estado cuenta como
activo, qué correos son la misma persona y cómo se arma la lista con las cuentas resueltas.
"""
import os

# El buzón puede ser usuario@maquita.org y en nómina figurar usuario@maquita.com.ec (o al revés).
# Misma parte local en cualquiera de estos dominios = misma persona. Igual que en app_chat.
DOMINIOS_EQUIVALENTES = [
    d.strip().lower()
    for d in os.getenv("DOMINIOS_EQUIVALENTES",
                       "maquita.org,maquita.com.ec,fundacionmaquita.org").split(",")
    if d.strip()
]


def es_activo(estado) -> bool:
    """Nómina escribe «Activo»; hubo épocas con «ACTIVO» y con espacios de más."""
    return (estado or "").strip().upper() == "ACTIVO"


def correos_equivalentes(correo: str) -> list:
    """El correo dado y sus equivalentes institucionales, sin repetir y en minúsculas."""
    correo = (correo or "").strip().lower()
    if "@" not in correo:
        return []
    local, _, dominio = correo.partition("@")
    if not local:
        return []
    salida = [correo]
    if dominio in DOMINIOS_EQUIVALENTES:
        for d in DOMINIOS_EQUIVALENTES:
            if d != dominio:
                salida.append(f"{local}@{d}")
    return salida


def candidatos(filas) -> list:
    """Todos los correos a buscar de una vez, para no consultar la base fila por fila."""
    vistos = []
    for fila in filas:
        for c in correos_equivalentes(fila.get("email_institucional")):
            if c not in vistos:
                vistos.append(c)
    return vistos


def armar_lista(filas, cuentas: dict, usuario_actual, limite: int) -> list:
    """Convierte las fichas de nómina en entradas del chat, con el id de la CUENTA.

    `cuentas` es {correo en minúsculas: {"id": int, "nombre": str}}. Quien no tenga cuenta de
    usuario queda fuera: no se le puede escribir, y mostrarlo solo llevaría a un error. La
    persona que consulta tampoco aparece: no se chatea con uno mismo.
    """
    salida = []
    ya = set()
    for fila in filas:
        if not es_activo(fila.get("estado")):
            continue
        cuenta = None
        for correo in correos_equivalentes(fila.get("email_institucional")):
            if correo in cuentas:
                cuenta = cuentas[correo]
                break
        if not cuenta:
            continue
        uid = cuenta["id"]
        if usuario_actual is not None and str(uid) == str(usuario_actual):
            continue
        if uid in ya:
            continue
        ya.add(uid)
        nombre = (fila.get("nombre_completo") or "").strip() or cuenta.get("nombre") or ""
        salida.append({
            "id": uid,                                   # id de la CUENTA, no el de nómina
            "trabajador_id": fila.get("id"),             # se conserva por si hace falta trazar
            "name": nombre,
            "nombre_completo": nombre,
            "email": (fila.get("email_institucional") or "").strip().lower(),
            "role": fila.get("cargo"),
            "department": fila.get("departamento"),
            "departamento_nombre": fila.get("departamento"),
            "photo": fila.get("foto_url"),
            "foto_perfil": fila.get("foto_url"),
            "online": False,
        })
        if len(salida) >= limite:
            break
    return salida
