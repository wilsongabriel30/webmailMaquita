"""Observación y datos de los sitios (deploy/sitios/lib): visor de registros, resumen de visitas, disponibilidad
con avisos limitados y copias del sitio con su tope. Sin root: rutas y envíos inyectados."""

import datetime
import gzip
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sitios_lib import cargar, sitio  # noqa: E402

m = cargar()
ErrorSitio = m["comun"].ErrorSitio
D = "example.org"


@pytest.fixture
def meta(tmp_path, monkeypatch):
    return sitio(tmp_path, monkeypatch)


# --- Visor de registros ---


def test_registros_ultimas_y_filtro(meta):
    with open(os.path.join(meta["registros"], "error.log"), "w") as f:
        f.write("".join(f"línea {i} {'PHP Fatal' if i % 10 == 0 else 'aviso'}\n" for i in range(100)))
    r = m["visor_registros"].ultimas(D, "error", 5)
    assert r["lineas"] == [f"línea {i} {'PHP Fatal' if i % 10 == 0 else 'aviso'}" for i in range(95, 100)]
    r = m["visor_registros"].ultimas(D, "error", 3, "php fatal")
    assert r["lineas"] == ["línea 70 PHP Fatal", "línea 80 PHP Fatal", "línea 90 PHP Fatal"]
    assert m["visor_registros"].ultimas(D, "acceso", 10)["existe"] is False


@pytest.mark.parametrize("tipo", ["../error", "/etc/passwd", "cron-0000", "error.log"])
def test_registros_tipo_no_valido(meta, tipo):
    with pytest.raises(ErrorSitio):
        m["visor_registros"].ultimas(D, tipo, 10)


def test_registros_tope_y_filtro(meta):
    with pytest.raises(ErrorSitio):
        m["visor_registros"].ultimas(D, "error", 1001)
    with pytest.raises(ErrorSitio):
        m["visor_registros"].ultimas(D, "error", 10, "a\nb")


def test_registro_php_enlace_rechazado(meta, tmp_path):
    """tmp/ es del usuario del sitio: un enlace a un archivo del sistema no se lee."""
    (tmp_path / "shadow").write_text("root:secreto")
    os.symlink(str(tmp_path / "shadow"), os.path.join(meta["tmp"], "php-errores.log"))
    with pytest.raises(ErrorSitio):
        m["visor_registros"].ultimas(D, "php", 10)


# --- Estadísticas ---


def _linea(dia, ip="192.0.2.1", url="/", codigo=200, bytes_=1000, agente="Mozilla/5.0"):
    return f'{ip} - - [{dia:%d/%b/%Y}:10:00:00 +0000] "GET {url} HTTP/1.1" {codigo} {bytes_} "-" "{agente}"\n'


def test_resumen_por_dia(meta, tmp_path, monkeypatch):
    est = m["estadisticas"]
    monkeypatch.setattr(est, "DATOS", str(tmp_path / "estadisticas"))
    monkeypatch.setattr(est, "GOACCESS", "goaccess-que-no-existe")
    hoy = datetime.date(2026, 10, 21)
    ayer = hoy - datetime.timedelta(days=1)
    viejo = hoy - datetime.timedelta(days=40)
    with open(os.path.join(meta["registros"], "acceso.log"), "w") as f:
        f.write(_linea(hoy) + _linea(hoy, url="/estilo.css") + _linea(hoy, ip="198.51.100.7") +
                _linea(hoy, ip="203.0.113.9", agente="Googlebot/2.1") + "basura\n")
    with gzip.open(os.path.join(meta["registros"], "acceso.log.2.gz"), "wt") as f:
        f.write(_linea(ayer, bytes_=500) + _linea(viejo))
    datos = est.generar(D, hoy=hoy)
    resumen = datos["resumen"]
    assert len(resumen["dias"]) == 30 and datos["informe"] is False and datos["goaccess"] is False
    dia_hoy = resumen["dias"][-1]
    assert dia_hoy == {"fecha": "2026-10-21", "visitas": 2, "paginas": 3, "solicitudes": 4, "bytes": 4000}
    assert resumen["dias"][-2]["bytes"] == 500
    assert resumen["totales"]["solicitudes"] == 5  # la de hace 40 días no cuenta
    with pytest.raises(ErrorSitio):
        est.informe(D, str(tmp_path))


# --- Disponibilidad ---


@pytest.fixture
def disp(tmp_path, monkeypatch):
    d = m["disponibilidad"]
    monkeypatch.setattr(d, "DATOS", str(tmp_path / "disponibilidad"))
    monkeypatch.setattr(d, "ORGANIZACION", str(tmp_path / "organizacion.env"))
    (tmp_path / "organizacion.env").write_text('ORG_CORREOS_AVISOS="ti@example.com"\n')
    return d


def _fallo():
    return {"ok": False, "codigo": None, "ms": 15000, "dias_certificado": None, "motivo": "sin respuesta"}


def _bien():
    return {"ok": True, "codigo": 200, "ms": 80, "dias_certificado": 60, "motivo": None}


def test_aviso_tras_dos_fallos_y_al_volver(meta, disp):
    enviados = []
    enviar = lambda asunto, cuerpo, destinos: enviados.append((asunto, destinos)) or True  # noqa: E731
    disp.registrar(meta, _fallo(), enviar_fn=enviar)
    assert enviados == []
    disp.registrar(meta, _fallo(), enviar_fn=enviar)
    disp.registrar(meta, _fallo(), enviar_fn=enviar)
    assert enviados == [("El sitio example.org no responde", ["ti@example.com"])]
    disp.registrar(meta, _bien(), enviar_fn=enviar)
    assert enviados[-1][0] == "El sitio example.org vuelve a responder" and len(enviados) == 2
    estado = disp.ver(D)
    assert estado["caido"] is False and len(estado["historial"]) == 4 and estado["porcentaje"] == 25.0


def test_aviso_al_administrador_de_la_aplicacion(tmp_path, monkeypatch, disp):
    meta = sitio(tmp_path, monkeypatch, app_correo="admin@example.com")
    enviados = []
    for _ in range(2):
        disp.registrar(meta, _fallo(), enviar_fn=lambda a, c, d: enviados.append(d) or True)
    assert enviados == [["admin@example.com"]]


def test_limite_de_avisos_por_dia(meta, disp):
    enviados = []
    enviar = lambda asunto, cuerpo, destinos: enviados.append(cuerpo) or True  # noqa: E731
    ahora = datetime.datetime(2026, 10, 21, 8, 0).timestamp()
    for i in range(40):  # sube y baja sin parar
        resultado = _fallo() if i % 3 != 2 else _bien()
        disp.registrar(meta, resultado, ahora=ahora + i * 300, enviar_fn=enviar)
    assert len(enviados) == disp.TOPE_AVISOS_DIA
    assert "último aviso de hoy" in enviados[-1]
    # Al día siguiente vuelve a avisar.
    manana = datetime.datetime(2026, 10, 22, 8, 0).timestamp()
    for i in range(2):
        disp.registrar(meta, _fallo(), ahora=manana + i * 300, enviar_fn=enviar)
    assert len(enviados) == disp.TOPE_AVISOS_DIA + 1


def test_comprobar_todos_con_doble(meta, disp):
    r = disp.comprobar_todos(comprobar_fn=lambda dominio, https: _bien(), enviar_fn=lambda *a: True)
    assert r == {"comprobados": 1, "caidos": []}


# --- Copias del sitio ---


@pytest.fixture
def copias(tmp_path, monkeypatch, meta):
    c = m["copias_cliente"]
    monkeypatch.setattr(c, "COPIAS", str(tmp_path / "copias"))
    monkeypatch.setattr(c, "_permisos", lambda *a: None)  # chown al usuario del sitio: necesita root
    with open(os.path.join(meta["publico"], "index.html"), "w") as f:
        f.write("versión 1")
    ids = iter(f"20261021-1000{i:02d}" for i in range(60))
    monkeypatch.setattr(c.time, "strftime", lambda formato, *a: next(ids) if formato == "%Y%m%d-%H%M%S" else "2026-10-21 10:00")
    return c


def test_copias_tope(copias):
    for _ in range(copias.TOPE):
        copias.crear(D)
    assert len(copias.listar(D)["copias"]) == copias.TOPE
    with pytest.raises(ErrorSitio, match="máximo"):
        copias.crear(D)


def test_copia_restaurar_con_previa(copias, meta, tmp_path):
    primera = copias.crear(D)["copia"]["id"]
    with open(os.path.join(meta["publico"], "index.html"), "w") as f:
        f.write("versión 2")
    with open(os.path.join(meta["publico"], "nuevo.txt"), "w") as f:
        f.write("añadido después")
    r = copias.restaurar(D, primera)
    assert r["copia_previa"] and r["carpetas"] == ["publico"]
    with open(os.path.join(meta["publico"], "index.html")) as f:
        assert f.read() == "versión 1"
    assert not os.path.exists(os.path.join(meta["publico"], "nuevo.txt"))
    assert [c["motivo"] for c in copias.listar(D)["copias"]][0].startswith("antes de restaurar")
    # Descargar deja el archivo en subidas/ para el panel; borrar la quita.
    (tmp_path / "subidas").mkdir()
    d = copias.descargar(D, primera, str(tmp_path / "subidas"))
    assert os.path.getsize(tmp_path / "subidas" / d["archivo"]) == d["bytes"]
    copias.borrar(D, primera)
    assert primera not in [c["id"] for c in copias.listar(D)["copias"]]


def test_restaurar_exige_sitio_para_la_previa(copias):
    for _ in range(copias.TOPE):
        ultima = copias.crear(D)["copia"]["id"]
    with pytest.raises(ErrorSitio, match="copia previa"):
        copias.restaurar(D, ultima)


@pytest.mark.parametrize("ident", ["../../etc", "20261021", "x" * 15])
def test_copia_id_no_valido(copias, ident):
    with pytest.raises(ErrorSitio):
        copias.borrar(D, ident)


# --- Despacho y limpieza ---


def test_despacho_rechaza_formas_raras(meta):
    od = m["ordenes_datos"]
    for args in (["registros", D, "error"], ["archivos-listar", D], ["copia-borrar", D, "x"],
                 ["archivos-recuperar", D, "zz"], ["estadisticas", D, "extra"]):
        with pytest.raises(ErrorSitio):
            od.despachar(args)


def test_limpiar_sitio_y_huerfanos(meta, tmp_path, monkeypatch, disp):
    est, cop = m["estadisticas"], m["copias_cliente"]
    monkeypatch.setattr(est, "DATOS", str(tmp_path / "estadisticas"))
    monkeypatch.setattr(cop, "COPIAS", str(tmp_path / "copias"))
    monkeypatch.setattr(m["ordenes_datos"], "SUBIDAS", str(tmp_path / "subidas"))
    monkeypatch.setattr(m["ordenes_datos"], "PAPELERA", str(tmp_path / "papelera"))
    for carpeta in (tmp_path / "estadisticas" / D, tmp_path / "copias" / D, tmp_path / "estadisticas" / "example.com"):
        carpeta.mkdir(parents=True)
    disp.registrar(meta, _bien())
    papelera = tmp_path / "baja"
    papelera.mkdir()
    m["ordenes_datos"].limpiar_sitio(meta, str(papelera))
    assert not (tmp_path / "estadisticas" / D).exists() and not (tmp_path / "copias" / D).exists()
    assert (papelera / "copias-del-sitio").is_dir()
    assert not os.path.exists(disp._ruta(D))
    r = m["ordenes_datos"].huerfanos()
    assert "example.com" in r["datos_huerfanos_borrados"]
