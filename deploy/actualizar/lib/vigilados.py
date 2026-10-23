"""Archivos del sistema que cambia una actualización (fuera del código de /opt/maquita-webmail).

Antes de aplicar se toma una «foto» de las rutas de vigilados.txt: tipo, permisos, sha256 y, para lo que
el producto instala tal cual, la suma de git (blob) para compararla con el árbol de la versión anterior.
Del contenido anterior se guarda una copia (0600, en carpetas 0700, sin seguir enlaces y con límite de
tamaño) en el respaldo de la actualización. Al terminar se compara con una foto nueva: creados,
modificados y borrados, con la marca «tenía cambios locales» para lo que el operador había parcheado, y
se borran las copias de lo que no cambió.

No se lanza ninguna excepción hacia fuera por un archivo que no se pueda leer: se anota y se sigue.
"""

import fnmatch
import hashlib
import json
import os
import re
import stat

LISTA = "vigilados.txt"
MAX_ARCHIVOS = 20000            # por foto: más que eso es una lista mal escrita
MAX_SUMA = 64 * 1024**2         # más grande: se compara por tamaño y fecha, sin leerlo
MAX_COPIA = 4 * 1024**2         # por archivo
MAX_COPIAS_TOTAL = 256 * 1024**2
MAX_LISTA = 200                 # por categoría en progreso.json (el informe completo queda en el respaldo)
CATEGORIAS = ("creados", "modificados", "borrados")
_COMODIN = re.compile(r"[*?\[]")


def ruta_lista():
    """vigilados.txt junto al módulo instalado (/usr/local/lib/maquita-actualizar) o en el repositorio."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    for ruta in (os.path.join(aqui, LISTA), os.path.join(aqui, "..", LISTA)):
        if os.path.isfile(ruta):
            return os.path.normpath(ruta)
    return None


def _llaves(patron):
    """Expande {a,b} (sin anidar): /etc/{x,y}/*.{conf,local} → cuatro patrones."""
    m = re.search(r"\{([^{}]*)\}", patron)
    if not m:
        return [patron]
    return [r for alt in m.group(1).split(",") for r in _llaves(patron[:m.start()] + alt + patron[m.end():])]


def leer_lista(texto):
    """→ (entradas, exclusiones). Entrada: {"grupo", "patron", "origen"} con un patrón ya sin llaves."""
    entradas, excluir, grupo = [], [], "otros"
    for linea in texto.splitlines():
        linea = linea.split(" #", 1)[0].strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("[") and linea.endswith("]"):
            grupo = linea[1:-1].strip() or "otros"
            continue
        if linea.startswith("!"):
            excluir += [p for p in _llaves(linea[1:].strip()) if p.startswith("/")]
            continue
        partes = linea.split()
        origen = partes[1] if len(partes) > 1 else None
        for patron in _llaves(partes[0]):
            if patron.startswith("/") and ".." not in patron.split("/"):
                entradas.append({"grupo": grupo, "patron": os.path.normpath(patron), "origen": origen})
    return entradas, excluir


def _partes(ruta):
    return [c for c in ruta.split("/") if c]


def _coincide(patron, ruta):
    """Coincidencia por componentes: «*» no cruza «/», «**» abarca cero o más carpetas."""
    if not patron:
        return not ruta
    if patron[0] == "**":
        return any(_coincide(patron[1:], ruta[i:]) for i in range(len(ruta) + 1))
    return bool(ruta) and fnmatch.fnmatchcase(ruta[0], patron[0]) and _coincide(patron[1:], ruta[1:])


def _puede_contener(patron, carpeta):
    """¿Puede haber, dentro de `carpeta`, algo que coincida? Para no recorrer de más (p. ej. /usr/local/lib)."""
    for i, comp in enumerate(carpeta):
        if i >= len(patron):
            return False
        if patron[i] == "**":
            return True
        if not fnmatch.fnmatchcase(comp, patron[i]):
            return False
    return len(patron) > len(carpeta)


def expandir(patron):
    """Rutas existentes que coinciden (archivos y enlaces; nunca entra en un enlace a carpeta)."""
    comps = _partes(patron)
    fijo = []
    for c in comps:
        if _COMODIN.search(c):
            break
        fijo.append(c)
    base = "/" + "/".join(fijo)
    if len(fijo) == len(comps):
        return [base] if os.path.lexists(base) and not os.path.isdir(base) or os.path.islink(base) else []
    encontrados = []
    for raiz, carpetas, archivos in os.walk(base, followlinks=False):
        rel = _partes(raiz)
        carpetas[:] = sorted(d for d in carpetas if os.path.islink(os.path.join(raiz, d))
                             or _puede_contener(comps, rel + [d]))
        for nombre in sorted(archivos) + [d for d in carpetas if os.path.islink(os.path.join(raiz, d))]:
            if _coincide(comps, rel + [nombre]):
                encontrados.append(os.path.join(raiz, nombre))
        carpetas[:] = [d for d in carpetas if not os.path.islink(os.path.join(raiz, d))]
        if len(encontrados) > MAX_ARCHIVOS:
            break
    return encontrados


def _origen_de(entrada, ruta):
    origen = entrada["origen"]
    if not origen:
        return None
    if origen.endswith("/"):
        return origen + os.path.basename(ruta)
    if "*" in origen:
        antes, _, despues = entrada["patron"].partition("*")
        if "*" in despues or not (ruta.startswith(antes) and ruta.endswith(despues)):
            return None
        return origen.replace("*", ruta[len(antes):len(ruta) - len(despues)] if despues else ruta[len(antes):], 1)
    return origen


def rutas(entradas, excluir):
    """{ruta: {"grupo", "origen"}}: el grupo de la primera entrada que coincide, el origen de la primera que lo da."""
    excluidos = [_partes(p) for p in excluir]
    res = {}
    for e in entradas:
        for ruta in expandir(e["patron"]):
            if any(_coincide(x, _partes(ruta)) for x in excluidos):
                continue
            dato = res.setdefault(ruta, {"grupo": e["grupo"], "origen": None})
            if dato["origen"] is None:
                dato["origen"] = _origen_de(e, ruta)
        if len(res) > MAX_ARCHIVOS:
            break
    return res


def _crear_carpetas(carpeta, raiz):
    """Carpetas 0700 hasta `carpeta` (dentro de `raiz`), sin seguir enlaces que alguien hubiera dejado."""
    actual = raiz
    for comp in _partes(os.path.relpath(carpeta, raiz)):
        actual = os.path.join(actual, comp)
        try:
            os.mkdir(actual, 0o700)
        except FileExistsError:
            if os.path.islink(actual) or not os.path.isdir(actual):
                raise OSError(f"{actual} no es una carpeta")


def firma(ruta, copia=None, presupuesto=None):
    """Firma de una ruta sin seguir enlaces; con `copia`, escribe ahí el contenido (0600) si cabe.

    → {"tipo", "modo", "tam", "sha256", "blob", "copiado"} o None si no existe o no es archivo ni enlace.
    `presupuesto` es una lista de un elemento con los bytes que aún se pueden copiar (se descuenta).
    """
    try:
        st = os.lstat(ruta)
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode):
        destino = os.readlink(ruta)
        return {"tipo": "enlace", "modo": 0, "tam": len(destino), "destino": destino,
                "sha256": hashlib.sha256(b"enlace:" + os.fsencode(destino)).hexdigest()}
    if not stat.S_ISREG(st.st_mode):
        return None
    datos = {"tipo": "archivo", "modo": stat.S_IMODE(st.st_mode), "tam": st.st_size}
    if st.st_size > MAX_SUMA:
        datos["sha256"] = f"grande:{st.st_size}:{st.st_mtime_ns}"
        return datos
    copiar = copia is not None and st.st_size <= MAX_COPIA and (presupuesto is None or presupuesto[0] >= st.st_size)
    # SHA-1 solo para reproducir la suma de git (git hash-object) y compararla con el árbol del repositorio;
    # no protege nada: las versiones van firmadas y las copias se comprueban con SHA-256.
    suma = hashlib.sha256()
    blob = hashlib.sha1(b"blob %d\0" % st.st_size, usedforsecurity=False)  # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
    fd = os.open(ruta, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    salida = None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        if copiar:
            salida = os.open(copia, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        leidos = 0
        while True:
            trozo = os.read(fd, 1024 * 1024)
            if not trozo:
                break
            leidos += len(trozo)
            suma.update(trozo)
            blob.update(trozo)
            if salida is not None:
                os.write(salida, trozo)
    finally:
        os.close(fd)
        if salida is not None:
            os.close(salida)
    datos["sha256"] = suma.hexdigest()
    if leidos == st.st_size:  # si creció mientras se leía, la suma de git no vale
        datos["blob"] = blob.hexdigest()
    if copiar:
        datos["copiado"] = True
        if presupuesto is not None:
            presupuesto[0] -= st.st_size
    return datos


def tomar(vigiladas, copias=None):
    """Foto de las rutas {ruta: {"grupo", "origen"}}. Con `copias` (carpeta 0700), copia el contenido."""
    presupuesto = [MAX_COPIAS_TOTAL]
    foto = {}
    for ruta, dato in sorted(vigiladas.items()):
        destino = None
        if copias is not None:
            destino = os.path.join(copias, ruta.lstrip("/"))
            try:
                _crear_carpetas(os.path.dirname(destino), copias)
            except OSError:
                destino = None
        try:
            f = firma(ruta, destino, presupuesto)
        except OSError as e:
            f = {"tipo": "ilegible", "sha256": "error:" + type(e).__name__}
        if f is not None:
            foto[ruta] = dict(dato, **f)
    return foto


def arbol_git(commit, git):
    """{ruta del repositorio: blob} del commit, con la función git(*args) del actualizador."""
    arbol = {}
    for linea in git("ls-tree", "-r", "-z", "--full-tree", commit).split("\0"):
        cabeza, _, ruta = linea.partition("\t")
        partes = cabeza.split()
        if ruta and len(partes) == 3 and partes[1] == "blob":
            arbol[ruta] = partes[2]
    return arbol


def marcar_locales(foto, arbol):
    """Marca en la foto lo instalado por el producto que no es igual al archivo del repositorio de entonces."""
    for dato in foto.values():
        origen = dato.get("origen")
        if origen and origen in arbol and dato.get("tipo") == "archivo" and dato.get("blob"):
            dato["cambios_locales"] = dato["blob"] != arbol[origen]
    return foto


def _distinto(a, b):
    return a.get("sha256") != b.get("sha256") or a.get("tipo") != b.get("tipo") or a.get("modo") != b.get("modo")


def comparar(antes, despues, copias=None):
    """→ {"creados": [...], "modificados": [...], "borrados": [...]}, cada uno {"ruta", "grupo", ...}."""
    res = {c: [] for c in CATEGORIAS}

    def item(ruta, dato, previo=None):
        i = {"ruta": ruta, "grupo": dato.get("grupo", "otros")}
        if previo is not None:
            if previo.get("cambios_locales"):
                i["cambios_locales"] = True
            if previo.get("copiado") and copias:
                i["copia"] = os.path.join(copias, ruta.lstrip("/"))
            elif previo.get("tipo") == "enlace":
                i["antes"] = "→ " + previo.get("destino", "")
            if previo.get("sha256") == dato.get("sha256") and previo.get("modo") != dato.get("modo"):
                i["solo_permisos"] = True
        return i

    for ruta, dato in antes.items():
        if ruta not in despues:
            res["borrados"].append(item(ruta, dato, dato))
        elif _distinto(dato, despues[ruta]):
            res["modificados"].append(item(ruta, despues[ruta], dato))
    for ruta, dato in despues.items():
        if ruta not in antes:
            res["creados"].append(item(ruta, dato))
    for c in CATEGORIAS:
        res[c].sort(key=lambda i: (i["grupo"], i["ruta"]))
    return res


def podar(antes, cambios, copias):
    """Borra las copias de lo que no cambió (y las carpetas que quedan vacías)."""
    conservar = {i["ruta"] for c in ("modificados", "borrados") for i in cambios[c]}
    for ruta, dato in antes.items():
        if dato.get("copiado") and ruta not in conservar:
            try:
                os.remove(os.path.join(copias, ruta.lstrip("/")))
            except OSError:
                pass
    for raiz, _carpetas, _archivos in os.walk(copias, topdown=False):
        if raiz != copias:
            try:
                os.rmdir(raiz)
            except OSError:
                pass


def resumen(cambios, copias=None):
    """Lo que va a progreso.json: totales, listas acotadas y dónde están las copias."""
    res = {"totales": {c: len(cambios[c]) for c in CATEGORIAS},
           "cambios_locales": sum(1 for c in CATEGORIAS for i in cambios[c] if i.get("cambios_locales"))}
    for c in CATEGORIAS:
        res[c] = cambios[c][:MAX_LISTA]
    if any(len(cambios[c]) > MAX_LISTA for c in CATEGORIAS):
        res["recortado"] = True
    if copias:
        res["copias"] = copias
    return res


def texto(res):
    """Informe legible para el registro y la salida del actualizador."""
    t = res.get("totales", {})
    lineas = [f"Archivos del sistema cambiados: {t.get('creados', 0)} creados, {t.get('modificados', 0)} "
              f"modificados, {t.get('borrados', 0)} borrados."]
    for c in CATEGORIAS:
        grupo = None
        for i in res.get(c, []):
            if i["grupo"] != grupo:
                grupo = i["grupo"]
                lineas.append(f"  {c.capitalize()} · {grupo}:")
            marca = "  [TENÍA CAMBIOS LOCALES: se perdieron; copia anterior en " + i["copia"] + "]" if (
                i.get("cambios_locales") and i.get("copia")) else "  [TENÍA CAMBIOS LOCALES]" if i.get("cambios_locales") else ""
            lineas.append(f"    {i['ruta']}{' (solo permisos)' if i.get('solo_permisos') else ''}{marca}")
    if res.get("recortado"):
        lineas.append("  (lista recortada; el informe completo está en archivos-sistema.json del respaldo)")
    if res.get("cambios_locales"):
        lineas.append(f"  ¡Atención! {res['cambios_locales']} archivo(s) tenían cambios locales que esta versión "
                      "reemplazó. Compare con: diff <copia> <ruta>  (docs/ACTUALIZACIONES.md, «Si tiene parches locales»).")
    if res.get("copias"):
        lineas.append(f"  Copias del contenido anterior: {res['copias']}")
    if res.get("error_locales"):
        lineas.append(f"  No se pudieron comprobar los cambios locales: {res['error_locales']}")
    if res.get("error"):
        lineas.append(f"  No se pudo completar la comparación: {res['error']}")
    return "\n".join(lineas)


def _guardar(ruta, datos):
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump(datos, f, indent=1, ensure_ascii=False)
    os.replace(tmp, ruta)


def foto_previa(respaldo, commit, git, lista=None):
    """Antes de aplicar: foto con copias en <respaldo>/archivos-sistema y marca de cambios locales
    respecto al árbol de git del commit instalado. → estado para `informe`, o None si no hay lista."""
    lista = lista or ruta_lista()
    if not lista:
        return None
    with open(lista) as f:
        entradas, excluir = leer_lista(f.read())
    copias = os.path.join(respaldo, "archivos-sistema")
    os.mkdir(copias, 0o700)
    foto = tomar(rutas(entradas, excluir), copias)
    previa = {"entradas": entradas, "excluir": excluir, "copias": copias, "foto": foto, "respaldo": respaldo}
    try:
        marcar_locales(foto, arbol_git(commit, git))
    except Exception as e:  # sin el árbol no se marca nada, pero la lista de cambios sigue valiendo
        previa["error_locales"] = f"{type(e).__name__}: {e}"[:300]
    return previa


def locales(previa):
    """Rutas que ya tenían cambios locales antes de aplicar."""
    return sorted(r for r, d in previa["foto"].items() if d.get("cambios_locales"))


def informe(previa):
    """Después de aplicar (o de volver atrás): compara, poda las copias y deja el informe completo en
    <respaldo>/archivos-sistema.json (0600). → resumen para progreso.json."""
    despues = tomar(rutas(previa["entradas"], previa["excluir"]))
    cambios = comparar(previa["foto"], despues, previa["copias"])
    podar(previa["foto"], cambios, previa["copias"])
    tocados = {i["ruta"] for c in CATEGORIAS for i in cambios[c]}
    _guardar(os.path.join(previa["respaldo"], "archivos-sistema.json"),
             {"cambios": cambios, "cambios_locales_conservados": [r for r in locales(previa) if r not in tocados]})
    res = resumen(cambios, previa["copias"])
    if previa.get("error_locales"):
        res["error_locales"] = previa["error_locales"]
    return res
