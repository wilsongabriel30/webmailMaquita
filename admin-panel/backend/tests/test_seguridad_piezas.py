"""Configuración, rangos de fechas, informes, avisos, lectura incremental, GeoIP y registro JSON."""

import json
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.seguridad import ajustes, avisos, consultas, exportar, fuentes, informes, zona
from app.seguridad.anomalias import Hallazgo
from app.seguridad.geo import Geo

GYE = ZoneInfo("America/Guayaquil")


def test_validar_config():
    base = ajustes.por_omision()
    assert base["retencion_dias"] == 400 and base["aviso_severidad_minima"] == "alta"
    assert ajustes.validar({"retencion_dias": "500", "avisos": 0})["retencion_dias"] == 500
    for malo in ({"retencion_dias": 5}, {"umbral_fallos": "muchos"}, {"aviso_severidad_minima": "urgente"},
                 {"zona_horaria": "Marte/Base"}, {"zona_horaria": "../../etc/passwd"},
                 {"retencion_dias": 60, "retencion_detalle_dias": 90}):
        with pytest.raises(ValueError):
            ajustes.validar(malo)
    assert ajustes.validar({"zona_horaria": "America/Guayaquil"})["zona_horaria"] == "America/Guayaquil"


def test_zona():
    assert zona.valida("America/Guayaquil") and zona.valida("UTC")
    assert not zona.valida("America/Guayaquil\n") and not zona.valida("")
    assert zona.nombre("no-valida") == zona.del_servidor()


def test_rango_de_fechas():
    i, f = consultas.rango(None, None, GYE, hoy=date(2026, 10, 21))
    assert i == datetime(2026, 10, 15, tzinfo=GYE) and f == datetime(2026, 10, 22, tzinfo=GYE)
    i, f = consultas.rango("2026-10-01", "2026-10-01", GYE)
    assert f - i == timedelta(days=1)
    for d, h in (("2026-13-01", None), ("21/10/2026", None), ("2026-10-05", "2026-10-01"), ("2025-01-01", "2026-10-01"),
                 ("2026-10-01\n", None)):
        with pytest.raises(consultas.RangoInvalido):
            consultas.rango(d, h, GYE)
    assert consultas.agrupacion(i, i + timedelta(days=1), None) == "hour"
    assert consultas.agrupacion(i, i + timedelta(days=30), "hora") == "day"
    assert consultas.agrupacion(i, i + timedelta(days=3), "hora") == "hour"


def test_csv_sin_inyeccion_y_con_bom():
    texto = informes.a_csv("ips", [{"ip": "203.0.113.5", "pais": "EC", "fallos": 3, "ok": 0, "cuentas": 2,
                                    "servicios": ["imap", "smtp"], "ultima": "2026-10-21T10:00:00"},
                                   {"ip": "=HYPERLINK(\"x\")", "pais": "--"}])
    assert texto.startswith("﻿ip,pais,fallos")
    assert "imap smtp" in texto
    assert "'=HYPERLINK" in texto


def test_html_imprimible_escapa():
    h = informes.a_html("Informe", "2026-10-01 a 2026-10-07", "2026-10-21 10:00", {"Alertas": 1},
                        [("Alertas", "alertas", [{"id": 1, "descripcion": "<script>alert(1)</script>"}]),
                         ("IP", "ips", [])])
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert "Sin datos en el periodo" in h and "Guardar como PDF" in h


def _h(sev, texto="La cuenta ana@example.org entró desde BR"):
    return Hallazgo("pais_nuevo", sev, texto, "x", datetime(2026, 10, 21, tzinfo=timezone.utc), "ana@example.org")


def test_avisos_y_cupo():
    assert avisos.merece_aviso("alta", "alta") and avisos.merece_aviso("alta", "media")
    assert not avisos.merece_aviso("media", "alta") and not avisos.merece_aviso("baja", "media")
    asunto, cuerpo = avisos.componer_resumen([(7, _h("alta")), (8, _h("media"))], "mail.example.org")
    assert "2 alerta(s)" in asunto and "1 alta(s)" in asunto and "#7 [ALTA]" in cuerpo
    asunto, cuerpo = avisos.componer_escalamiento(
        [{"id": 3, "descripcion": "x", "creada": datetime(2026, 10, 21, 8, 0)}], 4, "mail.example.org")
    assert "ESCALADA" in asunto and "más de 4 h" in cuerpo
    e = None
    for _ in range(3):
        puede, e = avisos.cupo(e, "2026-10-21T10", 3)
        assert puede
    assert avisos.cupo(e, "2026-10-21T10", 3)[0] is False
    assert avisos.cupo(e, "2026-10-21T11", 3)[0] is True  # hora nueva


def test_enviar_sin_lib_no_falla(tmp_path):
    assert avisos.enviar("a", "b", [], lib=str(tmp_path / "no-existe.sh")) is False


def test_enviar_usa_lib_avisos(tmp_path):
    lib = tmp_path / "lib-avisos.sh"
    salida = tmp_path / "enviado"
    lib.write_text(f'vig_destinos() {{ echo postmaster@example.org; }}\nvig_enviar() {{ {{ echo "$1|$2"; cat; }} > "{salida}"; }}\n')
    assert avisos.enviar("Asunto", "Cuerpo", [], lib=str(lib))
    assert salida.read_text() == "Asunto|postmaster@example.org\nCuerpo"
    assert avisos.enviar("Asunto", "Cuerpo", ["ti@example.org", "jefa@example.org"], lib=str(lib))
    assert salida.read_text().startswith("Asunto|ti@example.org jefa@example.org")


def test_lectura_incremental_y_rotacion(tmp_path):
    ruta = tmp_path / "mail.log"
    ruta.write_text("uno\ndos\n")
    lineas, est = fuentes.leer_archivo(str(ruta), None)
    assert lineas == ["uno", "dos"]
    with open(ruta, "a") as f:
        f.write("tres\ncuatro a medias")
    lineas, est = fuentes.leer_archivo(str(ruta), est)
    assert lineas == ["tres"]  # la última línea incompleta espera
    with open(ruta, "a") as f:
        f.write(" ya\n")
    lineas, est = fuentes.leer_archivo(str(ruta), est)
    assert lineas == ["cuatro a medias ya"]
    # Rotación: lo que quedaba del viejo y luego el nuevo
    with open(ruta, "a") as f:
        f.write("cinco\n")
    os.rename(ruta, str(ruta) + ".1")
    ruta.write_text("seis\n")
    lineas, est = fuentes.leer_archivo(str(ruta), est)
    assert lineas == ["cinco", "seis"]
    assert fuentes.leer_archivo(str(ruta), est)[0] == []


def test_primera_lectura_solo_el_final(tmp_path, monkeypatch):
    monkeypatch.setattr(fuentes, "INICIO_BYTES", 20)
    ruta = tmp_path / "mail.log"
    ruta.write_text("".join(f"linea {i:03d}\n" for i in range(100)))
    lineas, _ = fuentes.leer_archivo(str(ruta), None)
    assert lineas == ["linea 099"]  # la primera, posiblemente cortada, se descarta


class _Lector:
    def get(self, ip):
        return {"198.51.100.7": {"country": {"iso_code": "BR"}}, "203.0.113.9": {"country": {"iso_code": "x<"}}}.get(ip)


def test_geo():
    g = Geo(["192.0.2.0/24"], lector=_Lector())
    assert g.pais("198.51.100.7") == "BR"
    assert g.pais("203.0.113.9") == "--"  # código raro: no se acepta
    assert g.pais("192.0.2.44") == "LAN" and g.pais("127.0.0.1") == "LAN"  # ORG_REDES y bucle local
    assert g.pais("") == "--" and g.pais("no-es-ip") == "--"
    assert Geo(lector=None, base="/no/existe.mmdb").pais("198.51.100.7") == "--"


def test_registro_json(tmp_path, monkeypatch):
    ruta = tmp_path / "maquita" / "seguridad.json"
    h = _h("alta")
    assert exportar.escribir([exportar.evento_alerta(5, h)], str(ruta)) == 1
    datos = json.loads(ruta.read_text().splitlines()[0])
    assert datos["origen"] == "maquita" and datos["tipo"] == "alerta" and datos["severidad"] == "alta"
    assert oct(ruta.stat().st_mode & 0o777) == "0o640"
    monkeypatch.setenv("SEG_EXPORTAR_JSON", "0")
    assert exportar.activo() is False
    monkeypatch.setenv("SEG_EXPORTAR_JSON", "1")
    assert exportar.activo() is True
