"""Entrada directa a phpMyAdmin o Adminer desde el panel, sin volver a escribir usuario y contraseña.

Las contraseñas de las bases no se guardan en ningún sitio. Cada «Entrar» crea un usuario temporal con los
mismos permisos que el de la base, que vence a las 2 horas, y un vale de un solo uso (60 s) que lee
/herramientas/adminer/entrar.php para abrir la herramienta ya conectada. El trabajo programado de los sitios
borra los usuarios vencidos.

- MariaDB: usuario «pv_…»@localhost con todos los permisos sobre esa base y nada más.
- PostgreSQL: rol «pv_…» miembro del dueño de la base, con VALID UNTIL y «SET ROLE» al dueño, así lo que cree
  queda a nombre del dueño y el rol temporal se puede borrar sin dejar nada huérfano.
"""

import json
import os
import re
import secrets
import time

from comun import ErrorSitio, clave, leer_meta

VALES = "/var/lib/herramientas-bd/vales"
TEMPORALES = "/var/lib/maquita-sitios/usuarios-temporales.json"
DURACION = 2 * 3600


def _leer():
    try:
        with open(TEMPORALES) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _guardar(lista):
    tmp = TEMPORALES + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(lista, f)
    os.replace(tmp, TEMPORALES)


def _base(meta, nombre):
    if nombre == meta.get("bd"):
        return "mariadb"
    for b in meta.get("bases", []):
        if b["nombre"] == nombre:
            return b["motor"]
    raise ErrorSitio("esa base no es de este sitio")


def entrar(dominio, nombre, herramienta):
    import pwd

    from aplicaciones import _mariadb
    from bases import _pg

    if herramienta not in ("phpmyadmin", "adminer"):
        raise ErrorSitio("herramienta no válida")
    meta = leer_meta(dominio)
    motor = _base(meta, nombre)
    if motor == "postgresql" and herramienta == "phpmyadmin":
        raise ErrorSitio("phpMyAdmin solo abre bases MariaDB: use Adminer")
    limpiar()
    usuario = "pv_" + secrets.token_hex(6)
    contrasena = clave(24).replace("'", "")
    vence = int(time.time()) + DURACION
    if motor == "mariadb":
        _mariadb(f"CREATE USER '{usuario}'@'localhost' IDENTIFIED BY '{contrasena}';"
                 f"GRANT ALL PRIVILEGES ON `{nombre}`.* TO '{usuario}'@'localhost';")
        servidor = "localhost"
    else:
        hasta = time.strftime("%Y-%m-%d %H:%M:%S%z", time.localtime(vence))
        _pg(f"CREATE ROLE \"{usuario}\" LOGIN PASSWORD '{contrasena}' VALID UNTIL '{hasta}' IN ROLE \"{nombre}\";\n"
            f"ALTER ROLE \"{usuario}\" SET role = \"{nombre}\";\n")
        servidor = "127.0.0.1"
    lista = _leer()
    lista.append({"usuario": usuario, "motor": motor, "base": nombre, "vence": vence})
    _guardar(lista)
    vale = secrets.token_urlsafe(24)
    datos = {"herramienta": herramienta, "motor": motor, "servidor": servidor, "usuario": usuario,
             "clave": contrasena, "base": nombre, "vence": int(time.time()) + 60}
    os.makedirs(VALES, mode=0o700, exist_ok=True)
    ruta = os.path.join(VALES, vale)
    with open(os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        json.dump(datos, f)
    cuenta = pwd.getpwnam("herramientas-bd")
    os.chown(ruta, cuenta.pw_uid, cuenta.pw_gid)
    return {"url": f"/herramientas/adminer/entrar.php?vale={vale}", "valido_segundos": 60, "usuario_temporal": usuario,
            "vence": time.strftime("%H:%M", time.localtime(vence))}


def limpiar():
    """Borra los usuarios temporales vencidos y los vales sin usar (lo llama el trabajo programado)."""
    from aplicaciones import _mariadb
    from bases import _pg

    ahora = time.time()
    quedan, borrados = [], []
    for t in _leer():
        if t["vence"] > ahora:
            quedan.append(t)
            continue
        if not re.fullmatch(r"pv_[0-9a-f]{12}", t["usuario"]):
            continue
        try:
            if t["motor"] == "mariadb":
                _mariadb(f"DROP USER IF EXISTS '{t['usuario']}'@'localhost';")
            else:
                try:
                    _pg(f"REASSIGN OWNED BY \"{t['usuario']}\" TO \"{t['base']}\";\nDROP OWNED BY \"{t['usuario']}\";\n"
                        f"DROP ROLE IF EXISTS \"{t['usuario']}\";\n", base=t["base"])
                except ErrorSitio:
                    _pg(f"DROP ROLE IF EXISTS \"{t['usuario']}\";\n")  # la base ya no existe
            borrados.append(t["usuario"])
        except ErrorSitio:
            quedan.append(t)  # se reintenta en la próxima pasada
    _guardar(quedan)
    if os.path.isdir(VALES):
        for vale in os.listdir(VALES):
            ruta = os.path.join(VALES, vale)
            if ahora - os.path.getmtime(ruta) > 120:
                os.remove(ruta)
    return borrados
