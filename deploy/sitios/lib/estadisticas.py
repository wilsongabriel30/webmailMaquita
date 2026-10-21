"""Estadísticas de visitas y ancho de banda de cada sitio, con GoAccess (software libre, licencia MIT).

Cada noche (temporizador sitios-datos-noche, «maquita-sitios datos-noche») se leen los registros de acceso del
sitio, también los ya rotados por logrotate (acceso.log.1 y acceso.log.N.gz: no se mueven ni se truncan), y se
dejan en DATOS/<dominio>/:

  informe.html   el informe de GoAccess. No es público: está fuera de la web y el panel lo entrega autenticado.
  resumen.json   visitas (IP + navegador distintos), páginas, solicitudes y bytes por día de los últimos 30 días.

El resumen lo calcula este módulo (no depende de GoAccess), así que existe aunque GoAccess no esté instalado.
GoAccess corre con el usuario «nobody» sobre una copia en su entrada: no lee nada del sitio por sí mismo.
"""

import datetime
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import tempfile

from comun import ErrorSitio, leer_meta, todos_los_meta

DATOS = "/var/lib/maquita-sitios/estadisticas"
GOACCESS = "goaccess"
DIAS = 30
# Formato «combined» de nginx (access_log sin formato, como en plantillas.py).
RE_LINEA = re.compile(r'^(\S+) \S+ \S+ \[(\d{2})/(\w{3})/(\d{4}):[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) (\d+|-) "[^"]*" "([^"]*)"')
MESES = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
ESTATICOS = re.compile(r"\.(?:css|js|mjs|jpe?g|gif|png|webp|avif|svg|ico|woff2?|ttf|eot|map|txt|xml|json)$", re.I)
ROBOTS = re.compile(r"bot|crawl|spider|slurp|curl|wget|python-requests|monitor", re.I)


def _carpeta(dominio):
    return os.path.join(DATOS, dominio)


def registros_acceso(meta):
    """El actual y los rotados, del más antiguo al más nuevo. Sin enlaces (la carpeta es de root)."""
    base = os.path.join(meta["registros"], "acceso.log")
    rotados = []
    for ruta in glob.glob(base + ".*"):
        sufijo = ruta[len(base) + 1:]
        numero = sufijo[:-3] if sufijo.endswith(".gz") else sufijo
        if numero.isdigit() and not os.path.islink(ruta):
            rotados.append((int(numero), ruta))
    salida = [r for _, r in sorted(rotados, reverse=True)]
    if os.path.isfile(base) and not os.path.islink(base):
        salida.append(base)
    return salida


def _lineas(rutas):
    for ruta in rutas:
        abrir = gzip.open if ruta.endswith(".gz") else open
        try:
            with abrir(ruta, "rt", encoding="utf-8", errors="replace") as f:
                yield from f
        except (OSError, EOFError):
            continue


def resumen(lineas, hoy=None, dias=DIAS):
    """Por día: solicitudes, visitas, páginas y bytes. Las visitas no cuentan robots conocidos."""
    hoy = hoy or datetime.date.today()
    desde = hoy - datetime.timedelta(days=dias - 1)
    por_dia = {}
    for linea in lineas:
        m = RE_LINEA.match(linea)
        if not m:
            continue
        ip, d, mes, a, _metodo, url, codigo, bytes_, agente = m.groups()
        try:
            fecha = datetime.date(int(a), MESES[mes], int(d))
        except (KeyError, ValueError):
            continue
        if not desde <= fecha <= hoy:
            continue
        dia = por_dia.setdefault(fecha, {"solicitudes": 0, "paginas": 0, "bytes": 0, "_visitantes": set()})
        dia["solicitudes"] += 1
        dia["bytes"] += int(bytes_) if bytes_ != "-" else 0
        ruta = url.split("?", 1)[0]
        if int(codigo) < 400 and not ESTATICOS.search(ruta):
            dia["paginas"] += 1
        if not ROBOTS.search(agente):
            dia["_visitantes"].add((ip, agente))
    salida = []
    for i in range(dias):
        fecha = desde + datetime.timedelta(days=i)
        dia = por_dia.get(fecha)
        salida.append({"fecha": fecha.isoformat(), "visitas": len(dia["_visitantes"]) if dia else 0,
                       "paginas": dia["paginas"] if dia else 0, "solicitudes": dia["solicitudes"] if dia else 0,
                       "bytes": dia["bytes"] if dia else 0})
    totales = {k: sum(x[k] for x in salida) for k in ("visitas", "paginas", "solicitudes", "bytes")}
    return {"dias": salida, "totales": totales}


def _goaccess(rutas, destino, dominio):
    """Genera el informe HTML en `destino`. Devuelve False si GoAccess no está instalado."""
    binario = shutil.which(GOACCESS)
    if not binario:
        return False
    tmp = tempfile.mkdtemp(prefix="goaccess-")
    try:
        os.chmod(tmp, 0o700)
        como = []
        if os.geteuid() == 0:
            shutil.chown(tmp, "nobody")
            como = ["runuser", "-u", "nobody", "--"]
        salida = os.path.join(tmp, "informe.html")
        orden = como + [binario, "--no-global-config", "--log-format=COMBINED", "--html-report-title",
                        f"Estadísticas de {dominio}", "-o", salida, "-"]
        # Los errores a un archivo y no a una tubería: si se llenara mientras se escribe la entrada, se bloquearían.
        with tempfile.TemporaryFile() as errores, \
                subprocess.Popen(orden, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errores, cwd=tmp,
                                 env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "HOME": tmp}) as p:
            try:
                for linea in _lineas(rutas):
                    p.stdin.write(linea.encode("utf-8", "replace"))
                p.stdin.close()
            except BrokenPipeError:
                pass
            codigo = p.wait(timeout=1800)
            errores.seek(0)
            error = errores.read().decode(errors="replace").strip().splitlines()
            if codigo != 0 or not os.path.isfile(salida):
                raise ErrorSitio("GoAccess no pudo generar el informe" + (f": {error[-1][:200]}" if error else ""))
        shutil.copyfile(salida, destino)
        os.chmod(destino, 0o600)
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def generar(dominio, hoy=None):
    meta = leer_meta(dominio)
    carpeta = _carpeta(dominio)
    os.makedirs(carpeta, mode=0o700, exist_ok=True)
    rutas = registros_acceso(meta)
    datos = resumen(_lineas(rutas), hoy=hoy)
    datos["generado"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    tmp_html = os.path.join(carpeta, "informe.html.tmp")
    datos["informe"] = _goaccess(rutas, tmp_html, dominio) if rutas else False
    if datos["informe"]:
        os.replace(tmp_html, os.path.join(carpeta, "informe.html"))
    tmp = os.path.join(carpeta, "resumen.json.tmp")
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(carpeta, "resumen.json"))
    return ver(dominio)


def ver(dominio):
    leer_meta(dominio)
    carpeta = _carpeta(dominio)
    try:
        with open(os.path.join(carpeta, "resumen.json")) as f:
            datos = json.load(f)
    except (OSError, ValueError):
        datos = None
    return {"dominio": dominio, "goaccess": bool(shutil.which(GOACCESS)), "resumen": datos,
            "informe": os.path.isfile(os.path.join(carpeta, "informe.html"))}


def informe(dominio, subidas):
    """Copia el informe HTML a subidas/ para que el panel lo entregue (y lo borre)."""
    leer_meta(dominio)
    origen = os.path.join(_carpeta(dominio), "informe.html")
    if not os.path.isfile(origen):
        raise ErrorSitio("todavía no hay informe: se genera cada noche (o pulse «Generar ahora»)")
    nombre = os.urandom(16).hex() + ".descarga"
    with open(origen, "rb") as f, open(os.open(os.path.join(subidas, nombre), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640), "wb") as g:
        shutil.copyfileobj(f, g)
    return {"dominio": dominio, "archivo": nombre}


def todos(hoy=None):
    hechos, fallos = [], {}
    for meta in todos_los_meta():
        try:
            generar(meta["dominio"], hoy=hoy)
            hechos.append(meta["dominio"])
        except (ErrorSitio, OSError, subprocess.SubprocessError) as e:
            fallos[meta["dominio"]] = str(e)[:200]
    return {"estadisticas": hechos, "fallos": fallos}


def quitar(dominio):
    shutil.rmtree(_carpeta(dominio), ignore_errors=True)
