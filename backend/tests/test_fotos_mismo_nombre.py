"""Misma foto de Raíces para los buzones emparejados por nombre (09/11/2026)."""

from app.tareas.fotos_mismo_nombre import decidir_copia

URL = "https://gestion.example.org/static/uploads/nomina/fotos/foto_1.webp"


def fila(**k):
    base = dict(
        email="logistica@example.com",
        photo_url="",
        foto_raices_url="",
        foto_raices_huella="",
        foto_propia_url="",
        foto_origen="",
        p_url=URL,
        p_huella="sha:abc",
    )
    base.update(k)
    return base


def test_secundario_sin_foto_recibe_la_de_raices():
    c = decidir_copia(fila())
    assert c is not None
    assert (
        c.photo_url == URL
        and c.foto_raices_url == URL
        and c.foto_raices_huella == "sha:abc"
    )
    assert c.foto_origen == "nomina" and c.invalidar_cache


def test_ya_sincronizado_no_cambia():
    assert (
        decidir_copia(
            fila(
                photo_url=URL,
                foto_raices_url=URL,
                foto_raices_huella="sha:abc",
                foto_origen="nomina",
            )
        )
        is None
    )


def test_foto_propia_se_respeta_si_raices_no_cambio():
    c = decidir_copia(
        fila(
            photo_url="/api/contacts/foto/x",
            foto_raices_url=URL,
            foto_raices_huella="sha:abc",
            foto_propia_url="/api/contacts/foto/x",
            foto_origen="propio",
        )
    )
    assert c is None


def test_raices_cambia_y_pisa_la_propia():
    c = decidir_copia(
        fila(
            photo_url="/api/contacts/foto/x",
            foto_raices_url=URL,
            foto_raices_huella="sha:vieja",
            foto_propia_url="/api/contacts/foto/x",
            foto_origen="propio",
            p_huella="sha:nueva",
        )
    )
    assert (
        c is not None
        and c.photo_url == URL
        and c.foto_propia_url == ""
        and c.foto_origen == "nomina"
    )


def test_principal_sin_foto_quita_la_copiada():
    c = decidir_copia(
        fila(
            photo_url=URL,
            foto_raices_url=URL,
            foto_raices_huella="sha:abc",
            foto_origen="nomina",
            p_url="",
            p_huella="",
        )
    )
    assert c is not None and c.photo_url == "" and c.foto_raices_url == ""


def test_principal_sin_foto_y_secundario_nunca_la_tuvo_no_toca():
    assert decidir_copia(fila(p_url="", p_huella="")) is None
