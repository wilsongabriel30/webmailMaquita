"""Índice de texto completo: maquita-sudo (maquita-fts), el ayudante maquita-fts, el envoltorio con
límites del decodificador, la consulta del eDiscovery y las capacidades de búsqueda del webmail."""

import importlib
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import zipfile

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FTS = os.path.join(_RAIZ, "deploy", "dovecot", "fts")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def _cargar(nombre, ruta):
    cargador = importlib.machinery.SourceFileLoader(nombre, ruta)
    modulo = importlib.util.module_from_spec(importlib.util.spec_from_loader(nombre, cargador))
    cargador.exec_module(modulo)
    return modulo


ms = _cargar("maquita_sudo_fts", os.path.join(_RAIZ, "deploy", "sudoers", "maquita-sudo"))
fts = _cargar("maquita_fts", os.path.join(_FTS, "maquita-fts"))

EXISTE = lambda b: b.endswith("@example.org")  # noqa: E731  doble de «doveadm user»


def _ok(usuario, *args):
    return ms.autorizar(usuario, "maquita-fts", list(args), comprobar_buzon=EXISTE)


def _no(usuario, *args):
    with pytest.raises(ms.Rechazo):
        _ok(usuario, *args)


def test_maquita_sudo_deja_pasar_solo_estado_y_reindexar():
    assert _ok("maquita-admin", "estado") == ["estado"]
    assert _ok("maquita-admin", "reindexar", "ana.perez@example.org") == ["reindexar", "ana.perez@example.org"]
    assert ms.BINARIOS["maquita-fts"] == "/usr/local/sbin/maquita-fts"
    assert "maquita-fts" in ms.SOLO_RUTA_FIJA


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["estado", "--json"],
        ["indexar-inicial"],  # es del instalador, no del panel
        ["reindexar"],
        ["reindexar", "Ana@example.org"],  # mayúsculas: exacto o nada
        ["reindexar", "ana@example.org", "extra"],
        ["reindexar", "-A"],
        ["reindexar", "*"],
        ["reindexar", "ana@example.org\n"],  # fullmatch: un salto final no cuela
        ["reindexar", "ana@example.org;id"],
        ["reindexar", "nadie@example.com"],  # no existe (dominio ajeno)
        ["REINDEXAR", "ana@example.org"],
    ],
)
def test_maquita_sudo_rechaza_lo_demas(args):
    _no("maquita-admin", *args)


def test_www_data_no_toca_el_indice():
    _no("www-data", "estado")
    _no("www-data", "reindexar", "ana@example.org")


def test_carpetas_excluidas_del_indice_previo():
    carpetas = ["INBOX", "Sent", "Trash", "Trash.Viejo", "Junk", "Spam", "Archive", "Papelera", "Clientes.Trash"]
    assert fts.carpetas_a_indexar(carpetas) == ["INBOX", "Sent", "Archive", "Clientes.Trash"]
    assert fts.carpeta_excluida("Deleted Items")
    assert not fts.carpeta_excluida("Trashumancia")


def test_ayudante_valida_el_buzon_antes_de_llamar_a_doveadm(monkeypatch):
    llamadas = []
    monkeypatch.setattr(fts, "_doveadm", lambda *a, **k: llamadas.append(a))
    assert "error" in fts.reindexar("-A")
    assert "error" in fts.reindexar("ana@example.org\n")
    assert llamadas == []
    assert fts.es_buzon("ana@example.org")


def test_ayudante_reindexa_sin_papelera(monkeypatch):
    llamadas = []

    class R:
        def __init__(self, salida=""):
            self.returncode, self.stdout, self.stderr = 0, salida, ""

    def doveadm(*args, **_):
        llamadas.append(args)
        return R("INBOX\nTrash\nSent\nJunk\n") if args[:2] == ("mailbox", "list") else R()

    monkeypatch.setattr(fts, "_doveadm", doveadm)
    monkeypatch.setattr(fts, "_registrar", lambda texto: None)
    res = fts.reindexar("ana@example.org")
    assert res == {"ok": True, "buzon": "ana@example.org", "carpetas": 2}
    assert ("fts", "rescan", "-u", "ana@example.org") in llamadas
    indexadas = [a[-1] for a in llamadas if a[0] == "index"]
    assert indexadas == ["INBOX", "Sent"]
    assert all("-q" in a for a in llamadas if a[0] == "index")  # en segundo plano, por el indexador
    assert not any(a[0] in ("expunge", "flags", "move") for a in llamadas)  # el índice no toca mensajes


@pytest.mark.skipif(not shutil.which("timeout") or not shutil.which("ionice"), reason="sin coreutils/util-linux")
def test_envoltorio_con_limites(tmp_path):
    guion = _leer(os.path.join(_FTS, "decode2text.sh"))
    guion = guion.replace("LIB=/usr/local/lib/maquita-fts", f"LIB={os.path.join(_FTS, 'decodificador')}")
    guion = guion.replace("CONF=/etc/maquita-fts/decodificador.conf", f"CONF={tmp_path / 'c.conf'}")
    (tmp_path / "c.conf").write_text("MEMORIA_MB=512\nTIEMPO_TOTAL_S=20\nMEMORIA_MB=$(id)\n")
    ruta = tmp_path / "decode2text.sh"
    ruta.write_text(guion)
    docx = tmp_path / "d.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", '<w:document xmlns:w="urn:w"><w:t>Informe de Otavalo</w:t></w:document>')
    with open(docx, "rb") as entrada:
        r = subprocess.run(["bash", str(ruta), "application/octet-stream"], stdin=entrada, capture_output=True, timeout=60, check=False)
    assert r.returncode == 0, r.stderr
    assert "Informe de Otavalo" in r.stdout.decode()
    r = subprocess.run(["bash", str(ruta)], capture_output=True, timeout=60, check=False)
    assert b"application/pdf pdf" in r.stdout


def test_configuracion_de_dovecot_24():
    conf = _leer(os.path.join(_FTS, "61-busqueda-adjuntos.conf"))
    assert "fts_decoder_driver = script" in conf
    assert "fts_decoder_script_socket_path = maquita-decode2text" in conf
    assert "user = maquita-fts" in conf
    assert "fts_autoindex = no" in conf
    # Sintaxis 2.3 que en 2.4 rompe doveconf.
    lineas = [x.strip() for x in conf.splitlines() if x.strip() and not x.strip().startswith("#")]
    assert not any(x.startswith(("fts_decoder =", "fts_autoindex_exclude", "plugin {")) for x in lineas)
    # Sin el bloque «fts flatcurve {}» Dovecot 2.4 carga el motor pero no lo usa (probado con 2.4.1).
    motor = _leer(os.path.join(_RAIZ, "deploy", "dovecot", "busqueda", "60-busqueda.conf"))
    assert "\nfts flatcurve {\n}" in motor


def test_instalador_y_ajuste():
    instalar = _leer(os.path.join(_FTS, "instalar.sh"))
    for frase in ("--simular", "Sin cambios:", "Pendiente:", "Listo:", "doveconf -n", ".bak.$sello", "doveadm reload"):
        assert frase in instalar
    assert "IOSchedulingClass=idle" in instalar and "--nice=19" in instalar
    ajuste = _leer(os.path.join(_RAIZ, "deploy", "ajustes", "63-busqueda-en-adjuntos.sh"))
    assert "dovecot/fts/instalar.sh" in ajuste
    nuevo = _leer(os.path.join(_RAIZ, "deploy", "webmail", "instalar.sh"))
    assert "deploy/dovecot/fts/instalar.sh" in nuevo


def test_consulta_del_ediscovery_va_al_indice():
    from app.compliance.busqueda_doveadm import consulta_busqueda, orden_doveadm

    assert consulta_busqueda("INBOX", "2026-01-01T00:00", "", ["contrato", "-o x", "factura 12"]) == [
        "mailbox",
        "INBOX",
        "since",
        "2026-01-01",
        "OR",
        "text",
        "contrato",
        "OR",
        "text",
        "o x",
        "text",
        "factura 12",
    ]
    assert consulta_busqueda("Sent") == ["mailbox", "Sent"]
    assert consulta_busqueda("Sent", palabras=["\x00", " "]) == ["mailbox", "Sent"]
    orden = orden_doveadm("search", "-u", "ana@example.org", *consulta_busqueda("INBOX", palabras=["acta"]))
    assert orden[:4] == ["/usr/bin/sudo", "-n", "/usr/local/sbin/maquita-sudo", "doveadm"]
    # maquita-sudo (www-data) acepta la orden tal cual.
    validados = ms.autorizar("www-data", "doveadm", orden[4:], comprobar_buzon=EXISTE)
    assert validados[0] == "search"


def test_capacidades_con_adjuntos(tmp_path, monkeypatch):
    hechos = tmp_path / "hechos.txt"
    hechos.write_text("ana@example.org\n")
    conf = tmp_path / "61.conf"
    monkeypatch.setenv("FTS_HECHOS", str(hechos))
    monkeypatch.setenv("FTS_CONF_ADJUNTOS", str(conf))
    import app.mail.services.indice_texto as m

    m = importlib.reload(m)
    assert m.cuenta_indexada("ANA@example.org")
    assert not m.adjuntos_indexados()
    conf.write_text("x")
    assert m.adjuntos_indexados()


def test_hechos_del_instalador_actual_y_del_anterior(tmp_path, monkeypatch):
    nueva, vieja = tmp_path / "nueva.txt", tmp_path / "vieja.txt"
    nueva.write_text("ana@example.org\n")
    vieja.write_text("luis@example.org\n")
    monkeypatch.delenv("FTS_HECHOS", raising=False)
    import app.mail.services.indice_texto as m

    m = importlib.reload(m)
    monkeypatch.setattr(m, "_RUTAS_HECHOS", (str(nueva), str(vieja)))
    assert m.cuenta_indexada("ana@example.org") and m.cuenta_indexada("luis@example.org")
    # La ruta nueva es la que escriben busqueda-indexar-noche y maquita-fts (antes el webmail leía
    # otra y nunca daba la cuenta por indexada).
    assert fts.HECHOS == importlib.reload(m)._RUTAS_HECHOS[0] == "/var/lib/maquita-busqueda/hechas.txt"
    noche = _leer(os.path.join(_RAIZ, "deploy", "dovecot", "busqueda", "busqueda-indexar-noche"))
    assert "EST=/var/lib/maquita-busqueda" in noche and '"$EST/hechas.txt"' in noche
