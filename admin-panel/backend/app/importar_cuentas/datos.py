"""Lo que la importación de cuentas necesita de la base (panel general): dominios, direcciones
ocupadas y el alta de cada cuenta con sus alias en una sola transacción."""

import logging

log = logging.getLogger("admin")


async def enrutados(db, dominios: list[str]) -> set[str]:
    """Dominios cuyo correo se entrega en otro servidor. Sin la migración aplicada, ninguno."""
    try:
        filas = await db.fetch(
            "SELECT dominio FROM enrutamiento_correo WHERE activo AND dominio = ANY($1::varchar[])", dominios)
    except Exception as e:  # tabla aún sin crear (migración 2026-10-21-enrutamiento-correo.sql)
        log.warning("importar cuentas: sin tabla de enrutamiento (%s)", type(e).__name__)
        return set()
    return {f["dominio"] for f in filas}


async def dominios_info(db, dominios: list[str]) -> dict:
    """Datos de cada dominio que aparece en el archivo y existe en el servidor.

    En el panel general no hay tope de cuota si el dominio no lo fija (maxquota = 0); la cuota por
    defecto es la máxima del dominio o, si no tiene, «sin límite» (0), como en el alta manual.
    """
    filas = await db.fetch(
        """SELECT d.domain, d.active, d.mailboxes, d.aliases, d.maxquota,
                  (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) AS cuentas,
                  (SELECT count(*) FROM alias a WHERE a.domain = d.domain
                      AND NOT EXISTS (SELECT 1 FROM mailbox m WHERE m.username = a.address)) AS alias_usados
             FROM domain d WHERE d.domain = ANY($1::varchar[])""",
        dominios)
    con_enrutamiento = await enrutados(db, dominios)
    info = {}
    for f in filas:
        maxima = int(f["maxquota"] or 0)
        info[f["domain"]] = {
            "activo": bool(f["active"]), "enrutado": f["domain"] in con_enrutamiento,
            "max_cuentas": int(f["mailboxes"] or 0), "cuentas": int(f["cuentas"]),
            "max_alias": int(f["aliases"] or 0), "alias": int(f["alias_usados"]),
            "cuota_maxima": maxima if maxima > 0 else None, "cuota_defecto": maxima if maxima > 0 else 0,
        }
    return info


async def ocupadas(db, direcciones: list[str]) -> set[str]:
    filas = await db.fetch(
        """SELECT address AS d FROM alias WHERE address = ANY($1::varchar[])
           UNION SELECT username FROM mailbox WHERE username = ANY($1::varchar[])
           UNION SELECT lower(address) FROM mail_groups WHERE lower(address) = ANY($1::varchar[])""",
        direcciones)
    return {f["d"] for f in filas}


async def contexto(db, filas: list[dict]) -> tuple[dict, set[str]]:
    direcciones = sorted({d for f in filas for d in [f["correo"], *f["alias"]] if d.count("@") == 1})
    dominios = sorted({d.split("@")[1] for d in direcciones})
    return await dominios_info(db, dominios), await ocupadas(db, direcciones)


async def crear(db, fila: dict, hash_clave: str) -> None:
    """La cuenta, su fila de entrega propia y sus alias, todo o nada."""
    local, dominio = fila["correo"].split("@")
    async with db.acquire() as con, con.transaction():
        await con.execute(
            """INSERT INTO mailbox (username, password, name, maildir, quota, domain, local_part, active)
               VALUES ($1::varchar, $2::varchar, $3::varchar, $4::varchar, $5, $6::varchar, $7::varchar, true)""",
            fila["correo"], hash_clave, fila["nombre"], f"{dominio}/{local}/", fila["cuota"], dominio, local)
        await con.execute(
            "INSERT INTO alias (address, goto, domain, active) VALUES ($1::varchar, $1::varchar, $2::varchar, true)",
            fila["correo"], dominio)
        for a in fila["alias"]:
            await con.execute(
                "INSERT INTO alias (address, goto, domain, active) VALUES ($1::varchar, $2::varchar, $3::varchar, true)",
                a, fila["correo"], a.split("@")[1])
