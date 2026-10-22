"""Usuarios adicionales de las bases de un sitio, con permisos a medida y acceso remoto opcional.

Cada usuario es de UNA base del sitio (la de la aplicación o una adicional) y se llama «u_<sitio>_<sufijo>»: el
prefijo lo pone el servidor, la persona solo elige el sufijo. La contraseña la genera el servidor y se muestra una
vez; no se guarda en ningún sitio. Lo que sí se guarda en el meta del sitio (meta["bases_usuarios"]):

    {"usuario", "base", "motor", "permisos": {"perfil"[, "lista"]}, "remoto": [redes], "creado"}

Al borrar una base se borran antes sus usuarios (bases.borrar llama a borrar_de_base).
"""

import re
import time

import bases_privilegios as bp
import bases_remoto as br
from comun import ErrorSitio, clave, guardar_meta, leer_meta, slug

MAXIMO = 20
RE_SUFIJO = re.compile(r"[a-z][a-z0-9]{1,9}")
RE_HASH_MARIADB = re.compile(r"\*[0-9A-F]{40}")


def _sql_mariadb(sql):
    from aplicaciones import _mariadb

    _mariadb(sql)


def _sql_pg(sql, base="postgres"):
    from bases import _pg

    _pg(sql, base=base)


def _valor_mariadb(sql):
    from bases import _mariadb_valor

    return _mariadb_valor(sql)


# --- Datos del sitio ---


def bases_del_sitio(meta):
    """{nombre: motor} de las bases del sitio (la de la aplicación es MariaDB)."""
    salida = {meta["bd"]: "mariadb"} if meta.get("bd") else {}
    salida.update({b["nombre"]: b["motor"] for b in meta.get("bases", [])})
    return salida


def _usuario_de(meta, usuario):
    if not isinstance(usuario, str) or not re.fullmatch(r"u_[a-z0-9]+_[a-z][a-z0-9]{1,9}", usuario):
        raise ErrorSitio("usuario no válido")
    u = next((u for u in meta.get("bases_usuarios", []) if u["usuario"] == usuario), None)
    if not u:
        raise ErrorSitio("ese usuario no es de este sitio")
    return u


def _dueno(meta, u):
    """Rol dueño de una base PostgreSQL del sitio: el de su mismo nombre (lo crea bases.crear)."""
    return u["base"]


def _hosts(u):
    return ["localhost"] + [br.host_mariadb(r) for r in u.get("remoto") or []]


def _publico(u):
    return {k: u.get(k) for k in ("usuario", "base", "motor", "permisos", "remoto", "creado")}


def listar(dominio):
    meta = leer_meta(dominio)
    servidor = br.servidor()
    return {"dominio": dominio, "maximo": MAXIMO, "bases": [{"nombre": n, "motor": m} for n, m in bases_del_sitio(meta).items()],
            "usuarios": [_publico(u) for u in meta.get("bases_usuarios", [])],
            "privilegios": {m: list(p) for m, p in bp.PRIVILEGIOS.items()},
            "remoto": servidor, "maximo_redes": br.MAXIMO}


def _conexion(meta, u, contrasena=None):
    servidor = br.servidor()
    datos = {"usuario": u["usuario"], "base": u["base"], "motor": u["motor"],
             "servidor": "localhost" if u["motor"] == "mariadb" else "127.0.0.1", "puerto": br.PUERTOS[u["motor"]]}
    if u.get("remoto") and servidor["host"]:
        datos["servidor_remoto"] = servidor["host"]
        datos["tls"] = "obligatorio"
    if contrasena:
        datos["clave"] = contrasena
    return datos


# --- Órdenes ---


def crear(dominio, base, sufijo, permisos):
    meta = leer_meta(dominio)
    motor = bases_del_sitio(meta).get(base)
    if not motor:
        raise ErrorSitio("esa base no es de este sitio")
    if not isinstance(sufijo, str) or not RE_SUFIJO.fullmatch(sufijo):
        raise ErrorSitio("nombre no válido: de 2 a 10 minúsculas o números, empezando por una letra")
    usuarios = meta.setdefault("bases_usuarios", [])
    if len(usuarios) >= MAXIMO:
        raise ErrorSitio(f"como máximo {MAXIMO} usuarios de bases por sitio")
    usuario = bp.ident(f"u_{slug(meta['dominio'])}_{sufijo}")
    if any(u["usuario"] == usuario for u in usuarios):
        raise ErrorSitio(f"el usuario {usuario} ya existe")
    permisos = bp.validar(motor, permisos)
    contrasena = clave(24).replace("'", "")
    if motor == "mariadb":
        cuenta = bp.cuenta_mariadb(usuario, "localhost")
        _sql_mariadb(f"CREATE USER {cuenta} IDENTIFIED BY '{contrasena}';"
                     + bp.mariadb_conceder(base, usuario, "localhost", permisos) + "FLUSH PRIVILEGES;")
    else:
        _sql_pg(f"CREATE ROLE \"{usuario}\" LOGIN PASSWORD '{contrasena}';\n")
        try:
            _sql_pg(bp.pg_conceder(base, usuario, base, permisos), base=base)
        except ErrorSitio:
            _sql_pg(f'DROP ROLE IF EXISTS "{usuario}";\n')
            raise
    u = {"usuario": usuario, "base": base, "motor": motor, "permisos": permisos, "remoto": [],
         "creado": time.strftime("%Y-%m-%d %H:%M")}
    usuarios.append(u)
    guardar_meta(meta)
    return {**listar(dominio), "creado": _conexion(meta, u, contrasena)}


def cambiar_permisos(dominio, usuario, permisos):
    meta = leer_meta(dominio)
    u = _usuario_de(meta, usuario)
    permisos = bp.validar(u["motor"], permisos)
    if u["motor"] == "mariadb":
        _sql_mariadb("".join(bp.mariadb_conceder(u["base"], usuario, h, permisos) for h in _hosts(u)) + "FLUSH PRIVILEGES;")
    else:
        _sql_pg(bp.pg_conceder(u["base"], usuario, _dueno(meta, u), permisos), base=u["base"])
    u["permisos"] = permisos
    guardar_meta(meta)
    return listar(dominio)


def nueva_clave(dominio, usuario):
    meta = leer_meta(dominio)
    u = _usuario_de(meta, usuario)
    contrasena = clave(24).replace("'", "")
    if u["motor"] == "mariadb":
        _sql_mariadb("".join(f"ALTER USER {bp.cuenta_mariadb(usuario, h)} IDENTIFIED BY '{contrasena}';" for h in _hosts(u)))
    else:
        _sql_pg(f"ALTER ROLE \"{bp.ident(usuario)}\" PASSWORD '{contrasena}';\n")
    return {**listar(dominio), "creado": _conexion(meta, u, contrasena)}


def _borrar_en_motor(meta, u):
    usuario = bp.ident(u["usuario"])
    if u["motor"] == "mariadb":
        _sql_mariadb("".join(f"DROP USER IF EXISTS {bp.cuenta_mariadb(usuario, h)};" for h in _hosts(u)))
        return
    dueno = bp.ident(_dueno(meta, u))
    try:
        _sql_pg(f'REASSIGN OWNED BY "{usuario}" TO "{dueno}";\nDROP OWNED BY "{usuario}";\n', base=u["base"])
    except ErrorSitio:
        pass  # la base ya no existe: no hay nada suyo que reasignar
    _sql_pg(f'DROP ROLE IF EXISTS "{usuario}";\n')


def borrar(dominio, usuario):
    meta = leer_meta(dominio)
    u = _usuario_de(meta, usuario)
    tenia_remoto = bool(u.get("remoto"))
    _borrar_en_motor(meta, u)
    meta["bases_usuarios"] = [x for x in meta["bases_usuarios"] if x["usuario"] != usuario]
    guardar_meta(meta)
    if tenia_remoto:
        _publicar_remoto(meta, u["motor"])
    return listar(dominio)


def borrar_de_base(meta, base):
    """Antes de borrar una base: sus usuarios adicionales (y sus reglas de acceso remoto). Guarda el meta."""
    suyos = [u for u in meta.get("bases_usuarios", []) if u["base"] == base]
    if not suyos:
        return
    for u in suyos:
        _borrar_en_motor(meta, u)
    meta["bases_usuarios"] = [u for u in meta["bases_usuarios"] if u["base"] != base]
    guardar_meta(meta)
    for motor in {u["motor"] for u in suyos if u.get("remoto")}:
        _publicar_remoto(meta, motor)


def remoto(dominio, usuario, lista, amplia=False):
    """Cambia la lista de IP o redes desde las que ese usuario puede entrar (con TLS). Lista vacía: solo local."""
    meta = leer_meta(dominio)
    u = _usuario_de(meta, usuario)
    nuevas = br.redes(lista, amplia)
    if nuevas:
        br.exigir_servidor(u["motor"])
    if u["motor"] == "mariadb":
        hosts_nuevos = [br.host_mariadb(r) for r in nuevas]  # antes de tocar nada: IPv6 con máscara, fuera
        _mariadb_remoto(u, hosts_nuevos)
    u["remoto"] = nuevas
    guardar_meta(meta)
    estado = _publicar_remoto(meta, u["motor"])
    return {**listar(dominio), "cortafuegos": estado}


def _mariadb_remoto(u, hosts_nuevos):
    """Rehace las cuentas remotas del usuario con el hash de su clave de localhost, sus permisos y REQUIRE SSL."""
    usuario = bp.ident(u["usuario"])
    sql = "".join(f"DROP USER IF EXISTS {bp.cuenta_mariadb(usuario, h)};" for h in _hosts(u)[1:])
    if hosts_nuevos:
        huella = _valor_mariadb("SELECT JSON_VALUE(Priv, '$.authentication_string') FROM mysql.global_priv "
                                f"WHERE User = '{usuario}' AND Host = 'localhost';").strip()
        if not RE_HASH_MARIADB.fullmatch(huella):
            raise ErrorSitio("no se pudo copiar la clave del usuario a las cuentas remotas: genera una clave nueva "
                             "y vuelve a intentarlo")
        for h in hosts_nuevos:
            cuenta = bp.cuenta_mariadb(usuario, h)
            sql += (f"CREATE USER {cuenta} IDENTIFIED BY PASSWORD '{huella}' REQUIRE SSL;"
                    + bp.mariadb_conceder(u["base"], usuario, h, u["permisos"]))
    _sql_mariadb(sql + "FLUSH PRIVILEGES;")


def _publicar_remoto(meta, motor):
    if motor == "postgresql":
        br.publicar_hba()
    return br.publicar_cortafuegos(meta)
