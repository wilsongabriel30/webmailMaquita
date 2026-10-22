"""Importar cuentas de correo desde un archivo CSV: lectura, reglas fila a fila y exportación.

Módulo puro (solo la biblioteca estándar) y COMPARTIDO: el panel general
(admin-panel/backend/app/importar_cuentas/formato_csv.py) y el portal de dominio
(panel-dominio/backend/app/importar/formato_csv.py) llevan una copia idéntica, y una prueba
comprueba que no se separen. Lo que depende de la base (qué dominios hay, qué direcciones ya
están ocupadas, cuántas cuentas quedan) lo reúne cada panel y lo pasa a `revisar`.

Columnas: correo, nombre, clave (opcional: si falta se genera), cuota_mb (opcional) y alias
(opcional, separados por punto y coma). El separador del archivo puede ser coma o punto y coma
(Excel en español guarda con punto y coma).
"""

import csv
import io
import re
import secrets
import unicodedata

MAX_FILAS = 2000
MAX_BYTES = 1024 * 1024
MAX_ALIAS_POR_CUENTA = 20
MIB = 1024 * 1024
CLAVE_MINIMA = 10
CLAVE_MAXIMA = 128

# Nombre de columna (sin tildes, en minúsculas) → campo. Se admiten los nombres en inglés que
# exportan otros paneles para no obligar a renombrar la cabecera.
COLUMNAS = {
    "correo": "correo", "email": "correo", "direccion": "correo", "username": "correo",
    "nombre": "nombre", "name": "nombre",
    "clave": "clave", "contrasena": "clave", "password": "clave",
    "cuota_mb": "cuota_mb", "cuota": "cuota_mb", "quota_mb": "cuota_mb",
    "alias": "alias", "aliases": "alias",
}
OBLIGATORIAS = ("correo", "nombre")
ADMITIDAS = "correo, nombre, clave, cuota_mb, alias"

_LOCAL = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?")
_DOMINIO = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_CUOTA = re.compile(r"[0-9]{1,8}")
# Lo que una hoja de cálculo interpreta como fórmula al abrir el CSV (OWASP: CSV injection).
_FORMULA = ("=", "+", "-", "@", "\t", "\r")


class ErrorArchivo(ValueError):
    """El archivo entero no se puede leer: no hay filas que revisar."""


def _nombre_columna(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[\s-]+", "_", sin_tildes.strip().lower())


def direccion_valida(direccion: str) -> str | None:
    """Mensaje de error, o None si la dirección tiene la forma usuario@dominio admitida."""
    if direccion.count("@") != 1:
        return "debe tener la forma usuario@dominio"
    local, dominio = direccion.split("@")
    if not _LOCAL.fullmatch(local) or ".." in local:
        return "el nombre de la cuenta solo admite letras, números, punto, guion y guion bajo"
    if not _DOMINIO.fullmatch(dominio) or ".." in dominio or "." not in dominio:
        return "el dominio no es válido"
    return None


def problema_clave(clave: str, direccion: str = "") -> str | None:
    """La política de contraseñas de las cuentas del portal (validacion.exigir_clave_fuerte)."""
    if len(clave) < CLAVE_MINIMA:
        return f"La contraseña debe tener al menos {CLAVE_MINIMA} caracteres"
    if len(clave) > CLAVE_MAXIMA:
        return "La contraseña es demasiado larga"
    clases = sum(bool(re.search(p, clave)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if clases < 3:
        return "La contraseña debe combinar al menos tres de: minúsculas, mayúsculas, números y símbolos"
    local = direccion.split("@")[0]
    if len(local) >= 4 and local in clave.lower():
        return "La contraseña no puede contener el nombre de la cuenta"
    return None


def generar_clave(direccion: str = "") -> str:
    """16 caracteres con las cuatro clases. Empieza por letra o número: así nunca se confunde
    con una fórmula al abrir el CSV de contraseñas, ni hay que escaparla (lo que la cambiaría)."""
    letras, mayus, numeros, simbolos = "abcdefghijkmnpqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789", ".-_+*"
    todo = letras + mayus + numeros + simbolos
    while True:
        partes = [secrets.choice(c) for c in (letras, mayus, numeros, simbolos)]
        partes += [secrets.choice(todo) for _ in range(11)]
        secrets.SystemRandom().shuffle(partes)
        clave = secrets.choice(letras + mayus + numeros) + "".join(partes)
        if problema_clave(clave, direccion) is None:
            return clave


def _alias(valor: str, errores: list[str]) -> list[str]:
    lista = []
    for a in re.split(r"[;,\s]+", valor.strip().lower()):
        if a and a not in lista:
            lista.append(a)
    if len(lista) > MAX_ALIAS_POR_CUENTA:
        errores.append(f"Demasiados alias (máximo {MAX_ALIAS_POR_CUENTA} por cuenta)")
        return []
    for a in lista:
        problema = direccion_valida(a)
        if problema:
            errores.append(f"El alias «{a}» no es válido: {problema}")
    return lista


def _fila(numero: int, campos: dict, sobrantes: list[str]) -> dict:
    errores = []
    if any(s.strip() for s in sobrantes):
        errores.append("La fila tiene más columnas que la cabecera")
    correo = campos.get("correo", "").strip().lower()
    if not correo:
        errores.append("Falta el correo")
    elif direccion_valida(correo):
        errores.append(f"El correo {direccion_valida(correo)}")
    nombre = _CONTROL.sub(" ", campos.get("nombre", "")).strip()[:255]
    if not nombre:
        errores.append("Falta el nombre")
    clave = campos.get("clave", "").strip() or None
    if clave and _CONTROL.search(clave):
        errores.append("La contraseña tiene caracteres no válidos")
    cuota_mb = None
    texto_cuota = campos.get("cuota_mb", "").strip()
    if texto_cuota:
        if not _CUOTA.fullmatch(texto_cuota):
            errores.append("La cuota debe ser un número entero de MB")
        elif int(texto_cuota) <= 0:
            errores.append("La cuota debe ser mayor que cero")
        else:
            cuota_mb = int(texto_cuota)
    alias = _alias(campos.get("alias", ""), errores)
    if correo in alias:
        errores.append("Un alias no puede ser el propio correo")
    return {"fila": numero, "correo": correo, "nombre": nombre, "clave": clave, "cuota_mb": cuota_mb,
            "alias": alias, "errores": errores}


def leer(texto) -> list[dict]:
    """Filas del archivo con sus errores de forma. Lanza ErrorArchivo si no se puede leer entero."""
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorArchivo("El archivo está vacío")
    if len(texto.encode("utf-8", "replace")) > MAX_BYTES:
        raise ErrorArchivo(f"El archivo pesa más de {MAX_BYTES // 1024} KB")
    if "�" in texto or "\x00" in texto:
        raise ErrorArchivo("El archivo no es texto en UTF-8: guárdalo como «CSV UTF-8» y vuelve a intentarlo")
    texto = texto.lstrip("﻿")
    primera = texto.splitlines()[0]
    separador = ";" if primera.count(";") > primera.count(",") else ","
    lector = csv.reader(io.StringIO(texto, newline=""), delimiter=separador, strict=True)
    try:
        cabecera = next(lector)
        columnas = []
        for c in cabecera:
            campo = COLUMNAS.get(_nombre_columna(c))
            if not campo:
                raise ErrorArchivo(f"Columna desconocida: «{c.strip()[:40]}». Las admitidas son: {ADMITIDAS}")
            if campo in columnas:
                raise ErrorArchivo(f"La columna «{campo}» está repetida")
            columnas.append(campo)
        faltan = [c for c in OBLIGATORIAS if c not in columnas]
        if faltan:
            raise ErrorArchivo("Faltan columnas obligatorias: " + ", ".join(faltan))
        filas = []
        for registro in lector:
            if not any(c.strip() for c in registro):
                continue
            if len(filas) >= MAX_FILAS:
                raise ErrorArchivo(f"El archivo tiene más de {MAX_FILAS} filas: divídelo en varios")
            campos = dict(zip(columnas, registro))
            filas.append(_fila(lector.line_num, campos, registro[len(columnas):]))
    except csv.Error:
        raise ErrorArchivo(f"El archivo no es un CSV válido (línea {lector.line_num}): revisa las comillas")
    if not filas:
        raise ErrorArchivo("El archivo no tiene filas debajo de la cabecera")
    return filas


def revisar(filas: list[dict], dominios: dict, ocupadas: set, ajeno: str, pendientes: dict | None = None) -> list[dict]:
    """Aplica las reglas que dependen del servidor y deja en cada fila `cuota` (bytes) y `valida`.

    dominios: {dominio: {"activo", "enrutado", "max_cuentas", "cuentas", "max_alias", "alias",
               "cuota_maxima" (bytes o None = sin tope), "cuota_defecto" (bytes)}}; un dominio que
               no está (no existe o no es de quien importa) recibe el mensaje `ajeno`.
    ocupadas:  direcciones que ya son cuenta, alias o grupo.
    pendientes: {"cuentas": {dominio: n}, "alias": {dominio: n}} ya contadas en bloques anteriores
                del mismo archivo (el portal lo manda por partes).
    """
    pendientes = pendientes or {}
    nuevas_cuentas = dict(pendientes.get("cuentas") or {})
    nuevos_alias = dict(pendientes.get("alias") or {})
    vistas: dict[str, int] = {}

    def problema_dominio(dominio: str) -> str | None:
        info = dominios.get(dominio)
        if info is None:
            return ajeno.format(dominio=dominio)
        if not info["activo"]:
            return f"El dominio {dominio} está desactivado"
        if info["enrutado"]:
            return f"El dominio {dominio} entrega su correo en otro servidor (enrutamiento)"
        return None

    for f in filas:
        errores = f["errores"]
        f["cuota"] = None
        if f["correo"] and not direccion_valida(f["correo"]):
            dominio = f["correo"].split("@")[1]
            problema = problema_dominio(dominio)
            if problema:
                errores.append(problema)
            else:
                info = dominios[dominio]
                if f["correo"] in ocupadas:
                    errores.append(f"{f['correo']} ya existe (cuenta, alias o grupo)")
                if f["correo"] in vistas:
                    errores.append(f"Repetido: ya aparece en la fila {vistas[f['correo']]}")
                if f["clave"] and problema_clave(f["clave"], f["correo"]):
                    errores.append(problema_clave(f["clave"], f["correo"]))
                if f["cuota_mb"] is None:
                    f["cuota"] = info["cuota_defecto"]
                else:
                    f["cuota"] = f["cuota_mb"] * MIB
                    if info["cuota_maxima"] is not None and f["cuota"] > info["cuota_maxima"]:
                        errores.append(f"Cuota excedida: el máximo del dominio es {info['cuota_maxima'] // MIB} MB")
        for a in f["alias"]:
            if direccion_valida(a):
                continue
            problema = problema_dominio(a.split("@")[1])
            if problema:
                errores.append(f"El alias {a}: {problema[0].lower()}{problema[1:]}")
            elif a in ocupadas:
                errores.append(f"El alias {a} ya existe")
            elif a in vistas:
                errores.append(f"El alias {a} ya aparece en la fila {vistas[a]}")
        if not errores:
            dominio = f["correo"].split("@")[1]
            info = dominios[dominio]
            if info["max_cuentas"] and info["cuentas"] + nuevas_cuentas.get(dominio, 0) >= info["max_cuentas"]:
                errores.append(f"El dominio {dominio} llegó a su límite de {info['max_cuentas']} cuentas")
            por_dominio: dict[str, int] = {}
            for a in f["alias"]:
                d = a.split("@")[1]
                por_dominio[d] = por_dominio.get(d, 0) + 1
            for d, n in por_dominio.items():
                tope = dominios[d]["max_alias"]
                if tope and dominios[d]["alias"] + nuevos_alias.get(d, 0) + n > tope:
                    errores.append(f"El dominio {d} llegó a su límite de {tope} alias")
            if not errores:
                nuevas_cuentas[dominio] = nuevas_cuentas.get(dominio, 0) + 1
                for d, n in por_dominio.items():
                    nuevos_alias[d] = nuevos_alias.get(d, 0) + n
        for direccion in [f["correo"], *f["alias"]]:
            vistas.setdefault(direccion, f["fila"])
        f["valida"] = not errores
    return filas


def para_mostrar(f: dict) -> dict:
    """Lo que vuelve al navegador en la vista previa: nunca la contraseña que vino en el archivo."""
    return {"fila": f["fila"], "correo": f["correo"], "nombre": f["nombre"], "alias": f["alias"],
            "cuota_mb": f["cuota"] // MIB if f.get("cuota") is not None else None,
            "clave": "en el archivo" if f["clave"] else "se generará", "errores": f["errores"],
            "valida": f.get("valida", False)}


def celda_segura(valor) -> str:
    """Un texto que una hoja de cálculo no ejecuta como fórmula: si empieza (aun tras espacios)
    por =, +, -, @, tabulador o retorno, se le antepone un apóstrofo."""
    texto = "" if valor is None else str(valor)
    if texto[:1] in _FORMULA or texto.lstrip()[:1] in _FORMULA:
        return "'" + texto
    return texto


def a_csv(columnas: list[str], filas: list[list]) -> str:
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow([celda_segura(c) for c in columnas])
    for fila in filas:
        escritor.writerow([celda_segura(c) for c in fila])
    return salida.getvalue()


def informe_csv(resultados: list[dict]) -> str:
    """Informe del lote: una línea por fila del archivo con lo que pasó."""
    return a_csv(["fila", "correo", "resultado", "detalle"],
                 [[r["fila"], r["correo"], r["resultado"], "; ".join(r.get("errores") or [])] for r in resultados])


def claves_csv(creadas: list[dict]) -> str | None:
    """Solo las contraseñas generadas, para entregarlas una vez. None si no se generó ninguna."""
    generadas = [c for c in creadas if c.get("clave_generada")]
    if not generadas:
        return None
    return a_csv(["correo", "nombre", "clave"], [[c["correo"], c["nombre"], c["clave_generada"]] for c in generadas])
