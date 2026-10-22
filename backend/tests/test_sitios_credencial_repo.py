"""Autenticación de git de un sitio (deploy/sitios/lib/git_clave.py y git_credencial.py): repositorios privados de los
sitios PHP y de las aplicaciones propias Node.js, Python y estáticas.

Sin root y sin red: el usuario del sitio es el de la prueba (se quitan runuser y chown) y la prueba con el servidor
de git («git ls-remote») se sustituye. Las claves SSH se crean en cada prueba con ssh-keygen y se tiran; el token y
la contraseña son valores ficticios evidentes."""

import json
import os
import shutil
import stat
import subprocess
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sitios_lib import cargar, sitio  # noqa: E402

m = cargar()
gc, gcred, gs, propias, srv = m["git_clave"], m["git_credencial"], m["git_sitio"], m["propias"], m["propias_servicio"]
comun = m["comun"]
ErrorSitio = comun.ErrorSitio
D = "example.org"
SSH = "git@git.example.org:ana/app.git"
HTTPS = "https://git.example.org/ana/app.git"
TOKEN = "token-ficticio-de-prueba-0000"
CONTRASENA = "contraseña ficticia de prueba"
con_ssh_keygen = pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="hace falta ssh-keygen")


def clave_nueva(tmp_path, tipo="ed25519", bits=None, frase=""):
    """Una clave SSH de usar y tirar (nunca una de verdad)."""
    ruta = tmp_path / f"clave-{tipo}-{bits or 0}-{len(frase)}"
    subprocess.run(["ssh-keygen", "-q", "-t", tipo, *(["-b", str(bits)] if bits else []), "-N", frase, "-C", "prueba",
                    "-f", str(ruta)], check=True)
    return ruta.read_text()


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    meta = sitio(tmp_path, monkeypatch, app=None)
    real = comun.ejecutar

    def ejecutar(cmd, entrada=None, como=None, cwd=None, tiempo=600, env_extra=None):  # sin runuser ni chown
        return "" if cmd[0] == "chown" else real(cmd, entrada=entrada, cwd=cwd, tiempo=tiempo, env_extra=env_extra)

    for modulo in (gc, gcred, gs):
        monkeypatch.setattr(modulo, "ejecutar", ejecutar)
    monkeypatch.setattr(gcred, "SUBIDAS", str(tmp_path / "subidas"))
    (tmp_path / "subidas").mkdir()
    pruebas = []

    def probar(meta_, repo, env):
        pruebas.append((repo, env))
        if mundo_.falla:
            raise ErrorSitio(mundo_.falla)

    monkeypatch.setattr(gc, "probar", probar)

    class Mundo:
        falla = None

    mundo_ = Mundo()
    mundo_.meta, mundo_.tmp, mundo_.pruebas = meta, tmp_path, pruebas
    return mundo_


def leer_meta():
    return comun.leer_meta(D)


def modo(ruta):
    return stat.S_IMODE(os.stat(ruta).st_mode)


# --- Dirección del repositorio ---


@pytest.mark.parametrize("repo,esquema", [(HTTPS, "https"), (SSH, "ssh"), ("ssh://git@git.example.org/ana/app.git", "ssh"),
                                          ("ssh://git@git.example.org:2222/ana/app.git", "ssh")])
def test_direcciones_validas(repo, esquema):
    assert gc.validar_repo(repo) == (esquema, "git.example.org")


@pytest.mark.parametrize("repo", [f"https://ana:{TOKEN}@git.example.org/a.git", f"https://{TOKEN}@git.example.org/a.git",
                                  "ssh://ana:clave@git.example.org/a.git", "http://ana:x@git.example.org/a.git"])
def test_credenciales_en_la_direccion_se_rechazan_explicando(repo):
    with pytest.raises(ErrorSitio) as e:
        gc.validar_repo(repo)
    assert "Autenticación" in str(e.value) and "clave de despliegue" in str(e.value)


@pytest.mark.parametrize("repo", ["http://git.example.org/a.git", "file:///srv/sitios/otro", "ext::sh -c id",
                                  "git@git.example.org:../a", "-oProxyCommand=id@git.example.org:a", "", None])
def test_direcciones_no_validas(repo):
    with pytest.raises(ErrorSitio):
        gc.validar_repo(repo)


# --- Entorno de git de cada método ---


def test_entorno_con_clave(mundo):
    meta = dict(mundo.meta, git_auth={"metodo": "clave-propia"})
    env = gc.entorno(meta, SSH)
    ssh = env["GIT_SSH_COMMAND"]
    assert f"-i {gc.ruta_clave(meta)}" in ssh and "IdentitiesOnly=yes" in ssh and "BatchMode=yes" in ssh
    assert f"UserKnownHostsFile={gc.ruta_conocidos(meta)}" in ssh and "StrictHostKeyChecking=accept-new" in ssh
    assert env["GIT_ALLOW_PROTOCOL"] == "https:ssh" and env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_KEY_0"] == "credential.helper" and env["GIT_CONFIG_VALUE_0"] == ""


def test_entorno_con_token_sin_el_secreto(mundo):
    meta = dict(mundo.meta, git_auth={"metodo": "token-https"})
    os.makedirs(gc.carpeta_credencial(meta))
    open(gc.ruta_credencial(meta), "w").write(f"username=ana\npassword={TOKEN}\n")
    env = gc.entorno(meta, HTTPS)
    assert env["GIT_ALLOW_PROTOCOL"] == "https" and "GIT_SSH_COMMAND" not in env
    assert env["GIT_CONFIG_COUNT"] == "2" and gc.ruta_credencial(meta) in env["GIT_CONFIG_VALUE_1"]
    assert not any(TOKEN in v for v in env.values())  # el token no va en el entorno: lo lee el ayudante


@pytest.mark.skipif(not shutil.which("git"), reason="hace falta git")
def test_el_ayudante_de_credenciales_da_el_token_a_git(mundo, tmp_path):
    """El ayudante de verdad, con «git credential fill» (sin red): devuelve el usuario y el token del archivo."""
    meta = dict(mundo.meta, git_auth={"metodo": "token-https"})
    os.makedirs(gc.carpeta_credencial(meta))
    open(gc.ruta_credencial(meta), "w").write(f"username=ana\npassword={TOKEN}\n")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), **gc.entorno(meta, HTTPS)}
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=git.example.org\n\n", text=True,
                       capture_output=True, env=env, check=True)
    assert "username=ana" in r.stdout and f"password={TOKEN}" in r.stdout


def test_entorno_sin_credencial_guardada(mundo):
    with pytest.raises(ErrorSitio, match="falta la credencial"):
        gc.entorno(dict(mundo.meta, git_auth={"metodo": "usuario-contrasena"}), HTTPS)


@pytest.mark.parametrize("metodo,repo", [("ninguna", SSH), ("token-https", SSH), ("usuario-contrasena", SSH),
                                         ("clave-propia", HTTPS)])
def test_metodo_que_no_sirve_para_la_direccion(mundo, metodo, repo):
    with pytest.raises(ErrorSitio):
        gc.entorno(dict(mundo.meta, git_auth={"metodo": metodo}), repo)


def test_sin_metodo_guardado():
    meta = {"dominio": D, "base": "/no-existe"}
    assert gc.metodo(meta) == "ninguna" and gc.metodo(meta, "clave-generada") == "clave-generada"
    assert gc.metodo(dict(meta, git_php={"repo": SSH})) == "clave-generada"  # sitios PHP de la v1.11
    assert gc.metodo(dict(meta, git_auth={"metodo": "token-https"}), "clave-generada") == "token-https"


@pytest.mark.parametrize("salida,parte", [
    ("git@git.example.org: Permission denied (publickey).\nfatal: Could not read from remote repository.", "credencial rechazada"),
    ("remote: Invalid username or password.\nfatal: Authentication failed for 'https://git.example.org/a.git/'", "credencial rechazada"),
    ("ERROR: Repository not found.\nfatal: Could not read from remote repository.", "repositorio no encontrado"),
    ("ssh: Could not resolve hostname git.example.org: Name or service not known", "servidor de git desconocido"),
    ("fatal: could not read Username for 'https://git.example.org': terminal prompts disabled", "pide credenciales"),
    ("Host key verification failed.", "huella del servidor"),
    ("warning: Could not find remote branch otra to clone.\nfatal: Remote branch otra not found in upstream origin", "rama"),
])
def test_errores_en_claro(salida, parte):
    assert parte in gc.explicar(salida)


def test_error_desconocido():
    assert gc.explicar("algo raro") is None


# --- Guardar cada método ---


@con_ssh_keygen
def test_clave_generada(mundo):
    datos = gcred.guardar(D, {"metodo": "clave-generada", "repo": SSH})
    assert datos["metodo"] == "clave-generada" and datos["configurada"]
    assert gc.RE_CLAVE_PUBLICA.fullmatch(datos["clave_publica"]) and datos["huella"].startswith("SHA256:")
    assert datos["prueba"] is None and mundo.pruebas == []  # recién creada: aún no está en el repositorio
    assert modo(gc.ruta_clave(mundo.meta)) == 0o600 and modo(gc.carpeta(mundo.meta)) == 0o700
    assert gcred.guardar(D, {"metodo": "clave-generada"})["prueba"] is None  # sin repositorio no se prueba
    otra = gcred.guardar(D, {"metodo": "clave-generada", "repo": SSH})  # ya existe: se conserva y se prueba
    assert otra["clave_publica"] == datos["clave_publica"] and otra["prueba"] == {"ok": True}
    mundo.falla = "credencial rechazada por el servidor de git"
    assert gcred.guardar(D, {"metodo": "clave-generada", "repo": SSH})["prueba"]["ok"] is False  # avisa, no falla
    assert gcred.guardar(D, {"metodo": "clave-generada", "regenerar": True})["clave_publica"] != datos["clave_publica"]
    with pytest.raises(ErrorSitio):
        gcred.guardar(D, {"metodo": "clave-generada", "repo": "https://git.example.org/a/../b.git"})


@con_ssh_keygen
@pytest.mark.parametrize("tipo,bits", [("ed25519", None), ("ecdsa", 256), ("rsa", 3072)])
def test_clave_propia(mundo, tipo, bits):
    privada = clave_nueva(mundo.tmp, tipo, bits)
    datos = gcred.guardar(D, {"metodo": "clave-propia", "repo": SSH, "clave_privada": privada.replace("\n", "\r\n")})
    ruta = gc.ruta_clave(mundo.meta)
    assert datos["configurada"] and datos["tipo_clave"].startswith(tipo.upper()) and datos["huella"].startswith("SHA256:")
    assert open(ruta).read() == privada and modo(ruta) == 0o600 and not os.path.exists(ruta + ".pub")
    assert "clave_publica" not in datos and privada.splitlines()[1] not in json.dumps(datos)
    assert privada.splitlines()[1] not in json.dumps(leer_meta())
    repo, env = mundo.pruebas[-1]
    assert repo == SSH and env["GIT_SSH_COMMAND"].startswith(f"ssh -i {ruta}.nueva ")  # se prueba antes de dejarla


@con_ssh_keygen
@pytest.mark.parametrize("tipo,bits,frase,error", [("rsa", 2048, "", "3072"), ("ed25519", None, "frase-de-prueba", "frase de paso")])
def test_clave_propia_no_admitida(mundo, tipo, bits, frase, error):
    with pytest.raises(ErrorSitio, match=error):
        gcred.guardar(D, {"metodo": "clave-propia", "repo": SSH, "clave_privada": clave_nueva(mundo.tmp, tipo, bits, frase)})
    assert not os.path.exists(gc.ruta_clave(mundo.meta) + ".nueva") and "git_auth" not in leer_meta()


@pytest.mark.parametrize("texto", ["no es una clave", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA== prueba", "x" * 20000])
def test_clave_propia_que_no_es_privada(mundo, texto):
    with pytest.raises(ErrorSitio, match="PRIVADA"):
        gcred.guardar(D, {"metodo": "clave-propia", "repo": SSH, "clave_privada": texto})


def test_token(mundo, monkeypatch):
    monkeypatch.setattr(gcred, "USUARIO_TOKEN", (("git.example.org", "x-access-token"),))
    datos = gcred.guardar(D, {"metodo": "token-https", "repo": HTTPS, "token": f" {TOKEN} "})
    ruta = gc.ruta_credencial(mundo.meta)
    assert open(ruta).read() == f"username=x-access-token\npassword={TOKEN}\n" and modo(ruta) == 0o600
    assert datos["configurada"] and datos["final"] == TOKEN[-4:] and datos["usuario"] == "x-access-token"
    assert TOKEN not in json.dumps(datos) and TOKEN not in json.dumps(leer_meta())
    assert mundo.pruebas[-1][1]["GIT_CONFIG_VALUE_1"].count(ruta + ".nueva") == 1


def test_token_sin_usuario_en_un_servidor_desconocido(mundo):
    with pytest.raises(ErrorSitio, match="usuario del token"):
        gcred.guardar(D, {"metodo": "token-https", "repo": HTTPS, "token": TOKEN})


def test_credencial_rechazada_deja_la_anterior(mundo):
    gcred.guardar(D, {"metodo": "usuario-contrasena", "repo": HTTPS, "usuario": "ana", "contrasena": CONTRASENA})
    mundo.falla = "credencial rechazada por el servidor de git"
    with pytest.raises(ErrorSitio, match="credencial rechazada"):
        gcred.guardar(D, {"metodo": "token-https", "repo": HTTPS, "usuario": "ana", "token": TOKEN})
    assert open(gc.ruta_credencial(mundo.meta)).read() == f"username=ana\npassword={CONTRASENA}\n"
    assert not os.path.exists(gc.ruta_credencial(mundo.meta) + ".nueva")
    assert gcred.estado(D)["metodo"] == "usuario-contrasena" and "final" not in leer_meta()["git_auth"]


@pytest.mark.parametrize("datos", [
    {"metodo": "otro"}, {"metodo": "token-https", "repo": HTTPS, "token": "corto"},
    {"metodo": "token-https", "repo": HTTPS, "token": "con espacio dentro"},
    {"metodo": "token-https", "token": TOKEN},  # sin repositorio no se puede probar
    {"metodo": "usuario-contrasena", "repo": HTTPS, "contrasena": CONTRASENA},  # falta el usuario
    {"metodo": "usuario-contrasena", "repo": HTTPS, "usuario": "ana", "contrasena": "a\nb"},
    {"metodo": "usuario-contrasena", "repo": HTTPS, "usuario": "ana;id", "contrasena": CONTRASENA},
    {"metodo": "token-https", "repo": SSH, "usuario": "ana", "token": TOKEN},
    {"metodo": "ninguna", "repo": SSH}, {"metodo": "ninguna", "desconocido": 1},
])
def test_formas_no_validas(mundo, datos):
    with pytest.raises(ErrorSitio):
        gcred.guardar(D, datos)
    assert "git_auth" not in leer_meta()


@con_ssh_keygen
def test_ninguna_y_borrar(mundo):
    gcred.guardar(D, {"metodo": "clave-generada"})
    datos = gcred.guardar(D, {"metodo": "ninguna", "repo": HTTPS})
    assert datos["metodo"] == "ninguna" and not datos["configurada"] and not os.path.exists(gc.ruta_clave(mundo.meta))
    gcred.guardar(D, {"metodo": "usuario-contrasena", "repo": HTTPS, "usuario": "ana", "contrasena": CONTRASENA})
    assert gcred.borrar(D)["metodo"] == "ninguna" and not os.path.exists(gc.ruta_credencial(mundo.meta))


def test_no_en_aplicaciones_del_catalogo(mundo):
    meta = leer_meta()
    meta["app"] = "wordpress"
    comun.guardar_meta(meta)
    with pytest.raises(ErrorSitio):
        gcred.guardar(D, {"metodo": "ninguna"})
    assert gcred.estado(D)["compatible"] is False


# --- La subida .cred ---


def test_subida_se_lee_y_se_borra(mundo):
    ruta = mundo.tmp / "subidas" / ("a" * 32 + ".cred")
    ruta.write_text(json.dumps({"metodo": "ninguna"}))
    assert gcred.leer_subida(ruta.name) == {"metodo": "ninguna"} and not ruta.exists()
    ruta.write_text("no es json")
    with pytest.raises(ErrorSitio):
        gcred.leer_subida(ruta.name)
    assert not ruta.exists()


@pytest.mark.parametrize("nombre", ["../x.cred", "a" * 32 + ".txt", "A" * 32 + ".cred", None])
def test_subida_nombres_no_validos(mundo, nombre):
    with pytest.raises(ErrorSitio):
        gcred.leer_subida(nombre)


def test_subida_enlace_no(mundo):
    destino = mundo.tmp / "fuera.json"
    destino.write_text(json.dumps({"metodo": "ninguna"}))
    os.symlink(destino, mundo.tmp / "subidas" / ("b" * 32 + ".cred"))
    with pytest.raises(ErrorSitio):
        gcred.leer_subida("b" * 32 + ".cred")
    assert destino.exists()


def test_despachar(mundo):
    (mundo.tmp / "subidas" / ("c" * 32 + ".cred")).write_text(json.dumps({"metodo": "ninguna"}))
    assert m["ordenes_v111"].despachar(["git-credencial-guardar", D, "c" * 32 + ".cred"])["metodo"] == "ninguna"
    assert m["ordenes_v111"].despachar(["git-credencial", D])["metodo"] == "ninguna"
    for args in (["git-credencial"], ["git-credencial", D, "x"], ["git-credencial-borrar", "../x"], ["git-credencial-otra", D]):
        with pytest.raises(ErrorSitio):
            m["ordenes_v111"].despachar(args)


# --- Sitios PHP y aplicaciones propias ---


def test_sitio_php_con_token_no_genera_clave(mundo, monkeypatch):
    monkeypatch.setitem(sys.modules, "sitio", types.SimpleNamespace(publicar_vhost=lambda meta: None))
    monkeypatch.setattr(m["red_publica"], "comprobar", lambda host: host)
    gcred.guardar(D, {"metodo": "token-https", "repo": HTTPS, "usuario": "ana", "token": TOKEN})
    datos = gs.configurar(D, {"repo": HTTPS})
    assert datos["configurado"] and datos["clave_publica"] is None and not os.path.exists(gc.ruta_clave(mundo.meta))
    with pytest.raises(ErrorSitio, match="SSH necesita una clave"):
        gs.configurar(D, {"repo": SSH})
    gs.quitar(D)
    assert "git_auth" not in leer_meta() and not os.path.exists(gc.ruta_credencial(mundo.meta))


@pytest.mark.parametrize("git", [SSH, "ssh://git@git.example.org/ana/app.git", HTTPS])
def test_propia_admite_repositorios_privados(git):
    assert propias._validar(D, "estatico", {"git": git})["git"] == git


@pytest.mark.parametrize("git", [f"https://ana:{TOKEN}@git.example.org/a.git", "http://git.example.org/a.git",
                                 "file:///etc/passwd"])
def test_propia_rechaza_credenciales_en_la_direccion(git):
    with pytest.raises(ErrorSitio):
        propias._validar(D, "estatico", {"git": git})


def test_propia_por_ssh_sin_clave_no_crea_nada(mundo, monkeypatch):
    monkeypatch.setitem(sys.modules, "sitio", types.SimpleNamespace())
    with pytest.raises(ErrorSitio, match="SSH necesita una clave"):
        propias.crear(D, "estatico", {"git": SSH})
    assert not os.path.exists(os.path.join(mundo.meta["base"], "app"))


def test_propia_clona_con_la_autenticacion(mundo, monkeypatch):
    vistas = []
    monkeypatch.setattr(gc, "correr_git", lambda meta, args, env, cwd=None, tiempo=600: vistas.append((args, env, cwd)) or "")
    meta = dict(mundo.meta, git_auth={"metodo": "clave-generada"}, app_dir="/srv/app", propia={"git": SSH})
    propias._git(meta, "pull", "--ff-only")
    args, env, cwd = vistas[0]
    assert args == ["pull", "--ff-only"] and cwd == "/srv/app" and env["HOME"] == mundo.meta["tmp"]
    assert f"-i {gc.ruta_clave(meta)}" in env["GIT_SSH_COMMAND"]


def test_correr_git_como_el_usuario(monkeypatch):
    vistas = []

    def run(cmd, **k):
        vistas.append((cmd, k))
        return subprocess.CompletedProcess(cmd, 128, "", "git@git.example.org: Permission denied (publickey).\nfatal: x")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ErrorSitio, match="credencial rechazada"):
        gc.correr_git({"usuario": "web0000", "base": "/srv/sitios/example.org"}, ["ls-remote", "--", SSH], {"A": "1"})
    cmd, k = vistas[0]
    assert cmd[:5] == ["runuser", "-u", "web0000", "--", "git"] and k["env"]["A"] == "1" and k["env"]["LANG"] == "C.UTF-8"


def test_la_aplicacion_no_ve_la_credencial(mundo):
    meta = dict(mundo.meta, app_dir=os.path.join(mundo.meta["base"], "app"),
                propia={"tipo": "node", "entrada": "server.js", "puerto": 20001})
    texto = srv.texto_unidad(meta)
    linea = next(x for x in texto.splitlines() if x.startswith("InaccessiblePaths="))
    assert "-" + gc.carpeta(meta) in linea.split()
