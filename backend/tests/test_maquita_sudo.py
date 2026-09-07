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

EXISTE = lambda b: b.endswith("@maquita.org")  # noqa: E731  doble de «doveadm user»


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
        "ana@maquita.org",
        "header",
        "message-id",
        "<x@y>",
    )
    assert _ok(
        "www-data",
        "doveadm",
        "expunge",
        "-u",
        "ana@maquita.org",
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
        "ana@maquita.org",
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
        "ana@maquita.org",
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
        "ana@maquita.org",
    )
    _no("www-data", "doveadm", "search", "-A", "header", "message-id", "<x@y>")
    _no("www-data", "doveadm", "search", "header", "message-id", "<x@y>")  # sin -u
    _no(
        "www-data", "doveadm", "mailbox", "delete", "-u", "ana@maquita.org", "INBOX"
    )  # subcomando ajeno


def test_buzon_estricto_y_de_dominio_propio():
    _no("www-data", "doveadm", "search", "-u", "-ana@maquita.org", "header", "x", "y")
    _no(
        "www-data",
        "doveadm",
        "search",
        "-u",
        "ana maquita@maquita.org",
        "header",
        "x",
        "y",
    )
    _no(
        "www-data", "doveadm", "search", "-u", "ana@otro.example", "header", "x", "y"
    )  # no existe en Dovecot
    _no("www-data", "doveadm", "search", "-u", "ana@maquita.org\n", "header", "x", "y")
    assert (
        ms.es_buzon("Ana.Perez+x@Maquita.org")
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
        "postmaster@maquita.org",
        "--",
        "ana@maquita.org",
    )
    _no(
        "maquita-admin",
        "sendmail",
        "-f",
        "postmaster@maquita.org",
        "-C",
        "/tmp/x",
        "--",
        "ana@maquita.org",
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
        "doveadm", ["auth", "test", "ana@maquita.org", "clave"]
    )
