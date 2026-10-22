"""Las dos órdenes SIN sesión del portal (v1.11): el gancho de git y la actualización del DNS dinámico.

Las llama alguien de fuera (el servidor de git al recibir un push, el router de la oficina), así que no hay
ficha de sesión: cada una trae su propia prueba, que se comprueba aquí, en root, con secretos que el portal no
tiene ni puede leer:

- «gancho-git»: el cuerpo (lo deja el portal en su carpeta de subidas) firmado con el secreto del gancho del
  sitio: X-Hub-Signature-256 (GitHub, Forgejo, Gitea), X-Gitea-Signature / X-Gogs-Signature (HMAC-SHA256 en
  hexadecimal) o X-Gitlab-Token (el secreto tal cual). Solo un push a la rama configurada despliega.
- «ddns-actualizar»: usuario y contraseña de una ficha del DNS dinámico (ddns.py), para su nombre y nada más.

Lo que no cuadra responde siempre igual (no se dice si el sitio, la ficha o el gancho existen) y nginx limita
además las peticiones por dirección IP.
"""

import hashlib
import hmac
import ipaddress
import json
import os
import re
import time

import alcance
import ayudantes
import ddns
import rutas
import subidas
from errores import ErrorPortal

NO_VALE = "Firma no válida o gancho sin activar"
RE_HEX = re.compile(r"[0-9a-f]{64}")
RE_USUARIO = re.compile(r"ddns-[0-9a-f]{8}")
EVENTOS_PUSH = ("push", "push hook")
VENTANA_DDNS = 600
MAX_DDNS = 10  # actualizaciones por ficha cada 10 minutos (las que no cambian nada también cuentan)


def _leer_json(ruta):
    try:
        with open(ruta) as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


# --- Gancho de git ---


def _firma_correcta(secreto, cuerpo, args):
    calculada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    firma = str(args.get("firma") or "").strip().lower()
    if firma.startswith("sha256="):
        firma = firma[7:]
    if RE_HEX.fullmatch(firma):
        return hmac.compare_digest(calculada, firma)
    ficha = args.get("ficha_gitlab")
    if isinstance(ficha, str) and 0 < len(ficha) <= 200:
        return hmac.compare_digest(ficha.encode(), secreto.encode())
    return False


def gancho_git(peticion):
    args = peticion.get("args") or {}
    try:
        cuerpo = subidas.leer(args.get("subida"), "gancho")
    except ErrorPortal as e:
        raise ErrorPortal(e.codigo if e.codigo == 413 else 403, NO_VALE)
    try:
        sitio = alcance.nombre_valido(peticion.get("dominio"))
    except ErrorPortal:
        raise ErrorPortal(403, NO_VALE)
    meta = _leer_json(os.path.join(rutas.META_SITIOS, f"{sitio}.json")) if alcance.RE_DOMINIO.fullmatch(sitio) else {}
    git = meta.get("git_php") if isinstance(meta.get("git_php"), dict) else {}
    secreto = _leer_json(os.path.join(rutas.GANCHOS, f"{sitio}.json")).get("secreto")
    if not git.get("gancho") or not isinstance(secreto, str) or len(secreto) < 20 or not _firma_correcta(secreto, cuerpo, args):
        raise ErrorPortal(403, NO_VALE)
    evento = str(args.get("evento") or "").strip().lower()
    if evento == "ping":
        return {"http": 200, "estado": "listo",
                "detalle": "Gancho comprobado: desplegará con cada push a " + str(git.get("rama"))}
    if evento and evento not in EVENTOS_PUSH:
        return {"http": 202, "estado": "ignorado", "detalle": "Solo los push despliegan"}
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ErrorPortal(400, "El gancho debe enviar JSON (tipo de contenido application/json)")
    rama = git.get("rama")
    if not isinstance(datos, dict) or datos.get("ref") != f"refs/heads/{rama}":
        return {"http": 202, "estado": "ignorado", "detalle": f"No es un push a la rama {rama}"}
    try:
        ayudantes.ejecutar("maquita-sitios", ["git-desplegar", sitio, "gancho"], tiempo=60)
    except ErrorPortal as e:
        if e.codigo == 400:  # en curso o demasiado seguido
            return {"http": 409, "estado": "ocupado", "detalle": e.texto}
        raise
    ayudantes.registro().info("MAQUITA_SITIOS_PORTAL gancho git dominio=%s commit=%s", sitio,
                              str(datos.get("after") or "")[:40])
    return {"http": 202, "estado": "en curso", "detalle": "Despliegue iniciado"}


# --- DNS dinámico (protocolo dyndns2) ---


def _respuesta(texto):
    """La respuesta de dyndns2 (good, nochg, badauth, notfqdn, nohost, abuse, dnserr): el portal la envía tal cual."""
    return {"respuesta": texto}


def _ip(args):
    valor = args.get("myip") or args.get("ip_cliente")
    try:
        ip = ipaddress.ip_address(str(valor or "").strip())
    except ValueError:
        return None
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return None
    return ip


def ddns_actualizar(peticion):
    args = peticion.get("args") or {}
    usuario, clave = args.get("usuario"), args.get("clave")
    if not (isinstance(usuario, str) and RE_USUARIO.fullmatch(usuario) and isinstance(clave, str) and 0 < len(clave) <= 200):
        return _respuesta("badauth")
    hostname = args.get("hostname")
    nombres = [h.strip().lower().rstrip(".") for h in hostname.split(",")] if isinstance(hostname, str) else []
    if not nombres or len(nombres) > 5 or not all(alcance.RE_NOMBRE.fullmatch(h) for h in nombres):
        return _respuesta("notfqdn")
    ip = _ip(args)
    with ddns.cerrojo():
        fichas = ddns.cargar()
        ficha = ddns.por_usuario(fichas, usuario)
        if not ddns.clave_correcta(ficha, clave):
            ayudantes.registro().warning("MAQUITA_SITIOS_PORTAL ddns rechazado usuario=%s motivo=clave", usuario)
            return _respuesta("badauth")
        completo = f"{ficha['nombre']}.{ficha['zona']}"
        if any(h != completo for h in nombres):
            return _respuesta("nohost")
        ahora = int(time.time())
        recientes = [t for t in ficha.get("peticiones") or [] if isinstance(t, int) and t > ahora - VENTANA_DDNS]
        if len(recientes) >= MAX_DDNS:
            ficha["peticiones"] = recientes
            ddns.guardar(fichas)
            return _respuesta("abuse")
        ficha["peticiones"] = recientes + [ahora]
        if ip is None:
            ddns.guardar(fichas)
            return _respuesta("dnserr")
        campo = "ip4" if ip.version == 4 else "ip6"
        if ficha.get(campo) == str(ip):
            ddns.guardar(fichas)
            return _respuesta(f"nochg {ip}")
        try:
            _poner(ficha, ip)
        except ErrorPortal as e:
            ddns.guardar(fichas)
            ayudantes.registro().warning("MAQUITA_SITIOS_PORTAL ddns fallo zona=%s nombre=%s: %s", ficha["zona"],
                                         ficha["nombre"], e.texto[:200])
            return _respuesta("dnserr")
        ficha[campo] = str(ip)
        ficha["actualizado"] = time.strftime("%Y-%m-%d %H:%M:%S")
        ddns.guardar(fichas)
    ayudantes.registro().info("MAQUITA_SITIOS_PORTAL ddns ok zona=%s nombre=%s", ficha["zona"], ficha["nombre"])
    return _respuesta(f"good {ip}")


def _poner(ficha, ip):
    """Cambia (o crea) el registro A/AAAA del nombre en su zona, con TTL corto."""
    import ordenes_dns

    zona, tipo = ficha["zona"], "A" if ip.version == 4 else "AAAA"
    registro = {"nombre": ficha["nombre"], "tipo": tipo, "valor": str(ip), "ttl": 60}
    actual = next((r for r in ordenes_dns.dns("ver", zona).get("registros", [])
                   if r.get("tipo") == tipo and r.get("nombre") == ficha["nombre"] and not r.get("sistema")), None)
    texto = ordenes_dns._b64(registro)
    if actual and re.fullmatch(r"[0-9a-f]{8}", str(actual.get("id"))):
        ordenes_dns.dns("modificar", zona, actual["id"], texto)
    else:
        ordenes_dns.dns("agregar", zona, texto)


ORDENES = {"gancho-git": gancho_git, "ddns-actualizar": ddns_actualizar}


def atender(peticion):
    if not isinstance(peticion.get("args") or {}, dict):
        raise ErrorPortal(400, "Petición no válida")
    return {"ok": True, "datos": ORDENES[peticion["orden"]](peticion)}
