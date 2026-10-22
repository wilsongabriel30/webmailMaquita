"""Reglas de anomalía con datos sintéticos: cada una salta cuando debe y calla cuando no."""

from datetime import datetime, timedelta, timezone

from app.seguridad import anomalias
from app.seguridad.parseo import EventoAcceso

UTC = timezone.utc
ZONA = timezone(timedelta(hours=-5))
T0 = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)  # 10:00 en UTC-5


def ev(minuto, resultado, cuenta="ana@example.org", ip="203.0.113.5", pais="EC", servicio="imap", veces=1):
    return EventoAcceso(T0 + timedelta(minutes=minuto), servicio, resultado, cuenta, ip, veces, pais)


def test_pais_nuevo_aprende_y_luego_alerta():
    conocidos = {}
    # Primera vez: sin historial, solo aprende
    assert anomalias.regla_pais_nuevo([ev(0, "ok", pais="EC")], conocidos) == []
    assert conocidos["ana@example.org"] == {"EC"}
    # Mismo país, red interna o desconocido: nada
    assert anomalias.regla_pais_nuevo([ev(1, "ok"), ev(2, "ok", pais="LAN"), ev(3, "ok", pais="--")], conocidos) == []
    # Un fallo desde otro país no es «entró desde»
    assert anomalias.regla_pais_nuevo([ev(4, "fallo", pais="BR")], conocidos) == []
    h = anomalias.regla_pais_nuevo([ev(5, "ok", pais="BR"), ev(6, "ok", pais="BR")], conocidos)
    assert len(h) == 1 and h[0].regla == "pais_nuevo" and h[0].pais == "BR" and h[0].severidad == "media"
    assert "BR" in h[0].descripcion and "EC" in h[0].descripcion
    assert h[0].huella == "pais_nuevo:ana@example.org:BR"


def test_fallos_seguidos_de_exito():
    fallos = [ev(i, "fallo", ip=f"203.0.113.{10 + i}") for i in range(5)]
    h, conservar = anomalias.regla_fallos_y_exito([], fallos + [ev(6, "ok")], umbral=5, ventana_min=15)
    assert len(h) == 1 and h[0].severidad == "alta" and h[0].detalles["fallos"] == 5
    assert len(h[0].detalles["ips_de_los_fallos"]) == 5
    assert conservar == []  # tras el acceso correcto la cuenta empieza de nuevo


def test_fallos_que_cruzan_dos_pasadas():
    _, conservar = anomalias.regla_fallos_y_exito([], [ev(0, "fallo", veces=3)], 5, 15)
    assert len(conservar) == 1 and conservar[0].veces == 3
    h, _ = anomalias.regla_fallos_y_exito(conservar, [ev(5, "fallo", veces=2), ev(7, "ok")], 5, 15)
    assert len(h) == 1


def test_fallos_fuera_de_ventana_o_pocos_no_alertan():
    h, _ = anomalias.regla_fallos_y_exito([], [ev(0, "fallo", veces=5), ev(30, "ok")], 5, 15)
    assert h == []
    h, _ = anomalias.regla_fallos_y_exito([], [ev(0, "fallo", veces=4), ev(1, "ok")], 5, 15)
    assert h == []
    # Fallos de otra cuenta no cuentan
    h, _ = anomalias.regla_fallos_y_exito([], [ev(0, "fallo", cuenta="luis@example.org", veces=9), ev(1, "ok")], 5, 15)
    assert h == []


def test_hora_inusual():
    # 200 accesos entre las 8 y las 17 (hora local), ninguno de madrugada
    horas = [0] * 24
    for h in range(8, 18):
        horas[h] = 20
    hist = {"ana@example.org": horas}
    madrugada = EventoAcceso(datetime(2026, 10, 21, 3, 10, tzinfo=ZONA), "webmail", "ok", "ana@example.org", "203.0.113.5", pais="EC")
    h = anomalias.regla_hora_inusual([madrugada], hist, ZONA, minimo=50, porcentaje_max=1)
    assert len(h) == 1 and h[0].severidad == "baja" and h[0].detalles["hora_local"] == 3
    assert hist["ana@example.org"][3] == 1  # aprende
    # Horario normal, IMAP (los teléfonos sincronizan de noche), red interna o poco historial: nada
    normal = EventoAcceso(datetime(2026, 10, 21, 9, 0, tzinfo=ZONA), "webmail", "ok", "ana@example.org", "203.0.113.5", pais="EC")
    imap = EventoAcceso(datetime(2026, 10, 21, 3, 0, tzinfo=ZONA), "imap", "ok", "ana@example.org", "203.0.113.5", pais="EC")
    lan = EventoAcceso(datetime(2026, 10, 21, 4, 0, tzinfo=ZONA), "panel", "ok", "ana@example.org", "192.0.2.10", pais="LAN")
    assert anomalias.regla_hora_inusual([normal, imap, lan], hist, ZONA, 50, 1) == []
    nuevo = EventoAcceso(datetime(2026, 10, 21, 3, 0, tzinfo=ZONA), "webmail", "ok", "luis@example.org", "203.0.113.5", pais="EC")
    assert anomalias.regla_hora_inusual([nuevo], {}, ZONA, 50, 1) == []


def test_una_alerta_por_dia_de_hora_inusual():
    horas = [0] * 24
    horas[12] = 100
    hist = {"ana@example.org": horas}
    dos = [EventoAcceso(datetime(2026, 10, 21, 2, m, tzinfo=ZONA), "webmail", "ok", "ana@example.org", "203.0.113.5", pais="EC") for m in (0, 30)]
    assert len(anomalias.regla_hora_inusual(dos, hist, ZONA, 50, 1)) == 1


def test_muchas_cuentas_desde_una_ip():
    filas = [
        {"ip": "203.0.113.66", "pais": "RU", "cuentas": 25, "fallos": 140, "ok_cuentas": 0},
        {"ip": "203.0.113.67", "pais": "CN", "cuentas": 12, "fallos": 40, "ok_cuentas": 1},
        {"ip": "203.0.113.68", "pais": "EC", "cuentas": 3, "fallos": 3, "ok_cuentas": 0},
        {"ip": "192.0.2.10", "pais": "LAN", "cuentas": 40, "fallos": 0, "ok_cuentas": 40},
    ]
    h = anomalias.regla_muchas_cuentas_ip(filas, umbral=10, ahora=T0)
    assert [(x.ip, x.severidad) for x in h] == [("203.0.113.66", "media"), ("203.0.113.67", "alta")]
    assert "25 cuentas" in h[0].descripcion and "ninguna entró" in h[0].descripcion
    assert h[0].huella == "muchas_cuentas_ip:203.0.113.66:2026102115"
