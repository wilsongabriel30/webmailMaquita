"""Permisos de los usuarios adicionales de una base (MariaDB y PostgreSQL) y el SQL que los aplica.

Aquí no se ejecuta nada: solo se valida y se arma el texto. Todos los identificadores (base, usuario, dueño) pasan
por `ident()` (re.fullmatch sobre [a-z0-9_]) antes de ir entre comillas, y los privilegios salen SIEMPRE de las
listas cerradas de este módulo: ningún texto de la persona llega al SQL tal cual.

Permisos que se pueden elegir:
  lectura      ver datos (SELECT)
  escritura    lectura + añadir, cambiar y borrar filas
  estructura   escritura + crear, cambiar y borrar tablas, índices y vistas
  todo         todos los permisos sobre esa base (y solo sobre esa)
  medida       una lista fina de los privilegios de PRIVILEGIOS[motor]

En PostgreSQL «todo» hace al usuario miembro del rol dueño de la base (como los usuarios temporales de Adminer):
lo que cree queda a nombre del dueño y se puede borrar el usuario sin dejar nada huérfano.
"""

import re

from comun import ErrorSitio

RE_IDENT = re.compile(r"[a-z][a-z0-9_]{0,62}")
PERFILES = ("lectura", "escritura", "estructura", "todo", "medida")

PRIVILEGIOS = {
    "mariadb": ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "INDEX", "ALTER", "REFERENCES",
                "CREATE TEMPORARY TABLES", "LOCK TABLES", "EXECUTE", "CREATE VIEW", "SHOW VIEW", "CREATE ROUTINE",
                "ALTER ROUTINE", "EVENT", "TRIGGER"),
    # Sobre las tablas del esquema «public», más CREATE (crear objetos en el esquema) y TEMPORARY (tablas temporales).
    "postgresql": ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "CREATE", "TEMPORARY"),
}

_LECTURA = {"mariadb": ("SELECT", "SHOW VIEW"), "postgresql": ("SELECT",)}
_ESCRITURA = {"mariadb": _LECTURA["mariadb"] + ("INSERT", "UPDATE", "DELETE", "LOCK TABLES", "CREATE TEMPORARY TABLES",
                                                "EXECUTE"),
              "postgresql": ("SELECT", "INSERT", "UPDATE", "DELETE", "TEMPORARY")}
_ESTRUCTURA = {"mariadb": _ESCRITURA["mariadb"] + ("CREATE", "DROP", "INDEX", "ALTER", "REFERENCES", "CREATE VIEW",
                                                   "TRIGGER"),
               "postgresql": _ESCRITURA["postgresql"] + ("TRUNCATE", "REFERENCES", "TRIGGER", "CREATE")}
_DE_PERFIL = {"lectura": _LECTURA, "escritura": _ESCRITURA, "estructura": _ESTRUCTURA}
_TABLAS_PG = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def ident(nombre):
    """Identificador seguro (minúsculas, números y «_», empezando por letra) o ErrorSitio."""
    if not isinstance(nombre, str) or not RE_IDENT.fullmatch(nombre):
        raise ErrorSitio("nombre no válido")
    return nombre


def validar(motor, permisos):
    """{"perfil": …[, "lista": […]]} limpio, o ErrorSitio. La lista se ordena como en PRIVILEGIOS."""
    if motor not in PRIVILEGIOS:
        raise ErrorSitio("motor no válido")
    if not isinstance(permisos, dict) or set(permisos) - {"perfil", "lista"}:
        raise ErrorSitio("permisos no válidos")
    perfil = permisos.get("perfil")
    if perfil not in PERFILES:
        raise ErrorSitio("permisos no válidos: lectura, escritura, estructura, todo o medida")
    if perfil != "medida":
        return {"perfil": perfil}
    lista = permisos.get("lista")
    if not isinstance(lista, list) or not lista or len(lista) > len(PRIVILEGIOS[motor]):
        raise ErrorSitio("elige al menos un permiso de la lista")
    desconocidos = [p for p in lista if p not in PRIVILEGIOS[motor]]
    if desconocidos:
        raise ErrorSitio(f"permiso no disponible en este motor: {str(desconocidos[0])[:40]}")
    return {"perfil": "medida", "lista": [p for p in PRIVILEGIOS[motor] if p in lista]}


def lista_de(motor, permisos):
    """Privilegios concretos de unos permisos ya validados (para «todo» en MariaDB: ALL PRIVILEGES)."""
    perfil = permisos["perfil"]
    if perfil == "medida":
        return list(permisos["lista"])
    if perfil == "todo":
        return ["ALL PRIVILEGES"] if motor == "mariadb" else ["MIEMBRO"]
    return list(_DE_PERFIL[perfil][motor])


# --- MariaDB ---


def cuenta_mariadb(usuario, host):
    """'usuario'@'host' con los dos ya comprobados (el host sale de bases_remoto o es «localhost»)."""
    if host != "localhost" and not re.fullmatch(r"[0-9a-f:.]{2,45}(/[0-9.]{7,15})?", host):
        raise ErrorSitio("origen no válido")
    return f"'{ident(usuario)}'@'{host}'"


def mariadb_conceder(base, usuario, host, permisos):
    """Quita todo lo que tuviera esa cuenta y concede exactamente los permisos elegidos sobre `base`.*."""
    cuenta = cuenta_mariadb(usuario, host)
    privilegios = ", ".join(lista_de("mariadb", permisos))
    return (f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {cuenta};"
            f"GRANT {privilegios} ON `{ident(base)}`.* TO {cuenta};")


# --- PostgreSQL (se ejecuta conectado a la propia base) ---


def pg_quitar(base, usuario, dueno):
    u, b, d = ident(usuario), ident(base), ident(dueno)
    return (f'REVOKE ALL ON DATABASE "{b}" FROM "{u}";\n'
            f'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM "{u}";\n'
            f'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM "{u}";\n'
            f'REVOKE ALL ON SCHEMA public FROM "{u}";\n'
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{d}" IN SCHEMA public REVOKE ALL ON TABLES FROM "{u}";\n'
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{d}" IN SCHEMA public REVOKE ALL ON SEQUENCES FROM "{u}";\n'
            f'REVOKE "{d}" FROM "{u}";\n'
            f'ALTER ROLE "{u}" IN DATABASE "{b}" RESET role;\n')


def pg_conceder(base, usuario, dueno, permisos):
    """Quita lo que tuviera y concede los permisos elegidos (también para las tablas que se creen después)."""
    u, b, d = ident(usuario), ident(base), ident(dueno)
    lista = lista_de("postgresql", permisos)
    sql = pg_quitar(b, u, d) + f'GRANT CONNECT ON DATABASE "{b}" TO "{u}";\n'
    if lista == ["MIEMBRO"]:
        return sql + f'GRANT "{d}" TO "{u}";\nALTER ROLE "{u}" IN DATABASE "{b}" SET role = "{d}";\n'
    if "TEMPORARY" in lista:
        sql += f'GRANT TEMPORARY ON DATABASE "{b}" TO "{u}";\n'
    sql += f'GRANT USAGE{", CREATE" if "CREATE" in lista else ""} ON SCHEMA public TO "{u}";\n'
    tablas = [p for p in _TABLAS_PG if p in lista]
    if tablas:
        texto = ", ".join(tablas)
        sql += (f'GRANT {texto} ON ALL TABLES IN SCHEMA public TO "{u}";\n'
                f'ALTER DEFAULT PRIVILEGES FOR ROLE "{d}" IN SCHEMA public GRANT {texto} ON TABLES TO "{u}";\n')
    secuencias = ["USAGE", "SELECT"] + (["UPDATE"] if "UPDATE" in lista or "INSERT" in lista else [])
    if "SELECT" in lista or "INSERT" in lista:
        texto = ", ".join(secuencias)
        sql += (f'GRANT {texto} ON ALL SEQUENCES IN SCHEMA public TO "{u}";\n'
                f'ALTER DEFAULT PRIVILEGES FOR ROLE "{d}" IN SCHEMA public GRANT {texto} ON SEQUENCES TO "{u}";\n')
    return sql
