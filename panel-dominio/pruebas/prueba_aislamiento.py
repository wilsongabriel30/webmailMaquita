"""Prueba de punta a punta del portal de dominio, contra el servicio instalado.

Crea un dominio de mentira (prueba-portal.invalid) con su administrador, intenta salirse de él
por todos los caminos y al final borra lo que creó. Se ejecuta como root en el servidor:

    panel-dominio/backend/venv/bin/python panel-dominio/pruebas/prueba_aislamiento.py
"""
import json, os, secrets, subprocess, sys, urllib.request, urllib.error

BASE = "http://127.0.0.1:8003/api"        # el servicio, sin pasar por nginx
GENERAL = "http://127.0.0.1:8001/api"     # el panel general
DOM = "prueba-portal.invalid"
ENTORNO = "/etc/maquita-mail/panel-dominio.env"
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def clave_nueva() -> str:
    """Contraseña al azar que cumple la política (cuatro clases de carácter)."""
    return "Aa1." + secrets.token_urlsafe(12)


INICIAL, DEFINITIVA, DE_CUENTA, OTRA = clave_nueva(), clave_nueva(), clave_nueva(), clave_nueva()
fallos = []

def sql(q, rol="postgres"):
    r = subprocess.run(["sudo", "-u", "postgres", "psql", "-d", "maildb", "-Atc", q], capture_output=True, text=True)
    return (r.stdout.strip(), r.stderr.strip())

def http(metodo, ruta, cuerpo=None, ficha=None, base=BASE):
    req = urllib.request.Request(base + ruta, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None)
    req.add_header("Content-Type", "application/json"); 
    if ficha: req.add_header("Authorization", "Bearer " + ficha)
    try:
        with urllib.request.urlopen(req) as r:
            cuerpo_r = r.read()
            try: return r.status, json.loads(cuerpo_r or b"{}")
            except Exception: return r.status, {}
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except Exception: return e.code, {}

def espero(nombre, real, esperado):
    bien = real == esperado if not callable(esperado) else esperado(real)
    print(("  bien  " if bien else "  FALLO ") + nombre + ("" if bien else f"  -> {real!r}"))
    if not bien: fallos.append(nombre)

import bcrypt
OTRO = sql(f"select domain from mailbox where domain<>'{DOM}' group by 1 order by count(*) desc limit 1")[0]
if not OTRO: sys.exit("Hace falta al menos otro dominio con cuentas para probar el aislamiento")
ajena = sql(f"select username from mailbox where domain='{OTRO}' and active order by username limit 1")[0]
antes = sql(f"select md5(password)||modified::text||active::text from mailbox where username='{ajena}'")[0]
alias_ajeno = sql(f"select address from alias where domain='{OTRO}' and address<>goto limit 1")[0]
sql(f"insert into domain (domain, description) values ('{DOM}','prueba temporal del portal')")
h = bcrypt.hashpw(INICIAL.encode(), bcrypt.gensalt()).decode()
sql(f"insert into pd_admins (username, password_hash, display_name, created_by) values ('prueba-portal','{h}','Prueba','prueba')")
sql(f"insert into pd_admin_dominios (admin_id, domain) select id,'{DOM}' from pd_admins where username='prueba-portal'")
try:
    print("Entrada")
    espero("sin sesión no se ve nada", http("GET", "/cuentas")[0], 401)
    espero("ficha inventada no vale", http("GET", "/cuentas", ficha="x" * 43)[0], 401)
    espero("clave mala rechazada", http("POST", "/acceso/entrar", {"username": "prueba-portal", "password": clave_nueva()})[0], 401)
    c, r = http("POST", "/acceso/entrar", {"username": "prueba-portal", "password": INICIAL})
    espero("entra con la clave inicial", (c, r.get("debe_cambiar_clave")), (200, True)); f = r.get("token")
    espero("con clave inicial no puede gestionar", http("GET", "/cuentas", ficha=f)[0], 403)
    espero("clave nueva débil rechazada", http("POST", "/acceso/clave", {"actual": INICIAL, "nueva": "abc" * 2}, f)[0], 400)
    espero("cambia su clave", http("POST", "/acceso/clave", {"actual": INICIAL, "nueva": DEFINITIVA}, f)[0], 200)
    espero("la sesión anterior quedó cerrada", http("GET", "/acceso/yo", ficha=f)[0], 401)
    c, r = http("POST", "/acceso/entrar", {"username": "prueba-portal", "password": DEFINITIVA}); f = r.get("token")
    espero("entra con la clave nueva", (c, r.get("debe_cambiar_clave")), (200, False))
    espero("solo ve su dominio", http("GET", "/acceso/yo", ficha=f)[1].get("dominios"), [DOM])

    print("Cuentas propias")
    espero("lista vacía al inicio", http("GET", "/cuentas", ficha=f), (200, []))
    c, r = http("POST", "/cuentas", {"username": f"Ana.Perez@{DOM}", "name": "Ana Pérez", "password": DE_CUENTA}, f)
    espero("crea cuenta en su dominio", (c, r.get("username"), r.get("quota")), (201, f"ana.perez@{DOM}", 5 * 1024**3))
    espero("la respuesta no trae la contraseña", "password" in r, False)
    guardado = sql(f"select password from mailbox where username='ana.perez@{DOM}'")[0]
    v = subprocess.run(["doveadm", "pw", "-t", guardado, "-p", DE_CUENTA], capture_output=True, text=True)
    espero("Dovecot acepta el hash guardado", "verified" in (v.stdout + v.stderr), True)
    espero("entrada propia de la cuenta creada", sql(f"select count(*) from alias where address='ana.perez@{DOM}' and goto=address")[0], "1")
    espero("duplicada rechazada", http("POST", "/cuentas", {"username": f"ana.perez@{DOM}", "name": "x", "password": DE_CUENTA}, f)[0], 409)
    espero("clave débil rechazada", http("POST", "/cuentas", {"username": f"b@{DOM}", "name": "x", "password": "1" * 12}, f)[0], 400)
    espero("cuota por encima del tope rechazada", http("PUT", f"/cuentas/ana.perez@{DOM}", {"quota": 50 * 1024**3}, f)[0], 400)
    espero("edita nombre", http("PUT", f"/cuentas/ana.perez@{DOM}", {"name": "Ana P."}, f)[1].get("name"), "Ana P.")
    espero("cambia clave de la cuenta", http("POST", f"/cuentas/ana.perez@{DOM}/clave", {"password": OTRA}, f)[0], 200)
    g2 = sql(f"select password from mailbox where username='ana.perez@{DOM}'")[0]
    v = subprocess.run(["doveadm", "pw", "-t", g2, "-p", OTRA], capture_output=True, text=True)
    espero("Dovecot acepta la clave nueva", "verified" in (v.stdout + v.stderr), True)
    espero("desactiva", http("POST", f"/cuentas/ana.perez@{DOM}/activa", {"active": False}, f)[1].get("active"), False)
    espero("no existe ruta para eliminar cuentas", http("DELETE", f"/cuentas/ana.perez@{DOM}", ficha=f)[0], 405)

    print("Otros dominios (todo debe fallar)")
    espero("crear cuenta en dominio ajeno", http("POST", "/cuentas", {"username": f"intruso.prueba@{OTRO}", "name": "x", "password": DE_CUENTA}, f)[0], 404)
    espero("editar cuenta ajena", http("PUT", f"/cuentas/{ajena}", {"name": "Intruso"}, f)[0], 404)
    espero("cambiar clave ajena", http("POST", f"/cuentas/{ajena}/clave", {"password": DE_CUENTA}, f)[0], 404)
    espero("desactivar cuenta ajena", http("POST", f"/cuentas/{ajena}/activa", {"active": False}, f)[0], 404)
    espero("dos arrobas en la ruta", http("POST", f"/cuentas/x@{DOM}@{OTRO}/activa", {"active": False}, f)[0], 404)
    espero("subdominio parecido", http("POST", "/cuentas", {"username": f"x@sub.{DOM}", "name": "x", "password": DE_CUENTA}, f)[0], 404)
    espero("la cuenta ajena sigue intacta", sql(f"select md5(password)||modified::text||active::text from mailbox where username='{ajena}'")[0], antes)
    espero("no se creó nada en el dominio ajeno", sql(f"select count(*) from mailbox where username='intruso.prueba@{OTRO}'")[0], "0")
    espero("el listado no trae cuentas ajenas", all(x["domain"] == DOM for x in http("GET", "/cuentas", ficha=f)[1]), True)

    print("Alias")
    espero("alias hacia afuera rechazado", http("POST", "/alias", {"address": f"info@{DOM}", "goto": "alguien@gmail.com"}, f)[0], 400)
    espero("alias hacia cuenta de otro dominio rechazado", http("POST", "/alias", {"address": f"info@{DOM}", "goto": ajena}, f)[0], 400)
    espero("alias con dirección de otro dominio", http("POST", "/alias", {"address": f"info.intruso@{OTRO}", "goto": f"ana.perez@{DOM}"}, f)[0], 404)
    espero("alias hacia cuenta que no existe", http("POST", "/alias", {"address": f"info@{DOM}", "goto": f"nadie@{DOM}"}, f)[0], 400)
    espero("crea alias propio", http("POST", "/alias", {"address": f"info@{DOM}", "goto": f"ana.perez@{DOM}"}, f)[0], 201)
    espero("no deja borrar la entrada propia de una cuenta", http("DELETE", f"/alias/ana.perez@{DOM}", ficha=f)[0], 404)
    if alias_ajeno:
        espero("editar alias ajeno", http("PUT", f"/alias/{alias_ajeno}", {"goto": f"ana.perez@{DOM}"}, f)[0], 404)
        espero("borrar alias ajeno", http("DELETE", f"/alias/{alias_ajeno}", ficha=f)[0], 404)
    espero("borra su alias", http("DELETE", f"/alias/info@{DOM}", ficha=f)[0], 200)

    print("Separación entre servicios")
    espero("la ficha del portal no vale en el panel general", http("GET", "/mailboxes", ficha=f, base=GENERAL)[0] in (401, 403), True)
    espero("el portal no tiene rutas del panel general", http("GET", "/mailboxes", ficha=f)[0], 404)
    espero("sin documentación expuesta", all(http("GET", x, base=BASE[:-4])[0] == 404 for x in ("/openapi.json", "/docs", "/redoc")), True)

    print("Usuario de base de datos del portal")
    clave = open(ENTORNO).read().split("=", 1)[1].strip()
    def como_portal(q):
        r = subprocess.run(["psql", "-h", "127.0.0.1", "-U", "panel_dominio", "-d", "maildb", "-Atc", q], capture_output=True, text=True, env={"PGPASSWORD": clave, "PATH": "/usr/bin:/bin"})
        return "denegado" if "permission denied" in r.stderr else ("ok:" + r.stdout.strip()[:30] if r.returncode == 0 else r.stderr.strip()[:80])
    for nombre, q in [("leer contraseñas de buzones", "select password from mailbox limit 1"), ("borrar buzones", f"delete from mailbox where username='ana.perez@{DOM}'"),
                      ("leer administradores del panel general", "select * from admin_users"), ("leer la auditoría general", "select * from admin_audit limit 1"),
                      ("crearse un administrador", "insert into pd_admins (username,password_hash) values ('x','x')"), ("asignarse un dominio", "insert into pd_admin_dominios values (1,'" + OTRO + "')"),
                      ("leer su propia auditoría", "select * from pd_auditoria limit 1"), ("borrar su auditoría", "delete from pd_auditoria"),
                      ("leer preferencias de usuarios", "select * from user_preferences limit 1"), ("cambiar el dominio de un buzón", f"update mailbox set domain='{OTRO}' where username='ana.perez@{DOM}'"),
                      ("crear tablas", "create table pd_x (a int)")]:
        espero("no puede " + nombre, como_portal(q), "denegado")
    espero("sí puede leer dominios", como_portal("select count(*) > 0 from domain"), "ok:t")

    print("Usuario del sistema del portal")
    for ruta in [RAIZ + "/backend/.env", RAIZ + "/admin-panel/backend/.env", ENTORNO, "/var/vmail"]:
        r = subprocess.run(["sudo", "-u", "maquita-dominio", "ls", ruta] if ruta == "/var/vmail" else ["sudo", "-u", "maquita-dominio", "cat", ruta], capture_output=True, text=True)
        espero("no puede leer " + ruta, r.returncode != 0, True)
    espero("no tiene sudo", subprocess.run(["sudo", "-u", "maquita-dominio", "sudo", "-n", "true"], capture_output=True).returncode != 0, True)
    espero("auditoría registrada", int(sql("select count(*) from pd_auditoria where admin_username='prueba-portal'")[0]) >= 8, True)
finally:
    sql(f"delete from alias where domain='{DOM}'"); sql(f"delete from mailbox where domain='{DOM}'")
    sql("delete from pd_auditoria where admin_username='prueba-portal'"); sql("delete from pd_admins where username='prueba-portal'")
    sql(f"delete from domain where domain='{DOM}'")
    print("Limpieza:", sql(f"select (select count(*) from mailbox where domain='{DOM}') + (select count(*) from alias where domain='{DOM}') + (select count(*) from pd_admins where username='prueba-portal') + (select count(*) from domain where domain='{DOM}')")[0], "restos")
print("\nRESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
