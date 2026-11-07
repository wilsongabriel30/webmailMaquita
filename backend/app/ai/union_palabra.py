"""Autocompletado: ¿la sugerencia continúa la palabra que la persona dejó a medias?

Antes el frontend pegaba la sugerencia SIEMPRE con un espacio delante, y una palabra a medias
quedaba partida: «Estimad» + «as compañeras…» → «Estimad as compañeras…». Aquí se decide, con
reglas deterministas, si hay que unir sin espacio («Estimad» + «as» → «Estimadas») o separar
(«Le escribo para» + «informarle» → «Le escribo para informarle»). El frontend inserta según
`continua_palabra` (y pone espacio solo si hace falta: ver `frontend/src/lib/autocompletar.ts`).

Reglas, en orden (`unir`):
0. Si la sugerencia repite las últimas palabras escritas («I hope» + «I hope this…»), se quitan.
1. La persona no dejó una palabra a medias (texto vacío o que termina en espacio o signo), o la
   sugerencia no empieza por letra: no hay nada que unir (False).
2. El modelo repitió la última palabra: completa («Estimad» → «Estimadas compañeras») se queda
   solo con lo que falta y se une; igual («para» → «para informarle») se quita la repetición.
   La regla 1 de completar no se aplica si la palabra escrita ya es una palabra corriente («de»
   + «decidimos» es una palabra nueva).
3. La salida del modelo empezaba con espacio, o la sugerencia empieza en mayúscula: palabra
   nueva (False).
4. Lo escrito + el comienzo de la sugerencia forman una palabra conocida (y no son las dos, por
   separado, palabras corrientes): se une («Estimad» + «as» → «Estimadas»).
5. La última palabra escrita, o la primera de la sugerencia, es una palabra corriente
   («para», «que», «the»…): palabra nueva (False).
6. La sugerencia empieza por una terminación típica («as», «os», «ción», «mente», «ing»…): se
   une.
7. En cualquier otro caso, palabra nueva (False): un espacio de más se nota y se corrige fácil;
   dos palabras pegadas, menos.
"""

import re

from app.ai.idioma import _EN, _ES

# Palabras frecuentes en correos (además de las de detección de idioma) para la regla 4.
_LEXICO = _ES | _EN | frozenset("""
        estimados estimadas estimado estimada compañeros compañeras compañero compañera
        colaboradores colaboradoras queridos queridas apreciados apreciadas distinguidos
        distinguidas saludos cordiales cordialmente atentamente información informe informes
        reunión reuniones convocatoria invitación invitamos informamos comunicamos recordamos
        solicitud solicitamos agradecemos adjuntamos coordinación capacitación asamblea
        semana mañana personal productores comercio justo
        colleagues regards sincerely meeting meetings information attached schedule
        please thank thanks invitation reminder report reports dear everyone
        """.split())
_SUFIJOS = frozenset("""
    os as o es s ados adas idos idas ado ada ido ida ando iendo ción ciones sión siones ión
    iones mente ar er ir amos emos imos aron ieron ía ían aba aban ente entes ante antes
    ing ed ly tion tions ment ments ness ance ence ers est ings
    """.split())
_FIN_PALABRA = re.compile(r"([^\W\d_]+)$")
_INICIO_PALABRA = re.compile(r"^([^\W\d_]+)")


def unir(previo: str, sugerencia: str, inicio_con_espacio: bool = False):
    """(sugerencia ajustada, continua_palabra).

    previo: lo que ya escribió la persona. sugerencia: salida del modelo, ya recortada.
    inicio_con_espacio: la salida cruda del modelo empezaba con espacio o salto de línea.
    """
    if not isinstance(sugerencia, str) or not sugerencia:
        return sugerencia, False
    sugerencia = quitar_solape(previo, sugerencia)
    m_fin = _FIN_PALABRA.search(previo or "")
    m_ini = _INICIO_PALABRA.match(sugerencia)
    if not m_fin or not m_ini:  # regla 1
        return sugerencia, False
    escrita, primera = m_fin.group(1), m_ini.group(1)
    e, p = escrita.lower(), primera.lower()
    if p == e:  # regla 2: repitió la palabra entera
        return sugerencia[len(primera) :].lstrip(" \t"), False
    if p.startswith(e) and e not in _LEXICO:  # regla 2: la completó
        return sugerencia[len(escrita) :], True
    if inicio_con_espacio or primera[0].isupper():  # regla 3
        return sugerencia, False
    if (e + p) in _LEXICO and not (e in _LEXICO and p in _LEXICO):  # regla 4
        return sugerencia, True
    if e in _LEXICO or p in _LEXICO:  # regla 5
        return sugerencia, False
    return sugerencia, p in _SUFIJOS  # reglas 6 y 7


_PALABRAS = re.compile(r"\S+")


def quitar_solape(previo: str, sugerencia: str) -> str:
    """Si la sugerencia repite las últimas palabras escritas (2 a 8), se quitan.

    «Good morning, I hope» + «I hope this message finds you well» → «this message finds you
    well». Una sola palabra repetida la trata `unir` (regla 2).
    """
    escritas = _PALABRAS.findall(previo or "")[-8:]
    nuevas = _PALABRAS.findall(sugerencia)
    norm = [w.lower().strip(".,;:!?¡¿") for w in escritas]
    for n in range(min(len(escritas), len(nuevas)), 1, -1):
        if [w.lower().strip(".,;:!?¡¿") for w in nuevas[:n]] == norm[-n:]:
            pos = 0
            for w in nuevas[:n]:
                pos = sugerencia.index(w, pos) + len(w)
            resto = sugerencia[pos:].lstrip(" \t")
            return resto or sugerencia
    return sugerencia


def reevaluar(previo: str, antes: str, despues: str, continua: bool) -> bool:
    """Tras el posprocesado (p. ej. el saludo al personal), si cambió el comienzo de la
    sugerencia, se vuelve a decidir con el texto nuevo; si no, vale lo decidido antes.
    """
    a, d = _INICIO_PALABRA.match(antes or ""), _INICIO_PALABRA.match(despues or "")
    if (a and a.group(1)) == (d and d.group(1)):
        return continua
    return unir(previo, despues)[1]
