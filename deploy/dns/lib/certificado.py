"""Certificado del correo (botón «Certificado del correo» y temporizador maquita-certificado-correo).

Certificado del servidor: un linaje de Let's Encrypt con el nombre del servidor tal cual (MAIL_HOST:
mail.<dominio>, hosting.<dominio>…) que cubre mail., autoconfig., autodiscover. y mta-sts. de los
dominios, solo con los nombres que desde Internet ya apuntan a la IP del correo. Lo usan nginx (webmail,
panel, portal de dominio, autoconfiguración, MTA-STS), Postfix, Dovecot y vsftpd, y queda un gancho que
los recarga en cada renovación. Su clave no cambia nunca (DANE: ver certificado_base.py).

Dos modos (CERTIFICADO_MODO en /etc/maquita-mail/organizacion.env):
- «compartido» (por defecto, lo de siempre): el certificado del servidor cubre todos los dominios con
  zona aquí. Pensado para dominios de una misma organización: el certificado es público (Certificate
  Transparency) y lista todos los nombres.
- «por-dominio» (hospedaje): el del servidor cubre solo el dominio principal y cada dominio de cliente
  tiene el suyo, instalado por SNI (certificado_dominios.py, certificado_sni.py). Los nombres de clientes
  que ya estaban en el del servidor siguen ahí hasta que su certificado propio existe; entonces se
  retiran (con la misma clave).
"""

import glob
import ipaddress
import os
import subprocess

import certificado_base as B
import certificado_dominios as D
import certificado_espera as E
import certificado_sni as S
import zona as Z
from certificado_base import SNAKEOIL, ErrorConfiguracion
from comun import ErrorDns, ejecutar, escribir, servidor

NOMBRES_NGINX = "/etc/nginx/snippets/correo-nombres.conf"
SITIOS = "/etc/nginx/sites-available"
GANCHO = "/etc/letsencrypt/renewal-hooks/deploy/servicios-correo.sh"
DOVECOT_PROPIO = ("/etc/dovecot/private/dovecot.pem", "/etc/dovecot/private/dovecot.key")
_respaldar = B.respaldar
_reemplazar = B.reemplazar


def _principal():
    return B.principal()


def _candidatos(host, dominio_principal, zonas=None):
    if zonas is None:
        zonas = sorted({z["zona"] for z in Z.listar()} | {dominio_principal})
    nombres = [host]
    for z in zonas:
        for prefijo in ("mail", "autoconfig", "autodiscover", "mta-sts"):
            n = f"{prefijo}.{z}"
            if prefijo == "mta-sts" and not os.path.exists(f"/etc/nginx/sites-enabled/mta-sts.{z}"):
                continue
            if n not in nombres:
                nombres.append(n)
    return nombres


def _de_clientes(nombres, dominios):
    """{dominio de cliente: [nombres suyos]} de una lista de nombres."""
    salida = {}
    for n in nombres:
        d = next((d for d in dominios if n == d or n.endswith("." + d)), None)
        if d:
            salida.setdefault(d, []).append(n)
    return salida


def _candidatos_servidor(host, principal, modo):
    """Nombres que pide el certificado del servidor. En «por-dominio», los del dominio principal más los de
    clientes que ya estaban en él y todavía no tienen certificado propio (para no dejarlos sin cubrir)."""
    if modo == "compartido":
        return _candidatos(host, principal)
    nombres = _candidatos(host, principal, [principal])
    propios = D.activos(host, principal)
    cubiertos = (B.leer_certificado(host) or {}).get("nombres", [])
    for d, suyos in _de_clientes(cubiertos, D.dominios_cliente(host, principal)).items():
        if d not in propios:
            nombres += [n for n in suyos if n not in nombres]
    return nombres


def _sobrantes(host, principal):
    """Nombres de clientes con certificado propio que aún figuran en el del servidor («por-dominio»)."""
    cubiertos = (B.leer_certificado(host) or {}).get("nombres", [])
    propios = D.activos(host, principal)
    return sorted(n for d, suyos in _de_clientes(cubiertos, D.dominios_cliente(host, principal)).items()
                  if d in propios for n in suyos)


def _vhost_correo(host):
    ruta = f"{SITIOS}/{host}"
    if not os.path.exists(ruta):
        raise ErrorConfiguracion(f"no se encontró el sitio del webmail ({ruta})")
    return ruta


def _snippet(host, extra):
    """Los mail.<dominio> extra se sirven con el mismo webmail (snippet incluido tras server_name).
    Devuelve True si cambió algo."""
    texto = "# Generado por el panel (Certificado del correo).\n" + (f"server_name {' '.join(extra)};\n" if extra else "")
    try:
        with open(NOMBRES_NGINX) as f:
            cambiado = f.read() != texto
    except OSError:
        cambiado = True
    if cambiado:
        escribir(NOMBRES_NGINX, texto, 0o644)
    ruta = _vhost_correo(host)
    with open(ruta) as f:
        lineas = f.read().split("\n")
    incluir = f"    include {NOMBRES_NGINX};"
    salida, incluido = [], False
    for i, linea in enumerate(lineas):
        salida.append(linea)
        if linea.strip() == f"server_name {host};" and (i + 1 >= len(lineas) or lineas[i + 1].strip() != incluir.strip()):
            salida.append(incluir)
            incluido = True
    if incluido:
        _respaldar(ruta, "/etc/nginx/respaldos")
        with open(ruta, "w") as f:
            f.write("\n".join(salida))
    return cambiado or incluido


def _nombres_en_nginx(host, nombres):
    extra = [n for n in nombres if n.startswith("mail.") and n != host]
    _snippet(host, extra)
    ejecutar(["nginx", "-t"])
    ejecutar(["systemctl", "reload", "nginx"])


def _nombres_por_dominio(host, principal, activos):
    """«por-dominio»: el webmail del servidor atiende el mail.<dominio> de cada zona que todavía no tiene
    certificado propio (provisional, con el del servidor); los que ya lo tienen van en su propio bloque."""
    zonas = {z["zona"] for z in Z.listar()} | {principal}
    extra = sorted({f"mail.{z}" for z in zonas} - {host} - {f"mail.{d}" for d in activos})
    if _snippet(host, extra):
        ejecutar(["nginx", "-t"])
        ejecutar(["systemctl", "reload", "nginx"])


def _usar_en_servicios(host):
    cadena, llave = B.rutas(host)
    cambios = [(SNAKEOIL[0], cadena), (SNAKEOIL[1], llave)]
    for ruta in [_vhost_correo(host), f"/etc/nginx/sites-available/{host}-admin",
                 "/etc/nginx/sites-available/autodiscover-dominios",
                 "/etc/nginx/sites-available/panel-dominio"] + glob.glob("/etc/nginx/sites-available/mta-sts.*"):
        if os.path.exists(ruta) and ".bak" not in ruta:
            _reemplazar(ruta, cambios)
    ejecutar(["nginx", "-t"])
    actual = ejecutar(["postconf", "-h", "smtpd_tls_cert_file"]).strip()
    if actual != cadena:
        _respaldar("/etc/postfix/main.cf")
        ejecutar(["postconf", "-e", f"smtpd_tls_cert_file={cadena}", f"smtpd_tls_key_file={llave}"])
    for ruta in ("/etc/dovecot/dovecot.conf", "/etc/dovecot/conf.d/10-ssl.conf"):
        if os.path.exists(ruta):
            _reemplazar(ruta, [(f"= {DOVECOT_PROPIO[0]}", f"= {cadena}"), (f"= {DOVECOT_PROPIO[1]}", f"= {llave}"),
                               (f"= {SNAKEOIL[0]}", f"= {cadena}"), (f"= {SNAKEOIL[1]}", f"= {llave}")])
    ejecutar(["doveconf", "-n"])
    if os.path.exists("/etc/vsftpd.conf"):
        _reemplazar("/etc/vsftpd.conf", [(f"rsa_cert_file={SNAKEOIL[0]}", f"rsa_cert_file={cadena}"),
                                          (f"rsa_private_key_file={SNAKEOIL[1]}", f"rsa_private_key_file={llave}")])
    os.makedirs(os.path.dirname(GANCHO), exist_ok=True)
    escribir(GANCHO, "#!/bin/sh\n# Generado por el panel: recarga los servicios que usan el certificado del correo.\n"
             "systemctl reload nginx postfix dovecot 2>/dev/null\nsystemctl restart vsftpd 2>/dev/null || true\n", 0o755)
    subprocess.run(["sh", GANCHO], capture_output=True, timeout=120)


def _emitir_servidor(host, principal, ip, modo):
    candidatos = _candidatos_servidor(host, principal, modo)
    incluidos = [n for n in candidatos if B.apunta(n, ip)]
    omitidos = [n for n in candidatos if n not in incluidos]
    if host not in incluidos:
        raise ErrorDns(f"{host} todavía no apunta a {ip} desde Internet: espere a que propague el DNS")
    if modo == "compartido":
        _nombres_en_nginx(host, incluidos)
    else:
        _nombres_por_dominio(host, principal, D.activos(host, principal))
    try:
        # Siempre con --reuse-key --key-type ecdsa (certificado_base.pedir): la clave del servidor no cambia.
        B.pedir(host, incluidos, f"postmaster@{principal}")
    except ErrorDns as e:
        E.fallo(host, e)
        raise
    E.exito(host)
    _usar_en_servicios(host)
    return incluidos, omitidos


def _pasada_por_dominio(host, principal, ip, forzar=False):
    """Certificados de los dominios de cliente y su instalación por SNI. Nunca lanza por un dominio."""
    dominios = D.pasada(host, principal, ip, forzar=forzar)
    activos = D.activos(host, principal)
    errores = []
    try:
        _nombres_por_dominio(host, principal, activos)
    except ErrorDns as e:
        errores.append(f"nginx (nombres del webmail): {e}")
    sni = S.instalar(host, activos)
    sni["errores"] = errores + sni["errores"]
    return dominios, sni


def emitir():
    """Botón del panel: emite o amplía el certificado del servidor (y, en «por-dominio», los de los
    clientes, sin esperar a los reintentos)."""
    host, principal = _principal()
    modo = B.modo()
    ip = servidor()["ip_correo"]
    incluidos, omitidos = _emitir_servidor(host, principal, ip, modo)
    salida = {"incluidos": incluidos, "omitidos": omitidos}
    if modo == "por-dominio":
        dominios, sni = _pasada_por_dominio(host, principal, ip, forzar=True)
        salida.update(pasada=dominios, sni=sni)
        E.anotar_aviso("; ".join(sni["errores"]))
    return dict(estado(), **salida)


def estado():
    host, principal = _principal()
    cert = B.leer_certificado(host)
    if not cert:
        salida = {"emitido": False, "linaje": host}
    else:
        salida = {"emitido": True, "linaje": host, "nombres": cert["nombres"], "vence": cert["vence"],
                  "en_uso": ejecutar(["postconf", "-h", "smtpd_tls_cert_file"]).strip().startswith("/etc/letsencrypt/")}
    try:
        salida["modo"] = B.modo()
    except ErrorConfiguracion as e:
        salida.update(modo="compartido", aviso=str(e))
    if salida["modo"] == "por-dominio":
        salida["dominios"] = D.estado(host, principal)
    previo = E.de_linaje(host)
    if previo.get("fallos"):
        salida.update(error=previo.get("error", ""), espera=E.espera(host))
    aviso = E.aviso()
    if aviso and "aviso" not in salida:
        salida["aviso"] = aviso["texto"]
    return salida


def _automatico_servidor(host, principal, ip, modo):
    apuntan = [n for n in _candidatos_servidor(host, principal, modo) if B.apunta(n, ip)]
    if host not in apuntan:
        return {"accion": "nada", "motivo": f"{host} todavía no apunta a {ip} desde Internet"}
    cubiertos = set((B.leer_certificado(host) or {}).get("nombres") or [])
    nuevos = [n for n in apuntan if n not in cubiertos]
    sobrantes = _sobrantes(host, principal) if modo == "por-dominio" else []
    if not nuevos and not sobrantes:
        return {"accion": "nada", "motivo": "el certificado ya cubre todos los nombres que apuntan aquí"}
    falta = E.espera(host)
    if falta:
        return {"accion": "en-espera", "motivo": f"el último intento falló ({E.de_linaje(host).get('error', '')}); "
                f"se reintenta en {max(1, falta // 60)} min"}
    incluidos, omitidos = _emitir_servidor(host, principal, ip, modo)
    return dict(estado(), accion="emitido", nuevos=nuevos, retirados=sobrantes, incluidos=incluidos, omitidos=omitidos)


def automatico():
    """Lo lanza el temporizador (cada 30 min): si algún nombre de correo ya apunta a este servidor desde
    Internet y su certificado no lo cubre, lo emite o lo amplía. Así un servidor recién conectado, o un
    dominio nuevo del panel, queda con HTTPS y autoconfiguración sin pulsar nada.

    Solo pide a Let's Encrypt nombres que ya resuelven aquí (los fallidos cuentan para su límite), y lo
    que falla espera cada vez más antes de reintentarse. Un error de configuración (nombre del servidor,
    CERTIFICADO_MODO, sitio del webmail que falta…) no se arregla reintentando: se responde como aviso,
    sin código de error, para que el temporizador no quede «failed» cada media hora; el panel lo muestra
    en «Certificado del correo»."""
    try:
        return _automatico()
    except ErrorConfiguracion as e:
        E.anotar_aviso(str(e))
        return {"accion": "aviso", "motivo": str(e)}


def _ip_publica(ip):
    return ipaddress.ip_address(ip).is_global


def _automatico():
    try:
        ip = servidor()["ip_correo"]
    except ErrorDns:
        return {"accion": "nada", "motivo": "sin IP del servidor (Zonas DNS → Ajustes)"}
    if not _ip_publica(ip):
        return {"accion": "nada", "motivo": f"la IP del correo ({ip}) no es pública todavía"}
    host, principal = _principal()
    modo = B.modo()
    fallo = None
    try:
        resultado = _automatico_servidor(host, principal, ip, modo)
    except ErrorConfiguracion:
        raise
    except ErrorDns as e:
        if modo == "compartido":
            raise
        fallo, resultado = e, {"accion": "error", "motivo": str(e)}
    avisos = []
    if modo == "por-dominio":
        dominios, sni = _pasada_por_dominio(host, principal, ip)
        resultado = dict(resultado, dominios=dominios, sni=sni)
        avisos = sni["errores"]
    E.anotar_aviso("; ".join(avisos))
    if fallo:
        raise fallo  # el certificado del servidor falló: código de error esta vez (después, en espera)
    return resultado
