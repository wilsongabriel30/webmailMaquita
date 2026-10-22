"""Despliegue desde git de los sitios PHP (deploy/sitios/lib/git_sitio.py y git_despliegue.py), sin root.

Con git, rsync y ssh-keygen de verdad: el repositorio es una carpeta local (la red y el usuario del sitio se
sustituyen), así se prueban de verdad las exclusiones, el borrado de lo que ya no está, los enlaces inseguros, los
permisos de lo publicado, las versiones guardadas y la vuelta atrás. La forma exacta de las órdenes que se lanzan
como el usuario del sitio (runuser, umask, sin ganchos de git) se comprueba aparte."""

import ipaddress
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sitios_lib import cargar, sitio  # noqa: E402

m = cargar()
gs, gd, red, ov = m["git_sitio"], m["git_despliegue"], m["red_publica"], m["ordenes_v111"]
ErrorSitio = m["comun"].ErrorSitio
D = "example.org"
REPO = "git@git.example.org:ana/sitio.git"
DOC = ipaddress.ip_network("203.0.113.0/24")
HERRAMIENTAS = all(shutil.which(h) for h in ("git", "rsync", "ssh-keygen"))
con_herramientas = pytest.mark.skipif(not HERRAMIENTAS, reason="hacen falta git, rsync y ssh-keygen")


@pytest.fixture
def red_de_prueba(monkeypatch):
    """203.0.113.x hace de Internet; 192.0.2.x y 127.0.0.1, de red interna."""
    monkeypatch.setattr(red, "es_publica", lambda d: d in DOC)
    nombres = {"git.example.org": "203.0.113.20", "interno.example.org": "192.0.2.5", "local.example.org": "127.0.0.1"}

    def resolver(host, *a, **k):
        if host not in nombres:
            raise socket.gaierror("no existe")
        return [(2, 1, 6, "", (nombres[host], 0))]

    monkeypatch.setattr(socket, "getaddrinfo", resolver)


@pytest.fixture
def mundo(tmp_path, monkeypatch, red_de_prueba):
    meta = sitio(tmp_path, monkeypatch, app=None, indexnow="0123456789abcdef0123456789abcdef")
    os.chmod(meta["publico"], 0o2750)
    monkeypatch.setattr(gs, "GANCHOS", str(tmp_path / "ganchos"))
    monkeypatch.setattr(gd, "CERROJOS", str(tmp_path / "cerrojos"))
    vhosts = []
    monkeypatch.setitem(sys.modules, "sitio", types.SimpleNamespace(publicar_vhost=lambda meta: vhosts.append(dict(meta))))
    real = m["comun"].ejecutar

    def ejecutar(cmd, entrada=None, como=None, cwd=None, tiempo=600, env_extra=None):  # sin runuser ni chown
        return "" if cmd[0] == "chown" else real(cmd, entrada=entrada, cwd=cwd, tiempo=tiempo, env_extra=env_extra)

    monkeypatch.setattr(gs, "ejecutar", ejecutar)
    monkeypatch.setattr(m["git_clave"], "ejecutar", ejecutar)  # carpetas y clave: comunes con las apps propias
    monkeypatch.setattr(gd, "en_curso", lambda meta: False)
    copias = []
    monkeypatch.setattr(m["copias_cliente"], "crear", lambda dominio, motivo="manual": copias.append((dominio, motivo)))
    repo = tmp_path / "repo"
    ordenes = []

    def correr(meta_, cmd, tiempo, env_extra=None, umask=0o027):
        """Como _correr, sin runuser; el repositorio de prueba es la carpeta local."""
        ordenes.append(list(cmd))
        cmd = [str(repo) if c == REPO else ("protocol.file.allow=always" if c == "protocol.file.allow=never" else c) for c in cmd]
        env = {**os.environ, **(env_extra or {}), "GIT_ALLOW_PROTOCOL": "file"}
        env.pop("GIT_SSH_COMMAND", None)
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, umask=umask)
        if r.returncode:
            raise ErrorSitio(f"{os.path.basename(cmd[0])}: {(r.stderr or r.stdout).strip()[-200:]}")
        return (r.stdout or "") + (r.stderr or "")

    monkeypatch.setattr(gd, "_correr", correr)
    numeros = iter(range(10, 60))
    monkeypatch.setattr(gd, "_nuevo_id", lambda meta: f"20261021-1010{next(numeros):02d}")

    class Mundo:
        pass

    w = Mundo()
    w.meta, w.tmp, w.vhosts, w.copias, w.repo, w.ordenes = meta, tmp_path, vhosts, copias, repo, ordenes
    return w


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@example.org",
                               "GIT_COMMITTER_NAME": "Ana", "GIT_COMMITTER_EMAIL": "ana@example.org"}).stdout


def confirmar(repo, archivos, mensaje):
    repo.mkdir(exist_ok=True)
    if not (repo / ".git").exists():
        git(repo, "init", "-q", "-b", "main")
    for nombre, contenido in archivos.items():
        ruta = repo / nombre
        if contenido is None:
            ruta.unlink()
            continue
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, tuple):  # («enlace», destino)
            os.symlink(contenido[1], ruta)
        else:
            ruta.write_text(contenido)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", mensaje)
    return git(repo, "rev-parse", "HEAD").strip()


def publico(w, *partes):
    return os.path.join(w.meta["publico"], *partes)


def leer_meta():
    return m["comun"].leer_meta(D)


# --- Validación ---


@pytest.mark.parametrize("repo", ["https://git.example.org/ana/sitio.git", "ssh://git@git.example.org/ana/sitio.git",
                                  "ssh://git@git.example.org:2222/ana/sitio.git", "git@git.example.org:ana/sitio.git"])
def test_repositorios_validos(red_de_prueba, repo):
    assert gs.validar({"repo": repo})["repo"] == repo


@pytest.mark.parametrize("repo", [
    "http://git.example.org/a.git", "file:///srv/sitios/otro", "/srv/sitios/otro", "ext::sh -c id",
    "-oProxyCommand=id@git.example.org:a", "git@-oProxyCommand=id:a", "git@git.example.org:-u/a",
    "https://ana:clave@git.example.org/a.git", "git@git.example.org:../a", "https://git.example.org/a/../../b",
    "git@interno.example.org:a.git", "git@local.example.org:a.git", "git@127.0.0.1:a.git", "git@192.0.2.1:a.git",
    "https://[::1]/a.git", "git@no-existe.example.org:a.git", "git@git.example.org:a b", "", None,
])
def test_repositorios_no_validos(red_de_prueba, repo):
    with pytest.raises(ErrorSitio):
        gs.validar({"repo": repo})


@pytest.mark.parametrize("campo,valor", [
    ("rama", "../x"), ("rama", "-x"), ("rama", "a..b"), ("rama", "x.lock"), ("rama", "a b"), ("rama", "a/"),
    ("carpeta", "../x"), ("carpeta", "a/../b"), ("carpeta", "."), ("carpeta", "a b"), ("raiz_web", "../publico"),
    ("raiz_web", "a\\b"), ("exclusiones", ["../x"]), ("exclusiones", ["*"]), ("exclusiones", ["a"] * 21),
    ("exclusiones", "subidas"), ("otra", "x"),
])
def test_campos_no_validos(red_de_prueba, campo, valor):
    with pytest.raises(ErrorSitio):
        gs.validar({"repo": REPO, campo: valor})


def test_validar_limpia(red_de_prueba):
    assert gs.validar({"repo": REPO, "rama": "", "carpeta": "/dist/", "raiz_web": "public",
                       "exclusiones": ["/subidas/", "subidas", "", ".env"]}) == {
        "repo": REPO, "rama": "main", "carpeta": "dist", "raiz_web": "public", "exclusiones": ["subidas", ".env"]}


# --- Configuración, clave y gancho ---


@con_herramientas
def test_configurar_sitio_vacio(mundo):
    datos = gs.configurar(D, {"repo": REPO, "raiz_web": "public", "exclusiones": ["subidas"]})
    assert datos["configurado"] and datos["repo"] == REPO and datos["rama"] == "main"
    assert gs.RE_CLAVE_PUBLICA.fullmatch(datos["clave_publica"]) and datos["clave_publica"].endswith(f"despliegue@{D}")
    assert datos["gancho"] is False and datos["gancho_ruta"] == f"/git-despliegue/{D}"
    meta = leer_meta()
    assert meta["app"] == "paquete" and meta["paquete"] == {"raiz": "public", "origen": "git"}
    assert len(mundo.vhosts) == 1 and mundo.vhosts[0]["paquete"]["raiz"] == "public"
    clave = os.path.join(meta["base"], "despliegues", ".ssh", "clave")
    assert stat.S_IMODE(os.stat(clave).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(os.path.join(meta["base"], "despliegues")).st_mode) == 0o700
    # La misma raíz otra vez no reescribe el vhost; la clave se conserva.
    assert gs.configurar(D, {"repo": REPO, "raiz_web": "public"})["clave_publica"] == datos["clave_publica"]
    assert len(mundo.vhosts) == 1
    assert gs.regenerar_clave(D)["clave_publica"] != datos["clave_publica"]


@con_herramientas
def test_otro_repositorio_olvida_la_huella(mundo):
    gs.configurar(D, {"repo": REPO})
    conocidos = gs.ruta_conocidos(leer_meta())
    open(conocidos, "w").write("git.example.org ssh-ed25519 AAAA\n")
    gs.configurar(D, {"repo": REPO, "rama": "otra"})
    assert os.path.exists(conocidos)  # mismo repositorio: se conserva
    gs.configurar(D, {"repo": "https://git.example.org/ana/otro.git"})
    assert not os.path.exists(conocidos)


@pytest.mark.parametrize("app", ["wordpress", "joomla", "propia"])
def test_configurar_no_en_apps(mundo, app):
    meta = leer_meta()
    meta["app"] = app
    m["comun"].guardar_meta(meta)
    with pytest.raises(ErrorSitio):
        gs.configurar(D, {"repo": REPO})
    assert "git_php" not in leer_meta() and mundo.vhosts == []


@con_herramientas
def test_configurar_deshace_si_nginx_rechaza(mundo, monkeypatch):
    def rechaza(meta):
        raise ErrorSitio("nginx: configuración no válida")

    monkeypatch.setitem(sys.modules, "sitio", types.SimpleNamespace(publicar_vhost=rechaza))
    with pytest.raises(ErrorSitio):
        gs.configurar(D, {"repo": REPO, "raiz_web": "public"})
    meta = leer_meta()
    assert meta.get("app") is None and "git_php" not in meta and "paquete" not in meta


@con_herramientas
def test_gancho_secreto_una_vez(mundo):
    gs.configurar(D, {"repo": REPO})
    datos = gs.gancho(D, "activar")
    secreto = datos["secreto"]
    assert len(secreto) >= 40 and datos["gancho"] is True
    ruta = os.path.join(gs.GANCHOS, f"{D}.json")
    assert json.load(open(ruta))["secreto"] == secreto and stat.S_IMODE(os.stat(ruta).st_mode) == 0o600
    assert secreto not in json.dumps(gs.estado(D)) and secreto not in json.dumps(leer_meta())
    assert gs.gancho(D, "activar")["secreto"] != secreto  # activar otra vez renueva
    assert gs.gancho(D, "desactivar")["gancho"] is False and not os.path.exists(ruta)


@con_herramientas
def test_secreto_viejo_de_otro_sitio_se_borra(mundo):
    os.makedirs(gs.GANCHOS)
    with open(os.path.join(gs.GANCHOS, f"{D}.json"), "w") as f:
        json.dump({"secreto": "de-un-sitio-anterior-con-el-mismo-nombre"}, f)
    gs.configurar(D, {"repo": REPO})
    assert not os.path.exists(os.path.join(gs.GANCHOS, f"{D}.json"))


def test_carpeta_de_despliegues_enlazada(mundo, tmp_path):
    os.symlink(str(tmp_path), os.path.join(mundo.meta["base"], "despliegues"))
    with pytest.raises(ErrorSitio):
        gs._preparar(mundo.meta)


# --- Desplegar ---


def _preparar_publico(w):
    os.makedirs(publico(w, "subidas"))
    os.makedirs(publico(w, ".well-known", "acme-challenge"))
    for ruta, texto in {"index.html": "en construcción", "viejo.html": "viejo", "subidas/foto.jpg": "foto",
                        ".well-known/acme-challenge/x": "reto", "0123456789abcdef0123456789abcdef.txt": "clave"}.items():
        with open(publico(w, ruta), "w") as f:
            f.write(texto)


@con_herramientas
def test_desplegar_publica_y_respeta_exclusiones(mundo):
    _preparar_publico(mundo)
    commit = confirmar(mundo.repo, {"index.php": "<?php echo 1;", "public/index.php": "<?php echo 2;",
                                    "src/a/b.php": "<?php", "subidas/de-git.txt": "no debe llegar",
                                    "bueno": ("enlace", "index.php"), "malo": ("enlace", "/etc/passwd")}, "Primera versión")
    gs.configurar(D, {"repo": REPO, "exclusiones": ["subidas"]})
    datos = gd.desplegar(D, "panel")
    assert open(publico(mundo, "index.php")).read() == "<?php echo 1;"
    assert not os.path.exists(publico(mundo, "viejo.html")) and not os.path.exists(publico(mundo, "index.html"))
    assert open(publico(mundo, "subidas", "foto.jpg")).read() == "foto"  # lo subido no se toca
    assert not os.path.exists(publico(mundo, "subidas", "de-git.txt"))
    assert os.path.exists(publico(mundo, ".well-known", "acme-challenge", "x"))
    assert os.path.exists(publico(mundo, "0123456789abcdef0123456789abcdef.txt"))  # IndexNow
    assert not os.path.exists(publico(mundo, ".git"))
    assert os.path.islink(publico(mundo, "bueno")) and not os.path.lexists(publico(mundo, "malo"))  # --safe-links
    # Lo nuevo: 0640 y las carpetas con el grupo de nginx heredado (setgid de la carpeta pública).
    assert stat.S_IMODE(os.stat(publico(mundo, "src", "a", "b.php")).st_mode) == 0o640
    assert os.stat(publico(mundo, "src", "a")).st_mode & stat.S_ISGID
    assert mundo.copias == [(D, "antes del primer despliegue desde git")]
    ultimo = datos["despliegues"][0]
    assert ultimo["estado"] == "ok" and ultimo["commit"] == commit and ultimo["autor"] == "Ana"
    assert ultimo["mensaje"] == "Primera versión" and ultimo["origen"] == "panel"
    assert datos["actual"] == datos["versiones"][-1]["id"] and datos["versiones"][-1]["commit"] == commit


@con_herramientas
def test_versiones_guardadas_y_volver(mundo):
    gs.configurar(D, {"repo": REPO})
    commits = []
    for i in range(4):
        commits.append(confirmar(mundo.repo, {"index.php": f"versión {i}"}, f"cambio {i}"))
        datos = gd.desplegar(D, "gancho" if i else "panel")
    assert len(mundo.copias) == 1  # solo antes del primero
    assert [v["commit"] for v in datos["versiones"]] == commits[1:]  # se guardan 3
    carpetas = sorted(os.listdir(os.path.join(mundo.meta["base"], "despliegues", "versiones")))
    assert carpetas == [v["id"] for v in datos["versiones"]]
    anterior = datos["versiones"][-2]["id"]
    datos = gd.volver(D, anterior)
    assert open(publico(mundo, "index.php")).read() == "versión 2" and datos["actual"] == anterior
    assert datos["despliegues"][0]["origen"] == "volver" and datos["despliegues"][0]["estado"] == "ok"
    with pytest.raises(ErrorSitio):
        gd.volver(D, anterior)  # ya es la publicada
    with pytest.raises(ErrorSitio):
        gd.volver(D, "20200101-000000")  # ya no está guardada
    with pytest.raises(ErrorSitio):
        gd.volver(D, "../../etc")


@con_herramientas
def test_error_queda_anotado_y_no_toca_lo_publicado(mundo):
    _preparar_publico(mundo)
    confirmar(mundo.repo, {"index.php": "x"}, "sin carpeta dist")
    gs.configurar(D, {"repo": REPO, "carpeta": "dist"})
    with pytest.raises(ErrorSitio):
        gd.desplegar(D, "panel")
    assert open(publico(mundo, "viejo.html")).read() == "viejo"
    estado = gs.estado(D)
    assert estado["despliegues"][0]["estado"] == "error" and "dist" in estado["despliegues"][0]["error"]
    assert estado["versiones"] == []
    versiones = os.path.join(mundo.meta["base"], "despliegues", "versiones")
    assert os.listdir(versiones) == []  # ni la temporal ni la que no llegó a publicarse


@con_herramientas
def test_rama_que_no_existe(mundo):
    confirmar(mundo.repo, {"index.php": "x"}, "uno")
    gs.configurar(D, {"repo": REPO, "rama": "produccion"})
    with pytest.raises(ErrorSitio):
        gd.desplegar(D, "panel")
    assert gs.estado(D)["despliegues"][0]["estado"] == "error"


@con_herramientas
def test_desplegar_comprueba_otra_vez_la_red(mundo, monkeypatch):
    confirmar(mundo.repo, {"index.php": "x"}, "uno")
    gs.configurar(D, {"repo": REPO})
    monkeypatch.setattr(red, "es_publica", lambda d: False)  # el nombre pasó a apuntar a la red interna
    with pytest.raises(ErrorSitio):
        gd.desplegar(D, "panel")
    assert not any(o[:1] == ["git"] and "clone" in o for o in mundo.ordenes)


@con_herramientas
def test_quitar_deja_lo_publicado(mundo):
    confirmar(mundo.repo, {"index.php": "x"}, "uno")
    gs.configurar(D, {"repo": REPO})
    gs.gancho(D, "activar")
    gd.desplegar(D, "panel")
    assert gs.quitar(D)["quitado"]
    meta = leer_meta()
    assert "git_php" not in meta and "origen" not in meta["paquete"] and meta["app"] == "paquete"
    assert not os.path.exists(os.path.join(meta["base"], "despliegues"))
    assert not os.path.exists(os.path.join(gs.GANCHOS, f"{D}.json"))
    assert open(publico(mundo, "index.php")).read() == "x"


def test_un_despliegue_a_la_vez(mundo, red_de_prueba):
    meta = leer_meta()
    meta["git_php"] = {"repo": REPO, "rama": "main", "despliegues": [], "versiones": []}
    m["comun"].guardar_meta(meta)
    with gd._Cerrojo(D):
        with pytest.raises(ErrorSitio):
            gd.desplegar(D, "panel")
        with pytest.raises(ErrorSitio):
            gd.volver(D, "20261021-101010")


# --- Lanzar en segundo plano ---


def test_lanzar(mundo, monkeypatch):
    meta = leer_meta()
    meta["git_php"] = {"repo": REPO, "rama": "main", "despliegues": [{"inicio_ts": 0}], "versiones": []}
    m["comun"].guardar_meta(meta)
    lanzadas = []
    monkeypatch.setattr(gd, "ejecutar", lambda cmd, **k: lanzadas.append(cmd) or "")
    assert gd.lanzar(D, "gancho")["en_curso"] is True
    orden = lanzadas[-1]
    assert orden[:3] == ["systemd-run", "--unit", "sitio-git-web0000"] and "--collect" in orden
    assert orden[-4:] == [gd.MAQUITA_SITIOS, "git-desplegar-ahora", D, "gancho"]
    monkeypatch.setattr(gd, "en_curso", lambda meta: True)
    with pytest.raises(ErrorSitio):
        gd.lanzar(D, "panel")
    assert len(lanzadas) == 1


def test_ganchos_demasiado_seguidos(mundo, monkeypatch):
    import time

    meta = leer_meta()
    meta["git_php"] = {"repo": REPO, "rama": "main", "despliegues": [{"inicio_ts": int(time.time()) - 5}], "versiones": []}
    m["comun"].guardar_meta(meta)
    lanzadas = []
    monkeypatch.setattr(gd, "ejecutar", lambda cmd, **k: lanzadas.append(cmd) or "")
    with pytest.raises(ErrorSitio):
        gd.lanzar(D, "gancho")
    gd.lanzar(D, "panel")  # desde el panel sí: lo pide una persona
    assert len(lanzadas) == 1


def test_correr_como_el_usuario_del_sitio(monkeypatch):
    """La forma real: runuser con el usuario del sitio, umask 027, entorno limpio y sin ganchos de git."""
    vistas = []

    def run(cmd, **k):
        vistas.append((cmd, k))
        return subprocess.CompletedProcess(cmd, 0, "abc\x1fAna\x1fmensaje", "")

    monkeypatch.setattr(subprocess, "run", run)
    meta = {"usuario": "web0000", "base": "/srv/sitios/example.org", "dominio": D}
    monkeypatch.setattr(red, "comprobar", lambda host: host)
    gd._traer(meta, {"repo": REPO, "rama": "main"}, "/srv/sitios/example.org/despliegues/versiones/.nueva-x")
    clonar, kw = vistas[0]
    assert clonar[:4] == ["runuser", "-u", "web0000", "--"] and kw["umask"] == 0o027 and kw["cwd"] == "/"
    assert "core.hooksPath=/dev/null" in clonar and "protocol.file.allow=never" in clonar
    assert clonar[clonar.index("--branch") + 1] == "main" and clonar[clonar.index(REPO) - 1] == "--"
    assert kw["env"]["GIT_ALLOW_PROTOCOL"] == "https:ssh" and kw["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert "IdentitiesOnly=yes" in kw["env"]["GIT_SSH_COMMAND"] and "BatchMode=yes" in kw["env"]["GIT_SSH_COMMAND"]
    assert "SUDO_USER" not in kw["env"] and set(kw["env"]) >= {"PATH", "HOME"}
    assert "/usr/sbin" in kw["env"]["PATH"].split(":")  # runuser está en /usr/sbin
    assert vistas[-1][0][4:] == ["rm", "-rf", "--", "/srv/sitios/example.org/despliegues/versiones/.nueva-x/.git"]


# --- Órdenes ---


def test_despachar_formas(mundo):
    for args in (["git-estado"], ["git-gancho", D, "renovar"], ["git-desplegar", D, "otro"], ["git-volver", D],
                 ["git-quitar", D, "example.com"], ["git-nada", D], ["recursos"], ["git-estado", "../x"]):
        with pytest.raises(ErrorSitio):
            ov.despachar(args)
    assert ov.despachar(["git-estado", D]) == {"dominio": D, "configurado": False, "compatible": True, "motivo": None}
