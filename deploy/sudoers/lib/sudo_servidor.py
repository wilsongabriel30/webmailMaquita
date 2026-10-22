# -*- coding: utf-8 -*-
"""Validadores de maquita-sudo para los ayudantes del servidor: maquita-dns, maquita-cortafuegos, maquita-identidad,
maquita-actualizar, maquita-respaldos, maquita-fts y maquita-wazuh.
"""
import re

from sudo_base import _RE_B64URL_LARGO, _RE_DOMINIO_SITIO, _RE_ID_REGISTRO, _RE_JAIL, Rechazo, _buzon_existe, es_buzon


def validar_dns(args):
    """maquita-dns: subacciones con su forma exacta; los datos libres van en base64url (el ayudante revalida)."""
    zona = lambda z: bool(_RE_DOMINIO_SITIO.fullmatch(z))  # noqa: E731
    b64 = lambda v: bool(_RE_B64URL_LARGO.fullmatch(v))  # noqa: E731
    if args in (["estado"], ["servidor-ver"], ["listar"], ["certificado-estado"], ["certificado-correo"],
                ["transferencias-ver"], ["transferencias-secreto"]):
        return args
    # «servidor --opciones» y «transferencias-importar» son de la consola del servidor, no del panel.
    if len(args) == 2 and args[0] in ("servidor", "transferencias") and b64(args[1]) and not args[1].startswith("-"):
        return args
    if len(args) == 2 and args[0] in ("ver", "comprobar") and zona(args[1]):
        return args
    if args[:1] == ["crear"] and len(args) in (2, 3) and zona(args[1]) and (len(args) == 2 or args[2] == "sin-web"):
        return args
    if len(args) == 3 and args[0] == "agregar" and zona(args[1]) and b64(args[2]):
        return args
    if len(args) == 4 and args[0] == "modificar" and zona(args[1]) and _RE_ID_REGISTRO.fullmatch(args[2]) and b64(args[3]):
        return args
    if len(args) == 3 and args[0] == "borrar-registro" and zona(args[1]) and _RE_ID_REGISTRO.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] == "borrar" and zona(args[1]) and args[1] == args[2]:
        return args
    raise Rechazo("maquita-dns: subacción o argumentos no permitidos")


_RE_IP_O_RED = re.compile(r"^[0-9a-fA-F:.]{2,45}(?:/\d{1,3})?$")


def validar_cortafuegos(args):
    """maquita-cortafuegos: solo lo que usa el panel; «cargar», «quitar» e «inicial» son del sistema."""
    if args in (["estado"], ["confirmar"], ["revertir"]):
        return args
    if len(args) == 3 and args[0] == "aplicar" and _RE_B64URL_LARGO.fullmatch(args[1]) and _RE_IP_O_RED.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] == "desbloquear" and _RE_JAIL.fullmatch(args[1]) and _RE_IP_O_RED.fullmatch(args[2]):
        return args
    raise Rechazo("maquita-cortafuegos: subacción o argumentos no permitidos")


def validar_identidad(args):
    """maquita-identidad aplicar <JSON base64url> (el ayudante revalida cada campo)."""
    if len(args) == 2 and args[0] == "aplicar" and _RE_B64URL_LARGO.fullmatch(args[1]):
        return args
    raise Rechazo("maquita-identidad: solo «aplicar <identidad en base64url>»")


_RE_REF_VERSION = re.compile(r"^(?:v\d{1,4}\.\d{1,4}\.\d{1,4}|origin/[A-Za-z0-9][A-Za-z0-9._/-]{0,99})$")


def validar_actualizar(args):
    """maquita-actualizar: lo que usa el panel; «ejecutar» y «automatico» son del sistema."""
    if args in (["estado"], ["buscar"]):
        return args
    if len(args) == 2 and args[0] == "aplicar" and _RE_REF_VERSION.fullmatch(args[1]) and ".." not in args[1]:
        return args
    if len(args) == 2 and args[0] == "config" and _RE_B64URL_LARGO.fullmatch(args[1]):
        return args
    raise Rechazo("maquita-actualizar: solo estado, buscar, aplicar <versión> o config <json>")


_RE_INSTANTANEA = re.compile(r"^[0-9a-f]{8,64}$")


def validar_respaldos(args):
    """maquita-respaldos: lo que usa el panel; «automatico» y «ejecutar» son del sistema."""
    if args in (["estado"], ["respaldar"], ["comprobar"], ["clave"]):
        return args
    if len(args) == 2 and args[0] in ("config", "credenciales") and _RE_B64URL_LARGO.fullmatch(args[1]):
        return args
    if len(args) == 3 and args[0] == "restaurar-sitio" and _RE_DOMINIO_SITIO.fullmatch(args[1]) and _RE_INSTANTANEA.fullmatch(args[2]):
        return args
    if len(args) == 3 and args[0] == "restaurar-buzon" and es_buzon(args[1]) and _RE_INSTANTANEA.fullmatch(args[2]):
        return args
    raise Rechazo("maquita-respaldos: subacción o argumentos no permitidos")


def validar_fts(args, comprobar_buzon=_buzon_existe):
    """maquita-fts: «estado» o «reindexar <buzón>» (buzón existente, en minúsculas). Nada más:
    «indexar-inicial» es del instalador, no del panel."""
    if args == ["estado"]:
        return args
    if len(args) == 2 and args[0] == "reindexar" and args[1] == args[1].lower() and es_buzon(args[1]):
        if not comprobar_buzon(args[1]):
            raise Rechazo("maquita-fts: buzón inexistente")
        return args
    raise Rechazo("maquita-fts: solo estado o reindexar <buzón>")


_RE_ORDEN_WAZUH = re.compile(r"estado")


def validar_wazuh(args):
    """maquita-wazuh: solo «estado» (lee el estado del agente; no cambia nada)."""
    if len(args) == 1 and isinstance(args[0], str) and _RE_ORDEN_WAZUH.fullmatch(args[0]):
        return args
    raise Rechazo("maquita-wazuh: solo «estado»")
