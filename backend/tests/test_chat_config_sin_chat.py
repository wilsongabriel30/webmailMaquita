"""Sin chat instalado, la configuración pública no lo da por activo (la interfaz sondeaba y recibía 404)."""

from app.chatcfg import router as chatcfg


def test_sin_decision_del_panel_ni_chat_instalado_queda_apagado(monkeypatch):
    monkeypatch.delenv("CHAT_INTERNAL_URL", raising=False)
    assert chatcfg.activo_por_omision("/chat/?embed=1") is False


def test_con_el_chat_instalado_en_el_mismo_servidor_queda_encendido(monkeypatch):
    monkeypatch.setenv("CHAT_INTERNAL_URL", "http://127.0.0.1:8790")
    assert chatcfg.activo_por_omision("/chat/?embed=1") is True


def test_con_el_chat_en_otro_origen_queda_encendido(monkeypatch):
    monkeypatch.delenv("CHAT_INTERNAL_URL", raising=False)
    assert chatcfg.activo_por_omision("https://chat.example.org/chat/") is True


def test_lo_que_decide_el_panel_manda(monkeypatch):
    monkeypatch.delenv("CHAT_INTERNAL_URL", raising=False)
    publica = chatcfg._to_public(
        {"enabled": "1", "embed_url": "/chat/?embed=1"}, {"enabled"}
    )
    assert publica["enabled"] is True
    publica = chatcfg._to_public({"enabled": "1", "embed_url": "/chat/?embed=1"}, set())
    assert publica["enabled"] is False
