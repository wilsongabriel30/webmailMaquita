# -*- coding: utf-8 -*-
"""Validadores de maquita-sudo para el correo y el sistema: doveadm, postqueue, postsuper, postconf, systemctl,
journalctl, sievec, fail2ban-client, nginx, sendmail, maquita-outbound, depurar-adjuntos-peligrosos y geoip-country.sh.
"""
import ipaddress
import os
import re

from sudo_base import (_RE_JAIL, _RE_PROP, _RE_QID, _RE_SIEVE, _RE_SINCE, _RE_VALOR, Rechazo, _buzon_existe,
                       _tokens_limpios, es_buzon)

UNIDADES = {"postfix", "dovecot", "rspamd", "redis-server", "postgresql@17-main", "postgresql",
            "nginx", "clamav-daemon", "fail2ban", "maquita-webmail", "maquita-milter",
            "maquita-almacen", "maquita-admin", "radicale"}
ACCIONES_SYSTEMCTL = {"start", "stop", "restart", "reload", "is-active", "is-enabled", "status", "show"}
POSTCONF_PARAMS = {
    "bounce_queue_lifetime", "command_directory", "header_size_limit", "inet_interfaces",
    "inet_protocols", "mail_version", "mailbox_size_limit", "maximal_queue_lifetime",
    "message_size_limit", "mydestination", "mydomain", "myhostname", "myorigin",
    "queue_directory", "smtp_tls_security_level", "smtpd_banner",
    "smtpd_client_connection_rate_limit", "smtpd_client_message_rate_limit",
    "smtpd_recipient_limit", "smtpd_sasl_auth_enable", "smtpd_sasl_type",
    "smtpd_tls_security_level", "virtual_mailbox_domains", "virtual_mailbox_limit",
    "virtual_transport", "smtpd_milters", "milter_default_action",
}
FLAGS_DOVEADM = {
    "search": {"-u"}, "fetch": {"-u"}, "expunge": {"-u"}, "move": {"-u"}, "copy": {"-u"},
    "flags": {"-u"},
    "quota": {"-u"}, "mailbox": {"-u"}, "acl": {"-u"}, "force-resync": {"-u"}, "user": {"-u"},
    "pw": {"-s", "-p"}, "auth": set(), "who": set(),
}


def validar_doveadm(args, comprobar_buzon=_buzon_existe):
    if not args:
        raise Rechazo("doveadm sin subcomando")
    sub = args[0]
    if sub not in FLAGS_DOVEADM:
        raise Rechazo(f"doveadm {sub} no permitido")
    resto = list(args[1:])
    _tokens_limpios(resto)
    permitidas = FLAGS_DOVEADM[sub]
    i = 0
    vio_u = False
    while i < len(resto):
        t = resto[i]
        if t.startswith("-"):
            if t not in permitidas:
                raise Rechazo(f"opción {t} no permitida en doveadm {sub}")
            if i + 1 >= len(resto):
                raise Rechazo(f"{t} sin valor")
            val = resto[i + 1]
            if t == "-u":
                if not es_buzon(val):
                    raise Rechazo("buzón con formato inválido")
                if not comprobar_buzon(val):
                    raise Rechazo("buzón inexistente o de dominio ajeno")
                vio_u = True
            elif t == "-s" and val != "SHA512-CRYPT":
                raise Rechazo("esquema de hash no permitido")
            i += 2
            continue
        i += 1
    if sub in ("search", "fetch", "expunge", "move", "copy", "flags", "quota", "mailbox", "acl", "force-resync", "user") and not vio_u:
        raise Rechazo(f"doveadm {sub} exige -u <buzón>")
    if sub == "auth":
        if len(resto) != 3 or resto[0] != "test" or not es_buzon(resto[1]):
            raise Rechazo("doveadm auth solo admite: test <buzón> <clave>")
    return [sub] + resto


def validar_postqueue(args):
    if args in (["-p"], ["-j"], ["-f"]):
        return args
    if len(args) == 2 and args[0] == "-i" and _RE_QID.fullmatch(args[1]):
        return args
    raise Rechazo("postqueue: solo -p, -j, -f o -i <id de cola>")


def validar_postsuper(args):
    if len(args) == 2 and args[0] in ("-d", "-r", "-h", "-H") and (args[1] == "ALL" or _RE_QID.fullmatch(args[1])):
        return args
    raise Rechazo("postsuper: solo -d/-r/-h/-H <id de cola|ALL>")


def validar_postconf(args):
    if not args:
        return args
    if len(args) == 1 and args[0] in POSTCONF_PARAMS:
        return args
    if len(args) == 2 and args[0] == "-h" and args[1] in POSTCONF_PARAMS:
        return args
    if len(args) == 2 and args[0] == "-e" and "=" in args[1]:
        k, v = args[1].split("=", 1)
        if k in POSTCONF_PARAMS and _RE_VALOR.fullmatch(v):
            return args
    raise Rechazo("postconf: parámetro fuera de la lista o valor con caracteres no permitidos")


def validar_systemctl(args):
    if len(args) < 2 or args[0] not in ACCIONES_SYSTEMCTL or args[1] not in UNIDADES:
        raise Rechazo("systemctl: acción o unidad fuera de la lista")
    resto = args[2:]
    i = 0
    while i < len(resto):
        if resto[i] in ("--no-pager", "-l", "--quiet"):
            i += 1
        elif resto[i] == "-p" and i + 1 < len(resto) and _RE_PROP.fullmatch(resto[i + 1]):
            i += 2
        else:
            raise Rechazo(f"systemctl: opción {resto[i]} no permitida")
    return args


def validar_journalctl(args):
    if len(args) < 2 or args[0] != "-u" or args[1] not in UNIDADES:
        raise Rechazo("journalctl: exige -u <unidad de la lista>")
    resto = args[2:]
    i = 0
    while i < len(resto):
        t = resto[i]
        if t in ("--no-pager", "--output=short-iso", "--output=short", "-r"):
            i += 1
        elif t == "-n" and i + 1 < len(resto) and resto[i + 1].isdigit() and int(resto[i + 1]) <= 2000:
            i += 2
        elif t == "--since" and i + 1 < len(resto) and _RE_SINCE.fullmatch(resto[i + 1]):
            i += 2
        else:
            raise Rechazo(f"journalctl: opción {t} no permitida")
    return args


def validar_sievec(args):
    if len(args) != 1 or not _RE_SIEVE.fullmatch(args[0]):
        raise Rechazo("sievec: solo un .sieve bajo /var/vmail/<dominio>/<usuario>/")
    real = os.path.realpath(args[0])
    if real != args[0]:
        raise Rechazo("sievec: la ruta no puede ser un enlace")
    return args


def validar_fail2ban(args):
    if args == ["status"]:
        return args
    if len(args) == 2 and args[0] == "status" and _RE_JAIL.fullmatch(args[1]):
        return args
    if len(args) == 4 and args[0] == "set" and _RE_JAIL.fullmatch(args[1]) and args[2] in ("banip", "unbanip"):
        try:
            ipaddress.ip_address(args[3])
        except ValueError:
            raise Rechazo("fail2ban-client: IP inválida")
        return args
    if len(args) == 3 and args[0] == "get" and _RE_JAIL.fullmatch(args[1]) and _RE_PROP.fullmatch(args[2]):
        return args
    if len(args) == 4 and args[0] == "set" and _RE_JAIL.fullmatch(args[1]) and _RE_PROP.fullmatch(args[2]) and _RE_VALOR.fullmatch(args[3]):
        return args
    raise Rechazo("fail2ban-client: forma no permitida")


def validar_nginx(args):
    if args == ["-t"]:
        return args
    raise Rechazo("nginx: solo -t")


def validar_sendmail(args):
    # sendmail [-i] -f <remitente> -- <destinatarios...>
    a = list(args)
    if a and a[0] == "-i":
        a = a[1:]
    if len(a) < 4 or a[0] != "-f" or not es_buzon(a[1]) or a[2] != "--":
        raise Rechazo("sendmail: solo [-i] -f <remitente> -- <destinatarios>")
    if not all(es_buzon(d) for d in a[3:]) or len(a) > 103:
        raise Rechazo("sendmail: destinatario inválido")
    return list(args)


def _lista_de_buzones(csv: str) -> bool:
    partes = [p for p in csv.split(",") if p]
    return 0 < len(partes) <= 200 and all(es_buzon(p) for p in partes)


def validar_outbound(args):
    """maquita-outbound: solo sus subacciones, cada una con la forma exacta de sus argumentos."""
    if args == ["get-limits"]:
        return args
    if len(args) == 3 and args[0] == "set-limits" and all(a.isdigit() and len(a) <= 6 for a in args[1:]):
        if 1 <= int(args[1]) <= 100000 and 1 <= int(args[2]) <= 10000:
            return args
        raise Rechazo("maquita-outbound set-limits: valores fuera de rango")
    if args[:1] in (["set-whitelist"], ["set-dlp-exempt"]):
        # Sin lista = vaciarla. Con lista: buzones separados por comas, nada más.
        if len(args) == 1 or (len(args) == 2 and _lista_de_buzones(args[1])):
            return args
        raise Rechazo(f"maquita-outbound {args[0]}: solo una lista de buzones separados por comas")
    if args[:1] == ["activity"]:
        if len(args) == 1 or (len(args) == 2 and args[1].isdigit() and 1 <= int(args[1]) <= 168):
            return args
        raise Rechazo("maquita-outbound activity: horas entre 1 y 168")
    if len(args) == 2 and args[0] in ("lock", "unlock", "status") and es_buzon(args[1]):
        return args
    raise Rechazo("maquita-outbound: subacción o argumentos no permitidos")


def validar_depurar(args):
    """depurar-adjuntos-peligrosos --dias <1..365> [--borrar]"""
    if len(args) in (2, 3) and args[0] == "--dias" and args[1].isdigit() and 1 <= int(args[1]) <= 365:
        if len(args) == 2 or args[2] == "--borrar":
            return args
    raise Rechazo("depurar-adjuntos-peligrosos: solo --dias <1..365> [--borrar]")


_RE_PAIS = re.compile(r"^[a-z]{2}$")


def validar_geoip(args):
    """geoip-country.sh enable|disable <código ISO de dos letras>"""
    if len(args) == 2 and args[0] in ("enable", "disable") and _RE_PAIS.fullmatch(args[1]):
        return args
    raise Rechazo("geoip-country.sh: solo enable|disable <país en dos letras minúsculas>")

