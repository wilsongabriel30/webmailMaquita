"""La marca dice si hay app móvil publicada, para que la interfaz no pida su manifiesto a ciegas."""

from app.branding.router import hay_app_movil


def test_sin_manifiesto_no_hay_app(tmp_path):
    assert hay_app_movil(str(tmp_path)) is False


def test_con_manifiesto_hay_app(tmp_path):
    (tmp_path / "maquita-mail.json").write_text(
        '{"versionName": "1.0"}', encoding="utf-8"
    )
    assert hay_app_movil(str(tmp_path)) is True
