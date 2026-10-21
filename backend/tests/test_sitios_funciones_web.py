"""Funciones web por sitio (deploy/sitios/lib): configuración de nginx generada, rechazo de inyecciones y marcha
atrás si `nginx -t` falla. Sin root: todas las rutas y binarios del ayudante se redirigen a una carpeta temporal."""

import json
import os
import shutil
import sys

import pytest

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "deploy", "sitios", "lib")
# Otros ayudantes (deploy/dns/lib) también tienen un «comun.py»: los módulos de sitios se cargan aparte y cada prueba
# los pone en sys.modules solo mientras dura (las importaciones dentro de las funciones los buscan ahí).
_NOMBRES = {os.path.splitext(n)[0] for n in os.listdir(LIB) if n.endswith(".py")} | {"apps"}


def _cargar():
    previos = {n: m for n, m in sys.modules.items() if n.split(".")[0] in _NOMBRES}
    for n in previos:
        del sys.modules[n]
    sys.path.insert(0, LIB)
    try:
        import funciones_web  # noqa: F401  arrastra los demás

        for n in ("avanzado", "comun", "ftp_cuentas", "nginx_web", "sitio", "validacion", *_NOMBRES - {"apps"}):
            __import__(n)
        propios = {n: m for n, m in sys.modules.items() if n.split(".")[0] in _NOMBRES}
    finally:
        sys.path.remove(LIB)
        for n in list(sys.modules):
            if n.split(".")[0] in _NOMBRES:
                del sys.modules[n]
        sys.modules.update(previos)
    return propios


_PROPIOS = _cargar()
avanzado, comun, ftp_cuentas, funciones_web, nginx_web, sitio, web_optimizacion, web_privacidad = (
    _PROPIOS[n] for n in ("avanzado", "comun", "ftp_cuentas", "funciones_web", "nginx_web", "sitio",
                          "web_optimizacion", "web_privacidad"))
ErrorSitio = comun.ErrorSitio


@pytest.fixture(autouse=True)
def _modulos_de_sitios(monkeypatch):
    for n, m in _PROPIOS.items():
        monkeypatch.setitem(sys.modules, n, m)
    monkeypatch.syspath_prepend(LIB)


DOMINIO = "example.org"
NGINX_BIEN = [sys.executable, "-c", "pass"]
NGINX_MAL = [sys.executable, "-c", "import sys; sys.stderr.write('nginx: [emerg] directiva rota in x:1\\n'); sys.exit(1)"]
INYECCIONES = ["/a;}", "/a{", "/a}", "/a\nreturn 200", '/a"', "/a$host", "/a b", "/a\\", "/a#x"]


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    for nombre in ("meta", "disp", "act", "extra", "web", "confd", "cache", "modulos", "sitios"):
        (tmp_path / nombre).mkdir()
    monkeypatch.setattr(comun, "META_DIR", str(tmp_path / "meta"))
    monkeypatch.setattr(sitio, "NGINX_DISP", str(tmp_path / "disp"))
    monkeypatch.setattr(sitio, "NGINX_ACT", str(tmp_path / "act"))
    monkeypatch.setattr(sitio, "recargar_nginx", lambda: None)
    monkeypatch.setattr(avanzado, "EXTRA", str(tmp_path / "extra"))
    monkeypatch.setattr(nginx_web, "RAIZ", str(tmp_path / "web"))
    monkeypatch.setattr(nginx_web, "HTTP_CONF", str(tmp_path / "confd"))
    monkeypatch.setattr(nginx_web, "CERROJO", str(tmp_path / "meta" / ".cerrojo"))
    monkeypatch.setattr(nginx_web, "NGINX_PRUEBA", NGINX_BIEN)
    monkeypatch.setattr(web_optimizacion, "CACHE_RAIZ", str(tmp_path / "cache"))
    monkeypatch.setattr(web_optimizacion, "MODULOS_NGINX", str(tmp_path / "modulos"))
    monkeypatch.setattr(web_privacidad, "_cifrar", lambda u, c: f"{u}:$apr1$prueba${len(c)}")
    base = tmp_path / "sitios" / DOMINIO
    (base / "publico" / "errores").mkdir(parents=True)
    (base / "publico" / "errores" / "404.html").write_text("<h1>No está</h1>")
    meta = {"dominio": DOMINIO, "www": True, "usuario": "webexample1234", "base": str(base),
            "publico": str(base / "publico"), "tmp": str(base / "tmp"), "registros": str(base / "registros"),
            "php": "8.4", "app": "wordpress", "ssl": False}
    comun.guardar_meta(meta)
    sitio.escribir_vhost(meta)
    return tmp_path


def servidor(entorno):
    return (entorno / "web" / DOMINIO / "servidor.conf").read_text()


def todo(entorno):
    """Contenido de todos los archivos que tocan las funciones web (para comparar antes y después)."""
    salida = {}
    for carpeta in ("web", "confd", "disp"):
        for raiz, _d, archivos in os.walk(entorno / carpeta):
            for a in archivos:
                with open(os.path.join(raiz, a)) as f:
                    salida[os.path.join(raiz, a)] = f.read()
    return salida


# --- Vhost y valores de serie ---


def test_vhost_incluye_los_archivos_del_sitio(entorno):
    vhost = (entorno / "disp" / f"sitio-{DOMINIO}.conf").read_text()
    carpeta = str(entorno / "web" / DOMINIO)
    for parte in ("servidor", "estaticos", "php"):
        assert f"include {carpeta}/{parte}.conf;" in vhost
        assert (entorno / "web" / DOMINIO / f"{parte}.conf").exists()
    assert "expires 30d;" in (entorno / "web" / DOMINIO / "estaticos.conf").read_text()  # lo de siempre
    assert "gzip on;" in servidor(entorno)
    assert "brotli" not in servidor(entorno)
    assert not os.listdir(entorno / "confd")  # sin caché de página no hay zona en http{}


def test_brotli_si_el_modulo_esta(entorno):
    (entorno / "modulos" / "50-mod-http-brotli-filter.conf").write_text("load_module x;")
    funciones_web.despachar(["web-optimizacion", DOMINIO, _b64({"compresion": True})])
    assert "brotli on;" in servidor(entorno)


def test_sin_gzip_repetido_si_las_reglas_propias_lo_ponen(entorno):
    with open(avanzado.ruta_extra(DOMINIO), "w") as f:
        f.write("gzip on;\n")
    sitio.escribir_vhost(comun.leer_meta(DOMINIO))
    assert "gzip" not in servidor(entorno)


# --- Redirecciones ---


def _b64(datos):
    import base64

    texto = datos if isinstance(datos, str) else json.dumps(datos)
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def test_redirecciones_generadas(entorno):
    funciones_web.despachar(["web-redirecciones", DOMINIO, _b64([
        {"origen": "/viejo.html", "destino": "https://example.com/nuevo", "codigo": 301},
        {"origen": "/blog/", "destino": "https://example.com/noticias/", "codigo": 302, "subrutas": True},
        {"origen": "*", "destino": "https://example.com/", "codigo": 301, "conservar_ruta": True},
    ])])
    texto = servidor(entorno)
    assert 'rewrite "^/viejo\\.html$" "https://example.com/nuevo" permanent;' in texto
    assert 'rewrite "^/blog(/.*)?$" "https://example.com/noticias$1" redirect;' in texto
    assert 'return 301 "https://example.com$request_uri";' in texto
    assert "acme-challenge" in texto
    # La de todo el dominio va antes que las de una ruta.
    assert texto.index("return 301") < texto.index("rewrite")
    assert funciones_web.despachar(["web", DOMINIO])["redirecciones"]["lista"][0]["origen"] == "/viejo.html"


@pytest.mark.parametrize("origen", INYECCIONES)
def test_redirecciones_rechazan_inyeccion_en_el_origen(entorno, origen):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-redirecciones", DOMINIO, _b64([{"origen": origen, "destino": "https://example.com/"}])])


@pytest.mark.parametrize("destino", ["https://example.com/x;return 200", "https://example.com/{", "https://example.com/}",
                                     "https://example.com/\nreturn 200", 'https://example.com/"', "https://example.com/$host",
                                     "https://example.com/ a", "javascript:alert(1)", "//example.com", "ftp://example.com"])
def test_redirecciones_rechazan_inyeccion_en_el_destino(entorno, destino):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-redirecciones", DOMINIO, _b64([{"origen": "/a", "destino": destino}])])
    assert "rewrite" not in servidor(entorno)


def test_redirecciones_sin_bucles_ni_acme(entorno):
    for entrada in ({"origen": "*", "destino": "https://www.example.org/"},
                    {"origen": "/a", "destino": "http://example.org/a"},
                    {"origen": "/.well-known/acme-challenge", "destino": "https://example.com/"},
                    {"origen": "/a", "destino": "https://example.com/", "codigo": 307}):
        with pytest.raises(ErrorSitio):
            funciones_web.despachar(["web-redirecciones", DOMINIO, _b64([entrada])])


# --- Bloqueo de IP ---


def test_bloqueo_normaliza(entorno):
    funciones_web.despachar(["web-bloqueo", DOMINIO, _b64(["192.0.2.7", "198.51.100.9/24", "2001:DB8::/32", "192.0.2.7"])])
    texto = servidor(entorno)
    assert "deny 192.0.2.7;" in texto and "deny 198.51.100.0/24;" in texto and "deny 2001:db8::/32;" in texto
    assert texto.count("deny 192.0.2.7;") == 1


@pytest.mark.parametrize("valor", ["192.0.2.1; allow all", "192.0.2.1}", "192.0.2.1\n", "0.0.0.0/0", "::/0",
                                   "203.0.113.300", "ejemplo", "192.0.2.1 #"])
def test_bloqueo_rechaza(entorno, valor):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-bloqueo", DOMINIO, _b64([valor])])
    assert "deny" not in servidor(entorno)


# --- Hotlinking ---


def test_hotlink(entorno):
    funciones_web.despachar(["web-hotlink", DOMINIO, _b64({"activo": True, "extensiones": ["jpg", ".PNG"],
                                                            "permitidos": ["example.com", "*.example.net"]})])
    texto = servidor(entorno)
    assert "valid_referers none blocked server_names example.com www.example.com *.example.net" in texto
    assert '\\.(?:jpg|png)$' in texto and "return 403;" in texto
    funciones_web.despachar(["web-hotlink", DOMINIO, _b64({"activo": False})])
    assert "valid_referers" not in servidor(entorno)


@pytest.mark.parametrize("datos", [{"activo": True, "extensiones": ["jpg|php"]}, {"activo": True, "extensiones": ["jp;g"]},
                                   {"activo": True, "permitidos": ["example.com; return 200"]},
                                   {"activo": True, "permitidos": ["example.com\n}"]}, {"activo": True, "extensiones": []}])
def test_hotlink_rechaza(entorno, datos):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-hotlink", DOMINIO, _b64(datos)])


# --- Páginas de error ---


def test_paginas_de_error(entorno):
    r = funciones_web.despachar(["web", DOMINIO])
    assert "/errores/404.html" in r["errores"]["candidatos"]
    funciones_web.despachar(["web-errores", DOMINIO, _b64({"404": "/errores/404.html", "503": ""})])
    assert "error_page 404 /errores/404.html;" in servidor(entorno)
    assert "error_page 503" not in servidor(entorno)


@pytest.mark.parametrize("datos", [{"404": "/no-existe.html"}, {"404": "/errores/404.html;"}, {"404": "/../../etc/passwd"},
                                   {"418": "/errores/404.html"}, {"404": "/errores/404.php"}, {"404": "/a.html\nlocation"}])
def test_paginas_de_error_rechaza(entorno, datos):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-errores", DOMINIO, _b64(datos)])


def test_paginas_de_error_no_en_aplicaciones_propias(entorno):
    meta = comun.leer_meta(DOMINIO)
    meta.update(app="propia", propia={"tipo": "python", "puerto": 8001})
    comun.guardar_meta(meta)
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-errores", DOMINIO, _b64({"404": "/errores/404.html"})])


# --- Carpetas con contraseña ---


def test_privacidad_agregar_y_quitar(entorno):
    r = funciones_web.despachar(["web-privado-agregar", DOMINIO, _b64("/privado/"), "ana"])
    assert r["usuario"] == "ana" and len(r["clave"]) >= 16  # generada, se devuelve una vez
    r2 = funciones_web.despachar(["web-privado-agregar", DOMINIO, _b64("/privado"), "luis", _b64("clave-propia-1")])
    assert "clave" not in r2  # la puso la persona: no se devuelve
    archivo = web_privacidad.ruta_claves(comun.leer_meta(DOMINIO), "/privado")
    assert archivo.startswith(str(entorno / "sitios" / DOMINIO / "claves-carpetas"))  # fuera de la pública
    assert oct(os.stat(archivo).st_mode & 0o777) == "0o640"
    with open(archivo) as f:
        assert [l.split(":")[0] for l in f] == ["ana", "luis"]
    texto = servidor(entorno)
    assert 'if ($uri ~ "^/privado(?:/|$)")' in texto and "auth_basic $sitio_privado;" in texto
    assert f'set $sitio_claves "{archivo}";' in texto
    assert "clave-propia-1" not in json.dumps(comun.leer_meta(DOMINIO))  # nada en claro en el meta
    funciones_web.despachar(["web-privado-quitar", DOMINIO, _b64("/privado"), "ana"])
    with open(archivo) as f:
        assert [l.split(":")[0] for l in f] == ["luis"]
    funciones_web.despachar(["web-privado-quitar", DOMINIO, _b64("/privado")])
    assert not os.path.exists(archivo) and "auth_basic" not in servidor(entorno)


@pytest.mark.parametrize("carpeta", INYECCIONES + ["/", "/../etc", "/.git", "/.well-known/x"])
def test_privacidad_rechaza_carpetas(entorno, carpeta):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-privado-agregar", DOMINIO, _b64(carpeta), "ana"])


def test_privacidad_rechaza_usuario_y_contrasena(entorno):
    for args in (["ana:x"], ["ana\n"], ["ana", _b64("corta")], ["ana", _b64("con:dos-puntos")], ["ana", _b64("salto\nde-linea")]):
        with pytest.raises(ErrorSitio):
            funciones_web.despachar(["web-privado-agregar", DOMINIO, _b64("/privado")] + args)


def test_privacidad_rechaza_reino_con_inyeccion(entorno):
    with pytest.raises(ErrorSitio):
        web_privacidad.agregar(DOMINIO, "/privado", "ana", reino='Zona"; return 200; #')
    with pytest.raises(ErrorSitio):
        web_privacidad.agregar(DOMINIO, "/privado", "ana", reino="Zona\n")


@pytest.mark.skipif(not shutil.which("openssl"), reason="sin openssl")
def test_cifrado_apr1_por_la_entrada_estandar(monkeypatch):
    monkeypatch.setattr(web_privacidad, "HTPASSWD", "/no/existe")
    monkeypatch.setattr(web_privacidad, "OPENSSL", shutil.which("openssl"))
    linea = web_privacidad._cifrar("ana", "una-clave-larga")
    assert linea.startswith("ana:$apr1$") and "una-clave-larga" not in linea


# --- Optimización y caché de página ---


def test_cache_de_pagina(entorno):
    funciones_web.despachar(["web-optimizacion", DOMINIO, _b64({"compresion": True, "estaticos": "7d", "cache_pagina": True,
                                                                 "cache_minutos": 15})])
    assert "expires 7d;" in (entorno / "web" / DOMINIO / "estaticos.conf").read_text()
    php = (entorno / "web" / DOMINIO / "php.conf").read_text()
    assert "fastcgi_cache sitio_webexample1234;" in php and "fastcgi_cache_valid 200 301 302 15m;" in php
    assert "fastcgi_no_cache $sitio_sin_cache;" in php and "fastcgi_cache_bypass $sitio_sin_cache;" in php
    texto = servidor(entorno)
    assert "wordpress_logged_in" in texto and "/wp-admin/" in texto and "woocommerce_items_in_cart" in texto
    http = (entorno / "confd" / f"sitios-cache-{DOMINIO}.conf").read_text()
    assert "keys_zone=sitio_webexample1234:10m" in http
    assert os.path.isdir(entorno / "cache" / DOMINIO)
    (entorno / "cache" / DOMINIO / "a").mkdir()
    (entorno / "cache" / DOMINIO / "a" / "1").write_text("x")
    assert funciones_web.despachar(["web-purgar", DOMINIO])["purgados"] == 1
    funciones_web.despachar(["web-optimizacion", DOMINIO, _b64({"cache_pagina": False})])
    assert not (entorno / "confd" / f"sitios-cache-{DOMINIO}.conf").exists()
    assert "fastcgi_cache" not in (entorno / "web" / DOMINIO / "php.conf").read_text()


@pytest.mark.parametrize("datos", [{"estaticos": "30d; autoindex on"}, {"estaticos": "2y"}, {"cache_minutos": 0},
                                   {"cache_minutos": "10m"}, {"compresion": "quizas"}])
def test_optimizacion_rechaza(entorno, datos):
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-optimizacion", DOMINIO, _b64(datos)])


# --- Mecanismo común: marcha atrás y regenerar ---


def test_marcha_atras_si_nginx_rechaza(entorno, monkeypatch):
    funciones_web.despachar(["web-bloqueo", DOMINIO, _b64(["192.0.2.1"])])
    antes, meta_antes = todo(entorno), comun.leer_meta(DOMINIO)
    monkeypatch.setattr(nginx_web, "NGINX_PRUEBA", NGINX_MAL)
    with pytest.raises(ErrorSitio, match="directiva rota"):
        funciones_web.despachar(["web-redirecciones", DOMINIO, _b64([{"origen": "/a", "destino": "https://example.com/"}])])
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-optimizacion", DOMINIO, _b64({"cache_pagina": True})])
    with pytest.raises(ErrorSitio):
        funciones_web.despachar(["web-privado-agregar", DOMINIO, _b64("/privado"), "ana"])
    assert todo(entorno) == antes
    assert comun.leer_meta(DOMINIO) == meta_antes
    assert not os.path.exists(web_privacidad.ruta_claves(meta_antes, "/privado"))


def test_regenerar_conserva_los_ajustes(entorno):
    funciones_web.despachar(["web-bloqueo", DOMINIO, _b64(["203.0.113.5"])])
    funciones_web.despachar(["web-optimizacion", DOMINIO, _b64({"cache_pagina": True})])
    shutil.rmtree(entorno / "web")
    for f in os.listdir(entorno / "confd"):
        os.remove(entorno / "confd" / f)
    assert sitio.regenerar() == {"regenerados": [DOMINIO]}
    assert "deny 203.0.113.5;" in servidor(entorno)
    assert (entorno / "confd" / f"sitios-cache-{DOMINIO}.conf").exists()


def test_meta_editado_a_mano_no_cuela_texto(entorno):
    meta = comun.leer_meta(DOMINIO)
    meta["web"] = {"bloqueo": ["192.0.2.1; return 200"]}
    with pytest.raises(ErrorSitio):
        sitio.escribir_vhost(meta)


def test_dominio_con_salto_final_rechazado():
    with pytest.raises(ErrorSitio):
        _PROPIOS["validacion"].dominio("example.org\n")


def test_despachar_rechaza_formas_raras(entorno):
    for args in (["web"], ["web", DOMINIO, "x"], ["web-purgar"], ["web-bloqueo", DOMINIO], ["ftp-cuenta-crear", DOMINIO, "ana"],
                 ["web-redirecciones", DOMINIO, "%%%"], ["web-privado-agregar", DOMINIO, _b64("x" * 300), "ana"]):
        with pytest.raises(ErrorSitio):
            funciones_web.despachar(args)


# --- Cuentas FTP adicionales (lo que se puede probar sin root) ---


def test_ftp_nombres_y_subcarpetas():
    assert ftp_cuentas.nombre("disenio") == "disenio"
    for malo in ("Ana", "1ana", "a", "ana_b", "ana-b", "a" * 12, "ana;id"):
        with pytest.raises(ErrorSitio):
            ftp_cuentas.nombre(malo)
    assert ftp_cuentas.subcarpeta("/imagenes/2026/") == "imagenes/2026"
    for mala in ("", "..", "a/../b", ".git", "a/.ssh", "a b", "a;b", "a\nb", "/".join(["a"] * 6)):
        with pytest.raises(ErrorSitio):
            ftp_cuentas.subcarpeta(mala)
    meta = {"usuario": "web" + "a" * 12 + "1234", "dominio": DOMINIO}
    assert len(ftp_cuentas.usuario_sistema(meta, "a" * 11)) <= 32


def test_ftp_no_sigue_enlaces_simbolicos(tmp_path):
    publico = tmp_path / "publico"
    (publico / "fotos").mkdir(parents=True)
    os.symlink("/etc", publico / "atajo")
    (publico / "fotos" / "dentro").symlink_to(tmp_path)
    meta = {"publico": str(publico)}
    os.close(ftp_cuentas._abrir(meta, "fotos"))
    for mala in ("atajo", "fotos/dentro", "no-existe"):
        with pytest.raises(ErrorSitio):
            ftp_cuentas._abrir(meta, mala)


def test_ftp_quitar_carpetas_nunca_borra_contenido(tmp_path, monkeypatch):
    monkeypatch.setattr(ftp_cuentas, "RAIZ_FTP", str(tmp_path))
    meta = {"dominio": DOMINIO}
    montaje = ftp_cuentas.montaje(meta, "ana")
    os.makedirs(montaje)
    with open(os.path.join(montaje, "archivo-del-sitio.txt"), "w") as f:
        f.write("no se borra")  # como si el montaje siguiera puesto
    ftp_cuentas._quitar_carpetas(meta, "ana")
    assert os.path.exists(os.path.join(montaje, "archivo-del-sitio.txt"))
