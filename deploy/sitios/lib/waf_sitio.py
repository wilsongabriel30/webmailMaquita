"""Cortafuegos de aplicaciones web por sitio: ModSecurity v3 (conector de nginx) con las reglas OWASP CRS completas.

Cada sitio tiene su archivo de reglas, generado a partir de su meta (meta["web"]["waf"]):

    /etc/maquita-sitios/waf/<dominio>.conf     lo carga el vhost con «modsecurity_rules_file»
    /var/log/nginx/sitios-waf/<dominio>.log    registro de auditoría del sitio (lo lee waf_bloqueos.py)

Ajustes (los de serie, si el sitio no tiene: bloquear, paranoia 1 y sin exclusiones):

    modo         «apagado» (sin ModSecurity), «detectar» (solo anota) o «bloquear»
    paranoia     1 o 2 (nivel de paranoia de CRS: 2 detecta más y da más falsos positivos)
    exclusiones  [{"regla": 942100, "ruta": "/wp-admin/admin-ajax.php" | null}] (hasta 50)

El archivo sigue el orden que exige CRS: configuración base del servidor, motor, registro, crs-setup, nivel de
paranoia, perfil de la aplicación (las excepciones de WordPress, Joomla y el catálogo de siempre, en
/etc/nginx/sitios-waf/perfil-*.conf), exclusiones por ruta (antes de las reglas), las reglas y, al final, las
exclusiones de todo el sitio (SecRuleRemoveById solo quita reglas ya definidas).

Los cambios se aplican con el mecanismo común de las funciones web (nginx_web.aplicar): copia previa, `nginx -t` y
marcha atrás si nginx los rechaza.
"""

import os
import re

from comun import ErrorSitio, leer_meta

CARPETA = "/etc/maquita-sitios/waf"
REGISTROS = "/var/log/nginx/sitios-waf"
SITIOS_WAF = "/etc/nginx/sitios-waf"
CRS_SETUP = "/etc/modsecurity/crs/crs-setup.conf"
CRS_ANTES = "/etc/modsecurity/crs/REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf"
CRS_REGLAS = "/usr/share/modsecurity-crs/rules/*.conf"
CRS_DESPUES = "/etc/modsecurity/crs/RESPONSE-999-EXCLUSION-RULES-AFTER-CRS.conf"
MODOS = ("apagado", "detectar", "bloquear")
PERFILES = ("general", "wordpress", "joomla", "aplicacion")
DE_SERIE = {"modo": "bloquear", "paranoia": 1, "exclusiones": []}
MAXIMO = 50
RE_RUTA = re.compile(r"/[A-Za-z0-9._~/-]{0,200}")
# Reglas que no se pueden excluir: la puesta en marcha de CRS y la evaluación de la puntuación. Para dejar de
# bloquear todo el sitio está el modo «detectar»; quitar estas reglas lo haría a escondidas.
PROTEGIDAS = ((900000, 901999), (949000, 949999), (959000, 959999), (980000, 980999))
ID_RUTA = 9101000  # identificadores de las reglas de exclusión por ruta: 9101000 + posición


def ruta(dominio):
    return os.path.join(CARPETA, f"{dominio}.conf")


def registro(dominio):
    return os.path.join(REGISTROS, f"{dominio}.log")


def perfil_de(meta):
    """Perfil de excepciones según la aplicación del sitio (el mismo de siempre)."""
    app = meta.get("app")
    if app in ("wordpress", "joomla"):
        return app
    if app == "paquete":
        return "aplicacion"
    if app and app != "propia":
        try:
            from apps import CATALOGO

            if app in CATALOGO:
                return "aplicacion"
        except ImportError:
            pass
    return "general"


def ajustes(meta):
    guardados = (meta.get("web") or {}).get("waf")
    return {**DE_SERIE, **guardados} if isinstance(guardados, dict) else dict(DE_SERIE)


# --- Validación ---


def _regla(valor):
    if isinstance(valor, bool) or not isinstance(valor, int) or not 900000 <= valor <= 999999:
        raise ErrorSitio("regla no válida: un número de regla de OWASP CRS (de 6 cifras, 9xxxxx)")
    if any(a <= valor <= b for a, b in PROTEGIDAS):
        raise ErrorSitio(f"la regla {valor} es de la puesta en marcha o de la puntuación de CRS y no se puede excluir: "
                         "para no bloquear, usa el modo «solo detectar»")
    return valor


def _ruta(valor):
    if valor in (None, ""):
        return None
    if not isinstance(valor, str) or not RE_RUTA.fullmatch(valor) or "/../" in valor + "/" or "//" in valor:
        raise ErrorSitio("ruta no válida: empieza por «/» y solo lleva letras sin tilde, números y . _ ~ / -")
    return valor


def validar(meta, datos):
    """Ajustes limpios (o None si son los de serie, para no guardar nada)."""
    if not isinstance(datos, dict) or set(datos) - {"modo", "paranoia", "exclusiones"}:
        raise ErrorSitio("datos del cortafuegos no válidos")
    modo = datos.get("modo", "bloquear")
    if modo not in MODOS:
        raise ErrorSitio("modo no válido: apagado, detectar o bloquear")
    paranoia = datos.get("paranoia", 1)
    if paranoia not in (1, 2) or isinstance(paranoia, bool):
        raise ErrorSitio("el nivel de paranoia es 1 o 2")
    lista = datos.get("exclusiones", [])
    if not isinstance(lista, list) or len(lista) > MAXIMO:
        raise ErrorSitio(f"se admiten hasta {MAXIMO} exclusiones")
    exclusiones = []
    for e in lista:
        if not isinstance(e, dict) or set(e) - {"regla", "ruta"}:
            raise ErrorSitio("exclusión no válida")
        limpia = {"regla": _regla(e.get("regla")), "ruta": _ruta(e.get("ruta"))}
        if limpia not in exclusiones:
            exclusiones.append(limpia)
    limpio = {"modo": modo, "paranoia": paranoia, "exclusiones": exclusiones}
    return None if limpio == DE_SERIE else limpio


# --- Generación ---


def texto(meta):
    """Contenido del archivo de reglas del sitio, o None si el cortafuegos está apagado."""
    a = ajustes(meta)
    if a["modo"] == "apagado":
        return None
    lineas = ["# Generado por maquita-sitios (panel → Sitios web → Cortafuegos). No editar a mano.",
              f"Include {SITIOS_WAF}/base.conf",
              "SecRuleEngine " + ("On" if a["modo"] == "bloquear" else "DetectionOnly"),
              f"SecAuditLog {registro(meta['dominio'])}",
              f"Include {CRS_SETUP}"]
    if a["paranoia"] == 2:
        # CRS 3.3 usa tx.paranoia_level; CRS 4, tx.blocking_paranoia_level. Antes de la regla 901 de CRS.
        lineas.append('SecAction "id:9100010,phase:1,nolog,pass,t:none,setvar:tx.paranoia_level=2,'
                      'setvar:tx.blocking_paranoia_level=2"')
    lineas.append(f"Include {SITIOS_WAF}/perfil-{perfil_de(meta)}.conf")
    globales = []
    for i, e in enumerate(a["exclusiones"]):
        regla = _regla(e["regla"])
        if e.get("ruta"):
            lineas.append(f'SecRule REQUEST_FILENAME "@beginsWith {_ruta(e["ruta"])}" '
                          f'"id:{ID_RUTA + i},phase:1,nolog,pass,t:none,ctl:ruleRemoveById={regla}"')
        elif regla not in globales:
            globales.append(regla)
    lineas += [f"Include {CRS_ANTES}", f"Include {CRS_REGLAS}", f"Include {CRS_DESPUES}"]
    lineas += [f"SecRuleRemoveById {r}" for r in globales]
    return "\n".join(lineas) + "\n"


def directivas(meta):
    """Lo que va en el server{} del vhost."""
    if ajustes(meta)["modo"] == "apagado":
        return "    # Cortafuegos de aplicación web apagado para este sitio (panel → Cortafuegos).\n    modsecurity off;\n"
    return ("    # Cortafuegos de aplicación web (OWASP CRS), con las excepciones propias de la aplicación y los ajustes\n"
            "    # del sitio (panel → Cortafuegos).\n"
            f"    modsecurity on;\n    modsecurity_rules_file {ruta(meta['dominio'])};\n")


def escribir(meta):
    """Escribe (o quita) el archivo de reglas del sitio y prepara su registro. Antes que el vhost."""
    contenido = texto(meta)
    destino = ruta(meta["dominio"])
    if contenido is None:
        if os.path.exists(destino):
            os.remove(destino)
        return
    os.makedirs(CARPETA, mode=0o755, exist_ok=True)
    tmp = destino + ".tmp"
    with open(tmp, "w") as f:
        f.write(contenido)
    os.chmod(tmp, 0o644)
    os.replace(tmp, destino)
    _preparar_registro(meta["dominio"])


def _preparar_registro(dominio):
    os.makedirs(REGISTROS, mode=0o750, exist_ok=True)
    archivo = registro(dominio)
    if not os.path.exists(archivo):
        os.close(os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o640))
    try:
        import grp
        import pwd

        uid, gid = pwd.getpwnam("www-data").pw_uid, grp.getgrnam("adm").gr_gid
        os.chown(REGISTROS, uid, gid)
        os.chown(archivo, uid, gid, follow_symlinks=False)
    except (KeyError, PermissionError):
        pass  # pruebas sin root o sistema sin esos usuarios


def quitar(dominio):
    for archivo in (ruta(dominio), registro(dominio)):
        if os.path.lexists(archivo):
            os.remove(archivo)


# --- Órdenes ---


def ver(dominio):
    meta = leer_meta(dominio)
    return {"dominio": dominio, "perfil": perfil_de(meta), **ajustes(meta), "maximo": MAXIMO,
            "modos": list(MODOS)}


def guardar(dominio, datos):
    import nginx_web

    meta = leer_meta(dominio)
    limpio = validar(meta, datos)
    nginx_web.aplicar(dominio, "waf", limpio, extra_rutas=[ruta(dominio)])
    return ver(dominio)
