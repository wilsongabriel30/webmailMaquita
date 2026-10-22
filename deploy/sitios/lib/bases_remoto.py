"""Acceso remoto a las bases de un sitio: solo desde las IP o redes elegidas, solo con TLS.

- MariaDB: cada origen es una cuenta más del usuario ('u'@'192.0.2.10' o 'u'@'192.0.2.0/255.255.255.0') con la
  misma clave (se copia su hash, no se conoce la clave), los mismos permisos y REQUIRE SSL.
- PostgreSQL: una línea «hostssl <base> <usuario> <red> scram-sha-256» por origen en ARCHIVO_HBA, que incluye el
  pg_hba.conf del servidor (lo prepara el ajuste 72). Antes de recargar se comprueba con pg_hba_file_rules.
- Cortafuegos del proyecto: /etc/maquita-cortafuegos/bases.d/<dominio>.json con el puerto de cada motor y sus
  orígenes; maquita-cortafuegos solo abre el puerto para esas IP.

El servidor tiene que estar preparado (TLS con el certificado del servidor y escucha en la red): lo hace el ajuste
72 y lo deja escrito en ESTADO_SERVIDOR. Sin eso, aquí no se abre nada.

Nunca se abre a todo Internet: /0 jamás; en IPv4 una red más amplia que /16 (y en IPv6 que /48) solo con la
confirmación del superadministrador (argumento «amplia», que el portal no puede enviar), y nunca más amplia que /8
(o /32 en IPv6).
"""

import ipaddress
import json
import os
import subprocess

from comun import ErrorSitio, todos_los_meta

ESTADO_SERVIDOR = "/etc/maquita-sitios/bases-remoto.json"
ARCHIVO_HBA = "/etc/postgresql/maquita-bases-remoto.conf"
CORTAFUEGOS_BASES = "/etc/maquita-cortafuegos/bases.d"
CORTAFUEGOS = "/usr/local/sbin/maquita-cortafuegos"
MAXIMO = 20
PUERTOS = {"mariadb": 3306, "postgresql": 5432}
# (sin confirmación, con confirmación del superadministrador): prefijo mínimo admitido.
LIMITES = {4: (16, 8), 6: (48, 32)}


def red(valor, amplia=False):
    """Una IP o red normalizada («192.0.2.0/24»), o ErrorSitio con el motivo."""
    if not isinstance(valor, str) or not 2 <= len(valor.strip()) <= 50:
        raise ErrorSitio("IP o red no válida")
    try:
        r = ipaddress.ip_network(valor.strip(), strict=False)
    except ValueError:
        raise ErrorSitio(f"IP o red no válida: {valor[:50]}")
    if r.prefixlen == 0:
        raise ErrorSitio("nunca se abre una base a todo Internet (/0)")
    normal, extremo = LIMITES[r.version]
    if r.prefixlen < extremo:
        raise ErrorSitio(f"red demasiado amplia: {r} (como mucho /{extremo})")
    if r.prefixlen < normal and not amplia:
        raise ErrorSitio(f"red demasiado amplia: {r}. Usa una red de /{normal} o menor; una más amplia solo la "
                         "puede autorizar el administrador general")
    if r.is_loopback or r.is_multicast or r.is_unspecified or r.is_link_local:
        raise ErrorSitio(f"{r} no es un origen válido para el acceso remoto")
    return str(r)


def redes(lista, amplia=False):
    if not isinstance(lista, list) or len(lista) > MAXIMO:
        raise ErrorSitio(f"se admiten hasta {MAXIMO} IP o redes por usuario")
    salida = []
    for valor in lista:
        normal = red(valor, amplia)
        if normal not in salida:
            salida.append(normal)
    return salida


def host_mariadb(texto):
    """'192.0.2.10' o '192.0.2.0/255.255.255.0'. MariaDB no admite máscaras en IPv6: ahí solo direcciones sueltas."""
    r = ipaddress.ip_network(texto)
    if r.num_addresses == 1:
        return str(r.network_address)
    if r.version == 6:
        raise ErrorSitio(f"MariaDB solo admite direcciones IPv6 sueltas, no redes ({texto})")
    return f"{r.network_address}/{r.netmask}"


# --- Servidor preparado ---


def servidor():
    """{"mariadb": {...}, "postgresql": {...}, "host": nombre del certificado} según el ajuste 72."""
    try:
        with open(ESTADO_SERVIDOR) as f:
            datos = json.load(f)
    except (OSError, ValueError):
        datos = {}
    salida = {"host": datos.get("host") if isinstance(datos.get("host"), str) else None}
    for motor, puerto in PUERTOS.items():
        d = datos.get(motor) if isinstance(datos.get(motor), dict) else {}
        salida[motor] = {"activo": d.get("activo") is True, "puerto": puerto}
    return salida


def exigir_servidor(motor):
    if not servidor()[motor]["activo"]:
        nombre = "MariaDB" if motor == "mariadb" else "PostgreSQL"
        raise ErrorSitio(f"el acceso remoto a {nombre} no está preparado en este servidor (TLS y escucha en la red): "
                         "pídeselo al administrador general (ajuste 72)")


# --- PostgreSQL: pg_hba ---


def lineas_hba(metas=None):
    """Las líneas hostssl de todos los usuarios con acceso remoto de todos los sitios."""
    import bases_privilegios as bp

    lineas = ["# Generado por maquita-sitios (acceso remoto a bases). No editar a mano."]
    for meta in metas if metas is not None else todos_los_meta():
        for u in meta.get("bases_usuarios") or []:
            if u.get("motor") != "postgresql":
                continue
            for origen in u.get("remoto") or []:
                origen = str(ipaddress.ip_network(origen))  # lo guardado ya se validó; se normaliza otra vez
                lineas.append(f"hostssl {bp.ident(u['base'])} {bp.ident(u['usuario'])} {origen} scram-sha-256")
    return "\n".join(lineas) + "\n"


def publicar_hba():
    """Escribe ARCHIVO_HBA, comprueba que PostgreSQL lo entiende y recarga; si no, deja el anterior."""
    from bases import _pg, _pg_valor

    anterior = None
    if os.path.exists(ARCHIVO_HBA):
        with open(ARCHIVO_HBA) as f:
            anterior = f.read()
    _escribir(ARCHIVO_HBA, lineas_hba(), dueno="postgres", modo=0o640)
    errores = _pg_valor("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL;")
    if errores.strip() not in ("", "0"):
        if anterior is None:
            os.remove(ARCHIVO_HBA)
        else:
            _escribir(ARCHIVO_HBA, anterior, dueno="postgres", modo=0o640)
        raise ErrorSitio("PostgreSQL no aceptó las reglas de acceso remoto; se dejaron las anteriores")
    _pg("SELECT pg_reload_conf();")


def _escribir(ruta, texto, dueno=None, modo=0o600):
    os.makedirs(os.path.dirname(ruta), mode=0o755, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, modo), "w") as f:
        f.write(texto)
    if dueno:
        import pwd

        try:
            cuenta = pwd.getpwnam(dueno)
            os.chown(tmp, cuenta.pw_uid, cuenta.pw_gid)
        except KeyError:
            pass
    os.chmod(tmp, modo)
    os.replace(tmp, ruta)


# --- Cortafuegos del proyecto ---


def reglas_cortafuegos(meta):
    """[{puerto, origenes}] del sitio: la unión de los orígenes de sus usuarios, por motor."""
    por_motor = {}
    for u in meta.get("bases_usuarios") or []:
        for origen in u.get("remoto") or []:
            lista = por_motor.setdefault(u["motor"], [])
            if origen not in lista:
                lista.append(origen)
    return [{"puerto": PUERTOS[m], "origenes": sorted(o)} for m, o in sorted(por_motor.items()) if o]


def publicar_cortafuegos(meta):
    """Deja el archivo del sitio para maquita-cortafuegos y le pide recargar. Devuelve cómo quedó."""
    ruta = os.path.join(CORTAFUEGOS_BASES, f"{meta['dominio']}.json")
    reglas = reglas_cortafuegos(meta)
    if reglas:
        _escribir(ruta, json.dumps({"dominio": meta["dominio"], "reglas": reglas}))
    elif os.path.exists(ruta):
        os.remove(ruta)
    else:
        return "sin cambios"
    if not os.path.exists(CORTAFUEGOS):
        return "sin cortafuegos propio: el puerto queda como lo tenga el sistema"
    r = subprocess.run([CORTAFUEGOS, "recargar"], capture_output=True, text=True, timeout=60)
    try:
        datos = json.loads(r.stdout)
    except ValueError:
        raise ErrorSitio("el cortafuegos no respondió al recargar sus reglas")
    if datos.get("error"):
        raise ErrorSitio(f"cortafuegos: {datos['error']}")
    return "aplicado" if datos.get("recargado") else "cortafuegos inactivo"
