"""Alertas de seguridad: detección del ataque lento a contraseñas y su explicación en lenguaje llano."""

from datetime import datetime, timedelta

from app.alertas_seguridad.ataques import agrupar, explicar

T0 = datetime(2026, 11, 12, 7, 0)


def fila(cuenta, ip, pais="ES", ok=0, fallos=1, servicio="smtp", minutos=0):
    return {
        "cuenta": cuenta,
        "ip": ip,
        "pais": pais,
        "servicio": servicio,
        "ok": ok,
        "fallos": fallos,
        "hora": T0 + timedelta(minutes=minutos),
    }


def test_tres_direcciones_que_solo_fallan_son_un_ataque():
    a = agrupar(
        [fila("a@example.org", f"198.51.100.{i}", minutos=i) for i in range(1, 4)]
    )
    assert len(a) == 1 and a[0]["cuenta"] == "a@example.org" and a[0]["intentos"] == 3
    assert a[0]["direcciones"][0]["ip"] == "198.51.100.3"  # la más reciente primero


def test_dos_direcciones_no_bastan():
    assert (
        agrupar(
            [
                fila("a@example.org", "198.51.100.1"),
                fila("a@example.org", "198.51.100.2"),
            ]
        )
        == []
    )


def test_la_direccion_que_alguna_vez_acerto_no_cuenta():
    filas = [fila("a@example.org", f"198.51.100.{i}") for i in range(1, 4)]
    filas.append(fila("a@example.org", "198.51.100.3", ok=1, fallos=0, minutos=5))
    assert agrupar(filas) == []


def test_los_accesos_del_propio_servidor_se_ignoran():
    filas = [
        fila("a@example.org", "127.0.0.1"),
        fila("a@example.org", "::1"),
        fila("a@example.org", "198.51.100.1"),
    ]
    assert agrupar(filas) == []


def test_suma_intentos_y_servicios_por_direccion():
    filas = [
        fila("a@example.org", "198.51.100.1", fallos=2),
        fila("a@example.org", "198.51.100.1", servicio="imap", minutos=9),
        fila("a@example.org", "198.51.100.2"),
        fila("a@example.org", "198.51.100.3"),
    ]
    a = agrupar(filas)[0]
    d = next(x for x in a["direcciones"] if x["ip"] == "198.51.100.1")
    assert (
        d["intentos"] == 3
        and d["servicios"] == ["imap", "smtp"]
        and a["servicios"] == ["imap", "smtp"]
    )


def _ataque(pais="ES"):
    return agrupar(
        [fila("a@example.org", f"198.51.100.{i}", pais=pais) for i in range(1, 4)]
    )[0]


def test_ataque_del_exterior_sobre_cuenta_solo_webmail_sugiere_cerrar_sin_efecto_para_la_persona():
    e = explicar(_ataque(), True, False, False, 0)
    assert (
        e["gravedad"] == "alta"
        and e["accion"] == "proteger"
        and "no notará nada" in e["sugerencia"]
    )


def test_ataque_sobre_cuenta_con_outlook_advierte_de_los_equipos():
    e = explicar(_ataque(), True, False, True, 0)
    assert e["accion"] == "proteger" and "dejarán de funcionar" in e["sugerencia"]


def test_cuenta_ya_protegida_queda_resuelta_y_sin_boton():
    e = explicar(_ataque(), True, True, False, 0)
    assert e["gravedad"] == "resuelta" and e["accion"] == ""


def test_cuenta_inexistente_no_ofrece_proteger():
    e = explicar(_ataque(), False, False, False, 0)
    assert e["accion"] == "" and "no existe" in e["que_pasa"]


def test_direcciones_del_pais_piden_preguntar_antes():
    e = explicar(_ataque("EC"), True, False, True, 0)
    assert e["gravedad"] == "media" and "Pregunte" in e["sugerencia"]


def test_la_red_interna_no_cuenta_como_exterior():
    filas = [
        fila("a@example.org", "192.0.2.1", pais="LAN"),
        fila("a@example.org", "192.0.2.2", pais="EC"),
        fila("a@example.org", "192.0.2.3", pais="EC"),
    ]
    e = explicar(agrupar(filas)[0], True, False, False, 0)
    assert e["gravedad"] == "media"
