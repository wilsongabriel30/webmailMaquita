from datetime import datetime, timedelta, timezone

from app.mail.services import entregado_sin_identificador as e

SERVIDOR = "mail.example.org"
ID_SERVIDOR = "<20261119190945.F3BDC20506@mail.example.org>"
ASUNTO_Q = "=?ISO-8859-1?Q?RE:_Segundo_Seguimiento=5FEscu?= =?ISO-8859-1?Q?ela_de_Formaci=F3n_(No_inscritos)?="
ENVIADO = {
    "asunto": ASUNTO_Q,
    "fechas": [e.fecha_de_cabecera("Thu, 19 Nov 2026 14:09:40 -0500"), None],
}


def test_hora_del_identificador_solo_si_es_de_este_servidor():
    assert e.hora_del_identificador(ID_SERVIDOR, SERVIDOR) == datetime(
        2026, 11, 19, 19, 9, 45, tzinfo=timezone.utc
    )
    assert e.hora_del_identificador(ID_SERVIDOR, "otro.example.org") is None
    assert e.hora_del_identificador("<abc.123@email.android.com>", SERVIDOR) is None
    assert (
        e.hora_del_identificador("<20261399999999.ABCDEF@mail.example.org>", SERVIDOR)
        is None
    )


def test_asunto_se_compara_decodificado():
    assert e.asunto_normalizado(ASUNTO_Q) == e.asunto_normalizado(
        "re: segundo  seguimiento_escuela de Formación (No inscritos)"
    )


def test_el_caso_real_se_encuentra():
    entregados = [{"message_id": ID_SERVIDOR, "asunto": ASUNTO_Q}]
    assert e.elegir(ENVIADO, entregados, SERVIDOR) == ID_SERVIDOR


def test_copias_del_mismo_correo_en_varias_carpetas_cuentan_como_uno():
    entregados = [{"message_id": ID_SERVIDOR, "asunto": ASUNTO_Q}] * 2
    assert e.elegir(ENVIADO, entregados, SERVIDOR) == ID_SERVIDOR


def test_dos_candidatos_distintos_no_se_recupera_nada():
    entregados = [
        {"message_id": ID_SERVIDOR, "asunto": ASUNTO_Q},
        {
            "message_id": "<20261119191000.AAAAAA1111@mail.example.org>",
            "asunto": ASUNTO_Q,
        },
    ]
    assert e.elegir(ENVIADO, entregados, SERVIDOR) is None


def test_no_vale_otro_asunto_otra_hora_ni_un_identificador_ajeno():
    assert (
        e.elegir(
            ENVIADO, [{"message_id": ID_SERVIDOR, "asunto": "Otro asunto"}], SERVIDOR
        )
        is None
    )
    tarde = "<20261119200945.F3BDC20506@mail.example.org>"
    assert (
        e.elegir(ENVIADO, [{"message_id": tarde, "asunto": ASUNTO_Q}], SERVIDOR) is None
    )
    ajeno = "<123.abc@correo.example.net>"
    assert (
        e.elegir(ENVIADO, [{"message_id": ajeno, "asunto": ASUNTO_Q}], SERVIDOR) is None
    )


def test_sin_fecha_comprobable_no_se_recupera():
    sin_fecha = {"asunto": ASUNTO_Q, "fechas": [None, None]}
    assert (
        e.elegir(sin_fecha, [{"message_id": ID_SERVIDOR, "asunto": ASUNTO_Q}], SERVIDOR)
        is None
    )


def test_vale_la_hora_de_guardado_si_el_reloj_del_telefono_esta_mal():
    enviado = {
        "asunto": ASUNTO_Q,
        "fechas": [
            e.fecha_de_cabecera("Thu, 19 Nov 2026 09:00:00 -0500"),
            datetime(2026, 11, 19, 19, 9, 55, tzinfo=timezone.utc),
        ],
    }
    assert (
        e.elegir(enviado, [{"message_id": ID_SERVIDOR, "asunto": ASUNTO_Q}], SERVIDOR)
        == ID_SERVIDOR
    )
    assert e.TOLERANCIA == timedelta(minutes=5)


def test_registros_une_cabeceras_plegadas_y_separa_mensajes():
    salida = (
        "hdr.message-id: <a@x>\nhdr.subject: =?ISO-8859-1?Q?uno?=\n =?ISO-8859-1?Q?dos?=\n\f\n"
        "hdr.message-id: <b@x>\nhdr.subject: tres\n"
    )
    assert e.registros(salida) == [
        {
            "hdr.message-id": "<a@x>",
            "hdr.subject": "=?ISO-8859-1?Q?uno?= =?ISO-8859-1?Q?dos?=",
        },
        {"hdr.message-id": "<b@x>", "hdr.subject": "tres"},
    ]
    assert e.registros("") == []
