"""Reglas de anomalía en el acceso a los buzones: simples, explicables y probadas con datos sintéticos.

Cada regla recibe eventos (o filas ya agregadas) y lo que se sabe de cada cuenta, y devuelve
hallazgos con una frase que entiende cualquiera («La cuenta nunca había entrado desde Brasil»).
Nada de aprendizaje automático: si una alerta salta, el administrador puede ver exactamente por qué.

  pais_nuevo         acceso correcto desde un país del que la cuenta nunca había entrado.
  fallos_y_exito     varios fallos seguidos de un acceso correcto (clave adivinada o filtrada).
  hora_inusual       acceso al webmail o al panel a una hora en la que la cuenta casi nunca entra.
  muchas_cuentas_ip  una misma IP prueba muchas cuentas distintas (ataque de diccionario o rociado).

La red interna («LAN») y las IP desconocidas («--») no cuentan como país.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, tzinfo

from .parseo import EventoAcceso

SIN_PAIS = ("", "LAN", "--")
SERVICIOS_INTERACTIVOS = ("webmail", "panel")  # los teléfonos e IMAP sincronizan a cualquier hora


@dataclass
class Hallazgo:
    regla: str
    severidad: str
    descripcion: str
    huella: str
    momento: datetime
    cuenta: str = ""
    ip: str = ""
    pais: str = ""
    servicio: str = ""
    detalles: dict = field(default_factory=dict)


def _pais(e) -> str:
    return e.pais if e.pais not in SIN_PAIS else ""


def regla_pais_nuevo(eventos, paises_conocidos: dict) -> list:
    """`paises_conocidos`: {cuenta: set(países)}; se actualiza con lo visto (aprendizaje).

    Una cuenta sin ningún país conocido solo aprende (no alerta): la primera vez que el recolector la
    ve no hay con qué comparar."""
    hallazgos = []
    for e in sorted(eventos, key=lambda x: x.momento):
        pais = _pais(e)
        if e.resultado != "ok" or not e.cuenta or not pais:
            continue
        conocidos = paises_conocidos.setdefault(e.cuenta, set())
        if conocidos and pais not in conocidos:
            hallazgos.append(Hallazgo(
                "pais_nuevo", "media",
                f"La cuenta {e.cuenta} entró por {e.servicio} desde un país nuevo ({pais}); "
                f"hasta ahora solo desde {', '.join(sorted(conocidos))}.",
                f"pais_nuevo:{e.cuenta}:{pais}", e.momento, e.cuenta, e.ip, pais, e.servicio,
                {"paises_conocidos": sorted(conocidos)}))
        conocidos.add(pais)
    return hallazgos


def regla_fallos_y_exito(fallos_previos, eventos, umbral: int, ventana_min: int) -> tuple:
    """Por cuenta: `umbral` fallos o más dentro de la ventana y, después, un acceso correcto.

    `fallos_previos`: fallos de pasadas anteriores aún dentro de la ventana (la ventana cruza
    pasadas del recolector). Devuelve (hallazgos, fallos que hay que conservar para la próxima)."""
    ventana = timedelta(minutes=ventana_min)
    todos = sorted(list(fallos_previos) + list(eventos), key=lambda x: x.momento)
    recientes: dict = defaultdict(list)  # cuenta → [(momento, veces, ip)]
    hallazgos, ya = [], set()
    for e in todos:
        if not e.cuenta:
            continue
        lista = recientes[e.cuenta]
        while lista and e.momento - lista[0][0] > ventana:
            lista.pop(0)
        if e.resultado == "fallo":
            lista.append((e.momento, e.veces, e.ip))
            continue
        total = sum(v for _, v, _ in lista)
        if total >= umbral and e.cuenta not in ya:
            ips = sorted({ip for _, _, ip in lista if ip})
            hallazgos.append(Hallazgo(
                "fallos_y_exito", "alta",
                f"La cuenta {e.cuenta} tuvo {total} intentos fallidos en {ventana_min} min y luego entró "
                f"correctamente por {e.servicio} desde {e.ip or 'IP desconocida'}: la clave pudo ser adivinada.",
                f"fallos_y_exito:{e.cuenta}:{e.momento:%Y%m%d%H}", e.momento, e.cuenta, e.ip, e.pais, e.servicio,
                {"fallos": total, "ips_de_los_fallos": ips[:20], "ventana_min": ventana_min}))
            ya.add(e.cuenta)
        lista.clear()  # tras un acceso correcto la cuenta vuelve a empezar
    if todos:
        limite = todos[-1].momento - ventana
        conservar = [(c, m, v, ip) for c, lista in recientes.items() for m, v, ip in lista if m >= limite]
    else:
        conservar = []
    fallos = [EventoAcceso(m, "", "fallo", c, ip, v) for c, m, v, ip in conservar]
    return hallazgos, fallos


def regla_hora_inusual(eventos, histograma: dict, zona: tzinfo, minimo: int, porcentaje_max: int) -> list:
    """Acceso correcto al webmail o al panel, desde fuera de la red interna, a una hora (± 1 h) en la
    que la cuenta tiene menos del `porcentaje_max` % de sus accesos. Solo con historial suficiente
    (`minimo` accesos). `histograma`: {cuenta: [24 contadores por hora local]}; se actualiza."""
    hallazgos, ya = [], set()
    for e in sorted(eventos, key=lambda x: x.momento):
        if e.resultado != "ok" or not e.cuenta or e.servicio not in SERVICIOS_INTERACTIVOS:
            continue
        hora = e.momento.astimezone(zona).hour
        horas = histograma.setdefault(e.cuenta, [0] * 24)
        total = sum(horas)
        cerca = horas[(hora - 1) % 24] + horas[hora] + horas[(hora + 1) % 24]
        clave = (e.cuenta, e.momento.astimezone(zona).date())
        if e.pais != "LAN" and total >= minimo and cerca * 100 < porcentaje_max * total and clave not in ya:
            ya.add(clave)
            hallazgos.append(Hallazgo(
                "hora_inusual", "baja",
                f"La cuenta {e.cuenta} entró al {e.servicio} a las {hora:02d}:00, hora en la que casi nunca "
                f"entra ({cerca} de {total} accesos entre las {(hora - 1) % 24:02d} y las {(hora + 1) % 24:02d}:59).",
                f"hora_inusual:{e.cuenta}:{clave[1]:%Y%m%d}", e.momento, e.cuenta, e.ip, e.pais, e.servicio,
                {"hora_local": hora, "accesos_cerca": cerca, "accesos_total": total}))
        horas[hora] += 1
    return hallazgos


def regla_muchas_cuentas_ip(filas, umbral: int, ahora: datetime) -> list:
    """`filas`: [{"ip", "pais", "cuentas", "ok", "fallos"}] de la última hora (agregado en SQL).

    Alta si además alguna de esas cuentas entró correctamente desde esa IP; si no, media."""
    hallazgos = []
    for f in filas:
        if not f.get("ip") or f.get("pais") == "LAN" or int(f.get("cuentas") or 0) < umbral:
            continue
        exito = int(f.get("ok_cuentas") or 0) > 0
        hallazgos.append(Hallazgo(
            "muchas_cuentas_ip", "alta" if exito else "media",
            f"La IP {f['ip']} ({f.get('pais') or 'país desconocido'}) probó {f['cuentas']} cuentas distintas en la "
            f"última hora ({f.get('fallos', 0)} fallos)" + (
                f" y entró en {f['ok_cuentas']} de ellas." if exito else "; ninguna entró."),
            f"muchas_cuentas_ip:{f['ip']}:{ahora:%Y%m%d%H}", ahora, "", f["ip"], f.get("pais") or "", "",
            {"cuentas": int(f["cuentas"]), "fallos": int(f.get("fallos") or 0),
             "cuentas_con_acceso": int(f.get("ok_cuentas") or 0)}))
    return hallazgos
