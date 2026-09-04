"""IMAP Connection Pool — reuse authenticated connections per user.

Eliminates the ~100ms overhead of connect+login on every request.
Keeps up to MAX_PER_USER connections per user, with TTL expiration.
"""
from app.mail.errors import CredencialIMAPInvalida
import asyncio
import time
import logging
import aioimaplib

from app.config import get_settings

logger = logging.getLogger("imap_pool")

_pools: dict[str, asyncio.Queue] = {}
_locks: dict[str, asyncio.Lock] = {}
_semaforos: dict[str, asyncio.Semaphore] = {}
_global_lock = asyncio.Lock()

MAX_PER_USER = 2            # conexiones OCIOSAS guardadas por usuario (por worker)
MAX_EN_VUELO = 5            # peticiones simultaneas por usuario (por worker):
                            # el resto espera su turno en vez de abrir conexiones
                            # nuevas y chocar con mail_max_userip_connections
TTL_SECONDS = 300
CLEANUP_INTERVAL = 60


async def _create_connection(username: str, password: str) -> aioimaplib.IMAP4:
    settings = get_settings()
    imap = aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port, timeout=30)
    await imap.wait_hello_from_server()
    resp = await imap.login(username, password)
    if resp.result != "OK":
        # Fallback for master user
        if "*" in username:
            try:
                await imap.logout()
            except Exception:
                pass
            base_user = username.split("*")[0]
            imap = aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port, timeout=30)
            await imap.wait_hello_from_server()
            resp = await imap.login(base_user, password)
            if resp.result == "OK":
                return imap
        raise CredencialIMAPInvalida(f"IMAP login failed for {username}")
    return imap


async def _is_alive(imap: aioimaplib.IMAP4) -> bool:
    try:
        resp = await asyncio.wait_for(imap.noop(), timeout=5)
        return resp.result == "OK"
    except Exception:
        return False


async def _get_user_pool(username: str) -> asyncio.Queue:
    async with _global_lock:
        if username not in _pools:
            _pools[username] = asyncio.Queue(maxsize=MAX_PER_USER)
        return _pools[username]


class PooledIMAP:
    """Async context manager for pooled IMAP connections."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.imap = None
        self._returned = False

    async def __aenter__(self) -> aioimaplib.IMAP4:
        async with _global_lock:
            if self.username not in _semaforos:
                _semaforos[self.username] = asyncio.Semaphore(MAX_EN_VUELO)
        self._semaforo = _semaforos[self.username]
        await self._semaforo.acquire()
        try:
            return await self._abrir()
        except BaseException:
            self._semaforo.release()
            raise

    async def _abrir(self) -> aioimaplib.IMAP4:
        pool = await _get_user_pool(self.username)

        # Try to reuse existing connection
        while not pool.empty():
            try:
                imap, created_at = pool.get_nowait()
            except asyncio.QueueEmpty:
                break

            if time.time() - created_at > TTL_SECONDS:
                try:
                    await imap.logout()
                except Exception:
                    pass
                continue

            if await _is_alive(imap):
                self.imap = imap
                return self.imap
            else:
                try:
                    await imap.logout()
                except Exception:
                    pass

        # Create new
        self.imap = await _create_connection(self.username, self.password)
        return self.imap

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._returned or self.imap is None:
            if not self._returned:
                self._returned = True
                self._semaforo.release()
            return
        self._returned = True
        self._semaforo.release()

        if exc_type is not None:
            # Error — don't return to pool
            try:
                await self.imap.logout()
            except Exception:
                pass
            return

        pool = await _get_user_pool(self.username)
        try:
            pool.put_nowait((self.imap, time.time()))
        except asyncio.QueueFull:
            try:
                await self.imap.logout()
            except Exception:
                pass


def get_pooled_imap(username: str, password: str) -> PooledIMAP:
    """Get a pooled IMAP connection as async context manager."""
    return PooledIMAP(username, password)


async def close_all_pools():
    """Close all pooled connections (for graceful shutdown)."""
    async with _global_lock:
        for username, pool in list(_pools.items()):
            while not pool.empty():
                try:
                    imap, _ = pool.get_nowait()
                    await imap.logout()
                except Exception:
                    pass
        _pools.clear()
        _locks.clear()
    logger.info("All IMAP pools closed")


async def _cleanup_loop():
    """Background task: close expired connections every CLEANUP_INTERVAL seconds."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            async with _global_lock:
                usernames = list(_pools.keys())

            for username in usernames:
                pool = await _get_user_pool(username)
                keep = []
                while not pool.empty():
                    try:
                        imap, created_at = pool.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if time.time() - created_at < TTL_SECONDS:
                        keep.append((imap, created_at))
                    else:
                        try:
                            await imap.logout()
                        except Exception:
                            pass
                        logger.debug("pool_expired | user=%s", username)

                for item in keep:
                    try:
                        pool.put_nowait(item)
                    except asyncio.QueueFull:
                        try:
                            await item[0].logout()
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("pool_cleanup_error: %s", e)


_cleanup_task = None


def start_cleanup_task():
    """Start background cleanup. Call once at app startup."""
    global _cleanup_task
    _cleanup_task = asyncio.ensure_future(_cleanup_loop())
    logger.info("IMAP pool cleanup task started (interval=%ds, ttl=%ds)", CLEANUP_INTERVAL, TTL_SECONDS)
