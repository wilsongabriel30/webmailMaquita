"""Matriz de cierre de F-01 / F-04 (tercera revisión ASVS).

{logout, logout-all, password-change, admin-reset, disable} × {REST, WebSocket, refresh}
Cada celda tiene que dar 401 (o «refreshed: false») o cierre de la conexión (4401).
Las celdas del chat (REST y Socket.IO) viven en chat-service/tests/test_revocacion.py.

Necesita PostgreSQL y Redis reales (los del CI o un entorno de laboratorio):
DATABASE_URL, REDIS_URL, SECRET_KEY, ADMIN_JWT_SECRET, MASTER_PASSWORD, MAIL_DOMAIN.
Dovecot se sustituye por dobles: la clave de prueba siempre autentica.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from app.main import app
from httpx import ASGITransport, AsyncClient

USUARIO = "matriz@example.com"
ADMIN = "admin-matriz@example.com"
CLAVE = "Clave-de-prueba-2026!"
CLAVE_NUEVA = "Otra-clave-de-prueba-2026!"
COOKIE_HOST = "test"

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------- entorno
@pytest_asyncio.fixture
async def estado(monkeypatch):
    """Pool + Redis reales en app.state, dobles de Dovecot/doveadm y usuarios de prueba."""
    from app.database import create_db_pool
    from app.redis_client import create_redis
    from app.websocket.router import start_redis_subscriber

    pool = await create_db_pool()
    redis = await create_redis()
    app.state.db_pool = pool
    app.state.redis = redis

    async def _auth(username, password, *a, **k):
        return password in (CLAVE, CLAVE_NUEVA)

    async def _sin_totp(db, username):
        return False

    async def _nada(*a, **k):
        return None

    monkeypatch.setattr("app.auth.router.authenticate", _auth)
    monkeypatch.setattr("app.auth.router.is_totp_enabled", _sin_totp)
    monkeypatch.setattr("app.risky_login.detection.analyze", _nada)
    monkeypatch.setattr("app.auth.password.verify_imap", lambda u, p: True)
    monkeypatch.setattr("app.auth.password.hash_password_doveadm", lambda p: "{PLAIN}x")

    async def _update_mailbox(db, username, **k):
        return {"username": username}

    async def _toggle(db, username):
        return {"username": username, "active": False}

    monkeypatch.setattr(
        "app.admin.router.mailboxes_service.update_mailbox", _update_mailbox
    )
    monkeypatch.setattr("app.admin.router.mailboxes_service.toggle_active", _toggle)
    monkeypatch.setattr("app.admin.router._audit", _nada)

    dominio = USUARIO.split("@")[1]
    await pool.execute(
        "INSERT INTO domain (domain) VALUES ($1) ON CONFLICT (domain) DO NOTHING",
        dominio,
    )
    for u in (USUARIO, ADMIN):
        await pool.execute(
            """INSERT INTO mailbox (username, password, name, maildir, local_part, domain, active)
               VALUES ($1, '{PLAIN}x', 'Prueba', $2, $3, $4, true)
               ON CONFLICT (username) DO UPDATE SET active = true""",
            u,
            f"{dominio}/{u.split('@')[0]}/",
            u.split("@")[0],
            dominio,
        )
    await pool.execute(
        """INSERT INTO admin (username, superadmin, active) VALUES ($1, true, true)
           ON CONFLICT (username) DO UPDATE SET superadmin = true, active = true""",
        ADMIN,
    )
    await _limpiar(pool, redis)

    suscriptor = await start_redis_subscriber(app.state)
    await asyncio.sleep(0.2)  # que el suscriptor llegue a suscribirse
    try:
        yield {"pool": pool, "redis": redis}
    finally:
        suscriptor.cancel()
        try:
            await suscriptor
        except (asyncio.CancelledError, Exception):
            pass
        await _limpiar(pool, redis)
        await pool.close()
        await (redis.aclose() if hasattr(redis, "aclose") else redis.close())


async def _limpiar(pool, redis):
    for u in (USUARIO, ADMIN):
        await pool.execute("DELETE FROM refresh_tokens WHERE username = $1", u)
        await pool.execute("DELETE FROM auth_estado WHERE username = $1", u)
        claves = []
        for patron in (f"sess:{u}:*", f"imap_pass:{u}:*", f"imap_master:{u}:*"):
            async for k in redis.scan_iter(patron):
                claves.append(k)
        claves += [f"sids:{u}", f"av:{u}", f"login_rl:user:{u}", f"mcp:{u}"]
        await redis.delete(*claves)


def _cliente() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app), base_url=f"https://{COOKIE_HOST}"
    )


async def entrar(usuario=USUARIO, clave=CLAVE) -> AsyncClient:
    """Sesión nueva (un navegador): devuelve un cliente con sus cookies."""
    c = _cliente()
    r = await c.post("/api/auth/login", json={"username": usuario, "password": clave})
    assert r.status_code == 200, r.text
    assert "access_token" in c.cookies and "refresh_token" in c.cookies
    return c


async def rest(c: AsyncClient) -> int:
    return (await c.get("/api/auth/verify")).status_code


async def refresh(c: AsyncClient) -> bool:
    r = await c.post("/api/auth/refresh")
    return r.status_code == 200 and r.json().get("refreshed") is not False


# ----------------------------------------------------------------- WebSocket en el mismo bucle
class WS:
    """Conductor ASGI mínimo: abre /api/ws con la cookie de sesión y lee lo que manda
    el servidor. Corre en el mismo bucle que el resto de la prueba."""

    def __init__(self, cookie: str):
        self.cookie = cookie
        self.entrada: asyncio.Queue = asyncio.Queue()
        self.salida: asyncio.Queue = asyncio.Queue()
        self.tarea = None

    async def _receive(self):
        return await self.entrada.get()

    async def _send(self, m):
        await self.salida.put(m)

    async def abrir(self):
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "path": "/api/ws",
            "raw_path": b"/api/ws",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", COOKIE_HOST.encode()),
                (b"cookie", f"access_token={self.cookie}".encode()),
                (b"connection", b"upgrade"),
                (b"upgrade", b"websocket"),
            ],
            "client": ("127.0.0.1", 12345),
            "server": (COOKIE_HOST, 443),
            "scheme": "wss",
            "subprotocols": [],
            "state": {},
        }
        await self.entrada.put({"type": "websocket.connect"})
        self.tarea = asyncio.create_task(app(scope, self._receive, self._send))
        primero = await asyncio.wait_for(self.salida.get(), 5)
        return primero  # websocket.accept o websocket.close

    async def siguiente(self, timeout=5):
        return await asyncio.wait_for(self.salida.get(), timeout)

    async def cerrado_con(self, codigo, timeout=6) -> bool:
        fin = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < fin:
            try:
                m = await self.siguiente(timeout=1)
            except asyncio.TimeoutError:
                continue
            if m["type"] == "websocket.close":
                return m.get("code") == codigo
        return False

    async def cerrar(self):
        await self.entrada.put({"type": "websocket.disconnect", "code": 1000})
        if self.tarea:
            try:
                await asyncio.wait_for(self.tarea, 3)
            except Exception:
                self.tarea.cancel()


async def ws_conectado(c: AsyncClient) -> WS:
    ws = WS(c.cookies["access_token"])
    primero = await ws.abrir()
    assert primero["type"] == "websocket.accept", primero
    hola = await ws.siguiente()
    assert json.loads(hola["text"])["type"] == "connected"
    return ws


# ----------------------------------------------------------------- la matriz
async def _comprobar_revocada(a: AsyncClient, ws: WS):
    """Las tres celdas de una sesión revocada: REST 401, refresh no, WebSocket cerrado 4401."""
    assert await rest(a) == 401
    assert await refresh(a) is False
    assert await ws.cerrado_con(4401)


async def test_logout_cierra_solo_su_sesion(estado):
    a, b = await entrar(), await entrar()
    ws_a = await ws_conectado(a)
    assert await rest(a) == 200 and await rest(b) == 200
    assert (await a.post("/api/auth/logout")).status_code == 200
    await _comprobar_revocada(a, ws_a)
    assert await rest(b) == 200  # la otra sesión sigue
    assert await refresh(b) is True
    await ws_a.cerrar()


async def test_logout_all_cierra_todas(estado):
    a, b = await entrar(), await entrar()
    ws_a = await ws_conectado(a)
    assert (await b.post("/api/auth/logout-all")).status_code == 200
    await _comprobar_revocada(a, ws_a)
    assert await rest(b) == 401
    assert await refresh(b) is False
    await ws_a.cerrar()


async def test_cambio_de_contrasena_expulsa_a_las_demas(estado):
    a, b = await entrar(), await entrar()
    ws_a = await ws_conectado(a)
    r = await b.post(
        "/api/auth/change-password",
        json={"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert r.status_code == 200, r.text
    await _comprobar_revocada(a, ws_a)
    # quien cambió la clave recibe sesión nueva en la misma respuesta: no se cae
    assert await rest(b) == 200
    assert await refresh(b) is True
    await ws_a.cerrar()


async def test_reset_por_admin_expulsa(estado):
    a = await entrar()
    ws_a = await ws_conectado(a)
    adm = await entrar(ADMIN)
    r = await adm.post("/api/admin/password-audit/reset", json={"username": USUARIO})
    assert r.status_code == 200, r.text
    await _comprobar_revocada(a, ws_a)
    await ws_a.cerrar()


async def test_desactivar_cuenta_expulsa(estado):
    a = await entrar()
    ws_a = await ws_conectado(a)
    adm = await entrar(ADMIN)
    r = await adm.post(f"/api/admin/mailboxes/{USUARIO}/toggle-active")
    assert r.status_code == 200, r.text
    await _comprobar_revocada(a, ws_a)
    await ws_a.cerrar()


# ----------------------------------------------------------------- coherencia
async def test_relogin_no_revive_tokens_viejos(estado):
    a = await entrar()
    viejo = _cliente()
    viejo.cookies.update(a.cookies)
    assert (await a.post("/api/auth/logout-all")).status_code == 200
    nuevo = await entrar()  # re-login legítimo
    assert await rest(nuevo) == 200
    assert await rest(viejo) == 401  # el token viejo trae la generación anterior
    assert await refresh(viejo) is False


async def test_token_sin_sid_no_vale(estado):
    import jwt as pyjwt
    from app.config import get_settings

    viejo = pyjwt.encode(
        {
            "sub": USUARIO,
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        get_settings().secret_key,
        algorithm="HS256",
    )
    c = _cliente()
    c.cookies.set("access_token", viejo)
    assert await rest(c) == 401


async def test_impersonacion_no_se_renueva_mas_alla_de_la_hora(estado):
    """F-04: el refresh conserva el vencimiento absoluto; pasado, se rechaza."""
    from app.auth.cookies import poner_cookies_sesion
    from app.auth.sesiones import crear_sesion

    pool, redis = estado["pool"], estado["redis"]
    abs_exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    sesion = await crear_sesion(
        pool,
        redis,
        None,
        USUARIO,
        "maestra",
        kind="impersonation",
        abs_exp=abs_exp,
        master="admin",
        user_agent="prueba",
    )
    c = _cliente()
    c.cookies.set("access_token", sesion["access"])
    c.cookies.set("refresh_token", sesion["refresh_raw"], path="/api/auth/refresh")
    assert await rest(c) == 200
    assert await refresh(c) is True
    fila = await pool.fetchrow(
        "SELECT expires_at, absolute_expires_at, session_kind FROM refresh_tokens "
        "WHERE username = $1 AND is_revoked = false ORDER BY created_at DESC LIMIT 1",
        USUARIO,
    )
    assert fila["session_kind"] == "impersonation"
    assert fila["expires_at"] <= abs_exp and fila["absolute_expires_at"] == abs_exp

    # Sesión ya vencida de forma absoluta: ni REST ni refresh.
    vencida = await crear_sesion(
        pool,
        redis,
        None,
        USUARIO,
        "maestra",
        kind="impersonation",
        abs_exp=datetime.now(timezone.utc) + timedelta(seconds=1),
        master="admin",
    )
    await asyncio.sleep(1.2)
    c2 = _cliente()
    c2.cookies.set("access_token", vencida["access"])
    c2.cookies.set("refresh_token", vencida["refresh_raw"], path="/api/auth/refresh")
    assert await rest(c2) == 401
    assert await refresh(c2) is False


async def test_sesion_normal_no_hereda_impersonacion(estado):
    a = await entrar()
    pool = estado["pool"]
    fila = await pool.fetchrow(
        "SELECT session_kind FROM refresh_tokens WHERE username = $1 AND is_revoked = false",
        USUARIO,
    )
    assert fila["session_kind"] == "normal"
    yo = (await a.get("/api/auth/me")).json()
    assert yo["user"]["username"] == USUARIO


async def test_l01_listar_y_cerrar_una_sesion_por_sid(estado):
    """L-01 (cuarta revisión): la persona ve sus sesiones y cierra la de otro dispositivo."""
    a, b = await entrar(), await entrar()
    r = await a.get("/api/auth/sesiones")
    assert r.status_code == 200, r.text
    sesiones = r.json()["sesiones"]
    assert len(sesiones) == 2 and sesiones[0]["actual"] is True
    otra = [s for s in sesiones if not s["actual"]][0]
    assert (await a.delete("/api/auth/sesiones/no-existe-000")).status_code == 404
    assert (await a.delete(f"/api/auth/sesiones/{otra['sid']}")).status_code == 200
    assert await rest(b) == 401 and await refresh(b) is False
    assert await rest(a) == 200  # la propia sigue
    assert len((await a.get("/api/auth/sesiones")).json()["sesiones"]) == 1
