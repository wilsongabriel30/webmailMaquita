"""Saludo inclusivo al propio personal en el autocompletado, de forma determinista.

El modelo rápido (7B) no sigue bien una regla de saludo (y con reglas largas cambia de
idioma), así que el saludo NO se pide en la instrucción: se corrige aquí, después.

Se aplica solo si:
- hay saludo configurado (AI_ORG_SALUDO_GRUPO, p. ej. «Estimadas compañeras y estimados
  compañeros»);
- TODOS los destinatarios son de los dominios propios (`organizacion.dominios_propios`);
- el correo va a un grupo: dos o más destinatarios, o el saludo que escribió el modelo es
  plural o colectivo («Estimados coordinadores», «querido personal», «Estimados:»).

Dos casos:
1. La persona dejó el saludo a medias y lo que lleva es el comienzo del saludo configurado
   («Estimad»): se sustituye el primer tramo de la continuación (hasta el salto de línea, o
   la primera coma o dos puntos) por el resto del saludo, terminado en «:».
2. La continuación trae una línea que es solo un saludo plural («Estimados socios y
   colaboradores,»): se cambia por el saludo configurado con «:».
Lo que la persona ya escribió nunca se cambia.

En inglés (04/11/2026) vale lo mismo con el saludo `saludo_en()` (AI_ORG_SALUDO_GRUPO_EN; por
defecto «Dear colleagues» si hay saludo en español configurado), terminado en «,»: «Dea» +
«r all,» → «Dear colleagues,». El saludo en español solo se aplica a texto en español (sus
reglas solo reconocen palabras españolas) y el inglés solo a «Dear…».
"""

import re

from app import organizacion

_MAX_SALUDO = 80  # un tramo más largo no es un saludo

_COLECTIVO = re.compile(
    r"(?i)\b(?:estimad|querid|apreciad)[oa]s\b|\b(?:ustedes|todos|todas|personal|equipo)\b|"
    r"\b(?:compañer|colaborador|coordinador|miembro|socio|colega|señor|amig|integrante|"
    r"trabajador|funcionari|director|jef|técnic|tecnic|responsable)(?:os|as|es|s)\b"
)
_LINEA_SALUDO = re.compile(
    r"(?im)^(?P<sangria>[ \t]*)(?:estimad|querid|apreciad)[oa]s\b[^\n:,]{0,70}[:,][ \t]*$"
)
_DIRECCION = re.compile(r"[\w.+'-]+@([\w-]+(?:\.[\w-]+)+)")


def saludo() -> str:
    return organizacion.valor("AI_ORG_SALUDO_GRUPO", "").strip()


def saludo_en() -> str:
    """Saludo al personal en inglés: AI_ORG_SALUDO_GRUPO_EN, o «Dear colleagues» si hay
    saludo en español configurado (sin él, la organización no pidió corregir saludos).
    """
    propio = organizacion.valor("AI_ORG_SALUDO_GRUPO_EN", "").strip()
    return propio or ("Dear colleagues" if saludo() else "")


def _destino_interno(para: str):
    """(todos los destinatarios son de la casa, número de destinatarios)."""
    dominios = [d.lower() for d in _DIRECCION.findall(para or "")]
    propios = organizacion.dominios_propios()
    return bool(dominios) and all(d in propios for d in dominios), len(dominios)


def _primer_tramo(texto: str):
    """Fin del primer tramo de saludo: la línea entera si termina en «,» o «:» (el saludo
    ocupa su línea: «Quito, Guayaquil and Cuenca teams,»); si no, salto de línea o primera
    «,»/«:» antes de él. Nunca más de _MAX_SALUDO caracteres."""
    salto = texto.find("\n")
    if 0 < salto <= _MAX_SALUDO and texto[:salto].rstrip()[-1:] in (",", ":"):
        return salto
    m = re.search(r"[\n:,]", texto)
    if not m or m.start() > _MAX_SALUDO:
        return None
    return m.start() if m.group(0) == "\n" else m.end()


def ajustar(previo: str, continuacion: str, para: str) -> str:
    """Devuelve la continuación con el saludo al personal corregido (o igual si no aplica)."""
    sal = saludo()
    if not sal or not isinstance(continuacion, str) or not continuacion:
        return continuacion
    interno, n = _destino_interno(para)
    if not interno:
        return continuacion
    linea = (previo or "").rsplit("\n", 1)[-1].lstrip()
    sal_en = saludo_en()
    if (
        sal_en
        and len(linea) >= 3
        and not previo[-1].isspace()
        and sal_en.lower().startswith(linea.lower())
    ):
        return _completar(linea, continuacion, n, sal_en, ",", _COLECTIVO_EN)
    if (
        len(linea) >= 3
        and not previo[-1].isspace()
        and sal.lower().startswith(linea.lower())
    ):
        plural = bool(re.match(r"\w*[oa]s\b", continuacion))  # «Estimad» + «os …»
        return _completar(linea, continuacion, n, sal, ":", _COLECTIVO, plural)

    def _cambia(m):
        if n >= 2 or _COLECTIVO.search(m.group(0)):
            return m.group("sangria") + sal + ":"
        return m.group(0)

    return _LINEA_SALUDO.sub(_cambia, continuacion)


_COLECTIVO_EN = re.compile(
    r"(?i)\b(?:all|everyone|teams?|colleagues|staff|friends|partners|members)\b"
)


def _completar(linea, continuacion, n, sal, cierre, colectivo, plural=False) -> str:
    """Saludo a medias («Estimad», «Dea») + continuación → resto de `sal` + `cierre`.

    - Si la continuación empieza por el resto del saludo (en minúscula, «os compañeros:», o un
      saludo colectivo corto, «Quito and Cuenca teams,»), ese tramo se cambia por el saludo.
    - Si empieza otra oración (mayúscula, «We are writing…») y va a un grupo, el saludo se
      pone delante y la oración se conserva entera.
    """
    fin = _primer_tramo(continuacion)
    tramo = continuacion[: fin or 0]
    es_saludo = fin is not None and (
        not continuacion[:1].isupper()
        or (colectivo.search(tramo) and len(tramo.split()) <= 6)
    )
    if es_saludo and (n >= 2 or plural or colectivo.search(linea + tramo)):
        resto = continuacion[fin:].lstrip(" \t")
        if resto and not resto.startswith("\n"):
            resto = "\n\n" + resto
        # Tras el saludo, el párrafo empieza con mayúscula (RAE; igual en inglés).
        resto = re.sub(r"^(\s*)(\w)", lambda m: m.group(1) + m.group(2).upper(), resto)
        return sal[len(linea) :] + cierre + resto
    # Otra oración (mayúscula, o detrás de una palabra completa: «Dear» + «we hope…»): a un
    # grupo, el saludo va delante y la oración se conserva entera.
    palabra_completa = sal[len(linea) : len(linea) + 1] == " "
    inicio = continuacion.lstrip(" \t")
    if n >= 2 and inicio and (inicio[0].isupper() or palabra_completa):
        return sal[len(linea) :] + cierre + "\n\n" + inicio[0].upper() + inicio[1:]
    return continuacion
