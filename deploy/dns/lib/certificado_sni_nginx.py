"""nginx con el certificado propio de cada dominio de cliente (SNI), para certificado_sni.py.

nginx elige el certificado por bloque «server», así que cada dominio con linaje propio tiene su archivo
generado, /etc/nginx/sites-available/correo-dominio-<dominio> (enlazado en sites-enabled), con copias de
los bloques que hoy lo atienden con el certificado del servidor:

- el webmail (bloque 443 de sites-available/<servidor>) para mail.<dominio> y webmail.<dominio>;
- el portal de dominio (bloque 8444 de sites-available/panel-dominio) para mail.<dominio>;
- la autoconfiguración (bloque 443 de sites-available/autodiscover-dominios) para autoconfig. y
  autodiscover.<dominio> (los nombres exactos ganan al comodín autodiscover.*).

Las copias se rehacen en cada pasada desde los archivos vivos: lo que cambie en ellos (una actualización,
otro ajuste) llega a los dominios en la pasada siguiente. Los originales no se tocan. MTA-STS ya tiene un
archivo por dominio (sites-available/mta-sts.<dominio>): ahí solo se cambian las rutas del certificado.
"""

import glob
import os
import re

import certificado_base as B

DISPONIBLES = "/etc/nginx/sites-available"
ACTIVOS = "/etc/nginx/sites-enabled"
PREFIJO = "correo-dominio-"
MARCA = "# Generado por maquita-dns (certificado por dominio)"
NOMBRES_NGINX = "/etc/nginx/snippets/correo-nombres.conf"
# Opciones de «listen» que solo pueden aparecer una vez por dirección y puerto: se quedan en el original.
LISTEN_UNICOS = re.compile(r"\s+(?:default_server|default|reuseport|deferred|bind|"
                           r"(?:backlog|ipv6only|fastopen|so_keepalive|rcvbuf|sndbuf|accept_filter|setfib)=[^\s;]+)(?=[\s;])")


def bloques_server(texto):
    """[(inicio, fin)] de cada bloque «server { … }» de primer nivel (sin contar llaves en comentarios o comillas)."""
    bloques, i, n, nivel, inicio, comillas = [], 0, len(texto), 0, None, None
    while i < n:
        c = texto[i]
        if comillas:
            if c == "\\":
                i += 2
                continue
            if c == comillas:
                comillas = None
        elif c == "#":
            fin = texto.find("\n", i)
            i = n if fin < 0 else fin
            continue
        elif c in "\"'":
            comillas = c
        elif c == "{":
            if nivel == 0:
                previo = texto[:i].rstrip()
                if re.search(r"(?:^|[\s;}])server$", previo):
                    inicio = len(previo) - len("server")
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel == 0 and inicio is not None:
                bloques.append((inicio, i + 1))
                inicio = None
        i += 1
    return bloques


def _nombres_de(bloque):
    m = re.search(r"^\s*server_name\s+([^;]+);", bloque, re.M)
    return m.group(1).split() if m else []


def elegir(texto, puerto, nombre):
    """El primer bloque que escucha en el puerto y tiene ese nombre en server_name (None: cualquiera)."""
    for inicio, fin in bloques_server(texto):
        b = texto[inicio:fin]
        if re.search(rf"^\s*listen\s+(?:\S+:)?{puerto}\b", b, re.M) and (nombre is None or nombre in _nombres_de(b)):
            return b
    return None


def adaptar(bloque, nombres, cadena, llave):
    """Copia del bloque con otros server_name y otro certificado, sin las opciones únicas de listen."""
    salida, puesto, con_certificado = [], False, False
    for linea in bloque.split("\n"):
        s = linea.strip()
        sangria = linea[: len(linea) - len(linea.lstrip())]
        if re.match(r"server_name\s", s):
            if not puesto:
                salida.append(f"{sangria}server_name {' '.join(nombres)};")
                puesto = True
            continue
        if s.startswith("include") and NOMBRES_NGINX in s:
            continue
        if re.match(r"ssl_certificate\s", s):
            linea, con_certificado = f"{sangria}ssl_certificate {cadena};", True
        elif re.match(r"ssl_certificate_key\s", s):
            linea = f"{sangria}ssl_certificate_key {llave};"
        elif re.match(r"listen\s", s):
            linea = LISTEN_UNICOS.sub("", linea)
        salida.append(linea)
    texto = "\n".join(salida)
    if not con_certificado:
        texto = texto.replace(f"server_name {' '.join(nombres)};",
                              f"server_name {' '.join(nombres)};\n    ssl_certificate {cadena};\n"
                              f"    ssl_certificate_key {llave};", 1)
    return texto


def _leer(ruta):
    try:
        with open(ruta) as f:
            return f.read()
    except OSError:
        return None


def contenido(host, dominio, nombres):
    """Texto del archivo generado para el dominio, o None si no hay ningún bloque que copiar."""
    cadena, llave = B.rutas(f"mail.{dominio}")
    fuentes = [
        (f"{DISPONIBLES}/{host}", 443, host, ("mail", "webmail")),
        (f"{DISPONIBLES}/panel-dominio", 8444, None, ("mail",)),
        (f"{DISPONIBLES}/autodiscover-dominios", 443, "autodiscover.*", ("autoconfig", "autodiscover")),
    ]
    partes = []
    for ruta, puerto, nombre, prefijos in fuentes:
        texto = _leer(ruta)
        if texto is None:
            continue
        bloque = elegir(texto, puerto, nombre)
        propios = [n for n in nombres if n.split(".", 1)[0] in prefijos]
        if bloque and propios:
            partes.append(f"# Copia del bloque {puerto} de {ruta}\n" + adaptar(bloque, propios, cadena, llave))
    if not partes:
        return None
    return (f"{MARCA}: no editar, se rehace en cada pasada del temporizador maquita-certificado-correo.\n"
            f"# Dominio {dominio}: certificado propio {cadena}\n\n" + "\n\n".join(partes) + "\n")


def _mta_sts(dominio, nombres):
    """(ruta, texto nuevo) del vhost MTA-STS del dominio con su propio certificado, si hace falta."""
    ruta = f"{DISPONIBLES}/mta-sts.{dominio}"
    texto = _leer(ruta)
    if texto is None or f"mta-sts.{dominio}" not in nombres:
        return None
    cadena, llave = B.rutas(f"mail.{dominio}")
    nuevo = re.sub(r"(?m)^(\s*ssl_certificate)\s+[^;]+;", rf"\1 {cadena};", texto)
    nuevo = re.sub(r"(?m)^(\s*ssl_certificate_key)\s+[^;]+;", rf"\1 {llave};", nuevo)
    return (ruta, nuevo) if nuevo != texto else None


def planificar(host, activos):
    """{ruta: texto o None (borrar)} de todo lo que debe cambiar en nginx para los dominios activos."""
    cambios = {}
    queda = set()
    for dominio, nombres in sorted(activos.items()):
        ruta = f"{DISPONIBLES}/{PREFIJO}{dominio}"
        texto = contenido(host, dominio, nombres)
        if texto is not None:
            queda.add(ruta)
            if _leer(ruta) != texto:
                cambios[ruta] = texto
        mta = _mta_sts(dominio, nombres)
        if mta:
            cambios[mta[0]] = mta[1]
    # Archivos generados de dominios que ya no están (zona borrada): se retiran. El linaje no se toca.
    for ruta in glob.glob(f"{DISPONIBLES}/{PREFIJO}*"):
        if ruta not in queda and ".bak" not in ruta and (_leer(ruta) or "").startswith(MARCA):
            cambios[ruta] = None
    return cambios


def enlace(ruta):
    return os.path.join(ACTIVOS, os.path.basename(ruta))
