"""El barrido de datos propios encuentra lo que debe y no molesta con lo que no."""

import importlib.util
import os
import re

RUTA = os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "tools", "barrido-datos-propios.py")
especificacion = importlib.util.spec_from_file_location("barrido_datos_propios", RUTA)
barrido = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(barrido)

PATRONES = [("dominio", re.compile(r"organizacion-real\.example", re.I)), ("correo", re.compile(r"persona\.real@", re.I))]


def test_encuentra_dominio_y_correo_sin_importar_mayusculas():
    assert barrido.revisar_linea('URL = "https://Mail.Organizacion-Real.example/x"', PATRONES) == ["dominio"]
    assert barrido.revisar_linea("aviso a Persona.Real@otro.example", PATRONES) == ["correo"]


def test_valores_de_ejemplo_pasan():
    for linea in ('HOST = "mail.example.org"', "red 192.0.2.0/24 y 198.51.100.7", "proxy en 10.0.0.5, 172.16.4.1 y 192.168.1.1",
                  "resolver 8.8.8.8 y 1.1.1.1", "escucha en 127.0.0.1:8000 y 0.0.0.0", "usuario@example.com"):
        assert barrido.revisar_linea(linea, PATRONES) == [], linea


def test_una_direccion_publica_de_verdad_se_senala():
    publica = ".".join(("93", "184", "216", "34"))  # escrita a trozos: este fichero también pasa por el barrido
    assert barrido.revisar_linea(f'SERVIDOR = "{publica}"', []) != []
    assert barrido.revisar_linea(f"ip daddr {{ {publica}/32 }} accept", []) != []


def test_lo_que_parece_direccion_pero_es_version_pasa():
    publica = ".".join(("93", "184", "216", "34"))
    for linea in ("Chrome/120.0.0.0 Safari/537.36", f"paquete=={publica}", f"versión {publica} publicada", f"v{publica}"):
        assert barrido.revisar_linea(linea, []) == [], linea


def test_una_direccion_publica_declarada_pasa():
    publica = ".".join(("93", "184", "216", "34"))
    assert barrido.revisar_linea(f'NTP = "{publica}"  # guardian: ip-publica', []) == []


def test_no_se_revisan_binarios_ni_dependencias():
    assert not barrido.se_revisa("frontend/node_modules/x/index.js")
    assert not barrido.se_revisa("docs/captura.png")
    assert not barrido.se_revisa("frontend/package-lock.json")
    assert barrido.se_revisa("backend/app/config.py")


def test_patrones_desde_el_entorno(monkeypatch):
    monkeypatch.setenv("GUARDIAN_DATOS_PROPIOS", "# comentario\n\ndominio: uno\\.example\nsuelto-sin-categoria\nroto: (\n")
    patrones = barrido.cargar_patrones(".")
    assert [c for c, _ in patrones] == ["dominio", "dato propio"]
