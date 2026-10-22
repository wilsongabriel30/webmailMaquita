"""Vales de un solo uso emitidos desde la consola: entrada al panel general y soporte del portal.

- Vale de ENTRADA (maquita-panel vale-entrada): abre la sesión de un administrador del panel
  (8443) en https://<panel>/entrar?vale=…, sin contraseña ni segundo factor (lo emite root en el
  propio servidor). La sesión que abre queda marcada «sin segundo factor»: no puede impersonar
  buzones mientras IMPERSONAR_EXIGE_TOTP siga activo.
- Vale de SOPORTE (maquita-panel-dominio vale-soporte): abre el portal de UN dominio (8444) como
  soporte, en solo lectura salvo que se pida --con-acciones.

En la base solo queda el hash (sha256) del vale; caduca en N segundos (máximo 900) y se audita.
"""

import getpass
import hashlib
import os
import re
import secrets
from urllib.parse import urlsplit

import panel_bd

VIDA_MAXIMA = 900
VIDA_MINIMA = 10
RE_ADMIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@-]{0,254}")
RE_DOMINIO = re.compile(r"(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
RE_SERVIDOR = re.compile(r"(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(:[0-9]{1,5})?")
RE_USUARIO_SISTEMA = re.compile(r"[a-z_][a-z0-9_.-]{0,31}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")

SQL_ENTRADA = """
WITH u AS (SELECT id, username, role, active FROM admin_users WHERE username = :'admin'),
v AS (
  INSERT INTO admin_vales_entrada (vale_hash, user_id, origen, exige_totp, creado_por, expires_at)
  SELECT :'huella', u.id, 'consola', false, :'quien', NOW() + make_interval(secs => :'vida'::int)
    FROM u WHERE u.active
  RETURNING id),
a AS (
  INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address)
  SELECT u.id, u.username, 'vale_entrada_emitido', u.username,
         json_build_object('origen', 'consola', 'vida_segundos', :'vida'::int, 'emitido_por', :'quien')::jsonb, 'consola'
    FROM u WHERE EXISTS (SELECT 1 FROM v))
SELECT json_build_object('existe', EXISTS (SELECT 1 FROM u), 'activo', COALESCE((SELECT active FROM u), false),
                         'rol', (SELECT role FROM u), 'creado', EXISTS (SELECT 1 FROM v));
"""

SQL_SOPORTE = """
WITH d AS (SELECT domain FROM domain WHERE lower(domain) = :'dominio' LIMIT 1),
v AS (
  INSERT INTO pd_vales_soporte (vale_hash, domain, solo_lectura, superadmin, origen, motivo, expires_at)
  SELECT :'huella', d.domain, :'solo'::boolean, :'quien', 'consola', :'motivo', NOW() + make_interval(secs => :'vida'::int)
    FROM d
  RETURNING domain),
a AS (
  INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address)
  SELECT NULL, :'quien', 'soporte_vale_emitido', v.domain,
         json_build_object('origen', 'consola', 'modo', CASE WHEN :'solo'::boolean THEN 'solo_lectura' ELSE 'con_acciones' END,
                           'vida_segundos', :'vida'::int, 'motivo', :'motivo')::jsonb, 'consola'
    FROM v)
SELECT json_build_object('dominio', (SELECT domain FROM v));
"""

SQL_PORTAL_EMPRESA = """
SELECT json_build_object('host', (SELECT lower(host) FROM portal_empresa
                                    WHERE lower(dominio) = :'dominio' AND activo = true LIMIT 1));
"""


def vida(valor, defecto):
    try:
        n = int(valor if valor is not None else defecto)
    except (TypeError, ValueError):
        raise panel_bd.ErrorConsola("--vida debe ser un número de segundos")
    if not VIDA_MINIMA <= n <= VIDA_MAXIMA:
        raise panel_bd.ErrorConsola(f"--vida debe estar entre {VIDA_MINIMA} y {VIDA_MAXIMA} segundos")
    return n


def quien():
    """Quién emite el vale desde la consola, para la auditoría: consola:<usuario del sistema>."""
    usuario = os.environ.get("SUDO_USER") or getpass.getuser() or "root"
    return "consola:" + (usuario if RE_USUARIO_SISTEMA.fullmatch(usuario) else "root")


def nuevo():
    """(vale en claro, su hash). El vale solo se muestra una vez, a quien lo pidió."""
    vale = secrets.token_urlsafe(32)
    return vale, hashlib.sha256(vale.encode()).hexdigest()


def base_url(host, variable, puerto):
    """https://<servidor>:<puerto> — de --host, de la variable de la organización o de MAIL_HOST."""
    if host:
        host = host.strip().lower()
        if not RE_SERVIDOR.fullmatch(host):
            raise panel_bd.ErrorConsola("--host no es un nombre de servidor válido")
        return f"https://{host}" if ":" in host else f"https://{host}:{puerto}"
    explicita = panel_bd.valor_org(variable).rstrip("/")
    if explicita:
        partes = urlsplit(explicita)
        if partes.scheme == "https" and partes.hostname:
            return f"https://{partes.netloc}"
    servidor = panel_bd.servidor_correo()
    if not servidor or not RE_SERVIDOR.fullmatch(servidor):
        raise panel_bd.ErrorConsola(f"no se sabe el nombre del servidor: indíquelo con --host o en {variable}")
    return f"https://{servidor}:{puerto}"


def vale_entrada(admin, segundos, host=None):
    if not RE_ADMIN.fullmatch(admin or ""):
        raise panel_bd.ErrorConsola("nombre de administrador no válido")
    segundos = vida(segundos, 120)
    url = base_url(host, "ORG_URL_PANEL", 8443)
    vale, huella = nuevo()
    r = panel_bd.consultar(SQL_ENTRADA, {"admin": admin, "huella": huella, "quien": quien(), "vida": segundos},
                           tabla="admin_vales_entrada") or {}
    if not r.get("existe"):
        raise panel_bd.ErrorConsola(f"no hay ningún administrador del panel llamado «{admin}»")
    if not r.get("activo") or not r.get("creado"):
        raise panel_bd.ErrorConsola(f"la cuenta «{admin}» está desactivada: actívela antes (maquita-admin-recovery unlock)")
    return {"admin": admin, "rol": r.get("rol"), "valido_segundos": segundos, "url": f"{url}/entrar?vale={vale}"}


def vale_soporte(dominio, solo_lectura, segundos, motivo="", host=None):
    dominio = (dominio or "").strip().lower()
    if not RE_DOMINIO.fullmatch(dominio):
        raise panel_bd.ErrorConsola("dominio no válido")
    segundos = vida(segundos, 300)
    motivo = CONTROL.sub(" ", motivo or "").strip()[:255]
    url = base_url(host, "ORG_URL_PORTAL_DOMINIO", 8444) if host else _url_portal(dominio)
    vale, huella = nuevo()
    r = panel_bd.consultar(SQL_SOPORTE, {"dominio": dominio, "huella": huella, "quien": quien(), "vida": segundos,
                                         "solo": "true" if solo_lectura else "false", "motivo": motivo},
                           tabla="pd_vales_soporte") or {}
    if not r.get("dominio"):
        raise panel_bd.ErrorConsola(f"el dominio «{dominio}» no está en este servidor")
    return {"dominio": r["dominio"], "modo": "solo_lectura" if solo_lectura else "con_acciones",
            "valido_segundos": segundos, "url": f"{url}/?vale={vale}"}


def _url_portal(dominio):
    """El portal propio de la empresa si lo tiene (portal_empresa, con el puerto del portal general);
    si no, el general: ORG_URL_PORTAL_DOMINIO o el servidor del correo. Lo mismo que muestra el panel."""
    general = base_url(None, "ORG_URL_PORTAL_DOMINIO", 8444)
    try:
        host = (panel_bd.consultar(SQL_PORTAL_EMPRESA, {"dominio": dominio}, tabla="portal_empresa") or {}).get("host")
    except panel_bd.ErrorConsola:
        host = None  # instalación sin portales por empresa
    if host and RE_SERVIDOR.fullmatch(host) and ":" not in host:
        return f"https://{host}:{urlsplit(general).port or 8444}"
    return general
