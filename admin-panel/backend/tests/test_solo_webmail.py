"""Indicaciones de la pantalla «Solo webmail»: qué se le dice al administrador en cada caso."""

from app.solo_webmail.indicaciones import indicacion


def test_protegida_sin_equipos_queda_solo_en_el_webmail():
    r = indicacion(True, 0, 0, 9)
    assert r["nivel"] == "ok" and "Solo entra por el webmail" in r["texto"]


def test_protegida_con_contrasena_de_aplicacion():
    assert "contraseña de aplicación" in indicacion(True, 40, 2, 0)["texto"]


def test_intentos_desde_varias_direcciones_remiten_a_las_alertas():
    r = indicacion(False, 0, 0, 6)
    assert (
        r["nivel"] == "alerta"
        and "6 direcciones" in r["texto"]
        and "ahora" in r["texto"]
    )


def test_ataque_sobre_cuenta_con_outlook_avisa_de_crear_primero_la_clave():
    r = indicacion(False, 25, 0, 4)
    assert r["nivel"] == "alerta" and "primero" in r["texto"]


def test_dos_direcciones_con_fallos_no_es_ataque():
    assert indicacion(False, 0, 0, 2)["nivel"] == "info"


def test_cuenta_sin_equipos_se_puede_proteger_sin_afectar():
    assert "sin afectar" in indicacion(False, 0, 0, 0)["texto"]


def test_cuenta_con_outlook_y_sin_clave_de_aplicacion_avisa():
    r = indicacion(False, 12, 0, 0)
    assert r["nivel"] == "aviso" and "dejarán de funcionar" in r["texto"]


def test_cuenta_con_outlook_y_clave_de_aplicacion_se_puede_proteger():
    assert indicacion(False, 12, 1, 0)["nivel"] == "info"


def test_sin_datos_de_uso_pide_confirmar_con_la_persona():
    assert "confirme" in indicacion(False, 0, 0, 0, hay_datos_de_uso=False)["texto"]
