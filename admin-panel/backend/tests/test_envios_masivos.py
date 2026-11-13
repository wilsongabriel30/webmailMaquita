"""Bloqueos por envío a muchas personas: la explicación en lenguaje llano."""

from app.alertas_seguridad.envios_masivos import explicar, sin_revisar


def evento(**cambios):
    e = {
        "cuenta": "jefa@example.org",
        "nombre": "Ana Jefa",
        "mensajes": 1,
        "destinatarios": 46,
        "minutos": 10,
        "atendido": None,
        "existe": True,
        "destinos": [
            {
                "lista": "contadores@example.org",
                "destinatarios": 30,
                "es_lista": True,
                "autorizada": False,
            },
            {
                "lista": "gestorias@example.org",
                "destinatarios": 13,
                "es_lista": True,
                "autorizada": False,
            },
            {
                "lista": "directos",
                "destinatarios": 3,
                "es_lista": False,
                "autorizada": False,
            },
        ],
    }
    e.update(cambios)
    return e


def test_explica_que_paso_con_las_listas_y_los_directos():
    x = explicar(evento(), 30, activa=False)
    assert x["titulo"].startswith("Se bloqueó la cuenta de Ana Jefa")
    assert "1 correo a 46 personas en 10 minutos" in x["que_paso"]
    assert (
        "contadores@example.org (30)" in x["que_paso"]
        and "3 fueron directos" in x["que_paso"]
    )
    assert "pasa de 30" in x["que_paso"]
    assert x["estado"] == "bloqueada"


def test_si_iba_a_listas_ofrece_permitirlo():
    x = explicar(evento(), 30, activa=False)
    assert "«Es correcto»" in x["que_hacer"]
    assert "contadores@example.org y gestorias@example.org" in x["que_hacer"]
    assert (
        "La cuenta vuelve a funcionar y no se le volverá a bloquear" in x["que_hacer"]
    )
    activa = explicar(evento(), 30, activa=True)["que_hacer"]
    assert "«Es correcto». No se le volverá a bloquear" in activa
    assert "cambie la contraseña" in x["que_hacer"]


def test_sin_listas_solo_ofrece_reactivar():
    solo_directos = [
        {
            "lista": "directos",
            "destinatarios": 46,
            "es_lista": False,
            "autorizada": False,
        }
    ]
    x = explicar(evento(destinos=solo_directos), 30, activa=False)
    assert (
        "«Reactivar la cuenta»" in x["que_hacer"]
        and "«Es correcto»" not in x["que_hacer"]
    )
    assert "listas de la casa" not in x["que_paso"]


def test_con_las_listas_ya_permitidas_no_vuelve_a_ofrecerlo():
    destinos = [dict(d, autorizada=True) for d in evento()["destinos"]]
    x = explicar(evento(destinos=destinos), 30, activa=True)
    assert "«Es correcto»" not in x["que_hacer"] and x["estado"] == "activa"


def test_un_aviso_revisado_lo_dice_y_no_cuenta_como_pendiente():
    assert (
        explicar(evento(atendido="2026-11-13T10:00:00"), 30, activa=True)["que_hacer"]
        == "Ya se revisó."
    )
    assert sin_revisar([evento(), evento(atendido="x"), evento(existe=False)]) == 1


def test_sin_nombre_usa_la_direccion_y_el_plural_es_correcto():
    x = explicar(evento(nombre="", mensajes=3), 30, activa=False)
    assert "de jefa@example.org" in x["titulo"] and "3 correos" in x["que_paso"]


def test_si_no_iba_a_listas_dice_donde_dar_el_permiso_a_mano():
    solo_directos = [
        {
            "lista": "directos",
            "destinatarios": 46,
            "es_lista": False,
            "autorizada": False,
        }
    ]
    x = explicar(evento(destinos=solo_directos), 30, activa=False)
    assert "«Permisos para escribir a listas»" in x["que_hacer"]
