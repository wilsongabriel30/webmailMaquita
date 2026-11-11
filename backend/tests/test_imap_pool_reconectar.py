"""El fondo IMAP cambia la conexión cuando se cerró en mitad del uso (500 en búsquedas, 11/11/2026)."""

from types import SimpleNamespace

from app.mail.clients import imap_pool


def test_que_errores_son_de_conexion_caida():
    cerrado = RuntimeError(
        "unable to perform operation on <TCPTransport closed=True>; the handler is closed"
    )
    assert imap_pool.es_conexion_caida(cerrado)
    assert imap_pool.es_conexion_caida(ConnectionResetError())
    assert imap_pool.es_conexion_caida(BrokenPipeError())
    assert not imap_pool.es_conexion_caida(RuntimeError("otra cosa"))
    assert not imap_pool.es_conexion_caida(ValueError("closed"))


async def test_reconectar_cierra_la_vieja_y_entrega_una_nueva(monkeypatch):
    cerradas = []
    vieja = SimpleNamespace(
        protocol=SimpleNamespace(
            transport=SimpleNamespace(close=lambda: cerradas.append(1))
        )
    )
    nueva = object()

    async def _crear(usuario, clave):
        return nueva

    monkeypatch.setattr(imap_pool, "_create_connection", _crear)
    pooled = imap_pool.PooledIMAP("a@example.org", "clave")
    pooled.imap = vieja
    assert await pooled.reconectar() is nueva
    assert pooled.imap is nueva and cerradas == [1]
