"""N-7: las cuentas privilegiadas no usan el webmail sin segundo factor."""

import pytest

from app.auth import segundo_factor as sf

pytestmark = pytest.mark.asyncio


def test_cuenta_privilegiada_por_parte_local_o_direccion():
    p = "admin, postmaster, tecnologia@example.org"
    assert sf.cuenta_privilegiada("admin@example.org", p)
    assert sf.cuenta_privilegiada("Postmaster@red.example", p)
    assert sf.cuenta_privilegiada("tecnologia@example.org", p)
    assert not sf.cuenta_privilegiada("tecnologia@example.com", p)  # solo esa dirección
    assert not sf.cuenta_privilegiada("ana@example.org", p)
    assert not sf.cuenta_privilegiada("admin", p) and not sf.cuenta_privilegiada("", p)
    assert not sf.cuenta_privilegiada("admin@example.org", "")  # política vacía: nadie


class _Redis:
    def __init__(self):
        self.d = {}

    async def get(self, k):
        return self.d.get(k)

    async def set(self, k, v, ex=None):
        self.d[k] = v

    async def delete(self, k):
        self.d.pop(k, None)


async def test_debe_activar_solo_privilegiadas_sin_totp(monkeypatch):
    activos = {"admin@example.org": False, "ana@example.org": False}

    async def _enabled(db, u):
        return activos.get(u, False)

    import app.auth.totp as totp

    monkeypatch.setattr(totp, "is_totp_enabled", _enabled)
    r = _Redis()
    assert await sf.debe_activar_2fa(None, r, "admin@example.org", "admin") is True
    assert (
        await sf.debe_activar_2fa(None, r, "ana@example.org", "admin") is False
    )  # no privilegiada
    # cache: aunque active TOTP, hasta olvidar() sigue diciendo que falta
    activos["admin@example.org"] = True
    assert await sf.debe_activar_2fa(None, r, "admin@example.org", "admin") is True
    await sf.olvidar(r, "admin@example.org")
    assert await sf.debe_activar_2fa(None, r, "admin@example.org", "admin") is False


def test_rutas_permitidas_solo_activar_o_salir():
    assert "/api/auth/totp/setup" in sf.RUTAS_PERMITIDAS_2FA
    assert "/api/auth/totp/verify" in sf.RUTAS_PERMITIDAS_2FA
    assert "/api/mail/messages" not in sf.RUTAS_PERMITIDAS_2FA
    assert "/api/auth/totp/disable" not in sf.RUTAS_PERMITIDAS_2FA
