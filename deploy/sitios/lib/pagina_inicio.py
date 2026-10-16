"""Página «en construcción» de un sitio nuevo, lista para buscadores y asistentes de IA.

Una sola página HTML sin recursos externos (menos de 10 KB: carga en ADSL rural o satélite), con el
nombre de la institución, datos estructurados schema.org (Organization), Open Graph, modo oscuro, y
los archivos que leen buscadores y asistentes: robots.txt, sitemap.xml y llms.txt.
"""

import html
import json
import time

_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nombre}</title>
<meta name="description" content="{descripcion}">
<link rel="canonical" href="{url}/">
<meta property="og:type" content="website">
<meta property="og:title" content="{nombre}">
<meta property="og:description" content="{descripcion}">
<meta property="og:url" content="{url}/">
<meta name="theme-color" content="{color}">{og_imagen}
<script type="application/ld+json">{jsonld}</script>
<style>
:root{{--fondo:#f4f1ea;--tinta:#1d2b2c;--suave:#5b6b6c;--acento:{color};--linea:#d9d3c4;--tarjeta:#fffdf8}}
@media (prefers-color-scheme:dark){{:root{{--fondo:#0e1516;--tinta:#e8ecea;--suave:#9fb0ae;--acento:#7cc4b8;--linea:#24302f;--tarjeta:#141d1e}}}}
*{{box-sizing:border-box;margin:0}}
html,body{{height:100%}}
body{{background:var(--fondo);color:var(--tinta);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,Ubuntu,sans-serif;
display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px 16px;
background-image:radial-gradient(circle at 15% 20%,rgba(15,61,62,.08),transparent 40%),radial-gradient(circle at 85% 80%,rgba(176,137,64,.10),transparent 45%)}}
main{{width:100%;max-width:640px;background:var(--tarjeta);border:1px solid var(--linea);border-radius:20px;padding:48px 36px;text-align:center;
box-shadow:0 20px 60px -30px rgba(0,0,0,.35)}}
.sello{{width:64px;height:64px;margin:0 auto 24px;border-radius:50%;display:grid;place-items:center;background:var(--acento);color:var(--tarjeta);
font:600 26px/1 Georgia,"Times New Roman",serif;letter-spacing:.5px}}
h1{{font:600 clamp(28px,6vw,40px)/1.15 Georgia,"Times New Roman",serif;letter-spacing:-.01em;margin-bottom:14px}}
.linea{{width:56px;height:3px;border-radius:3px;background:var(--acento);margin:20px auto}}
p{{color:var(--suave)}}
a{{color:var(--acento);text-decoration:none;border-bottom:1px solid currentColor}}
a:hover{{opacity:.8}}
.contacto{{margin-top:28px;font-size:15px}}
.logo{{display:block;max-width:180px;max-height:96px;margin:0 auto 24px;object-fit:contain}}
.redes{{margin-top:14px;font-size:14px;display:flex;gap:14px;justify-content:center;flex-wrap:wrap}}
footer{{margin-top:28px;font-size:13px;color:var(--suave)}}
@media (max-width:480px){{main{{padding:36px 22px}}}}
</style>
</head>
<body>
<main>
{sello}
<h1>{nombre}</h1>
<div class="linea"></div>
<p>{texto}</p>
<p class="contacto">{contacto}</p>{redes}
</main>
<footer>© {anio} {nombre}</footer>
</body>
</html>
"""


def _iniciales(nombre):
    palabras = [p for p in nombre.replace("-", " ").split() if p[:1].isalpha() and len(p) > 2]
    letras = "".join(p[0] for p in palabras[:2]).upper()
    return letras or nombre[:1].upper()


REDES = {"facebook": "Facebook", "instagram": "Instagram", "x": "X", "youtube": "YouTube", "linkedin": "LinkedIn",
         "tiktok": "TikTok"}


def _color(valor):
    v = (valor or "").strip()
    return v if len(v) == 7 and v.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in v[1:]) else "#0f3d3e"


def archivos(dominio, nombre, con_www=True, identidad=None, logo=None):
    """{nombre de archivo: contenido} para la carpeta pública de un sitio nuevo.

    identidad (opcional, desde Personalización del panel): descripcion, correo, telefono, web,
    color, redes {red: url}. logo: nombre del archivo de logo ya copiado en la carpeta pública.
    """
    ide = identidad or {}
    nombre = (nombre or ide.get("nombre") or dominio).strip()
    url = f"https://{dominio}"
    correo = (ide.get("correo") or f"info@{dominio}").strip()
    telefono = (ide.get("telefono") or "").strip()
    descripcion = (ide.get("descripcion") or "").strip() or f"Sitio web de {nombre}. Contacto: {correo}."
    redes = {k: v for k, v in (ide.get("redes") or {}).items() if k in REDES and str(v).startswith("https://")}
    org = {"@context": "https://schema.org", "@type": "Organization", "name": nombre, "url": url + "/",
           "email": correo, "description": descripcion}
    if telefono:
        org["telephone"] = telefono
    if logo:
        org["logo"] = f"{url}/{logo}"
    if redes:
        org["sameAs"] = list(redes.values())
    jsonld = json.dumps(org, ensure_ascii=False).replace("</", "<\\/")
    e = html.escape
    sello = (f'<img class="logo" src="/{e(logo)}" alt="{e(nombre)}">' if logo
             else f'<div class="sello" aria-hidden="true">{e(_iniciales(nombre))}</div>')
    contacto = f'Escríbanos a <a href="mailto:{e(correo)}">{e(correo)}</a>'
    if telefono:
        contacto += f' · <a href="tel:{e(telefono.replace(" ", ""))}">{e(telefono)}</a>'
    enlaces = "".join(f'<a href="{e(u)}" rel="me noopener">{REDES[k]}</a>' for k, u in redes.items())
    texto = e(ide["descripcion"]) if ide.get("descripcion") else "Estamos preparando nuestro sitio web. Muy pronto encontrará aquí toda nuestra información."
    pagina = _HTML.format(nombre=e(nombre), descripcion=e(descripcion), url=url, jsonld=jsonld,
                          sello=sello, texto=texto, contacto=contacto,
                          redes=f'\n<p class="redes">{enlaces}</p>' if enlaces else "",
                          color=_color(ide.get("color")),
                          og_imagen=f'\n<meta property="og:image" content="{url}/{e(logo)}">' if logo else "",
                          anio=time.strftime("%Y"))
    hoy = time.strftime("%Y-%m-%d")
    llms = [f"# {nombre}", "", f"> {descripcion}", "", "Sitio en construcción.", "", f"- Sitio: {url}/", f"- Correo: {correo}"]
    if telefono:
        llms.append(f"- Teléfono: {telefono}")
    llms += [f"- {REDES[k]}: {u}" for k, u in redes.items()]
    return {
        "index.html": pagina,
        "robots.txt": f"User-agent: *\nAllow: /\n\nSitemap: {url}/sitemap.xml\n",
        "sitemap.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{url}/</loc><lastmod>{hoy}</lastmod></url>\n</urlset>\n"
        ),
        "llms.txt": "\n".join(llms) + "\n",
    }
