import asyncio, time
from app.database import create_pool
from app.safeattach import service
async def main():
    pool = await create_pool()
    t0 = time.time()
    res = await service.scan(pool)   # todos los usuarios activos, simulacion
    print("FIN scan en %.0fs:" % (time.time()-t0), res, flush=True)
    await pool.close()
asyncio.run(main())
