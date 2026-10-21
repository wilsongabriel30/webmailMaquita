"""Prueba de punta a punta de «Mi sitio web» contra el servidor instalado (portal y sitios web).

Crea un administrador de dominio de prueba sobre <dominio>, crea dos subdominios, instala WordPress,
recorre las pestañas, prueba los límites (alcance, reservados, cuota, DNS protegido) y al final borra
todo. Se ejecuta como root en el servidor:

    panel-dominio/backend/venv/bin/python panel-dominio/pruebas/prueba_mi_sitio.py <dominio asignable>
"""
import io, json, os, secrets, ssl, subprocess, sys, time, urllib.error, urllib.request, zipfile

import bcrypt
import pyotp

DOM = sys.argv[1]
SITIO = "pruebav19." + DOM
VACIO = "pruebav19b." + DOM
BASE = "https://127.0.0.1:8444/api"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
USUARIO, CLAVE, SECRETO = "prueba-v19", "Aa1." + secrets.token_urlsafe(14), pyotp.random_base32()
fallos = []


def sql(q):
    return subprocess.run(["sudo", "-u", "postgres", "psql", "-X", "-qtA", "-d", "maildb", "-c", q],
                          capture_output=True, text=True, check=True).stdout.strip()


def http(metodo, ruta, cuerpo=None, ficha=None, crudo=None, tiempo=1300):
    cab = {"Content-Type": "application/json"} if crudo is None else {"Content-Type": "application/octet-stream"}
    if ficha:
        cab["Authorization"] = "Bearer " + ficha
    datos = crudo if crudo is not None else (json.dumps(cuerpo).encode() if cuerpo is not None else None)
    pet = urllib.request.Request(BASE + ruta, data=datos, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(pet, context=CTX, timeout=tiempo) as r:
            t = r.read()
            return r.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        t = e.read()
        try:
            return e.code, json.loads(t)
        except Exception:
            return e.code, {"crudo": t[:200].decode(errors="replace")}


def espero(nombre, obtenido, esperado, detalle=""):
    ok = obtenido == esperado
    print(("  bien  " if ok else "  FALLO ") + nombre + ("" if ok else f"  -> {obtenido!r} {detalle}"[:400]))
    if not ok:
        fallos.append(nombre)


def limpiar():
    for s in (SITIO, VACIO):
        subprocess.run(["/usr/local/sbin/maquita-sitios", "borrar", s, s], capture_output=True)
    sql(f"DELETE FROM pd_admins WHERE username = '{USUARIO}'")
    sql(f"DELETE FROM pd_cuotas_sitio WHERE domain = '{DOM}'")
    sql(f"DELETE FROM pd_solicitudes WHERE objetivo = '{SITIO}'")


limpiar()
hash_ = bcrypt.hashpw(CLAVE.encode(), bcrypt.gensalt(rounds=10)).decode()
aid = sql(f"""INSERT INTO pd_admins (username, password_hash, display_name, must_change_password, totp_secret, totp_enabled, created_by)
              VALUES ('{USUARIO}', '{hash_}', 'Prueba v1.9', false, '{SECRETO}', true, 'prueba') RETURNING id""").splitlines()[0]
sql(f"INSERT INTO pd_admin_dominios (admin_id, domain) VALUES ({aid}, '{DOM}')")
try:
    c, r = http("POST", "/acceso/entrar", {"username": USUARIO, "password": CLAVE, "codigo": pyotp.TOTP(SECRETO).now()})
    espero("entra con segundo factor", c, 200, r)
    f = r.get("token")

    print("Lista y alcance")
    c, r = http("GET", "/sitios", ficha=f)
    espero("lista sus sitios", (c, DOM in [s.get("dominio") for s in r.get("sitios", [])]), (200, True), r)
    espero("ve su cuota y su uso", bool(r.get("dominios") and "cuota" in r["dominios"][0] and "uso" in r["dominios"][0]), True, r)
    espero("otro dominio da 404", http("GET", "/sitios/example.org/estado", ficha=f)[0], 404)
    espero("no crea en otro dominio", http("POST", "/sitios", {"sitio": "x.example.org", "www": False}, ficha=f)[0], 404)
    espero("no crea mail.<su dominio>", http("POST", "/sitios", {"sitio": "mail." + DOM, "www": False}, ficha=f)[0], 403)
    c, r = http("POST", "/sitios", {"sitio": SITIO, "www": False}, ficha=f)
    espero("la cuota de 1 sitio frena el segundo", c, 409, r)

    sql(f"INSERT INTO pd_cuotas_sitio (domain, max_sitios, disco_mb, bases_mb, actualizado_por) VALUES ('{DOM}', 3, 2048, 1024, 'prueba')")
    c, r = http("POST", "/sitios", {"sitio": SITIO, "www": False}, ficha=f)
    espero("crea el subdominio con cuota", c, 201, r)
    c, r = http("GET", f"/sitios/{SITIO}/estado", ficha=f)
    espero("abre la ficha", c, 200, r)

    print("Aplicación")
    c, r = http("GET", "/sitios/catalogo", ficha=f)
    espero("catálogo", (c, "wordpress" in json.dumps(r)), (200, True))
    t = time.time()
    c, r = http("POST", f"/sitios/{SITIO}/app", {"aplicacion": "wordpress", "titulo": "Prueba v1.9", "correo": "postmaster@" + DOM}, ficha=f)
    espero(f"instala WordPress ({int(time.time() - t)} s)", c, 200, r)
    c, r = http("POST", f"/sitios/{SITIO}/entrar", ficha=f)
    espero("Entrar da un enlace", (c, "url" in r), (200, True), r)
    c, r = http("POST", f"/sitios/{SITIO}/clave-admin", ficha=f)
    espero("nueva contraseña del administrador", c, 200, r)
    c, r = http("POST", f"/sitios/{SITIO}/revisar", ficha=f, tiempo=300)
    espero("revisa la seguridad", c, 200, r)

    print("Tareas, bases, PHP, archivos")
    espero("tareas", http("GET", f"/sitios/{SITIO}/tareas", ficha=f)[0], 200)
    c, r = http("GET", f"/sitios/{SITIO}/bases", ficha=f)
    espero("bases", c, 200, r)
    base = r.get("principal") or next((b.get("nombre") for b in (r.get("bases") or []) if b.get("nombre")), None)
    if base:
        c, r = http("POST", f"/sitios/{SITIO}/bases/{base}/entrar", {"herramienta": "adminer"}, ficha=f)
        espero("entrada a Adminer", (c, "url" in r), (200, True), r)
        if "url" in r:
            pet = urllib.request.Request("https://127.0.0.1:8444" + r["url"])
            try:
                with urllib.request.urlopen(pet, context=CTX, timeout=30) as rr:
                    codigo = rr.status
            except urllib.error.HTTPError as e:
                codigo = e.code
            espero("el enlace de Adminer abre en el portal", codigo in (200, 302), True, codigo)
    else:
        print("  aviso: sin base para probar Adminer", r)
    espero("PHP del sitio", http("GET", f"/sitios/{SITIO}/php", ficha=f)[0], 200)
    c, r = http("PUT", f"/sitios/{SITIO}/archivo?ruta=prueba-v19.txt", ficha=f, crudo=b"hola desde el portal\n")
    espero("guarda un archivo", c, 200, r)
    c, r = http("GET", f"/sitios/{SITIO}/archivo?ruta=prueba-v19.txt", ficha=f)
    espero("lo vuelve a leer", (c, r.get("contenido")), (200, "hola desde el portal\n"), r)
    espero("no sale de la carpeta", http("GET", f"/sitios/{SITIO}/archivo?ruta=../../../etc/passwd", ficha=f)[0], 400)

    print("Paquete")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("index.html", "<h1>Paquete v1.9</h1>")
    c, r = http("PUT", f"/sitios/{SITIO}/paquete?con_bd=0&nombre=sitio.zip", ficha=f, crudo=buf.getvalue())
    espero("no pisa un sitio con aplicación", c, 400, r)
    espero("crea un segundo sitio vacío", http("POST", "/sitios", {"sitio": VACIO, "www": False}, ficha=f)[0], 201)
    c, r = http("PUT", f"/sitios/{VACIO}/paquete?con_bd=0&nombre=sitio.zip", ficha=f, crudo=buf.getvalue())
    espero("sube y despliega un paquete", c, 200, r)
    portada = subprocess.run(["cat", f"/srv/sitios/{VACIO}/publico/index.html"], capture_output=True, text=True).stdout
    espero("el paquete quedó publicado", "Paquete v1.9" in portada, True, portada[:100])

    print("DNS")
    c, r = http("GET", f"/sitios/dns/{DOM}", ficha=f)
    espero("ve su zona", c, 200, r)
    if c == 200:
        registros = r.get("registros") or []
        mx = next((x for x in registros if x.get("tipo") == "MX"), None)
        espero("MX marcado como protegido", bool(mx and mx.get("protegido")), True)
        if mx:
            c2, _ = http("DELETE", f"/sitios/dns/{DOM}/{mx.get('id')}", ficha=f)
            espero("no puede borrar el MX", c2, 403)
    espero("zona ajena da 404", http("GET", "/sitios/dns/example.org", ficha=f)[0], 404)

    print("Baja")
    c, r = http("POST", f"/sitios/{SITIO}/baja", {"motivo": "fin de la prueba"}, ficha=f)
    espero("pide la baja", c, 201, r)
    espero("el sitio sigue existiendo", http("GET", f"/sitios/{SITIO}/estado", ficha=f)[0], 200)
    espero("no repite la solicitud", http("POST", f"/sitios/{SITIO}/baja", {"motivo": "otra"}, ficha=f)[0], 409)
    hechas = set(sql(f"SELECT DISTINCT action FROM pd_auditoria WHERE admin_username = '{USUARIO}'").split())
    falta = {"sitio_crear", "sitio_app", "sitio_entrar", "sitio_clave_admin", "sitio_avanzado_archivo", "sitio_paquete", "sitio_pedir_baja"} - hechas
    espero("los cambios quedan en la auditoría", falta, set(), sorted(hechas))
finally:
    limpiar()
    print("Limpieza hecha")
print("\nRESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS: {fallos}")
