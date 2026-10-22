"""Archivos del sistema que cambia una actualización (deploy/actualizar/lib/vigilados.py): foto con sumas,
comparación (creados, modificados, borrados), copias del contenido anterior y parches locales."""

import glob
import importlib.util
import os
import stat
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(RAIZ, "deploy", "actualizar", "lib")
LISTA = os.path.join(RAIZ, "deploy", "actualizar", "vigilados.txt")


@pytest.fixture
def v():
    spec = importlib.util.spec_from_file_location("vigilados_actualizar", os.path.join(LIB, "vigilados.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _importar(nombre):
    """Importa un módulo de la biblioteca del actualizador sin dejar en sys.modules «proceso», «version»…"""
    previos = set(sys.modules)
    sys.path.insert(0, LIB)
    try:
        return importlib.import_module(nombre)
    finally:
        sys.path.remove(LIB)
        for m in set(sys.modules) - previos:
            del sys.modules[m]


def _escribir(ruta, texto, modo=0o644):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w") as f:
        f.write(texto)
    os.chmod(ruta, modo)


def _git(repo):
    def git(*args, tiempo=300):
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True)
        return r.stdout.strip()
    return git


@pytest.fixture
def sistema(tmp_path):
    """Un «sistema» de juguete: bind, nginx con un enlace, una biblioteca del producto y un .env."""
    s = tmp_path / "sistema"
    _escribir(str(s / "etc/bind/maquita-zonas.conf"), 'zone "example.org" { type master; };\n')
    _escribir(str(s / "etc/bind/zona.jnl"), "diario\n")
    _escribir(str(s / "etc/nginx/sites-available/webmail"), "server { listen 192.0.2.10:443; }\n")
    os.makedirs(s / "etc/nginx/sites-enabled")
    os.symlink(str(s / "etc/nginx/sites-available/webmail"), str(s / "etc/nginx/sites-enabled/webmail"))
    _escribir(str(s / "usr/local/lib/maquita-dns/zona.py"), "ORIGINAL = True\n")
    _escribir(str(s / "usr/local/lib/maquita-dns/comun.py"), "COMUN = 1\n")
    _escribir(str(s / "opt/app/backend/.env"), "SECRET_KEY=valor-de-prueba\n", 0o640)
    lista = f"""
# comentario
[bind]
{s}/etc/bind/*
[nginx]
{s}/etc/nginx/{{sites-available,sites-enabled}}/**
[programas del producto]
{s}/usr/local/lib/maquita-dns/*.py  deploy/dns/lib/
[aplicaciones]
{s}/opt/app/*/.env
!/**/*.jnl
"""
    return s, lista


def test_leer_lista_grupos_llaves_origenes_y_exclusiones(v):
    entradas, excluir = v.leer_lista("""
[nginx]
/etc/nginx/{conf.d,snippets}/*.conf
[fail2ban]
/etc/fail2ban/filter.d/sitios-*.conf  deploy/sitios/fail2ban/filtro-sitios-*.conf
relativa/no/vale
/etc/../root/no/vale
!/**/*.{db,lmdb}
""")
    assert [(e["grupo"], e["patron"]) for e in entradas] == [
        ("nginx", "/etc/nginx/conf.d/*.conf"), ("nginx", "/etc/nginx/snippets/*.conf"),
        ("fail2ban", "/etc/fail2ban/filter.d/sitios-*.conf")]
    assert entradas[2]["origen"] == "deploy/sitios/fail2ban/filtro-sitios-*.conf"
    assert excluir == ["/**/*.db", "/**/*.lmdb"]


def test_origen_por_carpeta_y_por_comodin(v):
    e = {"patron": "/etc/fail2ban/filter.d/sitios-*.conf", "origen": "deploy/sitios/fail2ban/filtro-sitios-*.conf"}
    assert v._origen_de(e, "/etc/fail2ban/filter.d/sitios-wordpress.conf") == "deploy/sitios/fail2ban/filtro-sitios-wordpress.conf"
    e = {"patron": "/usr/local/lib/maquita-dns/*.py", "origen": "deploy/dns/lib/"}
    assert v._origen_de(e, "/usr/local/lib/maquita-dns/zona.py") == "deploy/dns/lib/zona.py"
    assert v._origen_de({"patron": "/x/**", "origen": "deploy/*"}, "/x/a/b") is None  # «**» no se traduce


def test_expandir_no_entra_en_enlaces_a_carpetas(v, tmp_path):
    _escribir(str(tmp_path / "fuera/secreto.txt"), "no debe aparecer\n")
    _escribir(str(tmp_path / "etc/x/a.conf"), "a\n")
    _escribir(str(tmp_path / "etc/x/sub/b.conf"), "b\n")
    os.symlink(str(tmp_path / "fuera"), str(tmp_path / "etc/x/enlace"))
    encontrados = v.expandir(f"{tmp_path}/etc/x/**")
    assert sorted(os.path.relpath(r, tmp_path) for r in encontrados) == ["etc/x/a.conf", "etc/x/enlace", "etc/x/sub/b.conf"]
    assert v.expandir(f"{tmp_path}/etc/x/*.conf") == [f"{tmp_path}/etc/x/a.conf"]
    assert v.expandir(f"{tmp_path}/etc/x/a.conf") == [f"{tmp_path}/etc/x/a.conf"]
    assert v.expandir(f"{tmp_path}/etc/x/no-existe") == []


def test_foto_y_comparacion(v, sistema, tmp_path):
    s, lista = sistema
    entradas, excluir = v.leer_lista(lista)
    vig = v.rutas(entradas, excluir)
    assert str(s / "etc/bind/zona.jnl") not in vig  # excluido
    assert vig[str(s / "usr/local/lib/maquita-dns/zona.py")]["origen"] == "deploy/dns/lib/zona.py"
    copias = str(tmp_path / "respaldo/archivos-sistema")
    os.makedirs(copias, mode=0o700)
    antes = v.tomar(vig, copias)
    enlace = antes[str(s / "etc/nginx/sites-enabled/webmail")]
    assert enlace["tipo"] == "enlace" and not enlace.get("copiado")

    # La «actualización»: reescribe la zona, borra un archivo, crea otro, cambia permisos y el enlace.
    _escribir(str(s / "etc/bind/maquita-zonas.conf"), "// regenerado\n")
    os.remove(s / "usr/local/lib/maquita-dns/comun.py")
    _escribir(str(s / "usr/local/lib/maquita-dns/nuevo.py"), "NUEVO = 1\n")
    os.chmod(s / "opt/app/backend/.env", 0o600)
    os.remove(s / "etc/nginx/sites-enabled/webmail")
    os.symlink("/dev/null", str(s / "etc/nginx/sites-enabled/webmail"))

    despues = v.tomar(v.rutas(entradas, excluir))
    cambios = v.comparar(antes, despues, copias)
    rel = {c: [os.path.relpath(i["ruta"], s) for i in cambios[c]] for c in v.CATEGORIAS}
    assert rel == {"creados": ["usr/local/lib/maquita-dns/nuevo.py"],
                   "modificados": ["opt/app/backend/.env", "etc/bind/maquita-zonas.conf", "etc/nginx/sites-enabled/webmail"],
                   "borrados": ["usr/local/lib/maquita-dns/comun.py"]}
    por_ruta = {os.path.relpath(i["ruta"], s): i for i in cambios["modificados"]}
    assert por_ruta["opt/app/backend/.env"]["solo_permisos"] is True
    assert por_ruta["etc/nginx/sites-enabled/webmail"]["antes"].startswith("→ ")
    zona = por_ruta["etc/bind/maquita-zonas.conf"]
    assert zona["grupo"] == "bind"
    with open(zona["copia"]) as f:
        assert "example.org" in f.read()  # el contenido ANTERIOR, para ver el diff o recuperarlo

    v.podar(antes, cambios, copias)
    quedan = sorted(os.path.relpath(os.path.join(r, a), copias) for r, _, archivos in os.walk(copias) for a in archivos)
    assert [q.split("sistema/", 1)[1] for q in quedan] == [
        "etc/bind/maquita-zonas.conf", "opt/app/backend/.env", "usr/local/lib/maquita-dns/comun.py"]


def test_copias_privadas_y_sin_seguir_enlaces(v, sistema, tmp_path):
    s, lista = sistema
    _escribir(str(tmp_path / "fuera/clave"), "privada\n", 0o600)
    os.symlink(str(tmp_path / "fuera/clave"), str(s / "etc/bind/clave-enlazada"))
    copias = str(tmp_path / "copias")
    os.makedirs(copias, mode=0o700)
    foto = v.tomar(v.rutas(*v.leer_lista(lista)), copias)
    copia_env = os.path.join(copias, str(s / "opt/app/backend/.env").lstrip("/"))
    assert foto[str(s / "opt/app/backend/.env")]["copiado"]
    assert stat.S_IMODE(os.stat(copia_env).st_mode) == 0o600  # el .env era 0640: la copia, 0600
    for raiz, carpetas, _ in os.walk(copias):
        for d in carpetas:
            assert stat.S_IMODE(os.stat(os.path.join(raiz, d)).st_mode) == 0o700
    assert foto[str(s / "etc/bind/clave-enlazada")]["tipo"] == "enlace"
    assert not os.path.lexists(os.path.join(copias, str(s / "etc/bind/clave-enlazada").lstrip("/")))


def test_limite_de_tamano_de_las_copias(v, sistema, tmp_path, monkeypatch):
    s, lista = sistema
    monkeypatch.setattr(v, "MAX_COPIA", 10)
    copias = str(tmp_path / "copias")
    os.makedirs(copias, mode=0o700)
    foto = v.tomar(v.rutas(*v.leer_lista(lista)), copias)
    assert foto[str(s / "usr/local/lib/maquita-dns/comun.py")].get("copiado")  # 10 bytes: cabe
    assert not foto[str(s / "etc/bind/maquita-zonas.conf")].get("copiado")  # más grande: solo la suma
    assert foto[str(s / "etc/bind/maquita-zonas.conf")]["sha256"]


def _repo_producto(tmp_path, zona):
    repo = str(tmp_path / "repo")
    _escribir(os.path.join(repo, "deploy/dns/lib/zona.py"), zona)
    _escribir(os.path.join(repo, "deploy/dns/lib/comun.py"), "COMUN = 1\n")
    git = _git(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    git("-c", "user.email=equipo@example.org", "-c", "user.name=Equipo", "add", "-A")
    git("-c", "user.email=equipo@example.org", "-c", "user.name=Equipo", "commit", "-q", "-m", "versión instalada")
    return git, git("rev-parse", "HEAD")


def test_detecta_parches_locales_contra_la_version_anterior(v, sistema, tmp_path):
    s, lista = sistema
    # El servidor tiene zona.py parcheado a mano; comun.py es el del repositorio tal cual.
    git, commit = _repo_producto(tmp_path, "ORIGINAL = False\n")
    archivo_lista = tmp_path / "vigilados.txt"
    archivo_lista.write_text(lista)
    respaldo = str(tmp_path / "respaldo")
    os.makedirs(respaldo, mode=0o700)
    previa = v.foto_previa(respaldo, commit, git, lista=str(archivo_lista))
    zona, comun = str(s / "usr/local/lib/maquita-dns/zona.py"), str(s / "usr/local/lib/maquita-dns/comun.py")
    assert previa["foto"][zona]["cambios_locales"] is True
    assert previa["foto"][comun]["cambios_locales"] is False
    assert "cambios_locales" not in previa["foto"][str(s / "etc/bind/maquita-zonas.conf")]  # sin origen: no se sabe
    assert v.locales(previa) == [zona]

    # La versión nueva reinstala los dos archivos: el parche de zona.py se pierde, y se avisa.
    _escribir(zona, "ORIGINAL = False\nNUEVO = True\n")
    _escribir(comun, "COMUN = 2\n")
    res = v.informe(previa)
    mod = {i["ruta"]: i for i in res["modificados"]}
    assert mod[zona]["cambios_locales"] is True and "cambios_locales" not in mod[comun]
    assert res["cambios_locales"] == 1 and res["totales"] == {"creados": 0, "modificados": 2, "borrados": 0}
    with open(mod[zona]["copia"]) as f:
        assert f.read() == "ORIGINAL = True\n"  # el parche, recuperable
    informe = os.path.join(respaldo, "archivos-sistema.json")
    assert stat.S_IMODE(os.stat(informe).st_mode) == 0o600
    texto = v.texto(res)
    assert "TENÍA CAMBIOS LOCALES" in texto and mod[zona]["copia"] in texto and "2 modificados" in texto


def test_sin_arbol_de_git_no_marca_pero_sigue(v, sistema, tmp_path):
    s, lista = sistema
    archivo_lista = tmp_path / "vigilados.txt"
    archivo_lista.write_text(lista)
    respaldo = str(tmp_path / "respaldo")
    os.makedirs(respaldo, mode=0o700)

    def git_roto(*args, tiempo=300):
        raise RuntimeError("git no responde")

    previa = v.foto_previa(respaldo, "0" * 40, git_roto, lista=str(archivo_lista))
    assert "git no responde" in previa["error_locales"] and v.locales(previa) == []
    res = v.informe(previa)
    assert res["totales"]["modificados"] == 0 and "error_locales" in res


def test_resumen_acotado(v, monkeypatch):
    monkeypatch.setattr(v, "MAX_LISTA", 2)
    cambios = {"creados": [{"ruta": f"/etc/x{i}", "grupo": "g"} for i in range(5)], "modificados": [], "borrados": []}
    res = v.resumen(cambios, "/var/backups/x")
    assert res["totales"]["creados"] == 5 and len(res["creados"]) == 2 and res["recortado"] and res["copias"] == "/var/backups/x"


def test_lista_del_repositorio_es_valida():
    """Cada origen declarado en vigilados.txt existe en el repositorio (si no, nunca se marcaría nada)."""
    vigilados = _importar("vigilados")
    with open(LISTA) as f:
        entradas, excluir = vigilados.leer_lista(f.read())
    assert entradas and excluir
    grupos = {e["grupo"] for e in entradas}
    assert {"bind", "nginx", "fail2ban", "postfix", "dovecot", "systemd", "sudoers"} <= grupos
    for e in entradas:
        origen = e["origen"]
        if not origen:
            continue
        if origen.endswith("/"):
            assert os.path.isdir(os.path.join(RAIZ, origen)), origen
            nombre = os.path.basename(e["patron"])
            if "*" not in nombre:
                assert os.path.isfile(os.path.join(RAIZ, origen, nombre)), (origen, nombre)
        elif "*" in origen:
            assert glob.glob(os.path.join(RAIZ, origen)), origen
        else:
            assert os.path.isfile(os.path.join(RAIZ, origen)), origen


def test_historial_guarda_solo_los_totales():
    proceso = _importar("proceso")
    estado = {"estado": "terminada", "archivos_sistema": {"totales": {"creados": 1}, "cambios_locales": 0,
                                                          "creados": [{"ruta": "/etc/x", "grupo": "g"}], "copias": "/c"}}
    h = proceso._para_historial(estado)
    assert h["archivos_sistema"] == {"totales": {"creados": 1}, "cambios_locales": 0, "copias": "/c"}
    assert "creados" in estado["archivos_sistema"]  # el estado de progreso.json conserva la lista
