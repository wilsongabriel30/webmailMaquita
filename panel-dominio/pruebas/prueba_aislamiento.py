"""Prueba de punta a punta del portal de dominio, contra el servicio instalado.

Crea un dominio de mentira (prueba-portal.invalid) con su administrador, intenta salirse de él
por todos los caminos y al final borra lo que creó. Se ejecuta como root en el servidor:

    panel-dominio/backend/venv/bin/python panel-dominio/pruebas/prueba_aislamiento.py
"""
import json, os, secrets, subprocess, sys, time, urllib.request, urllib.error

import bcrypt
import pyotp

BASE = "http://127.0.0.1:8003/api"        # el servicio, sin pasar por nginx
GENERAL = "http://127.0.0.1:8001/api"     # el panel general
DOM = "prueba-portal.invalid"
ENTORNO = "/etc/maquita-mail/panel-dominio.env"
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USUARIO = "prueba-portal"
fallos = []


def clave_nueva() -> str:
    """Contraseña al azar que cumple la política (cuatro clases de carácter)."""
    return "Aa1." + secrets.token_urlsafe(12)


INICIAL, DEFINITIVA, DE_CUENTA, OTRA = clave_nueva(), clave_nueva(), clave_nueva(), clave_nueva()


def sql(q):
    r = subprocess.run(["sudo", "-u", "postgres", "psql", "-d", "maildb", "-Atc", q], capture_output=True, text=True)
    return r.stdout.strip()


def http(metodo, ruta, cuerpo=None, ficha=None, base=BASE, crudo=None):
    datos = crudo if crudo is not None else (json.dumps(cuerpo).encode() if cuerpo is not None else None)
    req = urllib.request.Request(base + ruta, method=metodo, data=datos)
    req.add_header("Content-Type", "application/octet-stream" if crudo is not None else "application/json")
    if ficha:
        req.add_header("Authorization", "Bearer " + ficha)
    try:
        with urllib.request.urlopen(req) as r:
            leido = r.read()
            try:
                return r.status, json.loads(leido or b"{}")
            except Exception:
                return r.status, {}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def espero(nombre, real, esperado):
    bien = real == esperado
    print(("  bien  " if bien else "  FALLO ") + nombre + ("" if bien else f"  -> {real!r}"))
    if not bien:
        fallos.append(nombre)


def seccion(titulo):
    print(titulo)


def limpiar():
    for q in (f"delete from alias where domain='{DOM}'", f"delete from mail_group_members where group_id in (select id from mail_groups where domain='{DOM}')",
              f"delete from mail_groups where domain='{DOM}'", f"delete from mailbox where domain='{DOM}'",
              f"delete from branding_empresa where dominio='{DOM}'", f"delete from pd_solicitudes where dominio='{DOM}'",
              f"delete from pd_auditoria where admin_username='{USUARIO}'", f"delete from pd_admins where username='{USUARIO}'",
              f"delete from domain where domain='{DOM}'"):
        sql(q)
    carpeta = os.path.join(DIR_MARCA, DOM)
    if os.path.isdir(carpeta):
        subprocess.run(["rm", "-rf", "--", carpeta])


entorno = dict(l.strip().split("=", 1) for l in open(ENTORNO) if "=" in l)
DIR_MARCA = entorno.get("PD_DIR_MARCA", RAIZ + "/uploads/branding/empresas")
OTRO = sql(f"select domain from mailbox where domain<>'{DOM}' group by 1 order by count(*) desc limit 1")
if not OTRO:
    sys.exit("Hace falta al menos otro dominio con cuentas para probar el aislamiento")
ajena = sql(f"select username from mailbox where domain='{OTRO}' and active order by username limit 1")
huella = lambda: sql(f"select md5(m.password)||m.modified::text||m.active::text||(select goto from alias where address=m.username) from mailbox m where username='{ajena}'")
antes = huella()
alias_ajeno = sql(f"select address from alias a where domain='{OTRO}' and address<>goto and not exists (select 1 from mailbox m where m.username=a.address) limit 1")
grupo_ajeno = sql(f"select id from mail_groups where domain<>'{DOM}' order by id limit 1")
huella_grupos = lambda: sql(f"select md5(string_agg(g.id::text||g.name||g.active::text||coalesce(m.member_email,''), ',' order by g.id, m.id)) from mail_groups g left join mail_group_members m on m.group_id=g.id where g.domain<>'{DOM}'")
grupos_antes = huella_grupos()

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (64).to_bytes(4, "big") + (64).to_bytes(4, "big") + b"\x08\x06\x00\x00\x00" + b"\x00" * 64
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"

limpiar()
sql(f"insert into domain (domain, description) values ('{DOM}','prueba temporal del portal')")
sql(f"insert into pd_admins (username, password_hash, display_name, created_by) values ('{USUARIO}','{bcrypt.hashpw(INICIAL.encode(), bcrypt.gensalt()).decode()}','Prueba','prueba')")
sql(f"insert into pd_admin_dominios (admin_id, domain) select id,'{DOM}' from pd_admins where username='{USUARIO}'")
try:
    seccion("Entrada, cambio de clave y segundo factor")
    espero("sin sesión no se ve nada", http("GET", "/cuentas")[0], 401)
    espero("ficha inventada no vale", http("GET", "/cuentas", ficha="x" * 43)[0], 401)
    espero("clave mala rechazada", http("POST", "/acceso/entrar", {"username": USUARIO, "password": clave_nueva()})[0], 401)
    c, r = http("POST", "/acceso/entrar", {"username": USUARIO, "password": INICIAL})
    espero("entra con la clave inicial", (c, r.get("debe_cambiar_clave")), (200, True)); f = r.get("token")
    espero("con clave inicial no puede gestionar", http("GET", "/cuentas", ficha=f)[0], 403)
    espero("clave nueva débil rechazada", http("POST", "/acceso/clave", {"actual": INICIAL, "nueva": "abc" * 2}, f)[0], 400)
    espero("cambia su clave", http("POST", "/acceso/clave", {"actual": INICIAL, "nueva": DEFINITIVA}, f)[0], 200)
    espero("la sesión anterior quedó cerrada", http("GET", "/acceso/yo", ficha=f)[0], 401)
    c, r = http("POST", "/acceso/entrar", {"username": USUARIO, "password": DEFINITIVA}); f = r.get("token")
    espero("entra con la clave nueva y le falta el segundo factor", (c, r.get("debe_cambiar_clave"), r.get("debe_activar_segundo_factor")), (200, False, True))
    espero("sin segundo factor no puede gestionar", http("GET", "/cuentas", ficha=f)[0], 403)
    espero("sin segundo factor no puede tocar la marca", http("GET", "/marca", ficha=f)[0], 403)
    c, r = http("POST", "/acceso/totp/iniciar", {}, f); secreto = r.get("secreto", "")
    espero("recibe clave y código QR", (c, len(secreto) >= 16, str(r.get("qr", "")).startswith("data:image/svg+xml;base64,")), (200, True, True))
    espero("un código inventado no activa", http("POST", "/acceso/totp/activar", {"codigo": "000000" if pyotp.TOTP(secreto).now() != "000000" else "111111"}, f)[0], 400)
    paso = int(time.time() // 30)
    espero("el código correcto activa", http("POST", "/acceso/totp/activar", {"codigo": pyotp.TOTP(secreto).at(paso * 30)}, f)[0], 200)
    espero("ya puede gestionar", http("GET", "/cuentas", ficha=f), (200, []))
    espero("no puede reiniciar el segundo factor por su cuenta", http("POST", "/acceso/totp/iniciar", {}, f)[0], 400)
    espero("al entrar, la clave sola ya no basta", http("POST", "/acceso/entrar", {"username": USUARIO, "password": DEFINITIVA})[1].get("requiere_codigo"), True)
    espero("un código ya usado no sirve para entrar", http("POST", "/acceso/entrar", {"username": USUARIO, "password": DEFINITIVA, "codigo": pyotp.TOTP(secreto).at(paso * 30)})[0], 401)
    c, r = http("POST", "/acceso/entrar", {"username": USUARIO, "password": DEFINITIVA, "codigo": pyotp.TOTP(secreto).at((paso + 1) * 30)})
    espero("con clave y código nuevo entra", (c, bool(r.get("token"))), (200, True)); f = r.get("token") or f
    espero("solo ve su dominio", http("GET", "/acceso/yo", ficha=f)[1].get("dominios"), [DOM])

    seccion("Cuentas propias")
    c, r = http("POST", "/cuentas", {"username": f"Ana.Perez@{DOM}", "name": "Ana Pérez", "password": DE_CUENTA}, f)
    espero("crea cuenta en su dominio", (c, r.get("username"), r.get("quota")), (201, f"ana.perez@{DOM}", 5 * 1024**3))
    espero("la respuesta no trae la contraseña", "password" in r, False)
    http("POST", "/cuentas", {"username": f"luis@{DOM}", "name": "Luis", "password": DE_CUENTA}, f)
    guardado = sql(f"select password from mailbox where username='ana.perez@{DOM}'")
    v = subprocess.run(["doveadm", "pw", "-t", guardado, "-p", DE_CUENTA], capture_output=True, text=True)
    espero("Dovecot acepta el hash guardado", "verified" in (v.stdout + v.stderr), True)
    espero("duplicada rechazada", http("POST", "/cuentas", {"username": f"ana.perez@{DOM}", "name": "x", "password": DE_CUENTA}, f)[0], 409)
    espero("clave débil rechazada", http("POST", "/cuentas", {"username": f"b@{DOM}", "name": "x", "password": "1" * 12}, f)[0], 400)
    espero("cuota por encima del tope rechazada", http("PUT", f"/cuentas/ana.perez@{DOM}", {"quota": 50 * 1024**3}, f)[0], 400)
    espero("edita nombre", http("PUT", f"/cuentas/ana.perez@{DOM}", {"name": "Ana P."}, f)[1].get("name"), "Ana P.")
    espero("cambia clave de la cuenta", http("POST", f"/cuentas/ana.perez@{DOM}/clave", {"password": OTRA}, f)[0], 200)
    espero("no existe ruta para eliminar cuentas directamente", http("DELETE", f"/cuentas/ana.perez@{DOM}", ficha=f)[0], 405)

    seccion("Otros dominios (todo debe fallar)")
    espero("crear cuenta en dominio ajeno", http("POST", "/cuentas", {"username": f"intruso.prueba@{OTRO}", "name": "x", "password": DE_CUENTA}, f)[0], 404)
    espero("editar cuenta ajena", http("PUT", f"/cuentas/{ajena}", {"name": "Intruso"}, f)[0], 404)
    espero("cambiar clave ajena", http("POST", f"/cuentas/{ajena}/clave", {"password": DE_CUENTA}, f)[0], 404)
    espero("desactivar cuenta ajena", http("POST", f"/cuentas/{ajena}/activa", {"active": False}, f)[0], 404)
    espero("reenviar el correo de una cuenta ajena", http("PUT", f"/reenvios/{ajena}", {"destinos": [f"ana.perez@{DOM}"], "conserva_copia": True}, f)[0], 404)
    espero("pedir la eliminación de una cuenta ajena", http("POST", "/solicitudes/eliminar-cuenta", {"cuenta": ajena}, f)[0], 404)
    espero("dos arrobas en la ruta", http("POST", f"/cuentas/x@{DOM}@{OTRO}/activa", {"active": False}, f)[0], 404)
    espero("subdominio parecido", http("POST", "/cuentas", {"username": f"x@sub.{DOM}", "name": "x", "password": DE_CUENTA}, f)[0], 404)
    espero("marca de un dominio ajeno", http("PUT", f"/marca/{OTRO}", {"org_name": "Intruso"}, f)[0], 404)
    espero("logo de un dominio ajeno", http("PUT", f"/marca/{OTRO}/archivo/logo", ficha=f, crudo=PNG)[0], 404)
    espero("DNS de un dominio ajeno", http("GET", f"/dns/{OTRO}", ficha=f)[0], 404)
    espero("grupo con dirección de otro dominio", http("POST", "/grupos", {"address": f"intrusos@{OTRO}", "name": "x"}, f)[0], 404)
    if grupo_ajeno:
        espero("editar un grupo ajeno", http("PUT", f"/grupos/{grupo_ajeno}", {"name": "Intruso", "active": False}, f)[0], 404)
        espero("meter a alguien en un grupo ajeno", http("POST", f"/grupos/{grupo_ajeno}/miembros", {"email": f"ana.perez@{DOM}"}, f)[0], 404)
        espero("borrar un grupo ajeno", http("DELETE", f"/grupos/{grupo_ajeno}", ficha=f)[0], 404)
    if alias_ajeno:
        espero("editar alias ajeno", http("PUT", f"/alias/{alias_ajeno}", {"goto": f"ana.perez@{DOM}"}, f)[0], 404)
        espero("borrar alias ajeno", http("DELETE", f"/alias/{alias_ajeno}", ficha=f)[0], 404)
    espero("la cuenta ajena sigue intacta", huella(), antes)
    espero("los grupos ajenos siguen intactos", huella_grupos(), grupos_antes)
    espero("no se creó nada en el dominio ajeno", sql(f"select count(*) from mailbox where username='intruso.prueba@{OTRO}'"), "0")
    espero("el listado no trae cuentas ajenas", all(x["domain"] == DOM for x in http("GET", "/cuentas", ficha=f)[1]), True)
    espero("la marca ajena no aparece", [e["dominio"] for e in http("GET", "/marca", ficha=f)[1]["empresas"]], [DOM])

    seccion("Alias y reenvíos")
    espero("alias hacia cuenta propia que no existe", http("POST", "/alias", {"address": f"info@{DOM}", "goto": f"nadie@{DOM}"}, f)[0], 400)
    espero("alias con dirección de otro dominio", http("POST", "/alias", {"address": f"info.intruso@{OTRO}", "goto": f"ana.perez@{DOM}"}, f)[0], 404)
    espero("alias sobre una cuenta que ya existe", http("POST", "/alias", {"address": f"luis@{DOM}", "goto": f"ana.perez@{DOM}"}, f)[0], 409)
    espero("crea alias propio con un destino de fuera", http("POST", "/alias", {"address": f"info@{DOM}", "goto": f"ana.perez@{DOM}, socio@example.org"}, f)[0], 201)
    espero("el destino de fuera queda anotado en la auditoría", sql(f"select details->'externos'->>0 from pd_auditoria where action='alias_crear' and target='info@{DOM}'"), "socio@example.org")
    espero("reenvío sin destinos y sin copia", http("PUT", f"/reenvios/ana.perez@{DOM}", {"destinos": [], "conserva_copia": False}, f)[0], 400)
    espero("reenvío con copia", http("PUT", f"/reenvios/ana.perez@{DOM}", {"destinos": [f"luis@{DOM}"], "conserva_copia": True}, f)[0], 200)
    espero("la cuenta entrega en su buzón y en el destino", sql(f"select goto from alias where address='ana.perez@{DOM}'"), f"ana.perez@{DOM},luis@{DOM}")
    espero("la cuenta con reenvío no aparece como alias", [a["address"] for a in http("GET", "/alias", ficha=f)[1]], [f"info@{DOM}"])
    espero("no deja borrar la entrada de una cuenta", http("DELETE", f"/alias/ana.perez@{DOM}", ficha=f)[0], 404)
    espero("no deja editar la entrada de una cuenta como alias", http("PUT", f"/alias/luis@{DOM}", {"goto": "socio@example.org"}, f)[0], 404)
    espero("quita el reenvío", http("PUT", f"/reenvios/ana.perez@{DOM}", {"destinos": [], "conserva_copia": True}, f)[0], 200)
    espero("la cuenta vuelve a entregar solo en su buzón", sql(f"select goto from alias where address='ana.perez@{DOM}'"), f"ana.perez@{DOM}")
    espero("borra su alias", http("DELETE", f"/alias/info@{DOM}", ficha=f)[0], 200)

    seccion("Grupos")
    c, r = http("POST", "/grupos", {"address": f"todos@{DOM}", "name": "Todos"}, f); g = r.get("id")
    espero("crea un grupo", c, 201)
    espero("grupo sin miembros no recibe", sql(f"select count(*) from alias where address='todos@{DOM}'"), "0")
    espero("miembro propio que no existe", http("POST", f"/grupos/{g}/miembros", {"email": f"nadie@{DOM}"}, f)[0], 400)
    espero("miembro de fuera en grupo cerrado", http("POST", f"/grupos/{g}/miembros", {"email": "socio@example.org"}, f)[0], 400)
    espero("agrega dos miembros", [http("POST", f"/grupos/{g}/miembros", {"email": e}, f)[0] for e in (f"ana.perez@{DOM}", f"luis@{DOM}")], [201, 201])
    espero("miembro repetido", http("POST", f"/grupos/{g}/miembros", {"email": f"luis@{DOM}"}, f)[0], 409)
    espero("el grupo reparte a sus miembros", sql(f"select goto from alias where address='todos@{DOM}'"), f"ana.perez@{DOM},luis@{DOM}")
    espero("grupo como alias no aparece", [a["address"] for a in http("GET", "/alias", ficha=f)[1]], [])
    espero("abre el grupo a externos y agrega uno", (http("PUT", f"/grupos/{g}", {"allow_external": True}, f)[0], http("POST", f"/grupos/{g}/miembros", {"email": "socio@example.org"}, f)[0]), (200, 201))
    espero("no deja cerrarlo con externos dentro", http("PUT", f"/grupos/{g}", {"allow_external": False}, f)[0], 400)
    espero("pausar el grupo le quita la entrega", (http("PUT", f"/grupos/{g}", {"active": False}, f)[0], sql(f"select count(*) from alias where address='todos@{DOM}'")), (200, "0"))
    espero("elimina el grupo", http("DELETE", f"/grupos/{g}", ficha=f)[0], 200)

    seccion("Marca")
    espero("guarda nombre y color", http("PUT", f"/marca/{DOM}", {"org_name": "Organización de Prueba", "primary_color": "#1a7f37"}, f)[0], 200)
    espero("color mal escrito", http("PUT", f"/marca/{DOM}", {"primary_color": "rojo"}, f)[0], 400)
    espero("página web con javascript:", http("PUT", f"/marca/{DOM}", {"org_website": "javascript:alert(1)"}, f)[0], 400)
    espero("un SVG con código se rechaza", http("PUT", f"/marca/{DOM}/archivo/logo", ficha=f, crudo=SVG)[0], 400)
    espero("un ejecutable disfrazado se rechaza", http("PUT", f"/marca/{DOM}/archivo/logo", ficha=f, crudo=b"MZ\x90\x00" + b"\x00" * 100)[0], 400)
    espero("una imagen enorme se rechaza", http("PUT", f"/marca/{DOM}/archivo/logo", ficha=f, crudo=PNG + b"\x00" * (600 * 1024))[0], 400)
    espero("tipo de archivo inventado", http("PUT", f"/marca/{DOM}/archivo/..%2F..%2Fx", ficha=f, crudo=PNG)[0], 404)
    espero("sube un logo PNG", http("PUT", f"/marca/{DOM}/archivo/logo", ficha=f, crudo=PNG)[0], 200)
    logo = os.path.join(DIR_MARCA, DOM, "logo", "logo.png")
    espero("el logo quedó en su sitio y lo puede leer el webmail", os.path.isfile(logo) and oct(os.stat(logo).st_mode)[-3:], "664")
    espero("no escribió nada fuera de su carpeta", sorted(os.listdir(os.path.join(DIR_MARCA, DOM))), ["logo"])
    espero("quita el logo", (http("DELETE", f"/marca/{DOM}/archivo/logo", ficha=f)[0], os.path.exists(logo)), (200, False))

    seccion("DNS y eliminación de cuentas")
    c, r = http("GET", f"/dns/{DOM}", ficha=f)
    espero("verifica el DNS de su dominio", (c, sorted(k for k in r if k != "dominio")), (200, ["dkim", "dmarc", "mx", "spf"]))
    espero("pide eliminar una cuenta", http("POST", "/solicitudes/eliminar-cuenta", {"cuenta": f"luis@{DOM}", "motivo": "ya no trabaja aquí"}, f)[0], 201)
    espero("la cuenta queda desactivada pero existe", sql(f"select active from mailbox where username='luis@{DOM}'"), "f")
    espero("no se puede pedir dos veces", http("POST", "/solicitudes/eliminar-cuenta", {"cuenta": f"luis@{DOM}"}, f)[0], 409)
    espero("ve su solicitud pendiente", [(s["objetivo"], s["estado"]) for s in http("GET", "/solicitudes", ficha=f)[1]], [(f"luis@{DOM}", "pendiente")])

    seccion("Separación entre servicios")
    espero("la ficha del portal no vale en el panel general", http("GET", "/mailboxes", ficha=f, base=GENERAL)[0] in (401, 403), True)
    espero("no puede resolver solicitudes en el panel general", http("GET", "/admins-dominio/solicitudes", ficha=f, base=GENERAL)[0] in (401, 403), True)
    espero("el portal no tiene rutas del panel general", http("GET", "/mailboxes", ficha=f)[0], 404)
    espero("sin documentación expuesta", all(http("GET", x, base=BASE[:-4])[0] == 404 for x in ("/openapi.json", "/docs", "/redoc")), True)

    seccion("Usuario de base de datos del portal")
    def como_portal(q):
        r = subprocess.run(["psql", "-h", "127.0.0.1", "-U", "panel_dominio", "-d", "maildb", "-Atc", q], capture_output=True, text=True,
                           env={"PGPASSWORD": entorno["PD_DB_PASS"], "PATH": "/usr/bin:/bin"})
        return "denegado" if "permission denied" in r.stderr else ("ok:" + r.stdout.strip()[:30] if r.returncode == 0 else r.stderr.strip()[:80])
    for nombre, q in [("leer contraseñas de buzones", "select password from mailbox limit 1"), ("borrar buzones", f"delete from mailbox where username='ana.perez@{DOM}'"),
                      ("leer administradores del panel general", "select * from admin_users"), ("leer la auditoría general", "select * from admin_audit limit 1"),
                      ("crearse un administrador", "insert into pd_admins (username,password_hash) values ('x','x')"), ("asignarse un dominio", "insert into pd_admin_dominios values (1,'" + OTRO + "')"),
                      ("leer su propia auditoría", "select * from pd_auditoria limit 1"), ("borrar su auditoría", "delete from pd_auditoria"),
                      ("aprobarse una solicitud", "update pd_solicitudes set estado='aprobada'"), ("borrar solicitudes", "delete from pd_solicitudes"),
                      ("cambiar los nombres de servidor", "update portal_empresa set activo=false"), ("reactivar o renombrar administradores", "update pd_admins set active=true, username='x'"),
                      ("leer preferencias de usuarios", "select * from user_preferences limit 1"), ("cambiar el dominio de un buzón", f"update mailbox set domain='{OTRO}' where username='ana.perez@{DOM}'"),
                      ("crear tablas", "create table pd_x (a int)")]:
        espero("no puede " + nombre, como_portal(q), "denegado")
    espero("sí puede leer dominios", como_portal("select count(*) > 0 from domain"), "ok:t")

    seccion("Usuario del sistema del portal")
    for ruta in [RAIZ + "/backend/.env", RAIZ + "/admin-panel/backend/.env", ENTORNO, "/var/vmail"]:
        r = subprocess.run(["sudo", "-u", "maquita-dominio", "ls", ruta] if ruta == "/var/vmail" else ["sudo", "-u", "maquita-dominio", "cat", ruta], capture_output=True, text=True)
        espero("no puede leer " + ruta, r.returncode != 0, True)
    for ruta in [RAIZ + "/panel-dominio/frontend/js/x.js", RAIZ + "/panel-dominio/backend/app/x.py", os.path.dirname(DIR_MARCA) + "/x.png", "/etc/nginx/x"]:
        r = subprocess.run(["sudo", "-u", "maquita-dominio", "touch", ruta], capture_output=True, text=True)
        espero("no puede escribir en " + os.path.dirname(ruta), r.returncode != 0, True)
    espero("no tiene sudo", subprocess.run(["sudo", "-u", "maquita-dominio", "sudo", "-n", "true"], capture_output=True).returncode != 0, True)
    espero("auditoría registrada", int(sql(f"select count(*) from pd_auditoria where admin_username='{USUARIO}'")) >= 25, True)
finally:
    limpiar()
    print("Limpieza:", sql(f"select (select count(*) from mailbox where domain='{DOM}') + (select count(*) from alias where domain='{DOM}') + (select count(*) from mail_groups where domain='{DOM}') + (select count(*) from pd_admins where username='{USUARIO}') + (select count(*) from domain where domain='{DOM}')"), "restos")
print("\nRESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
