"""La búsqueda entra en el texto aunque la cuenta aún no figure como indexada, si la carpeta es
pequeña y el servidor tiene motor de búsqueda (informe de Andes, 15/11/2026)."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest

from app.mail.clients import imap_client


@pytest.fixture
def indice(tmp_path, monkeypatch):
    """`indice_texto` sin cuentas anotadas y sin motor; cada prueba pone lo que necesita."""
    monkeypatch.setenv("FTS_HECHOS", str(tmp_path / "hechas.txt"))
    monkeypatch.setenv("FTS_CONF_MOTOR", str(tmp_path / "60-busqueda.conf"))
    import app.mail.services.indice_texto as m

    m = importlib.reload(m)
    yield m, tmp_path
    monkeypatch.undo()
    importlib.reload(m)


def test_mensajes_de_la_carpeta_lee_el_exists_del_select(indice):
    m, _ = indice
    assert (
        m.mensajes_de_la_carpeta([b"FLAGS (\\Seen)", b"37 EXISTS", b"0 RECENT"]) == 37
    )
    assert m.mensajes_de_la_carpeta(["* 5 EXISTS"]) == 5
    assert m.mensajes_de_la_carpeta([b"[READ-WRITE] Select completed."]) is None
    assert m.mensajes_de_la_carpeta(None) is None


def test_sin_motor_de_busqueda_no_se_entra_en_el_texto(indice):
    m, _ = indice
    assert not m.motor_instalado()
    assert not m.carpeta_abarcable([b"3 EXISTS"])


def test_con_motor_solo_las_carpetas_pequenas(indice):
    m, carpeta = indice
    (carpeta / "60-busqueda.conf").write_text("fts flatcurve {\n}\n")
    assert m.motor_instalado()
    assert m.carpeta_abarcable([b"3 EXISTS"])
    assert m.carpeta_abarcable([f"{m.CARPETA_ABARCABLE} EXISTS".encode()])
    assert not m.carpeta_abarcable([f"{m.CARPETA_ABARCABLE + 1} EXISTS".encode()])
    assert not m.carpeta_abarcable([b"Select completed."]), "sin el dato, no"


def test_la_lista_de_cuentas_hechas_tambien_delata_al_motor(indice):
    m, carpeta = indice
    (carpeta / "hechas.txt").write_text("otra@example.org\n")
    assert m.motor_instalado() and not m.cuenta_indexada("ana@example.org")


class _Imap:
    def __init__(self, mensajes):
        self.mensajes = mensajes

    async def select(self, _carpeta):
        return SimpleNamespace(
            result="OK",
            lines=[f"{self.mensajes} EXISTS".encode(), b"Select completed."],
        )


def _criterio_enviado(monkeypatch, mensajes, abarcable_con_motor=True):
    """El criterio IMAP que el listado manda al buscar «murcielago» en una cuenta sin anotar."""
    enviado = {}

    async def uid_sort(imap, criterio):
        enviado["criterio"] = " ".join(criterio)
        return []

    monkeypatch.setattr(imap_client, "uid_sort", uid_sort)
    monkeypatch.setattr(imap_client, "cuenta_indexada", lambda u: False)
    from app.mail.services import indice_texto

    monkeypatch.setattr(indice_texto, "motor_instalado", lambda: abarcable_con_motor)
    monkeypatch.setattr(
        imap_client, "carpeta_abarcable", indice_texto.carpeta_abarcable
    )
    asyncio.run(
        imap_client.list_message_uids(
            _Imap(mensajes), "INBOX", 1, 25, "murcielago", username="ana@example.org"
        )
    )
    return enviado["criterio"]


def test_carpeta_pequena_de_cuenta_sin_anotar_busca_tambien_en_el_cuerpo(monkeypatch):
    criterio = _criterio_enviado(monkeypatch, 40)
    assert 'BODY "murcielago"' in criterio
    assert 'SUBJECT "murcielago"' in criterio and 'FROM "murcielago"' in criterio
    assert "SINCE" not in criterio, "no se acota por fecha: es la carpeta entera"
    assert "TEXT " not in criterio, "TEXT mira también las cabeceras técnicas"


def test_carpeta_grande_de_cuenta_sin_anotar_sigue_por_encabezados(monkeypatch):
    criterio = _criterio_enviado(monkeypatch, 150_000)
    assert "BODY" not in criterio and 'SUBJECT "murcielago"' in criterio


def test_sin_motor_la_carpeta_pequena_sigue_por_encabezados(monkeypatch):
    assert "BODY" not in _criterio_enviado(monkeypatch, 40, abarcable_con_motor=False)
