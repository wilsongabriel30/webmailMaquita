"""Séptima revisión, S7-1: el envoltorio maquita-sudo no deja pasar nada fuera de lo previsto."""

import importlib.util
import os

import pytest

_RUTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "deploy",
    "sudoers",
    "maquita-sudo",
)
import importlib.machinery

_loader = importlib.machinery.SourceFileLoader(
    "maquita_sudo", _RUTA
)  # sin extensión .py
_spec = importlib.util.spec_from_loader("maquita_sudo", _loader)
ms = importlib.util.module_from_spec(_spec)
_loader.exec_module(ms)

EXISTE = lambda b: b.endswith("@example.org")  # noqa: E731  doble de «doveadm user»


def _ok(usuario, programa, *args):
    return ms.autorizar(usuario, programa, list(args), comprobar_buzon=EXISTE)


def _no(usuario, programa, *args):
    with pytest.raises(ms.Rechazo):
        ms.autorizar(usuario, programa, list(args), comprobar_buzon=EXISTE)


def test_www_data_solo_lo_del_correo():
    assert _ok(
        "www-data",
        "doveadm",
        "search",
        "-u",
        "ana@example.org",
        "header",
        "message-id",
        "<x@y>",
    )
    assert _ok(
        "www-data",
        "doveadm",
        "expunge",
        "-u",
        "ana@example.org",
        "mailbox",
        "INBOX",
        "header",
        "message-id",
        "<x@y>",
    )
    assert _ok(
        "www-data",
        "doveadm",
        "fetch",
        "-u",
        "ana@example.org",
        "uid hdr.subject flags",
        "header",
        "message-id",
        "<x@y>",
    )
    _no("www-data", "doveadm", "pw", "-s", "SHA512-CRYPT", "-p", "x")  # solo el panel
    _no("www-data", "systemctl", "restart", "postfix")
    _no("nadie", "postqueue", "-p")


def test_el_comodin_ya_no_existe():
    # lo que antes pasaba por «doveadm search -u *»
    _no(
        "www-data",
        "doveadm",
        "search",
        "-u",
        "ana@example.org",
        "-o",
        "mail_location=/etc",
    )
    _no(
        "www-data",
        "doveadm",
        "search",
        "-c",
        "/etc/dovecot/otra.conf",
        "-u",
        "ana@example.org",
    )
    _no("www-data", "doveadm", "search", "-A", "header", "message-id", "<x@y>")
    _no("www-data", "doveadm", "search", "header", "message-id", "<x@y>")  # sin -u
    _no(
        "www-data", "doveadm", "mailbox", "delete", "-u", "ana@example.org", "INBOX"
    )  # subcomando ajeno


def test_buzon_estricto_y_de_dominio_propio():
    _no("www-data", "doveadm", "search", "-u", "-ana@example.org", "header", "x", "y")
    _no(
        "www-data",
        "doveadm",
        "search",
        "-u",
        "ana maquita@example.org",
        "header",
        "x",
        "y",
    )
    _no(
        "www-data", "doveadm", "search", "-u", "ana@otro.example", "header", "x", "y"
    )  # no existe en Dovecot
    _no("www-data", "doveadm", "search", "-u", "ana@example.org\n", "header", "x", "y")
    assert (
        ms.es_buzon("Ana.Perez+x@example.org")
        and not ms.es_buzon("ana@localhost")
        and not ms.es_buzon("")
    )


def test_cola_de_postfix():
    assert _ok("www-data", "postqueue", "-j") and _ok(
        "www-data", "postqueue", "-i", "4XyZ12abCD"
    )
    assert _ok("www-data", "postsuper", "-d", "ALL") and _ok(
        "www-data", "postsuper", "-h", "ABC123DEF0"
    )
    _no("www-data", "postqueue", "-i", "../x")
    _no("www-data", "postsuper", "-d", "*")
    _no("www-data", "postqueue", "-c", "/tmp")


def test_panel_systemctl_journalctl_postconf():
    assert _ok("maquita-admin", "systemctl", "restart", "postfix")
    assert _ok("maquita-admin", "systemctl", "status", "dovecot", "--no-pager", "-l")
    _no("maquita-admin", "systemctl", "restart", "sshd")
    _no("maquita-admin", "systemctl", "edit", "postfix")
    assert _ok(
        "maquita-admin",
        "journalctl",
        "-u",
        "rspamd",
        "--no-pager",
        "-n",
        "200",
        "--output=short-iso",
    )
    _no("maquita-admin", "journalctl", "-u", "rspamd", "-n", "999999")
    _no("maquita-admin", "journalctl", "--directory", "/var/log")
    assert _ok("maquita-admin", "postconf", "-e", "message_size_limit=52428800")
    _no(
        "maquita-admin", "postconf", "-e", "smtpd_recipient_restrictions=permit"
    )  # fuera de la lista
    _no("maquita-admin", "postconf", "-e", "myhostname=x\nsmtpd_milters=")


def test_panel_fail2ban_sievec_sendmail_nginx():
    assert _ok(
        "maquita-admin",
        "fail2ban-client",
        "set",
        "webmail-login",
        "unbanip",
        "10.0.0.5",
    )
    _no(
        "maquita-admin",
        "fail2ban-client",
        "set",
        "webmail-login",
        "unbanip",
        "10.0.0.5; rm -rf /",
    )
    _no("maquita-admin", "fail2ban-client", "reload")
    assert _ok(
        "maquita-admin",
        "sendmail",
        "-f",
        "postmaster@example.org",
        "--",
        "ana@example.org",
    )
    _no(
        "maquita-admin",
        "sendmail",
        "-f",
        "postmaster@example.org",
        "-C",
        "/tmp/x",
        "--",
        "ana@example.org",
    )
    assert _ok("maquita-admin", "nginx", "-t")
    _no("maquita-admin", "nginx", "-s", "stop")
    _no("maquita-admin", "sievec", "/etc/passwd")
    _no("maquita-admin", "sievec", "/var/vmail/x/y/../../etc/a.sieve")


def test_contrasenas_enmascaradas_en_el_registro():
    assert "secreta" not in ms._enmascarar(
        "doveadm", ["pw", "-s", "SHA512-CRYPT", "-p", "secreta"]
    )
    assert "clave" not in ms._enmascarar(
        "doveadm", ["auth", "test", "ana@example.org", "clave"]
    )


def test_proteccion_de_salida_solo_sus_subacciones():
    """El ayudante del panel: cada subacción con la forma exacta de sus argumentos."""
    assert _ok("maquita-admin", "maquita-outbound", "get-limits") == ["get-limits"]
    assert _ok("maquita-admin", "maquita-outbound", "set-limits", "200", "3")
    assert _ok("maquita-admin", "maquita-outbound", "set-whitelist")
    assert _ok("maquita-admin", "maquita-outbound", "set-whitelist", "a@example.org,b@example.org")
    assert _ok("maquita-admin", "maquita-outbound", "set-dlp-exempt", "noreply@example.org")
    assert _ok("maquita-admin", "maquita-outbound", "activity", "24")
    assert _ok("maquita-admin", "maquita-outbound", "lock", "ana@example.org")
    assert _ok("maquita-admin", "maquita-outbound", "status", "ana@example.org")
    # Una lista larga de exentos no choca con el límite general de 300 caracteres por argumento
    larga = ",".join(f"cuenta{i}@example.org" for i in range(60))
    assert len(larga) > 300 and _ok("maquita-admin", "maquita-outbound", "set-whitelist", larga)

    for malo in (
        [],
        ["get-limits", "--otra"],
        ["set-limits", "200"],
        ["set-limits", "200", "3; rm -rf /"],
        ["set-limits", "0", "3"],
        ["set-limits", "200", "99999"],
        ["set-whitelist", "a@example.org b@example.org"],
        ["set-whitelist", "a@example.org,$(id)"],
        ["set-whitelist", "a@example.org", "otro"],
        ["set-dlp-exempt", "no-es-correo"],
        ["activity", "999"],
        ["activity", "-1"],
        ["lock"],
        ["lock", "ana"],
        ["lock", "ana@example.org", "extra"],
        ["status", "ana@example.org\nlock"],
        ["borrar-todo"],
        ["--help"],
    ):
        _no("maquita-admin", "maquita-outbound", *malo)

    # El correo (www-data) no tiene nada que hacer con este ayudante
    _no("www-data", "maquita-outbound", "get-limits")
    _no("www-data", "maquita-outbound", "lock", "ana@example.org")


def test_depurar_adjuntos_y_acceso_por_pais():
    assert _ok("maquita-admin", "depurar-adjuntos-peligrosos", "--dias", "35")
    assert _ok("maquita-admin", "depurar-adjuntos-peligrosos", "--dias", "7", "--borrar")
    for malo in ([], ["--borrar"], ["--dias"], ["--dias", "0"], ["--dias", "9999"], ["--dias", "7; id"],
                 ["--dias", "7", "--otra"], ["--dias", "7", "--borrar", "x"]):
        _no("maquita-admin", "depurar-adjuntos-peligrosos", *malo)
    _no("www-data", "depurar-adjuntos-peligrosos", "--dias", "7")

    assert _ok("maquita-admin", "geoip-country.sh", "enable", "es")
    assert _ok("www-data", "geoip-country.sh", "disable", "co")
    for malo in ([], ["list"], ["enable"], ["enable", "ES"], ["enable", "esp"], ["enable", "e;"],
                 ["borrar", "es"], ["enable", "es", "x"], ["enable", "$(id)"]):
        _no("maquita-admin", "geoip-country.sh", *malo)


# --- Sitios web del panel (maquita-sitios) ---


def test_sitios_ordenes_permitidas():
    assert _ok("maquita-admin", "maquita-sitios", "listar") == ["listar"]
    assert _ok("maquita-admin", "maquita-sitios", "crear", "ejemplo.org.ec")
    assert _ok("maquita-admin", "maquita-sitios", "crear", "ejemplo.org", "sin-www")
    assert _ok(
        "maquita-admin",
        "maquita-sitios",
        "app",
        "ejemplo.org",
        "wordpress",
        "SG9sYQ",
        "a@example.org",
    )
    assert _ok("maquita-admin", "maquita-sitios", "ftp", "ejemplo.org", "activar")
    assert _ok("maquita-admin", "maquita-sitios", "ssl", "ejemplo.org", "a@example.org")
    assert _ok(
        "maquita-admin", "maquita-sitios", "borrar", "ejemplo.org", "ejemplo.org"
    )


@pytest.mark.parametrize(
    "args",
    [
        ("crear", "../etc/passwd"),
        ("crear", "ejemplo.org", "--otra"),
        ("crear", "EJEMPLO.org"),
        ("app", "ejemplo.org", "Drupal 11", "SG9sYQ", "a@example.org"),
        ("app", "ejemplo.org", "wordpress", "Hola mundo", "a@example.org"),
        ("ftp", "ejemplo.org", "root"),
        ("ssl", "ejemplo.org", "no-es-correo"),
        ("borrar", "ejemplo.org", "otro.org"),
        ("reinstalar",),
    ],
)
def test_sitios_rechaza(args):
    with pytest.raises(ms.Rechazo):
        _ok("maquita-admin", "maquita-sitios", *args)


def test_sitios_solo_panel():
    with pytest.raises(ms.Rechazo):
        _ok("www-data", "maquita-sitios", "listar")


def test_sitios_mantenimiento():
    for orden in ("entrar", "clave-admin", "revisar", "actualizar", "buscadores", "avisar"):
        assert _ok("maquita-admin", "maquita-sitios", orden, "ejemplo.org")
    # Solo el sistema: el panel no puede lanzar las tareas internas.
    for interna in (("cron",), ("regenerar",), ("entrar",), ("entrar", "ejemplo.org", "x")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-sitios", *interna)


# --- Zonas DNS del panel (maquita-dns) ---


def test_dns_ordenes_permitidas():
    larga = "eyJ0aXBvIjoiVFhUIn0" * 30  # base64url de más de 300 caracteres (registros DKIM)
    for args in (
        ("listar",),
        ("estado",),
        ("ver", "ejemplo.org"),
        ("crear", "ejemplo.org"),
        ("crear", "ejemplo.org", "sin-web"),
        ("agregar", "ejemplo.org", larga),
        ("modificar", "ejemplo.org", "0a1b2c3d", "eyJ0aXBvIjoiQSJ9"),
        ("borrar-registro", "ejemplo.org", "0a1b2c3d"),
        ("borrar", "ejemplo.org", "ejemplo.org"),
        ("comprobar", "ejemplo.org"),
        ("servidor", "eyJpcF9jb3JyZW8iOiIxLjIuMy40In0"),
        ("certificado-estado",),
        ("certificado-correo",),
    ):
        assert _ok("maquita-admin", "maquita-dns", *args)


@pytest.mark.parametrize(
    "args",
    [
        ("ver", "../etc"),
        ("agregar", "ejemplo.org", "no es base64 válido"),
        ("modificar", "ejemplo.org", "x", "eyJ9"),
        ("borrar", "ejemplo.org", "otro.org"),
        ("crear", "ejemplo.org", "--algo"),
        ("rndc", "reload"),
    ],
)
def test_dns_rechaza(args):
    with pytest.raises(ms.Rechazo):
        _ok("maquita-admin", "maquita-dns", *args)


def test_dns_solo_panel():
    with pytest.raises(ms.Rechazo):
        _ok("www-data", "maquita-dns", "listar")


# --- Cortafuegos del panel (maquita-cortafuegos) ---


def test_cortafuegos_ordenes_permitidas():
    for args in (
        ("estado",),
        ("confirmar",),
        ("revertir",),
        ("aplicar", "eyJzZXJ2aWNpb3MiOnt9fQ", "192.0.2.10"),
        ("desbloquear", "sitios-wp-login", "203.0.113.50"),
    ):
        assert _ok("maquita-admin", "maquita-cortafuegos", *args)


@pytest.mark.parametrize(
    "args",
    [
        ("quitar",),
        ("cargar",),
        ("inicial", "0.0.0.0/0"),
        ("aplicar", "eyJ9", "192.0.2.4; id"),
        ("desbloquear", "sshd;rm", "203.0.113.50"),
    ],
)
def test_cortafuegos_rechaza(args):
    with pytest.raises(ms.Rechazo):
        _ok("maquita-admin", "maquita-cortafuegos", *args)


# --- Identidad (maquita-identidad) y página «en construcción» (maquita-sitios inicio) ---


def test_identidad_y_pagina_inicio():
    assert _ok("maquita-admin", "maquita-identidad", "aplicar", "eyJub21icmUiOiJYIn0" * 40)
    assert _ok("maquita-admin", "maquita-sitios", "inicio", "ejemplo.org", "eyJub21icmUiOiJYIn0" * 40)
    for malo in (("aplicar",), ("aplicar", "no base64!"), ("borrar", "x")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-identidad", *malo)
    with pytest.raises(ms.Rechazo):
        _ok("www-data", "maquita-identidad", "aplicar", "eyJ9")


def test_sitios_catalogo_y_bases():
    for app in ("moodle", "dolibarr", "matomo"):
        assert _ok("maquita-admin", "maquita-sitios", "app", "ejemplo.org", app, "SG9sYQ", "a@example.org")
    assert _ok("maquita-admin", "maquita-sitios", "tienda", "ejemplo.org")
    assert _ok("maquita-admin", "maquita-sitios", "bases", "ejemplo.org")
    assert _ok("maquita-admin", "maquita-sitios", "base-crear", "ejemplo.org", "postgresql")
    assert _ok("maquita-admin", "maquita-sitios", "base-borrar", "ejemplo.org", "x_ejemplo1234_0a1b")
    for malo in (("base-crear", "ejemplo.org", "oracle"), ("base-borrar", "ejemplo.org", "mysql"),
                 ("app", "ejemplo.org", "../x", "SG9sYQ", "a@example.org"), ("app", "ejemplo.org", "A b", "SG9sYQ", "a@example.org")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-sitios", *malo)


def test_sitios_aplicaciones_propias():
    for tipo in ("estatico", "python", "node"):
        assert _ok("maquita-admin", "maquita-sitios", "propia-crear", "ejemplo.org", tipo, "eyJlbnRyYWRhIjoiYXBwOmFwcCJ9")
    assert _ok("maquita-admin", "maquita-sitios", "propia-estado", "ejemplo.org")
    for accion in ("iniciar", "detener", "reiniciar", "desplegar"):
        assert _ok("maquita-admin", "maquita-sitios", "propia-accion", "ejemplo.org", accion)
    assert _ok("maquita-admin", "maquita-sitios", "propia-entorno", "ejemplo.org", "eyJBIjoiYiJ9")
    assert _ok("maquita-admin", "maquita-sitios", "propia-quitar", "ejemplo.org", "ejemplo.org")
    for malo in (("propia-crear", "ejemplo.org", "php", "e30"), ("propia-crear", "ejemplo.org", "node", "a b"),
                 ("propia-accion", "ejemplo.org", "borrar"), ("propia-quitar", "ejemplo.org", "otro.org"),
                 ("propia-entorno", "ejemplo.org", "x;rm")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-sitios", *malo)


def test_valores_de_entorno_no_van_al_registro():
    assert "eyJBIjoiYiJ9" not in ms._enmascarar("maquita-sitios", ["propia-entorno", "ejemplo.org", "eyJBIjoiYiJ9"])


def test_actualizar():
    for args in (("estado",), ("buscar",), ("aplicar", "v1.8.0"), ("aplicar", "origin/feat/sitios-web"), ("config", "eyJhIjoxfQ")):
        assert _ok("maquita-admin", "maquita-actualizar", *args)
    for malo in (("ejecutar", "v1.8.0"), ("automatico",), ("aplicar", "main;rm"), ("aplicar", "origin/../x"), ("aplicar", "1.8.0")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-actualizar", *malo)
    with pytest.raises(ms.Rechazo):
        _ok("www-data", "maquita-actualizar", "estado")


def test_respaldos():
    for args in (("estado",), ("respaldar",), ("comprobar",), ("clave",), ("config", "eyJhIjoxfQ"), ("credenciales", "e30"),
                 ("restaurar-sitio", "ejemplo.org", "0a1b2c3d"), ("restaurar-buzon", "ana@ejemplo.org", "0a1b2c3d")):
        assert _ok("maquita-admin", "maquita-respaldos", *args)
    for malo in (("automatico",), ("ejecutar", "respaldar"), ("restaurar-sitio", "ejemplo.org", "latest"),
                 ("restaurar-buzon", "no-es-correo", "0a1b2c3d"), ("restaurar-sitio", "../etc", "0a1b2c3d")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-respaldos", *malo)
    assert "e30" not in ms._enmascarar("maquita-respaldos", ["credenciales", "e30"])


def test_sitios_alias():
    assert _ok("maquita-admin", "maquita-sitios", "alias", "ejemplo.org", "WyJlamVtcGxvLmNvbSJd")
    for malo in (("alias", "ejemplo.org", "a b"), ("alias", "Ejemplo..org", "W10"), ("alias", "ejemplo.org")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-sitios", *malo)


def test_sitios_trabajos_de_cron():
    assert _ok("maquita-admin", "maquita-sitios", "tareas", "ejemplo.org")
    assert _ok("maquita-admin", "maquita-sitios", "tareas-guardar", "ejemplo.org", "W10")
    assert _ok("maquita-admin", "maquita-sitios", "tarea-ejecutar", "ejemplo.org", "0a1b2c3d")
    assert _ok("maquita-admin", "maquita-sitios", "tarea-registro", "ejemplo.org", "0a1b2c3d")
    for malo in (("tarea-ejecutar", "ejemplo.org", "../x"), ("tareas-guardar", "ejemplo.org", "a;b"),
                 ("tarea-registro", "ejemplo.org"), ("tareas", "ejemplo.org", "x")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-sitios", *malo)


def test_sitios_catalogo_ampliado():
    assert _ok("maquita-admin", "maquita-sitios", "catalogo")
    assert _ok("maquita-admin", "maquita-sitios", "terminar", "ejemplo.org")
    assert _ok("maquita-admin", "maquita-sitios", "app", "ejemplo.org", "limesurvey", "SG9sYQ", "a@example.org")


def test_sitios_paquete_propio():
    assert _ok("maquita-admin", "maquita-sitios", "paquete", "ejemplo.org", "0123456789abcdef0123456789abcdef.zip", "con-bd")
    assert _ok("maquita-admin", "maquita-sitios", "paquete", "ejemplo.org", "0123456789abcdef0123456789abcdef.tar.gz", "sin-bd")
    assert _ok("maquita-admin", "maquita-sitios", "paquete", "ejemplo.org", "0123456789abcdef0123456789abcdef.zip", "con-bd",
               "fedcba9876543210fedcba9876543210.sql.gz")
    for malo in (("paquete", "ejemplo.org", "0123456789abcdef0123456789abcdef.zip", "con-bd", "../x.sql"),
                 ("paquete", "ejemplo.org", "../../etc/shadow", "con-bd"), ("paquete", "ejemplo.org", "x.zip", "con-bd"),
                 ("paquete", "ejemplo.org", "0123456789abcdef0123456789abcdef.zip", "si")):
        with pytest.raises(ms.Rechazo):
            _ok("maquita-admin", "maquita-sitios", *malo)
