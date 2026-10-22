"""v1.11: usuarios de bases con permisos a medida y acceso remoto con TLS (deploy/sitios/lib). Sin MariaDB ni
PostgreSQL: el SQL que se ejecutaría se guarda y se comprueba como texto (identificadores, comillas, REQUIRE SSL)."""

import json
import os

import pytest

from tests.test_sitios_funciones_web import _PROPIOS, _b64, _modulos_de_sitios  # noqa: F401  (fijación automática)

bp, br, bu, bases, comun, od = (_PROPIOS[n] for n in ("bases_privilegios", "bases_remoto", "bases_usuarios", "bases",
                                                       "comun", "ordenes_desarrollo"))
ErrorSitio = comun.ErrorSitio
DOMINIO = "example.org"
HASH = "*" + "A" * 40
INYECCIONES = ["a'b", "a`b", 'a"b', "a;b", "a b", "A1", "a-b", "a\\b", "a\nb", "ab' OR '1'='1", "x" * 11, "1a"]


@pytest.fixture
def sql(tmp_path, monkeypatch):
    (tmp_path / "meta").mkdir()
    monkeypatch.setattr(comun, "META_DIR", str(tmp_path / "meta"))
    hechas = {"mariadb": [], "pg": [], "valor": []}
    monkeypatch.setattr(bu, "_sql_mariadb", lambda s: hechas["mariadb"].append(s))
    monkeypatch.setattr(bu, "_sql_pg", lambda s, base="postgres": hechas["pg"].append((base, s)))

    def valor(s):
        hechas["valor"].append(s)
        return hechas.get("hash", HASH) + "\n"

    monkeypatch.setattr(bu, "_valor_mariadb", valor)
    monkeypatch.setattr(br, "ESTADO_SERVIDOR", str(tmp_path / "bases-remoto.json"))
    monkeypatch.setattr(br, "CORTAFUEGOS_BASES", str(tmp_path / "bases.d"))
    monkeypatch.setattr(br, "CORTAFUEGOS", str(tmp_path / "no-hay-cortafuegos"))
    monkeypatch.setattr(br, "publicar_hba", lambda: hechas.setdefault("hba", []).append(br.lineas_hba()))
    comun.guardar_meta({"dominio": DOMINIO, "usuario": "webexample1234", "bd": "w_example1234",
                        "bases": [{"motor": "postgresql", "nombre": "x_example1234_00ff"}]})
    hechas["tmp"] = tmp_path
    return hechas


def _servidor_listo(sql, mariadb=True, postgresql=True):
    (sql["tmp"] / "bases-remoto.json").write_text(json.dumps(
        {"host": "servidor.example.org", "mariadb": {"activo": mariadb}, "postgresql": {"activo": postgresql}}))


def _usuario(nombre="lector"):
    return f"u_{comun.slug(DOMINIO)}_{nombre}"


# --- Permisos ---


def test_perfiles_y_lista_a_medida():
    assert bp.validar("mariadb", {"perfil": "lectura"}) == {"perfil": "lectura"}
    medida = bp.validar("mariadb", {"perfil": "medida", "lista": ["INSERT", "SELECT"]})
    assert medida == {"perfil": "medida", "lista": ["SELECT", "INSERT"]}  # en el orden de la lista cerrada
    assert bp.lista_de("mariadb", {"perfil": "todo"}) == ["ALL PRIVILEGES"]
    assert "DROP" in bp.lista_de("mariadb", {"perfil": "estructura"})
    assert "DROP" not in bp.lista_de("mariadb", {"perfil": "escritura"})
    assert bp.lista_de("mariadb", {"perfil": "lectura"}) == ["SELECT", "SHOW VIEW"]


@pytest.mark.parametrize("permisos", [
    {"perfil": "superusuario"}, {"perfil": "medida"}, {"perfil": "medida", "lista": []},
    {"perfil": "medida", "lista": ["SELECT; DROP DATABASE x"]}, {"perfil": "medida", "lista": ["GRANT OPTION"]},
    {"perfil": "medida", "lista": ["FILE"]}, {"perfil": "medida", "lista": ["SUPER"]}, {"perfil": "lectura", "x": 1},
    "lectura", None, ["SELECT"],
])
def test_permisos_fuera_de_la_lista_cerrada(permisos):
    with pytest.raises(ErrorSitio):
        bp.validar("mariadb", permisos)


def test_privilegios_de_un_motor_no_valen_en_el_otro():
    with pytest.raises(ErrorSitio):
        bp.validar("postgresql", {"perfil": "medida", "lista": ["SHOW VIEW"]})
    with pytest.raises(ErrorSitio):
        bp.validar("mariadb", {"perfil": "medida", "lista": ["TRUNCATE"]})


@pytest.mark.parametrize("nombre", ["a'b", "a`b", 'a"b', "a;b", "A", "1a", "a b", "a\nb", "", None, 3])
def test_identificadores_con_fullmatch(nombre):
    with pytest.raises(ErrorSitio):
        bp.ident(nombre)
    with pytest.raises(ErrorSitio):
        bp.mariadb_conceder(nombre, "u_x_lector", "localhost", {"perfil": "lectura"})
    with pytest.raises(ErrorSitio):
        bp.pg_conceder("x_a_00ff", nombre, "x_a_00ff", {"perfil": "lectura"})


@pytest.mark.parametrize("host", ["%", "192.0.2.1' OR '1", "localhost'", "*", "a.example.org"])
def test_origen_de_mariadb_sin_comodines_ni_nombres(host):
    with pytest.raises(ErrorSitio):
        bp.cuenta_mariadb("u_x_lector", host)


def test_sql_de_mariadb_y_postgresql():
    texto = bp.mariadb_conceder("w_x1", "u_x1_lector", "localhost", {"perfil": "lectura"})
    assert texto == ("REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'u_x1_lector'@'localhost';"
                     "GRANT SELECT, SHOW VIEW ON `w_x1`.* TO 'u_x1_lector'@'localhost';")
    pg = bp.pg_conceder("x_a_00ff", "u_a_lector", "x_a_00ff", {"perfil": "lectura"})
    assert 'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "u_a_lector";' in pg
    assert 'ALTER DEFAULT PRIVILEGES FOR ROLE "x_a_00ff" IN SCHEMA public GRANT SELECT ON TABLES TO "u_a_lector";' in pg
    assert "INSERT" not in pg and "CREATE" not in pg
    todo = bp.pg_conceder("x_a_00ff", "u_a_todo", "x_a_00ff", {"perfil": "todo"})
    assert 'GRANT "x_a_00ff" TO "u_a_todo";' in todo
    assert 'ALTER ROLE "u_a_todo" IN DATABASE "x_a_00ff" SET role = "x_a_00ff";' in todo
    estructura = bp.pg_conceder("x_a_00ff", "u_a_dev", "x_a_00ff", {"perfil": "estructura"})
    assert 'GRANT USAGE, CREATE ON SCHEMA public TO "u_a_dev";' in estructura


# --- Crear, permisos, clave y borrar ---


def test_crear_usuario_mariadb_con_prefijo_del_sitio(sql):
    r = bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    usuario = _usuario()
    assert r["creado"]["usuario"] == usuario and r["creado"]["base"] == "w_example1234" and len(r["creado"]["clave"]) >= 24
    texto = sql["mariadb"][-1]
    assert texto.startswith(f"CREATE USER '{usuario}'@'localhost' IDENTIFIED BY '")
    assert f"GRANT SELECT, SHOW VIEW ON `w_example1234`.* TO '{usuario}'@'localhost';" in texto
    meta = comun.leer_meta(DOMINIO)
    assert meta["bases_usuarios"][0]["permisos"] == {"perfil": "lectura"}
    assert "clave" not in json.dumps(meta["bases_usuarios"])  # la contraseña no se guarda


def test_crear_usuario_postgresql(sql):
    bu.crear(DOMINIO, "x_example1234_00ff", "app", {"perfil": "escritura"})
    usuario = _usuario("app")
    assert sql["pg"][0][0] == "postgres" and sql["pg"][0][1].startswith(f'CREATE ROLE "{usuario}" LOGIN PASSWORD')
    base, texto = sql["pg"][1]
    assert base == "x_example1234_00ff" and f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{usuario}";' in texto


@pytest.mark.parametrize("sufijo", INYECCIONES)
def test_sufijo_con_inyeccion_rechazado(sql, sufijo):
    with pytest.raises(ErrorSitio):
        bu.crear(DOMINIO, "w_example1234", sufijo, {"perfil": "lectura"})
    assert sql["mariadb"] == [] and sql["pg"] == []


@pytest.mark.parametrize("base", ["w_otro0001", "x_otro0001_00ff", "mysql", "postgres", "w_example1234`; DROP"])
def test_solo_bases_del_propio_sitio(sql, base):
    with pytest.raises(ErrorSitio):
        bu.crear(DOMINIO, base, "lector", {"perfil": "lectura"})
    assert sql["mariadb"] == []


def test_repetido_y_maximo(sql, monkeypatch):
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    with pytest.raises(ErrorSitio, match="ya existe"):
        bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "todo"})
    monkeypatch.setattr(bu, "MAXIMO", 1)
    with pytest.raises(ErrorSitio, match="como máximo"):
        bu.crear(DOMINIO, "w_example1234", "otro", {"perfil": "lectura"})


def test_permisos_clave_y_borrar(sql):
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    usuario = _usuario()
    bu.cambiar_permisos(DOMINIO, usuario, {"perfil": "medida", "lista": ["SELECT", "INSERT"]})
    assert f"GRANT SELECT, INSERT ON `w_example1234`.* TO '{usuario}'@'localhost';" in sql["mariadb"][-1]
    r = bu.nueva_clave(DOMINIO, usuario)
    assert sql["mariadb"][-1] == f"ALTER USER '{usuario}'@'localhost' IDENTIFIED BY '{r['creado']['clave']}';"
    bu.borrar(DOMINIO, usuario)
    assert sql["mariadb"][-1] == f"DROP USER IF EXISTS '{usuario}'@'localhost';"
    assert comun.leer_meta(DOMINIO)["bases_usuarios"] == []


@pytest.mark.parametrize("usuario", ["u_otro0001_lector", "w_example1234", "root", "u_example1234_lector'--"])
def test_usuario_ajeno_o_raro(sql, usuario):
    with pytest.raises(ErrorSitio):
        bu.borrar(DOMINIO, usuario)
    with pytest.raises(ErrorSitio):
        bu.nueva_clave(DOMINIO, usuario)


def test_borrar_la_base_borra_antes_sus_usuarios(sql, monkeypatch, tmp_path):
    bu.crear(DOMINIO, "x_example1234_00ff", "app", {"perfil": "todo"})
    llamadas = []
    monkeypatch.setattr(bases, "volcar", lambda cmd, destino: llamadas.append("volcar"))
    monkeypatch.setattr(bases, "_pg", lambda s, base="postgres": llamadas.append(s))
    monkeypatch.setattr(bases, "ejecutar", lambda *a, **k: "")
    meta = comun.leer_meta(DOMINIO)
    meta["tmp"] = str(tmp_path)
    comun.guardar_meta(meta)
    bases.borrar(DOMINIO, "x_example1234_00ff")
    usuario = _usuario("app")
    assert any(f'DROP ROLE IF EXISTS "{usuario}"' in s for _b, s in sql["pg"])
    assert comun.leer_meta(DOMINIO)["bases_usuarios"] == []


# --- Acceso remoto ---


@pytest.mark.parametrize("valor", ["0.0.0.0/0", "::/0", "192.0.0.0/7", "2001::/31"])
def test_nunca_a_todo_internet_ni_con_confirmacion(valor):
    with pytest.raises(ErrorSitio):
        br.red(valor, amplia=True)


@pytest.mark.parametrize("valor", ["172.16.0.0/12", "10.0.0.0/15", "2001:db8::/40"])
def test_redes_amplias_solo_con_confirmacion(valor):
    with pytest.raises(ErrorSitio, match="administrador general"):
        br.red(valor)
    assert br.red(valor, amplia=True)


@pytest.mark.parametrize("valor", ["127.0.0.1", "224.0.0.1", "0.0.0.0", "169.254.1.1", "fe80::1", "::1",
                                   "192.0.2.1; DROP", "192.0.2.300", "ejemplo", "", None, "192.0.2.0/24' OR"])
def test_origenes_no_validos(valor):
    with pytest.raises(ErrorSitio):
        br.red(valor, amplia=True)


def test_red_normalizada_y_host_de_mariadb():
    assert br.red("192.0.2.77/24") == "192.0.2.0/24"
    assert br.host_mariadb("192.0.2.0/24") == "192.0.2.0/255.255.255.0"
    assert br.host_mariadb("198.51.100.7/32") == "198.51.100.7"
    assert br.host_mariadb("2001:db8::7/128") == "2001:db8::7"
    with pytest.raises(ErrorSitio, match="IPv6"):
        br.host_mariadb("2001:db8::/64")


def test_remoto_exige_el_servidor_preparado(sql):
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    antes = list(sql["mariadb"])
    with pytest.raises(ErrorSitio, match="ajuste 72"):
        bu.remoto(DOMINIO, _usuario(), ["192.0.2.10"])
    assert sql["mariadb"] == antes


def test_remoto_mariadb_con_require_ssl_y_cortafuegos(sql):
    _servidor_listo(sql)
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    usuario = _usuario()
    r = bu.remoto(DOMINIO, usuario, ["192.0.2.10", "198.51.100.0/24"])
    texto = sql["mariadb"][-1]
    assert f"CREATE USER '{usuario}'@'192.0.2.10' IDENTIFIED BY PASSWORD '{HASH}' REQUIRE SSL;" in texto
    assert f"CREATE USER '{usuario}'@'198.51.100.0/255.255.255.0' IDENTIFIED BY PASSWORD '{HASH}' REQUIRE SSL;" in texto
    assert f"GRANT SELECT, SHOW VIEW ON `w_example1234`.* TO '{usuario}'@'192.0.2.10';" in texto
    reglas = json.loads((sql["tmp"] / "bases.d" / f"{DOMINIO}.json").read_text())
    assert reglas == {"dominio": DOMINIO, "reglas": [{"puerto": 3306, "origenes": ["192.0.2.10/32", "198.51.100.0/24"]}]}
    assert "sin cortafuegos propio" in r["cortafuegos"]
    # Cambiar la clave la cambia en todas sus cuentas; quitar las redes borra las remotas y cierra el puerto.
    clave = bu.nueva_clave(DOMINIO, usuario)["creado"]
    assert sql["mariadb"][-1].count("ALTER USER") == 3 and clave["servidor_remoto"] == "servidor.example.org"
    bu.remoto(DOMINIO, usuario, [])
    assert f"DROP USER IF EXISTS '{usuario}'@'192.0.2.10';" in sql["mariadb"][-1]
    assert "CREATE USER" not in sql["mariadb"][-1]
    assert not (sql["tmp"] / "bases.d" / f"{DOMINIO}.json").exists()


def test_remoto_rechaza_red_amplia_sin_confirmacion(sql):
    _servidor_listo(sql)
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    antes = list(sql["mariadb"])
    with pytest.raises(ErrorSitio, match="demasiado amplia"):
        bu.remoto(DOMINIO, _usuario(), ["172.16.0.0/12"])
    assert sql["mariadb"] == antes
    bu.remoto(DOMINIO, _usuario(), ["172.16.0.0/12"], amplia=True)
    assert "'172.16.0.0/255.240.0.0'" in sql["mariadb"][-1]


def test_remoto_sin_hash_copiable_no_crea_nada(sql):
    _servidor_listo(sql)
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    sql["hash"] = "'; DROP USER root; --"
    antes = list(sql["mariadb"])
    with pytest.raises(ErrorSitio, match="clave nueva"):
        bu.remoto(DOMINIO, _usuario(), ["192.0.2.10"])
    assert sql["mariadb"] == antes


def test_remoto_postgresql_en_pg_hba(sql):
    _servidor_listo(sql)
    bu.crear(DOMINIO, "x_example1234_00ff", "app", {"perfil": "lectura"})
    bu.remoto(DOMINIO, _usuario("app"), ["2001:db8::/64", "203.0.113.5"])
    assert sql["hba"][-1].splitlines()[1:] == [
        f"hostssl x_example1234_00ff {_usuario('app')} 2001:db8::/64 scram-sha-256",
        f"hostssl x_example1234_00ff {_usuario('app')} 203.0.113.5/32 scram-sha-256"]
    reglas = json.loads((sql["tmp"] / "bases.d" / f"{DOMINIO}.json").read_text())["reglas"]
    assert reglas == [{"puerto": 5432, "origenes": ["2001:db8::/64", "203.0.113.5/32"]}]


def test_remoto_ipv6_con_mascara_no_vale_en_mariadb(sql):
    _servidor_listo(sql)
    bu.crear(DOMINIO, "w_example1234", "lector", {"perfil": "lectura"})
    with pytest.raises(ErrorSitio, match="IPv6"):
        bu.remoto(DOMINIO, _usuario(), ["2001:db8::/64"])


# --- Despacho (forma de los argumentos) ---


@pytest.mark.parametrize("args", [
    ["base-usuario-crear", DOMINIO, "mysql", "lector", "e30"],
    ["base-usuario-crear", DOMINIO, "w_example1234", "lector"],
    ["base-usuario-remoto", DOMINIO, "u_example1234_lector", "W10", "todas"],
    ["waf-bloqueos", DOMINIO, "0"], ["waf-bloqueos", DOMINIO, "1000"],
    ["ssh-clave-agregar", DOMINIO, "root", "eA"], ["bases-usuarios", "EXAMPLE.ORG"],
])
def test_despacho_rechaza_formas_raras(sql, args):
    with pytest.raises(ErrorSitio):
        od.despachar(args)


def test_despacho_crea_con_permisos_en_b64(sql):
    r = od.despachar(["base-usuario-crear", DOMINIO, "w_example1234", "lector", _b64({"perfil": "todo"})])
    assert r["creado"]["usuario"] == _usuario()
    assert os.path.basename(comun.ruta_meta(DOMINIO)) == f"{DOMINIO}.json"


def test_estado_del_servidor_no_cuenta_como_sitio(tmp_path, monkeypatch):
    """bases-remoto.json vive junto a los metadatos de los sitios: listar no debe tomarlo por un sitio (fortaleza)."""
    carpeta = tmp_path / "meta"
    carpeta.mkdir()
    monkeypatch.setattr(comun, "META_DIR", str(carpeta))
    (carpeta / f"{DOMINIO}.json").write_text(json.dumps({"dominio": DOMINIO}))
    (carpeta / "bases-remoto.json").write_text(json.dumps({"mariadb": True, "postgresql": True}))
    assert [m["dominio"] for m in comun.todos_los_meta()] == [DOMINIO]
