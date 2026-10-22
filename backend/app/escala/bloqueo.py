"""Bloqueo distribuido con Redis (SET NX con expiración) y elección de líder.

Sirve para que una tarea de fondo corra UNA sola vez aunque haya varios workers de
uvicorn o varias máquinas detrás del balanceador:

- `bloqueo()`: exclusión mutua mientras dura un bloque. El bloqueo caduca solo
  (si el proceso muere no queda tomado para siempre) y se renueva mientras el bloque
  sigue vivo. Solo lo libera quien lo tomó (se compara el testigo en Lua).
- `una_vez_por_intervalo()`: además de la exclusión, el bloqueo se conserva hasta que
  pasa el intervalo; así una tarea «cada 5 minutos» corre cada 5 minutos en todo el
  clúster y no una vez por worker.
- `Lider`: para tareas continuas (seguir un registro). Solo el líder la tiene en marcha;
  si el líder cae, otro proceso la toma cuando caduca el bloqueo.

Si Redis no responde, el bloqueo NO se concede: es preferible saltarse una vuelta de una
tarea de fondo que repetirla N veces (correos movidos dos veces, alertas duplicadas).
"""

import asyncio
import logging
import secrets
import socket
import time
from contextlib import asynccontextmanager

logger = logging.getLogger("escala.bloqueo")

PREFIJO = "bloqueo:"

# Renueva la caducidad solo si el bloqueo sigue siendo nuestro.
LUA_RENOVAR = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('pexpire', KEYS[1], ARGV[2]) else return 0 end"
)
# Libera solo si el bloqueo sigue siendo nuestro (nunca el de otro proceso).
LUA_LIBERAR = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


def nodo_id() -> str:
    """Identificador de este nodo (NODO_ID o el nombre de la máquina)."""
    try:
        from app.config import get_settings

        propio = (get_settings().nodo_id or "").strip()
        if propio:
            return propio
    except Exception:
        pass
    return socket.gethostname()


def _clave(nombre: str) -> str:
    return nombre if nombre.startswith(PREFIJO) else PREFIJO + nombre


def _testigo() -> str:
    # El testigo dice quién tiene el bloqueo (útil al diagnosticar) y es imposible de adivinar.
    return f"{nodo_id()}:{secrets.token_hex(8)}"


async def adquirir(redis, nombre: str, ttl_s: float) -> str | None:
    """Intenta tomar el bloqueo. Devuelve el testigo o None si lo tiene otro (o Redis falla)."""
    testigo = _testigo()
    try:
        ok = await redis.set(
            _clave(nombre), testigo, nx=True, px=max(1, int(ttl_s * 1000))
        )
    except Exception as exc:
        logger.warning("No se pudo pedir el bloqueo %s: %s", nombre, exc)
        return None
    return testigo if ok else None


async def renovar(redis, nombre: str, testigo: str, ttl_s: float) -> bool:
    """Alarga la caducidad si el bloqueo sigue siendo nuestro."""
    try:
        r = await redis.eval(
            LUA_RENOVAR, 1, _clave(nombre), testigo, max(1, int(ttl_s * 1000))
        )
        return bool(r)
    except Exception as exc:
        logger.warning("No se pudo renovar el bloqueo %s: %s", nombre, exc)
        return False


async def liberar(redis, nombre: str, testigo: str) -> bool:
    """Suelta el bloqueo si sigue siendo nuestro."""
    try:
        return bool(await redis.eval(LUA_LIBERAR, 1, _clave(nombre), testigo))
    except Exception as exc:
        logger.warning("No se pudo liberar el bloqueo %s: %s", nombre, exc)
        return False


async def titular(redis, nombre: str) -> str | None:
    """Quién tiene el bloqueo ahora (para diagnóstico)."""
    try:
        return await redis.get(_clave(nombre))
    except Exception:
        return None


class Bloqueo:
    """Estado de un bloqueo tomado con `bloqueo()`."""

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.testigo: str | None = None
        self.perdido = False  # True si dejó de ser nuestro mientras corría el bloque

    @property
    def obtenido(self) -> bool:
        return self.testigo is not None


async def _renovador(redis, b: Bloqueo, ttl_s: float):
    cada = max(0.05, ttl_s / 3)
    while True:
        await asyncio.sleep(cada)
        if not await renovar(redis, b.nombre, b.testigo, ttl_s):
            b.perdido = True
            logger.warning("Se perdió el bloqueo %s mientras se usaba", b.nombre)
            return


@asynccontextmanager
async def bloqueo(redis, nombre: str, ttl_s: float = 60, conservar_s: float = 0):
    """Exclusión mutua distribuida.

    `async with bloqueo(redis, "tarea", 60) as b:` → `b.obtenido` dice si se tomó.
    Mientras el bloque corre, el bloqueo se renueva cada ttl/3. Al salir se libera,
    salvo que `conservar_s` indique que debe seguir tomado hasta ese momento contado
    desde que se obtuvo (para «una vez por intervalo»).
    """
    b = Bloqueo(nombre)
    b.testigo = await adquirir(redis, nombre, max(ttl_s, conservar_s or 0))
    if not b.obtenido:
        yield b
        return
    inicio = time.monotonic()
    tarea = asyncio.create_task(_renovador(redis, b, ttl_s))
    try:
        yield b
    finally:
        tarea.cancel()
        try:
            await tarea
        except (asyncio.CancelledError, Exception):
            pass
        resto = (conservar_s or 0) - (time.monotonic() - inicio)
        if not b.perdido:
            if resto > 0.001:
                await renovar(redis, nombre, b.testigo, resto)
            else:
                await liberar(redis, nombre, b.testigo)


def una_vez_por_intervalo(redis, nombre: str, intervalo_s: float, ttl_s: float = 60):
    """Bloqueo que, al terminar, sigue tomado hasta completar `intervalo_s`.

    Con N workers que despiertan cada `intervalo_s`, el cuerpo corre una sola vez por
    intervalo en todo el clúster y nunca dos a la vez (aunque tarde más que el intervalo,
    porque mientras corre se renueva)."""
    return bloqueo(
        redis, nombre, ttl_s=min(ttl_s, intervalo_s), conservar_s=intervalo_s
    )


class Lider:
    """Mantiene en marcha una tarea continua solo en el proceso que es líder.

    `arrancar()` (asíncrona) pone en marcha el trabajo y devuelve un objeto; `parar(obj)`
    lo detiene. Si este proceso pierde el liderazgo (Redis caído, pausa larga), para el
    trabajo; los demás lo intentan cada `reintento_s` y uno lo retoma.
    """

    def __init__(self, redis, nombre, arrancar, parar, ttl_s=30.0, reintento_s=10.0):
        self.redis = redis
        self.nombre = nombre
        self.arrancar = arrancar
        self.parar = parar
        self.ttl_s = ttl_s
        self.reintento_s = reintento_s
        self.testigo: str | None = None
        self.trabajo = None
        self._tarea: asyncio.Task | None = None

    @property
    def es_lider(self) -> bool:
        return self.testigo is not None

    def iniciar(self) -> "Lider":
        self._tarea = asyncio.create_task(self._bucle(), name=f"{self.nombre}-lider")
        return self

    async def _soltar_trabajo(self):
        if self.trabajo is not None:
            try:
                r = self.parar(self.trabajo)
                if asyncio.iscoroutine(r):
                    await r
            except Exception:
                logger.exception("Error al parar %s", self.nombre)
            self.trabajo = None

    async def _bucle(self):
        try:
            while True:
                if self.es_lider:
                    await asyncio.sleep(self.ttl_s / 3)
                    if not await renovar(
                        self.redis, self.nombre, self.testigo, self.ttl_s
                    ):
                        logger.warning(
                            "%s: este proceso dejó de ser líder", self.nombre
                        )
                        self.testigo = None
                        await self._soltar_trabajo()
                    continue
                self.testigo = await adquirir(self.redis, self.nombre, self.ttl_s)
                if self.es_lider:
                    logger.info(
                        "%s: este proceso es el líder (%s)", self.nombre, self.testigo
                    )
                    try:
                        self.trabajo = await self.arrancar()
                    except Exception:
                        logger.exception(
                            "%s: no arrancó; se suelta el liderazgo", self.nombre
                        )
                        await liberar(self.redis, self.nombre, self.testigo)
                        self.testigo = None
                        await asyncio.sleep(self.reintento_s)
                    continue
                await asyncio.sleep(self.reintento_s)
        except asyncio.CancelledError:
            pass
        finally:
            await self._soltar_trabajo()
            if self.testigo:
                await liberar(self.redis, self.nombre, self.testigo)
                self.testigo = None

    def stop(self):
        """Compatible con el `.stop()` que el arranque ya llamaba al apagar."""
        if self._tarea and not self._tarea.done():
            self._tarea.cancel()

    async def detener(self):
        self.stop()
        if self._tarea:
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass
