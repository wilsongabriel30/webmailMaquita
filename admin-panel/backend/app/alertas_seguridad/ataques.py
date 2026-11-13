"""Detección del ataque lento a contraseñas, a partir de los accesos ya recogidos.

Función pura (sin base de datos): recibe filas de seg_accesos_detalle y devuelve, por cuenta, las
direcciones que fallaron la contraseña y nunca acertaron. Con tres o más direcciones distintas se
considera que alguien intenta adivinar la contraseña de esa cuenta.
"""

MIN_DIRECCIONES = 3
HORAS = 48  # ventana que mira la pantalla de alertas
LOCALES = ("127.0.0.1", "::1")


def agrupar(filas) -> list[dict]:
    """filas: iterables con cuenta, ip, pais, servicio, ok, fallos, hora. Devuelve los ataques, el más reciente primero."""
    aciertos: dict[str, set] = {}
    fallos: dict[str, dict] = {}
    for f in filas:
        cuenta, ip = (f["cuenta"] or "").lower(), f["ip"]
        if not cuenta or ip in LOCALES:
            continue
        if f["ok"]:
            aciertos.setdefault(cuenta, set()).add(ip)
        if f["fallos"]:
            d = fallos.setdefault(cuenta, {}).setdefault(
                ip,
                {
                    "ip": ip,
                    "pais": f["pais"] or "",
                    "intentos": 0,
                    "ultimo": f["hora"],
                    "servicios": set(),
                },
            )
            d["intentos"] += f["fallos"]
            d["ultimo"] = max(d["ultimo"], f["hora"])
            d["servicios"].add(f["servicio"])
    ataques = []
    for cuenta, por_ip in fallos.items():
        buenas = aciertos.get(cuenta, set())
        direcciones = [d for ip, d in por_ip.items() if ip not in buenas]
        if len(direcciones) < MIN_DIRECCIONES:
            continue
        direcciones.sort(key=lambda d: d["ultimo"], reverse=True)
        servicios = sorted({s for d in direcciones for s in d["servicios"]})
        for d in direcciones:
            d["servicios"] = sorted(d["servicios"])
        ataques.append(
            {
                "cuenta": cuenta,
                "direcciones": direcciones,
                "intentos": sum(d["intentos"] for d in direcciones),
                "paises": sorted({d["pais"] for d in direcciones if d["pais"]}),
                "servicios": servicios,
                "ultimo": direcciones[0]["ultimo"],
            }
        )
    ataques.sort(key=lambda a: a["ultimo"], reverse=True)
    return ataques


def explicar(
    ataque: dict,
    existe: bool,
    protegida: bool,
    usa_equipos: bool,
    claves_aplicacion: int,
    pais_propio: str = "EC",
) -> dict:
    """Texto llano para el administrador: qué pasa, qué se sugiere y si procede el botón de proteger."""
    n, intentos = len(ataque["direcciones"]), ataque["intentos"]
    # «LAN» es la red interna de la institución: no es un origen del exterior.
    fuera = [
        p for p in ataque["paises"] if p.upper() not in (pais_propio.upper(), "LAN")
    ]
    por = " y ".join(s.upper() for s in ataque["servicios"]) or "el correo"
    que = (
        f"Hubo {intentos} intentos fallidos de entrar por {por} desde {n} direcciones distintas. "
        "Ninguna de esas direcciones ha entrado nunca a la cuenta: no acertaron la contraseña."
    )
    if not existe:
        return {
            "gravedad": "media",
            "que_pasa": que + " La cuenta no existe: están probando nombres al azar.",
            "sugerencia": "No hace falta proteger nada. Puede bloquear las direcciones en Cortafuegos.",
            "accion": "",
        }
    if protegida:
        return {
            "gravedad": "resuelta",
            "que_pasa": que,
            "sugerencia": "La cuenta ya está protegida: desde fuera la contraseña no sirve aunque la adivinen.",
            "accion": "",
        }
    if not fuera:
        return {
            "gravedad": "media",
            "que_pasa": que
            + " Todas son del país o de la red interna: puede ser un celular u Outlook de la propia "
            "persona con una contraseña vieja guardada.",
            "sugerencia": "Pregunte a la persona antes de actuar. Si no reconoce esos equipos, proteja la cuenta.",
            "accion": "proteger",
        }
    if usa_equipos and claves_aplicacion == 0:
        return {
            "gravedad": "alta",
            "que_pasa": que,
            "sugerencia": "Se sugiere cerrar IMAP y SMTP en esta cuenta. Ojo: la persona usa Outlook o celular; al "
            "protegerla esos equipos dejarán de funcionar hasta que cree una contraseña de aplicación.",
            "accion": "proteger",
        }
    return {
        "gravedad": "alta",
        "que_pasa": que,
        "sugerencia": "Se sugiere cerrar IMAP y SMTP en esta cuenta. La persona no notará nada: solo usa el webmail.",
        "accion": "proteger",
    }
