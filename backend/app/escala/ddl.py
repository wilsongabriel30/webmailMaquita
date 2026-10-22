"""DDL de arranque serializado entre workers, compatible con PgBouncer.

Antes se usaba `pg_advisory_lock` / `pg_advisory_unlock` de SESIÓN. Detrás de un
PgBouncer en modo «transaction» cada sentencia puede ir a otra conexión del servidor:
el desbloqueo se pide en una conexión que no tiene el bloqueo, el bloqueo queda
tomado para siempre y el siguiente worker se queda colgado al arrancar. Y aun sin
PgBouncer, pedirlo con `pool.execute()` (una conexión distinta en cada llamada) dejaba
el bloqueo prendido de una conexión del pool.

Aquí se toma `pg_advisory_xact_lock()` dentro de una transacción abierta en una conexión
dedicada: el bloqueo dura lo que dura la transacción y se suelta solo al terminar (con
commit, con rollback o si la conexión se corta). Funciona igual con y sin PgBouncer.
"""

from contextlib import asynccontextmanager


@asynccontextmanager
async def ddl_serializado(pool, clave: int):
    """`async with ddl_serializado(pool, 815000) as con:` → solo un worker a la vez.

    El DDL puede ejecutarse en `con` (dentro de la misma transacción) o con el pool
    (otras conexiones): mientras el bloque corre, ningún otro worker entra.
    """
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute("SELECT pg_advisory_xact_lock($1)", int(clave))
            yield con
