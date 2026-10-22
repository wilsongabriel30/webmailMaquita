"""Órdenes de consola del panel (deploy/panel): maquita-panel vale-entrada y maquita-panel-dominio
vale-soporte. Sin root ni base real: psql es un guion que anota lo que recibe y responde lo previsto."""

import hashlib
import json
import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "deploy", "panel", "lib"))

import panel_bd  # noqa: E402
import panel_vales  # noqa: E402


@pytest.fixture
def consola(tmp_path, monkeypatch):
    (tmp_path / "admin-panel/backend").mkdir(parents=True)
    (tmp_path / "backend").mkdir()
    (tmp_path / "admin-panel/backend/.env").write_text(
        "DB_HOST=localhost\nDB_PORT=5432\nDB_NAME=maildb\nDB_USER=mailserver\nDB_PASS='clave-de-prueba'\n")
    (tmp_path / "backend/.env").write_text("MAIL_HOST=mail.example.org\n")
    org = tmp_path / "organizacion.env"
    org.write_text("")
    traza = tmp_path / "traza"
    traza.mkdir()
    psql = tmp_path / "psql"
    # Cada llamada deja sus argumentos y su SQL; responde según la consulta.
    psql.write_text(f"""#!/bin/sh
n=$(ls {traza} | wc -l)
printf '%s\\n' "$@" > {traza}/$n.args
cat > {traza}/$n.sql
case "$(cat {traza}/$n.sql)" in
  *portal_empresa*) cat {tmp_path}/resp.portal ;;
  *) cat {tmp_path}/resp.principal ;;
esac
""")
    psql.chmod(0o755)
    (tmp_path / "resp.portal").write_text('{"host": null}\n')
    monkeypatch.setattr(panel_bd, "PSQL", str(psql))
    monkeypatch.setattr(panel_bd, "ENTORNO_PANEL", str(tmp_path / "admin-panel/backend/.env"))
    monkeypatch.setattr(panel_bd, "ENTORNO_CORREO", str(tmp_path / "backend/.env"))
    monkeypatch.setattr(panel_bd, "ORGANIZACION", str(org))
    monkeypatch.delenv("ORG_URL_PANEL", raising=False)
    monkeypatch.delenv("ORG_URL_PORTAL_DOMINIO", raising=False)
    monkeypatch.setenv("SUDO_USER", "wilson")

    class C:
        def responder(self, datos, cual="principal"):
            (tmp_path / f"resp.{cual}").write_text(json.dumps(datos) + "\n")

        def llamadas(self):
            salida = []
            for n in sorted(int(p.split(".")[0]) for p in os.listdir(traza) if p.endswith(".sql")):
                salida.append(((traza / f"{n}.args").read_text().splitlines(), (traza / f"{n}.sql").read_text()))
            return salida

    c = C()
    c.org = org
    return c


def _variables(args):
    return dict(a.split("=", 1) for a in args if "=" in a and not a.startswith("ON_ERROR"))


def test_vale_entrada(consola):
    consola.responder({"existe": True, "activo": True, "rol": "superadmin", "creado": True})
    r = panel_vales.vale_entrada("admin", "120")
    assert r["url"].startswith("https://mail.example.org:8443/entrar?vale=")
    vale = r["url"].split("vale=")[1]
    assert len(vale) == 43 and r["valido_segundos"] == 120
    ((args, sql),) = consola.llamadas()
    v = _variables(args)
    assert v["huella"] == hashlib.sha256(vale.encode()).hexdigest()
    assert vale not in " ".join(args) and vale not in sql  # en la base solo el hash
    assert v["admin"] == "admin" and v["vida"] == "120" and v["quien"] == "consola:wilson"
    assert "clave-de-prueba" not in " ".join(args)
    assert ":'admin'" in sql and "vale_entrada_emitido" in sql


def test_vale_entrada_con_la_direccion_de_la_organizacion(consola):
    consola.org.write_text('ORG_URL_PANEL="https://panel.example.org:9443/"\n')
    consola.responder({"existe": True, "activo": True, "rol": "admin", "creado": True})
    assert panel_vales.vale_entrada("ana", None)["url"].startswith("https://panel.example.org:9443/entrar?vale=")
    assert panel_vales.vale_entrada("ana", None, host="otro.example.org")["url"].startswith("https://otro.example.org:8443/")


@pytest.mark.parametrize("vida", ["5", "901", "dos", "-1"])
def test_vida_acotada(consola, vida):
    with pytest.raises(panel_bd.ErrorConsola):
        panel_vales.vale_entrada("admin", vida)
    assert consola.llamadas() == []


@pytest.mark.parametrize("admin", ["", "con espacio", "a;b", "-x", "a" * 300, "admin'--"])
def test_nombre_de_admin_invalido(consola, admin):
    with pytest.raises(panel_bd.ErrorConsola):
        panel_vales.vale_entrada(admin, None)
    assert consola.llamadas() == []


def test_admin_inexistente_o_desactivado(consola):
    consola.responder({"existe": False, "activo": False, "rol": None, "creado": False})
    with pytest.raises(panel_bd.ErrorConsola, match="no hay ningún"):
        panel_vales.vale_entrada("nadie", None)
    consola.responder({"existe": True, "activo": False, "rol": "admin", "creado": False})
    with pytest.raises(panel_bd.ErrorConsola, match="desactivada"):
        panel_vales.vale_entrada("ana", None)


@pytest.mark.parametrize("host", ["mal host", "x/y", "a@b.example", "https://x.example"])
def test_host_invalido(consola, host):
    with pytest.raises(panel_bd.ErrorConsola):
        panel_vales.vale_entrada("admin", None, host=host)


def test_vale_soporte_solo_lectura_por_defecto(consola):
    consola.responder({"dominio": "example.com"})
    r = panel_vales.vale_soporte("Example.COM", True, None, "ticket\t42")
    assert r["url"].startswith("https://mail.example.org:8444/?vale=") and r["modo"] == "solo_lectura"
    assert r["valido_segundos"] == 300
    (_, (args, sql)) = consola.llamadas()  # primero el portal de la empresa, después el vale
    v = _variables(args)
    assert v["dominio"] == "example.com" and v["solo"] == "true" and v["motivo"] == "ticket 42"
    assert v["huella"] == hashlib.sha256(r["url"].split("vale=")[1].encode()).hexdigest()
    assert "pd_vales_soporte" in sql and "soporte_vale_emitido" in sql


def test_vale_soporte_con_acciones_y_portal_propio(consola):
    consola.responder({"host": "mail.example.com"}, "portal")
    consola.responder({"dominio": "example.com"})
    r = panel_vales.vale_soporte("example.com", False, "60")
    assert r["url"].startswith("https://mail.example.com:8444/?vale=") and r["modo"] == "con_acciones"
    assert _variables(consola.llamadas()[-1][0])["solo"] == "false"


def test_vale_soporte_dominio_ajeno_o_invalido(consola):
    consola.responder({"dominio": None})
    with pytest.raises(panel_bd.ErrorConsola, match="no está en este servidor"):
        panel_vales.vale_soporte("example.net", True, None)
    for malo in ("", "sin-punto", "a b.example", "x.example;", "-x.example"):
        with pytest.raises(panel_bd.ErrorConsola):
            panel_vales.vale_soporte(malo, True, None)


def test_falta_la_tabla(consola, tmp_path, monkeypatch):
    malo = tmp_path / "psql-sin-tabla"
    malo.write_text('#!/bin/sh\ncat >/dev/null\necho \'ERROR:  relation "pd_vales_soporte" does not exist\' >&2\nexit 1\n')
    malo.chmod(0o755)
    monkeypatch.setattr(panel_bd, "PSQL", str(malo))
    with pytest.raises(panel_bd.FaltaTabla, match="ajuste 66"):
        panel_vales.vale_soporte("example.com", True, None, host="mail.example.org")


def test_opciones():
    pos, op = panel_bd.opciones(["admin", "--vida", "60", "--json"], ("--vida",), ("--json",))
    assert pos == ["admin"] and op == {"--vida": "60", "--json": True}
    for malas in (["--vida"], ["--otra", "x"]):
        with pytest.raises(panel_bd.ErrorConsola):
            panel_bd.opciones(malas, ("--vida",), ())


@pytest.mark.parametrize("programa", ["maquita-panel", "maquita-panel-dominio"])
def test_ayuda_y_orden_desconocida(programa):
    ruta = os.path.join(RAIZ, "deploy", "panel", programa)
    r = subprocess.run([sys.executable, ruta, "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "vale-" in r.stdout
    r = subprocess.run([sys.executable, ruta, "borrar-todo"], capture_output=True, text=True)
    assert r.returncode == 1 and "orden desconocida" in r.stderr
