#!/usr/bin/env python3
"""Panel ↔ Almacén: vincular buzones a personas del directorio y fijar la cuota del Drive al crear el buzón.
Se ejecuta en la raíz del clon."""
import os
import shutil

O = "/root/p2m/drive/"


def leer(p):
    return open(p, encoding="utf-8").read()


def escribir(p, s):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)


def sustituir(p, old, new):
    s = leer(p)
    assert s.count(old) == 1, f"{p}: ancla x{s.count(old)}: {old[:80]!r}"
    escribir(p, s.replace(old, new))


shutil.copy(O + "api_panel.py", "almacen/servicio/api_panel.py")
shutil.copy(O + "test_enlaces_correo.py", "almacen/tests/test_enlaces_correo.py")
os.makedirs("admin-panel/backend/app/drive", exist_ok=True)
shutil.copy(O + "drive_router.py", "admin-panel/backend/app/drive/router.py")
open("admin-panel/backend/app/drive/__init__.py", "a").close()

# Almacén: tabla de enlaces, prioridad del enlace en la búsqueda, blueprint registrado y exento del candado
p = "almacen/servicio/auth_webmail.py"
sustituir(p, "    # instalaciones previas a la columna email\n    ejecutar('ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT;')\n",
          """    # instalaciones previas a la columna email
    ejecutar('ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT;')
    # Vínculo explícito buzón -> persona del directorio central (lo fija el panel de administración):
    # manda sobre la coincidencia por correo. Para personas cuyo correo del directorio no es el buzón.
    ejecutar(\"\"\"
        CREATE TABLE IF NOT EXISTS enlaces_correo (
            correo     TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    \"\"\")
""")
sustituir(p, '''def _buscar_en_nomina(correo: str) -> tuple:
    """Modo nomina: el correo del buzón debe existir en el directorio central.
    Devuelve el MISMO id que usa el resto del sistema (un almacén por persona)."""
    filas = consultar("""
        SELECT id, role FROM usuarios
        WHERE LOWER(email) = %s AND active = TRUE
        ORDER BY id LIMIT 1
    """, (correo,), nomina=True)
''', '''def _buscar_en_nomina(correo: str) -> tuple:
    """Modo nomina: el correo del buzón debe existir en el directorio central.
    Devuelve el MISMO id que usa el resto del sistema (un almacén por persona).
    Primero el vínculo explícito fijado desde el panel (`enlaces_correo`); después la
    coincidencia por correo (y por dominio institucional equivalente)."""
    enlace = consultar('SELECT usuario_id FROM enlaces_correo WHERE correo = %s', (correo,))
    if enlace:
        filas = consultar("""
            SELECT id, role FROM usuarios WHERE id = %s AND active = TRUE
        """, (enlace[0]['usuario_id'],), nomina=True)
        if not filas:
            log.warning('Buzón %s vinculado a la persona %s, que no existe o está inactiva', correo, enlace[0]['usuario_id'])
            return None, None
        uid = filas[0]['id']
        rol = filas[0]['role'] or 'user'
        if correo in _ADMINS and rol not in ('master', 'master_admin'):
            rol = 'master'
        return uid, rol
    filas = consultar("""
        SELECT id, role FROM usuarios
        WHERE LOWER(email) = %s AND active = TRUE
        ORDER BY id LIMIT 1
    """, (correo,), nomina=True)
''')
p = "almacen/servicio/app_webmail.py"
sustituir(p, "    app.register_blueprint(bp_acceso_externo)   # /acceso-externo (login de cuentas externas)\n",
          "    app.register_blueprint(bp_acceso_externo)   # /acceso-externo (login de cuentas externas)\n"
          "    from api_panel import bp_panel\n"
          "    app.register_blueprint(bp_panel, url_prefix='/api/almacen/panel')   # canal del panel de administración\n")
s = leer(p)
assert "_EXENTAS" in s
import re
m = re.search(r"_EXENTAS\s*=\s*\(", s)
assert m, "_EXENTAS"
s = s[: m.end()] + "\n        '/api/almacen/panel/',   # canal del panel: su propio secreto (api_panel.py)" + s[m.end():]
escribir(p, s)

# cuota por defecto de instalaciones nuevas: 5 GB (campo libre en el panel)
sustituir("almacen/servicio/config_almacen.py", "CUOTA_DEFECTO_BYTES = int(os.getenv('ALMACEN_CUOTA_DEFECTO', 20 * 1024 ** 3))  # 20 GB por defecto",
          "CUOTA_DEFECTO_BYTES = int(os.getenv('ALMACEN_CUOTA_DEFECTO', 5 * 1024 ** 3))  # 5 GB por defecto (el master la cambia en Configuración)")
sustituir("almacen/servicio/config_almacen.py", "    (se guarda en config_kv); si no, 20 GB.", "    (se guarda en config_kv); si no, ALMACEN_CUOTA_DEFECTO o 5 GB.")
sustituir("almacen/.env.example", "#ALMACEN_CUOTA_DEFECTO=21474836480", "#ALMACEN_CUOTA_DEFECTO=5368709120   # 5 GB por persona (bytes); el master puede cambiarla en Configuración\n# Canal del panel de administración (mismo servidor, loopback): el panel vincula buzones a personas del\n# directorio y fija la cuota del Drive al crear el buzón. Mismo valor en admin-panel/backend/.env.\n#ALMACEN_SECRETO_PANEL=")

# Panel: ruta incluida
sustituir("admin-panel/backend/app/main.py", "from app.mailboxes.router import router as mailboxes_router\n",
          "from app.drive.router import router as drive_router\nfrom app.mailboxes.router import router as mailboxes_router\n")
sustituir("admin-panel/backend/app/main.py", "app.include_router(mailboxes_router)\n", "app.include_router(mailboxes_router)\napp.include_router(drive_router)\n")

# Instalador: secreto compartido en los dos .env
p = "deploy/webmail/instalar.sh"
s = leer(p)
assert "ADMIN_BHASH=" in s
ancla = "  ADMIN_BHASH="
i = s.index(ancla)
# insertar antes de la línea de ADMIN_BHASH (una sola vez)
s = s[:i] + """  # Canal panel -> Almacén (loopback, secreto propio): vincular buzones y cuota del Drive
  SECRETO_PANEL=$(openssl rand -hex 24)
  grep -q '^ALMACEN_SECRETO_PANEL=' "${APP_DIR}/almacen/.env" 2>/dev/null || echo "ALMACEN_SECRETO_PANEL=${SECRETO_PANEL}" >> "${APP_DIR}/almacen/.env"
""" + s[i:]
escribir(p, s)
s = leer(p)
# y en el .env del panel: buscamos dónde se escribe ADMIN_JWT_SECRET del panel
cand = [l for l in s.splitlines() if "admin-panel/backend/.env" in l and (">>" in l or "cat >" in l)]
assert cand, "no encuentro la escritura del .env del panel"
linea = cand[-1]
s = s.replace(linea, linea + "\n" + 'printf "ALMACEN_URL=http://127.0.0.1:8788\\nALMACEN_SECRETO_PANEL=%s\\n" "${SECRETO_PANEL}" >> "${APP_DIR}/admin-panel/backend/.env"', 1)
escribir(p, s)
print("aplicado (falta el frontend)")
