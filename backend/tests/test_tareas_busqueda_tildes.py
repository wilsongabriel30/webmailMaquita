"""Buscar tareas sin tildes, como en To Do (29/10/2026): «accion» encuentra «Acción»; la ñ se respeta."""

from app.tasks import vistas


def test_el_patron_quita_tildes_y_respeta_la_enie():
    assert vistas._patron("Acción rápida") == "%Accion rapida%"
    assert vistas._patron("año") == "%año%"


def test_la_consulta_quita_tildes_de_titulo_nota_y_pasos():
    sql = vistas._sin_tildes("tc.title")
    assert sql.startswith("translate(tc.title, '") and len(vistas._CON_TILDE) == len(
        vistas._SIN_TILDE
    )
    assert "Acción".translate(vistas._QUITAR_TILDES) == "Accion"
