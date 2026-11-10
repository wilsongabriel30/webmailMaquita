"""Mantenimiento: borrar asignaciones de etiqueta que llevan más de 7 días faltantes (09/11/2026).

Una asignación se marca faltante cuando IMAP no devuelve su correo (ver etiquetas_faltantes.py). Si en
7 días no reaparece, el correo se borró o se movió desde otro cliente y la fila sobra. Se borra con registro
(cuántas, de qué cuentas) para poder explicar un contador que bajó.

Corre una vez al día en todo el clúster (bloqueo en Redis, app/escala/bloqueo.py) desde `bucle(app)`,
o a mano:  cd /opt/maquita-webmail/backend && venv/bin/python -m app.mail.services.etiquetas_huerfanas [--dias 7] [--simular]
"""

import asyncio
import logging

log = logging.getLogger("maquita.webmail.etiquetas")

DIAS_POR_DEFECTO = 7
INTERVALO_SEGUNDOS = 24 * 3600


async def purgar_faltantes(
    db, dias: int = DIAS_POR_DEFECTO, simular: bool = False
) -> int:
    """Borra las asignaciones con `faltante_desde` anterior a hoy − dias. Devuelve cuántas (o cuántas habría)."""
    if db is None:
        return 0
    dias = max(1, int(dias))
    filas = await db.fetch(
        """SELECT owner, COUNT(*) AS n FROM message_labels
           WHERE faltante_desde IS NOT NULL AND faltante_desde < now() - make_interval(days => $1)
           GROUP BY owner ORDER BY n DESC""",
        dias,
    )
    total = sum(f["n"] for f in filas)
    if not total:
        log.info("etiquetas huérfanas: nada que purgar (> %d días)", dias)
        return 0
    detalle = ", ".join(f"{f['owner']}={f['n']}" for f in filas[:20])
    if simular:
        log.info(
            "etiquetas huérfanas (simulación): se borrarían %d asignaciones: %s",
            total,
            detalle,
        )
        return total
    r = await db.execute(
        "DELETE FROM message_labels WHERE faltante_desde IS NOT NULL AND faltante_desde < now() - make_interval(days => $1)",
        dias,
    )
    log.info(
        "etiquetas huérfanas: borradas %s asignaciones faltantes > %d días: %s",
        str(r).split()[-1],
        dias,
        detalle,
    )
    return total


async def bucle(app) -> None:
    """Tarea de fondo: una purga diaria en todo el clúster."""
    from app.escala.bloqueo import una_vez_por_intervalo

    while True:
        try:
            await asyncio.sleep(15 * 60)  # no al arranque: que la app se asiente
            db = getattr(app.state, "db_pool", None)
            if not db:
                continue
            async with una_vez_por_intervalo(
                app.state.redis, "etiquetas:huerfanas", INTERVALO_SEGUNDOS - 60
            ) as turno:
                if turno.obtenido:
                    await purgar_faltantes(db)
            await asyncio.sleep(INTERVALO_SEGUNDOS - 15 * 60)
        except asyncio.CancelledError:
            break
        except Exception as e:  # la tarea no debe morir por un error puntual
            log.warning("etiquetas huérfanas: error en la pasada: %s", e)
            await asyncio.sleep(3600)


def _principal() -> None:
    import argparse

    import asyncpg

    from app.config import get_settings

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    ap = argparse.ArgumentParser(
        description="Borra asignaciones de etiqueta faltantes desde hace más de N días."
    )
    ap.add_argument("--dias", type=int, default=DIAS_POR_DEFECTO)
    ap.add_argument("--simular", action="store_true", help="solo informa; no borra")
    args = ap.parse_args()

    async def correr():
        con = await asyncpg.connect(get_settings().database_url)
        try:
            await purgar_faltantes(con, args.dias, args.simular)
        finally:
            await con.close()

    asyncio.run(correr())


if __name__ == "__main__":
    _principal()
