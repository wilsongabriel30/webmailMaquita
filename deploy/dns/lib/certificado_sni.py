"""Instala los certificados por dominio con SNI en nginx, Postfix y Dovecot (CERTIFICADO_MODO=por-dominio).

Cada servicio se cambia aparte, con copia previa, su comprobación (nginx -t, postfix check, doveconf -n)
y vuelta atrás si falla; un servicio que falla no impide configurar los demás. Solo se recarga lo que
cambió. El certificado del servidor sigue siendo el de siempre para todo lo demás (y para los dominios
cuyo certificado propio aún no existe).

- Postfix: tls_server_sni_maps = hash:/etc/postfix/sni-correo. El mapa se compila con «postmap -F»,
  que guarda una COPIA del certificado: tras cada renovación hay que volver a compilarlo y reiniciar
  Postfix (con reload no lo relee, lección #14). Lo hace el gancho de renovación y, por si acaso, cada
  pasada si un certificado es más nuevo que el mapa compilado.
- Dovecot: un bloque «local_name mail.<dominio> { … }» por dominio, con la sintaxis de su versión
  (2.4: ssl_server_cert_file = ruta; 2.3: ssl_cert = <ruta).
- nginx: certificado_sni_nginx.py.
"""

import os
import re
import subprocess

import certificado_base as B
import certificado_sni_nginx as N
from comun import ErrorDns, ejecutar, escribir

MAPA = "/etc/postfix/sni-correo"
GANCHO = "/etc/letsencrypt/renewal-hooks/deploy/sni-correo.sh"
DOVECOT_DIR = "/etc/dovecot"
DOVECOT_ARCHIVO = "90-sni-correo.conf"
RESPALDOS_NGINX = "/etc/nginx/respaldos"
CABECERA = "# Generado por maquita-dns (certificado por dominio): no editar, se rehace en cada pasada."


def _leer(ruta):
    try:
        with open(ruta) as f:
            return f.read()
    except OSError:
        return None


def _escribir_o_borrar(ruta, texto):
    if texto is None:
        if os.path.exists(ruta):
            os.remove(ruta)
    else:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, texto, 0o644)


def _aplicar(cambios, comprobar):
    """Escribe {ruta: texto|None}, comprueba y, si falla, deja cada archivo como estaba.

    Se respalda lo que no es generado (los generados se rehacen solos); los de nginx en
    /etc/nginx/respaldos/, nunca junto a los sitios (nginx leería la copia)."""
    previos = {r: _leer(r) for r in cambios}
    for ruta, previo in previos.items():
        if previo is not None and not previo.startswith((CABECERA, N.MARCA)):
            B.respaldar(ruta, RESPALDOS_NGINX if ruta.startswith((N.DISPONIBLES, N.ACTIVOS)) else None)
    try:
        for ruta, texto in cambios.items():
            _escribir_o_borrar(ruta, texto)
        comprobar()
    except (ErrorDns, OSError) as e:
        for ruta, texto in previos.items():
            _escribir_o_borrar(ruta, texto)
        raise ErrorDns(f"{e} (se dejó la configuración anterior)")


# --- nginx -------------------------------------------------------------------------------------------


def _poner_enlaces(estado):
    for enlace, poner in estado.items():
        if poner and not os.path.lexists(enlace):
            os.symlink(os.path.join(N.DISPONIBLES, os.path.basename(enlace)), enlace)
        elif not poner and os.path.lexists(enlace):
            os.remove(enlace)


def nginx(host, activos):
    cambios = N.planificar(host, activos)
    if not cambios:
        return False
    enlaces = {N.enlace(r): t is not None for r, t in cambios.items() if os.path.basename(r).startswith(N.PREFIJO)}
    antes = {e: os.path.lexists(e) for e in enlaces}

    def comprobar():
        _poner_enlaces(enlaces)
        ejecutar(["nginx", "-t"])

    try:
        _aplicar(cambios, comprobar)
    except ErrorDns:
        _poner_enlaces(antes)
        raise
    ejecutar(["systemctl", "reload", "nginx"])
    return True


# --- Postfix -----------------------------------------------------------------------------------------


def texto_mapa(activos):
    lineas = [CABECERA, f"# Compilar con «postmap -F hash:{MAPA}» y reiniciar Postfix (reload no basta)."]
    for dominio in sorted(activos):
        cadena, llave = B.rutas(f"mail.{dominio}")
        lineas.append(f"mail.{dominio} {llave} {cadena}")
    return "\n".join(lineas) + "\n"


def _mapa_caducado(activos):
    """El mapa compilado guarda una copia: si algún certificado es más nuevo, hay que recompilarlo."""
    try:
        compilado = os.path.getmtime(MAPA + ".db")
    except OSError:
        return True
    for dominio in activos:
        try:
            if os.path.getmtime(os.path.realpath(B.rutas(f"mail.{dominio}")[0])) > compilado:
                return True
        except OSError:
            continue
    return False


def postfix(activos):
    propio = f"hash:{MAPA}"
    actual = ejecutar(["postconf", "-h", "tls_server_sni_maps"]).strip()
    if actual and actual != propio:
        raise B.ErrorConfiguracion(f"Postfix ya usa otro mapa SNI (tls_server_sni_maps = {actual}): no se toca; "
                                   f"añada allí las líneas de {MAPA} o cambie el parámetro a {propio}")
    if not activos and not actual:
        return False
    texto = texto_mapa(activos)
    if texto == _leer(MAPA) and actual == propio and not _mapa_caducado(activos):
        return False

    def comprobar():
        ejecutar(["postmap", "-F", propio])
        if actual != propio:
            B.respaldar("/etc/postfix/main.cf")
            ejecutar(["postconf", "-e", f"tls_server_sni_maps={propio}"])
        try:
            ejecutar(["postfix", "check"])
        except ErrorDns:
            if actual != propio:
                ejecutar(["postconf", "-X", "tls_server_sni_maps"])
            raise

    try:
        _aplicar({MAPA: texto}, comprobar)
    except ErrorDns:
        if os.path.exists(MAPA):
            subprocess.run(["postmap", "-F", propio], capture_output=True, timeout=120)
        raise
    ejecutar(["systemctl", "restart", "postfix"])
    return True


# --- Dovecot -----------------------------------------------------------------------------------------


def version_dovecot():
    salida = ejecutar(["dovecot", "--version"]).strip()
    m = re.match(r"(\d+)\.(\d+)", salida)
    if not m:
        raise B.ErrorConfiguracion(f"versión de Dovecot desconocida ({salida[:40]})")
    return int(m.group(1)), int(m.group(2))


def destino_dovecot():
    """maquita.d (configuración del proyecto, Dovecot 2.4) o conf.d (la de Debian), la que se incluya."""
    conf = _leer(f"{DOVECOT_DIR}/dovecot.conf") or ""
    if "/etc/dovecot/maquita.d/" in conf and os.path.isdir(f"{DOVECOT_DIR}/maquita.d"):
        return f"{DOVECOT_DIR}/maquita.d/{DOVECOT_ARCHIVO}"
    if re.search(r"^\s*!include(?:_try)?\s+(?:/etc/dovecot/)?conf\.d/\*\.conf", conf, re.M):
        return f"{DOVECOT_DIR}/conf.d/{DOVECOT_ARCHIVO}"
    raise B.ErrorConfiguracion("/etc/dovecot/dovecot.conf no incluye maquita.d ni conf.d: no hay dónde poner los certificados por dominio")


def texto_dovecot(activos, version):
    lineas = [CABECERA]
    for dominio in sorted(activos):
        cadena, llave = B.rutas(f"mail.{dominio}")
        if version >= (2, 4):
            ajustes = [f"ssl_server_cert_file = {cadena}", f"ssl_server_key_file = {llave}"]
        else:
            ajustes = [f"ssl_cert = <{cadena}", f"ssl_key = <{llave}"]
        lineas += [f"local_name mail.{dominio} {{"] + [f"  {a}" for a in ajustes] + ["}"]
    return "\n".join(lineas) + "\n"


def dovecot(activos):
    if not activos and not any(os.path.exists(f"{DOVECOT_DIR}/{d}/{DOVECOT_ARCHIVO}") for d in ("maquita.d", "conf.d")):
        return False
    ruta = destino_dovecot()
    texto = texto_dovecot(activos, version_dovecot())
    if texto == _leer(ruta):
        return False
    _aplicar({ruta: texto}, lambda: ejecutar(["doveconf", "-n"]))
    ejecutar(["systemctl", "reload", "dovecot"])
    return True


# --- Gancho de renovación ------------------------------------------------------------------------------

TEXTO_GANCHO = f"""#!/bin/sh
{CABECERA}
# Tras renovar un certificado por dominio: el mapa SNI de Postfix guarda una copia (postmap -F), así que
# se recompila y se reinicia Postfix (reload no lo relee); Dovecot y nginx releen con reload.
MAPA={MAPA}
[ -s "$MAPA" ] || exit 0
grep -qF "${{RENEWED_LINEAGE:-/sin-linaje}}/" "$MAPA" || exit 0
postmap -F "hash:$MAPA" && systemctl restart postfix
systemctl reload dovecot nginx 2>/dev/null || true
exit 0
"""


def gancho():
    if _leer(GANCHO) == TEXTO_GANCHO:
        return False
    os.makedirs(os.path.dirname(GANCHO), exist_ok=True)
    escribir(GANCHO, TEXTO_GANCHO, 0o755)
    return True


def instalar(host, activos):
    """Configura los tres servicios. {"cambios": [...], "errores": [...]}; nunca lanza por un servicio."""
    cambios, errores = [], []
    for nombre, paso in (("nginx", lambda: nginx(host, activos)), ("postfix", lambda: postfix(activos)),
                         ("dovecot", lambda: dovecot(activos)), ("gancho", gancho)):
        try:
            if paso():
                cambios.append(nombre)
        except (ErrorDns, OSError) as e:
            errores.append(f"{nombre}: {e}")
    return {"cambios": cambios, "errores": errores}
