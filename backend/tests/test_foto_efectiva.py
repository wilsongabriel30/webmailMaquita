"""Pruebas de la decisión de foto efectiva («la foto de Raíces manda», 09/11/2026). Sin BD ni red."""

from app.contacts.foto_efectiva import (
    EstadoFoto,
    al_quitar_propia,
    al_subir_propia,
    decidir,
    huella_desde_cabeceras,
)

RAICES_A = "https://gestion.example.org/static/uploads/profiles/14_a.webp"
RAICES_B = "https://gestion.example.org/static/uploads/profiles/14_b.webp"
PROPIA = "/api/contacts/foto/ana@example.com?v=1"


def test_primera_vez_con_foto_en_raices_la_adopta():
    c = decidir(EstadoFoto(), RAICES_A, "etag:1")
    assert c.photo_url == RAICES_A
    assert c.foto_raices_url == RAICES_A
    assert c.foto_raices_huella == "etag:1"
    assert c.foto_origen == "nomina"
    assert c.invalidar_cache is True


def test_sin_cambios_no_escribe_nada():
    estado = EstadoFoto(
        photo_url=RAICES_A,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_origen="nomina",
    )
    assert decidir(estado, RAICES_A, "etag:1").vacio()


def test_propia_vigente_se_conserva_si_raices_no_cambio():
    estado = EstadoFoto(
        photo_url=PROPIA,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_propia_url=PROPIA,
        foto_origen="propio",
    )
    assert decidir(estado, RAICES_A, "etag:1").vacio()


def test_cambio_en_raices_pisa_la_propia():
    estado = EstadoFoto(
        photo_url=PROPIA,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_propia_url=PROPIA,
        foto_origen="propio",
    )
    c = decidir(estado, RAICES_B, "etag:2")
    assert c.photo_url == RAICES_B
    assert c.foto_propia_url == ""
    assert c.foto_origen == "nomina"
    assert c.invalidar_cache is True
    assert c.motivo == "raices_cambio"


def test_misma_url_pero_bytes_distintos_tambien_pisa():
    estado = EstadoFoto(
        photo_url=PROPIA,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_propia_url=PROPIA,
        foto_origen="propio",
    )
    c = decidir(estado, RAICES_A, "etag:2")
    assert c.photo_url == RAICES_A and c.foto_propia_url == ""


def test_huella_provisional_de_la_migracion_no_cuenta_como_cambio():
    # La migración deja huella 'url:<url>'; el primer HEAD trae un ETag: no es un cambio de foto.
    estado = EstadoFoto(
        photo_url=PROPIA,
        foto_raices_url=RAICES_A,
        foto_raices_huella="url:" + RAICES_A,
        foto_propia_url=PROPIA,
        foto_origen="propio",
    )
    c = decidir(estado, RAICES_A, "etag:9")
    assert c.photo_url == PROPIA
    assert c.foto_propia_url == PROPIA
    assert c.foto_raices_huella == "etag:9"
    assert c.invalidar_cache is False


def test_fila_antigua_incoherente_se_corrige_sin_tocar_cache_si_la_efectiva_no_cambia():
    # fuente='nomina' antigua: photo_url = Raíces pero sin columnas nuevas rellenas.
    estado = EstadoFoto(photo_url=RAICES_A)
    c = decidir(estado, RAICES_A, "etag:1")
    assert c.photo_url == RAICES_A and c.foto_origen == "nomina"
    assert c.invalidar_cache is False


def test_raices_deja_de_tener_foto_y_hay_propia():
    estado = EstadoFoto(
        photo_url=PROPIA,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_propia_url=PROPIA,
        foto_origen="propio",
    )
    c = decidir(estado, "", "")
    assert c.photo_url == PROPIA and c.foto_origen == "propio"
    assert c.foto_raices_url == "" and c.foto_raices_huella == ""
    assert c.invalidar_cache is False


def test_raices_deja_de_tener_foto_y_no_hay_propia():
    estado = EstadoFoto(
        photo_url=RAICES_A,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_origen="nomina",
    )
    c = decidir(estado, "", "")
    assert c.photo_url == "" and c.foto_origen == ""
    assert c.invalidar_cache is True


def test_nunca_tuvo_raices_y_sigue_sin_tenerla_no_toca_la_propia():
    estado = EstadoFoto(photo_url=PROPIA, foto_propia_url=PROPIA, foto_origen="propio")
    assert decidir(estado, "", "").vacio()


def test_subir_propia_pasa_a_ser_efectiva_y_conserva_raices():
    estado = EstadoFoto(
        photo_url=RAICES_A,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_origen="nomina",
    )
    c = al_subir_propia(estado, PROPIA)
    assert (
        c.photo_url == PROPIA
        and c.foto_propia_url == PROPIA
        and c.foto_origen == "propio"
    )
    assert c.foto_raices_url == RAICES_A and c.foto_raices_huella == "etag:1"
    assert c.invalidar_cache is True


def test_quitar_propia_restaura_raices():
    estado = EstadoFoto(
        photo_url=PROPIA,
        foto_raices_url=RAICES_A,
        foto_raices_huella="etag:1",
        foto_propia_url=PROPIA,
        foto_origen="propio",
    )
    c = al_quitar_propia(estado)
    assert (
        c.photo_url == RAICES_A
        and c.foto_origen == "nomina"
        and c.foto_propia_url == ""
    )


def test_quitar_propia_sin_raices_deja_vacio():
    estado = EstadoFoto(photo_url=PROPIA, foto_propia_url=PROPIA, foto_origen="propio")
    c = al_quitar_propia(estado)
    assert c.photo_url == "" and c.foto_origen == ""
    assert c.invalidar_cache is True


def test_huella_prefiere_etag_luego_tamano_y_fecha_luego_url():
    assert huella_desde_cabeceras({"ETag": '"abc"'}, RAICES_A) == "etag:abc"
    assert (
        huella_desde_cabeceras(
            {
                "Content-Length": "5822",
                "Last-Modified": "Fri, 30 Jan 2026 17:08:12 GMT",
            },
            RAICES_A,
        )
        == "len:5822|mod:Fri, 30 Jan 2026 17:08:12 GMT"
    )
    assert huella_desde_cabeceras({}, RAICES_A) == "url:" + RAICES_A
