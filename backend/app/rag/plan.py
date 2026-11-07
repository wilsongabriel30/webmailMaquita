"""Decisiones puras (sin IMAP ni BD) de la indexación incremental, para poder probarlas.

Un UID solo es único dentro de una carpeta y mientras no cambie su UIDVALIDITY.
"""

import time
from dataclasses import dataclass, field

SALTAR, REINICIAR, REVISAR = "saltar", "reiniciar", "revisar"


def accion(guardado: dict | None, actual: dict, formato: int) -> str:
    """Qué hacer con una carpeta según lo visto la última vez (`guardado`) y ahora (`actual`)."""
    if not guardado:
        return REVISAR
    if (
        guardado.get("uidvalidity") is not None
        and actual.get("uidvalidity") is not None
        and int(guardado["uidvalidity"]) != int(actual["uidvalidity"])
    ):
        return REINICIAR
    if (
        guardado.get("completa")
        and int(guardado.get("formato") or 0) >= formato
        and guardado.get("uidnext") == actual.get("uidnext")
        and int(guardado.get("mensajes") or 0) == int(actual.get("mensajes") or 0)
    ):
        return SALTAR
    return REVISAR


def pendientes(uids_servidor, indexados: dict[int, int], formato: int):
    """-> (por_indexar, a_borrar).

    por_indexar: primero los que nunca se indexaron y después los de un formato anterior,
    cada grupo del más reciente (UID mayor) al más antiguo. a_borrar: indexados que ya no
    están en la carpeta (borrados o movidos; si fueron a otra carpeta, allí se indexan).
    """
    en_servidor = set(uids_servidor)
    nuevos = sorted(en_servidor - indexados.keys(), reverse=True)
    viejos = sorted(
        (u for u, f in indexados.items() if u in en_servidor and f < formato),
        reverse=True,
    )
    a_borrar = sorted(set(indexados) - en_servidor)
    return nuevos + viejos, a_borrar


@dataclass
class Presupuesto:
    """Límite de una ejecución: correos (0 = sin límite) y hora tope (0 = sin tope)."""

    limite: int = 0
    hasta: float = 0.0
    usados: int = 0
    _reloj: object = field(default=time.monotonic, repr=False)

    @classmethod
    def con_minutos(cls, limite: int = 0, minutos: float = 0, reloj=time.monotonic):
        return cls(
            limite=limite,
            hasta=(reloj() + minutos * 60) if minutos > 0 else 0.0,
            _reloj=reloj,
        )

    def vencido(self) -> bool:
        return bool(self.hasta) and self._reloj() >= self.hasta

    def restante(self) -> int | None:
        """Correos que aún caben (None = sin límite de cantidad)."""
        if not self.limite:
            return None
        return max(0, self.limite - self.usados)

    def agotado(self) -> bool:
        r = self.restante()
        return self.vencido() or (r is not None and r <= 0)

    def consumir(self, n: int = 1) -> None:
        self.usados += n


def cupo(presupuesto: Presupuesto, limite_buzon: int, usados_buzon: int) -> int | None:
    """Cuántos correos más puede indexar este buzón en esta ejecución (None = sin límite)."""
    opciones = []
    if limite_buzon:
        opciones.append(max(0, limite_buzon - usados_buzon))
    r = presupuesto.restante()
    if r is not None:
        opciones.append(r)
    return min(opciones) if opciones else None
