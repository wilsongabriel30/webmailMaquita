from app.mail.services.direcciones_destinatarios import solo_direcciones


def test_quita_el_nombre_y_deja_la_direccion():
    assert solo_direcciones(["Mishel Pilicita <tecnicatth@example.org>"]) == [
        "tecnicatth@example.org"
    ]


def test_nombre_entre_comillas_con_coma():
    assert solo_direcciones(['"Pérez, Ana" <Ana@Example.org>', "luis@example.org"]) == [
        "ana@example.org",
        "luis@example.org",
    ]


def test_no_repite_y_respeta_el_orden():
    assert solo_direcciones(
        ["b@example.org", "B <b@example.org>", " a@example.org "]
    ) == ["b@example.org", "a@example.org"]


def test_vacios_fuera_y_lo_invalido_se_conserva_para_que_se_rechace():
    assert solo_direcciones(["", "  ", "no-es-correo"]) == ["no-es-correo"]
    assert solo_direcciones(None) == []
