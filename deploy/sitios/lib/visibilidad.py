"""Visibilidad de cada sitio en buscadores y asistentes de IA (sección «Buscadores» del panel).

- IndexNow (Bing, Yandex, Seznam, Naver…): cada sitio tiene su clave en un archivo de la raíz
  (<clave>.txt, como pide el protocolo); al avisar se mandan la portada y las direcciones del mapa del
  sitio a api.indexnow.org. WordPress además avisa solo cada vez que se publica algo (complemento
  obligatorio visibilidad-sitio.php).
- Google no admite avisos: se verifica la propiedad en Search Console (registro TXT en la zona DNS,
  lo pone el panel) y allí se envía el mapa del sitio.
- revisar(): comprueba, pidiendo las direcciones al propio nginx como lo haría un buscador, que el
  sitio responde, que robots.txt no bloquea, que hay mapa del sitio, llms.txt y datos estructurados.
"""

import json
import os
import re
import secrets
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from comun import ErrorSitio, guardar_meta, leer_meta

INDEXNOW = "https://api.indexnow.org/indexnow"
AGENTE = "Mozilla/5.0 (compatible; revision-visibilidad/1.0)"


def _url(meta):
    return ("https://" if meta.get("ssl") else "http://") + meta["dominio"]


def clave_indexnow(meta):
    """Clave IndexNow del sitio (32 hex) y su archivo de verificación en la raíz pública."""
    import pwd

    clave = meta.get("indexnow")
    if not clave or not re.match(r"^[0-9a-f]{32}$", clave):
        clave = secrets.token_hex(16)
        meta["indexnow"] = clave
        guardar_meta(meta)
    ruta = os.path.join(meta["publico"], f"{clave}.txt")
    if not os.path.exists(ruta):
        with open(ruta, "w") as f:
            f.write(clave)
        pw = pwd.getpwnam(meta["usuario"])
        os.chown(ruta, pw.pw_uid, pwd.getpwnam("www-data").pw_gid)
        os.chmod(ruta, 0o640)
    return clave


def _local(meta, ruta):
    """Pide una dirección al nginx local como la vería un buscador (curl --resolve: mismo nombre,
    mismo certificado y mismas redirecciones que desde Internet, pero contra este servidor)."""
    import subprocess

    esquema, puerto = ("https", 443) if meta.get("ssl") else ("http", 80)
    r = subprocess.run(
        ["curl", "-s", "-L", "--max-redirs", "3", "--max-time", "15", "--max-filesize", "2000000",
         "--resolve", f"{meta['dominio']}:{puerto}:127.0.0.1", "-A", AGENTE,
         "-w", "\n%{http_code}", f"{esquema}://{meta['dominio']}{ruta}"],
        capture_output=True, text=True, timeout=30)
    cuerpo, _, codigo = r.stdout.rpartition("\n")
    return (int(codigo) if codigo.isdigit() else 0), cuerpo


def _urls_del_mapa(meta, limite=200):
    """Direcciones del mapa del sitio (sitemap.xml o el índice de WordPress wp-sitemap.xml)."""
    urls = []
    for ruta in ("/sitemap.xml", "/wp-sitemap.xml"):
        estado, texto = _local(meta, ruta)
        if estado != 200 or not texto.strip().startswith("<?xml"):
            continue
        try:
            raiz = ET.fromstring(texto.encode())
        except ET.ParseError:
            continue
        locs = [e.text.strip() for e in raiz.iter() if e.tag.endswith("loc") and e.text]
        if raiz.tag.endswith("sitemapindex"):
            for sub in locs[:10]:
                ruta_sub = re.sub(r"^https?://[^/]+", "", sub)
                e2, t2 = _local(meta, ruta_sub)
                if e2 == 200:
                    try:
                        urls += [x.text.strip() for x in ET.fromstring(t2.encode()).iter() if x.tag.endswith("loc") and x.text]
                    except ET.ParseError:
                        pass
        else:
            urls += locs
        break
    return [u for u in dict.fromkeys(urls) if u.startswith(("http://", "https://"))][:limite]


def revisar(dominio):
    meta = leer_meta(dominio)
    pruebas = []

    def anotar(titulo, ok, detalle=""):
        pruebas.append({"titulo": titulo, "ok": bool(ok), "detalle": detalle})

    estado, portada = _local(meta, "/")
    anotar("La portada responde", estado == 200, f"HTTP {estado}")
    estado, robots = _local(meta, "/robots.txt")
    bloquea = bool(re.search(r"(?im)^\s*user-agent:\s*\*\s*$(?:\n(?!\s*user-agent).*)*?\n\s*disallow:\s*/\s*$", robots))
    anotar("robots.txt deja pasar a buscadores e IA", estado == 200 and not bloquea,
           "bloquea todo el sitio (Disallow: /)" if bloquea else f"HTTP {estado}")
    urls = _urls_del_mapa(meta)
    anotar("Mapa del sitio (sitemap)", bool(urls), f"{len(urls)} direcciones")
    estado, _ = _local(meta, "/llms.txt")
    anotar("llms.txt (descripción para asistentes de IA)", estado == 200, f"HTTP {estado}")
    anotar("Datos estructurados schema.org (Organization)", '"@type": "Organization"' in portada or '"@type":"Organization"' in portada)
    anotar("Descripción para buscadores (meta description)", re.search(r'<meta[^>]+name="description"[^>]+content="[^"]{20,}', portada) is not None)
    noindex = re.search(r'<meta[^>]+name="robots"[^>]+noindex', portada) is not None
    anotar("La portada no pide «no indexar»", not noindex, "tiene noindex" if noindex else "")
    anotar("HTTPS activo", meta.get("ssl"), "" if meta.get("ssl") else "los buscadores prefieren sitios con HTTPS")
    return {"dominio": dominio, "pruebas": pruebas, "indexnow": bool(meta.get("indexnow")),
            "ultimo_aviso": meta.get("ultimo_aviso")}


def avisar(dominio):
    """Avisa por IndexNow de la portada y las direcciones del mapa del sitio."""
    import time

    meta = leer_meta(dominio)
    clave = clave_indexnow(meta)
    base = _url(meta)
    urls = [base + "/"] + [u for u in _urls_del_mapa(meta) if u.rstrip("/") != base]
    cuerpo = json.dumps({"host": dominio, "key": clave, "keyLocation": f"{base}/{clave}.txt", "urlList": urls[:1000]}).encode()
    pet = urllib.request.Request(INDEXNOW, data=cuerpo, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(pet, timeout=30) as r:
            codigo = r.status
    except urllib.error.HTTPError as e:
        codigo = e.code
    except Exception as e:
        raise ErrorSitio(f"no se pudo contactar a IndexNow: {type(e).__name__}")
    # 200/202: recibido. 403: la clave no se pudo comprobar (el sitio aún no es visible desde Internet).
    significado = {200: "recibido", 202: "recibido (validación pendiente)", 400: "petición no válida",
                   403: "la clave no se pudo comprobar: el sitio debe ser visible desde Internet",
                   422: "las direcciones no corresponden al sitio", 429: "demasiados avisos; reintente más tarde"}
    meta = leer_meta(dominio)
    meta["ultimo_aviso"] = {"fecha": time.strftime("%Y-%m-%d %H:%M"), "codigo": codigo, "urls": len(urls)}
    guardar_meta(meta)
    if codigo not in (200, 202):
        raise ErrorSitio(f"IndexNow respondió {codigo}: {significado.get(codigo, 'error')}")
    return {"dominio": dominio, "avisadas": len(urls), "resultado": significado[codigo]}


def identidad_en_app(meta, identidad):
    """Sitio con WordPress o Joomla: llms.txt con la identidad y, en WordPress, los datos que usa
    visibilidad-sitio.php para schema.org. No toca el contenido ni el título del sitio."""
    import pwd

    import pagina_inicio

    nombre = identidad.get("nombre") or meta.get("nombre") or meta["dominio"]
    llms = pagina_inicio.archivos(meta["dominio"], nombre, meta.get("www", True), identidad)["llms.txt"]
    llms = llms.replace("Sitio en construcción.\n\n", "")
    ruta = os.path.join(meta["publico"], "llms.txt")
    with open(ruta, "w") as f:
        f.write(llms)
    pw = pwd.getpwnam(meta["usuario"])
    os.chown(ruta, pw.pw_uid, pwd.getpwnam("www-data").pw_gid)
    os.chmod(ruta, 0o640)
    if meta.get("app") == "wordpress":
        import aplicaciones

        datos = {k: identidad[k] for k in ("nombre", "descripcion", "correo", "telefono", "redes") if identidad.get(k)}
        aplicaciones._wp(meta, "option", "update", "identidad_institucion", json.dumps(datos, ensure_ascii=False))
        # El lema solo se cambia si sigue vacío o es el que puso el panel al instalar.
        lema = aplicaciones._wp(meta, "option", "get", "blogdescription").strip()
        if identidad.get("descripcion") and (not lema or lema.startswith("Sitio web de ")):
            aplicaciones._wp(meta, "option", "update", "blogdescription", identidad["descripcion"][:300])
    return {"dominio": meta["dominio"], "actualizada": True, "app": meta.get("app")}
