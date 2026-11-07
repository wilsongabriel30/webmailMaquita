"""Estilo institucional de todo texto que la IA genera para el usuario.

Un solo lugar para dos cosas:

1. `instrucciones()`: reglas de estilo que se añaden a la instrucción de sistema de cada
   función de IA. Son MUY cortas: con reglas largas el modelo pequeño (7B) se confunde y llega
   a cambiar de idioma (04/11/2026: chino en 5 de 10 autocompletados). Tres alcances:
   «minimo» (autocompletado y asuntos, 7B), «redaccion» (respuestas, 14B; lleva AI_ORG_ESTILO)
   y «analisis» (resúmenes, «Conversa con tu correo», partes).
2. `institucionalizar()`: posprocesado CONSERVADOR de la salida del modelo, para corregir
   cuando nombra a la propia organización como «nuestra empresa» o similar. Antes quita las
   oraciones en otro alfabeto (ver `app.ai.alfabeto`).
3. `institucionalizar_continuacion()`: lo mismo para el autocompletado, uniendo la línea que
   la persona deja a medias («Estimad») con la continuación, para poder corregir el saludo.

Idioma (04/11/2026): `instrucciones(alcance, idioma)` admite «en»; entonces las reglas van en
inglés y el nombre de la organización se mantiene sin traducir (si el modelo escribe «the X
Foundation» por «Fundación X», el posprocesado lo devuelve al nombre propio). El idioma lo
decide `app.ai.idioma`.

Nada de una organización concreta va en el código; todo sale de la configuración
(variable de entorno o fichero de la organización, ver `app.organizacion`):

- ORG_NAME             nombre de la organización. Sin él, el posprocesado no hace nada.
- AI_ORG_REFERENCIA    (opcional) cómo nombrarla en texto corrido, p. ej. «la Fundación X».
                       Por defecto, ORG_NAME tal cual.
- AI_ORG_ESTILO        (opcional) reglas propias de la organización, en UNA frase corta;
                       solo se añade en el alcance «redaccion» (modelo de calidad).
- AI_ORG_SALUDO_GRUPO  (opcional) saludo inclusivo para el propio personal, p. ej.
                       «Estimadas compañeras y estimados compañeros». Sin él no se toca.

CRITERIO DEL POSPROCESADO (conservador: ante la duda, no se toca)
- Solo se aplica al texto que generó el modelo, nunca al correo original. Además se dejan
  intactos los fragmentos entre comillas («…», "…", “…”) y las líneas citadas que empiezan
  con «>», porque suelen ser citas del correo.
- Si la frase aparece literalmente en la fuente (el correo o el texto que escribió la
  persona), no se toca: puede ser una copia de lo que dijo otra organización
  («nuestra empresa» de un proveedor).
- Regla 1, posesivo de primera persona en singular: «nuestra empresa», «nuestra compañía»,
  «nuestra corporación», «nuestro negocio». Quien escribe es la propia organización, así que
  se reemplaza, salvo si sigue un calificativo que señala a otra entidad («nuestra empresa
  proveedora», «nuestra empresa cliente», «nuestro negocio de cacao»: «de» indica una línea
  de negocio o una filial, no la institución). El plural («nuestras empresas») nunca se toca.
- Regla 2, artículo definido «la empresa» / «la compañía»: solo en modo «redaccion» (texto en
  la voz de la organización) y solo cuando va pegado a un verbo en primera persona del plural
  («en la empresa contamos con…») o detrás de «trabajamos en». En cualquier otro caso
  («la empresa enviará la factura») puede ser el proveedor o el cliente: no se toca.
- «nuestra <ORG_NAME>» se cambia por AI_ORG_REFERENCIA («nuestra Fundación X» →
  «la Fundación X») cuando esta lleva artículo.
- «Firma» nunca se reemplaza: en un correo casi siempre es la firma del mensaje.
- Saludo a grupos (solo modo «redaccion» y solo con AI_ORG_SALUDO_GRUPO): se corrige el
  saludo que ABRE una línea y nombra al propio personal solo en masculino («Estimados
  compañeros:», «Queridos colaboradores,»). «Estimados todos», «Estimados señores» o
  «Estimados colegas» no se tocan: pueden ir a personas de fuera.
"""

import re

from app import organizacion
from app.ai import alfabeto, saludo_grupo
from app.ai.idioma import EN, ES, regla

# Reglas neutras: valen para cualquier organización.
_NEUTRA_USTED = "Trata de usted."
_NEUTRA_GRUPO = "Para varias personas, usa lenguaje inclusivo."
# Las mismas en inglés (04/11/2026: la IA responde en el idioma del correo).
_EN_USTED = "Address the person formally."
_EN_GRUPO = "For several people, use inclusive language."

# «Fundación X» traducido por el modelo («the X Foundation», «Foundation X») → nombre propio.
_TRADUCCION_FIGURA = {
    "fundación": "Foundation",
    "fundacion": "Foundation",
    "asociación": "Association",
    "asociacion": "Association",
    "corporación": "Corporation",
    "corporacion": "Corporation",
    "cooperativa": "Cooperative",
}

_CALIFICATIVOS_AJENOS = (
    r"proveedora|proveedor|cliente|aliada|aliado|socia|socio|asociada|asociado|contratista|"
    r"consultora|auditora|transportista|amiga|hermana|filial|de|del"
)

_POSESIVO = re.compile(
    r"\b(?P<prep>de |a |en )?"
    r"(?P<frase>nuestra (?:empresa|compañía|compañia|corporación|corporacion)|nuestro negocio)\b"
    r"(?!\s+(?:" + _CALIFICATIVOS_AJENOS + r")\b)",
    re.IGNORECASE,
)

# «en la empresa contamos», «la empresa, hemos…», «trabajamos en la empresa»
_ARTICULO_PRIMERA_PERSONA = re.compile(
    r"\b(?P<prep>de |a |en )?(?P<frase>la (?:empresa|compañía|compañia))\b"
    r"(?=,?\s+(?:ya\s+|no\s+|también\s+|siempre\s+)?(?-i:[a-záéíóúñ]+mos)\b)",
    re.IGNORECASE,
)
_ARTICULO_TRAS_VERBO = re.compile(
    r"(?<=\btrabajamos )(?P<prep>en )(?P<frase>la (?:empresa|compañía|compañia))\b",
    re.IGNORECASE,
)

# Saludo de apertura de línea al propio personal, solo en masculino.
_SALUDO_GRUPO = re.compile(
    r"^(?P<sangria>[ \t]*)(?:estimados|queridos|apreciados)\s+(?:compañeros|colaboradores)"
    r"(?!\s+y\s)(?=\s*[,:]|\s*$)",
    re.IGNORECASE | re.MULTILINE,
)

# Citas que no se tocan: comillas y líneas que empiezan con «>».
_CITAS = re.compile(r"«[^»]*»|\"[^\"\n]*\"|“[^”]*”|^>.*$", re.MULTILINE)


def nombre() -> str:
    """Nombre configurado de la organización, o cadena vacía si no hay."""
    return organizacion.valor("ORG_NAME", "").strip()


def referencia() -> str:
    """Cómo nombrar a la organización en texto corrido (AI_ORG_REFERENCIA o ORG_NAME)."""
    return organizacion.valor("AI_ORG_REFERENCIA", "").strip() or nombre()


def instrucciones(alcance: str = "redaccion", idioma: str = ES) -> str:
    """Reglas de estilo para la instrucción de sistema (frases cortas, terminadas en espacio).

    idioma: «es» (por defecto) o «en». En inglés las reglas van en inglés, el nombre de la
    organización se mantiene tal cual (nombre propio, sin traducir) y AI_ORG_ESTILO (escrito
    en español) se sustituye por el saludo a grupos en inglés (`saludo_grupo.saludo_en`).

    alcance:
    - «minimo»: autocompletado y asuntos (modelo rápido). Idioma y nombre, nada más; el
      saludo a grupos lo corrige el posprocesado.
    - «redaccion»: respuestas redactadas (modelo de calidad). Añade lenguaje inclusivo y
      AI_ORG_ESTILO (p. ej. el saludo al personal).
    - «analisis»: resúmenes, «Conversa con tu correo», copiloto y partes. Idioma, nombre y usted.
    """
    if idioma == EN:
        return _instrucciones_en(alcance)
    partes = [regla(ES)]
    ref = referencia()
    if ref:
        partes.append(f"La institución es {ref}.")
    if alcance == "redaccion":
        partes.append(_NEUTRA_GRUPO)
        propio = organizacion.valor("AI_ORG_ESTILO", "").strip()
        if propio:
            partes.append(propio)
    elif alcance == "analisis":
        partes.append(_NEUTRA_USTED)
    return " ".join(partes) + " "


def _instrucciones_en(alcance: str) -> str:
    partes = [regla(EN)]
    org = nombre()
    if org:
        partes.append(
            f"The institution is {org}: always write this name exactly so, never translate it."
        )
    if alcance == "redaccion":
        partes.append(_EN_GRUPO)
        sal = saludo_grupo.saludo_en()
        if sal:
            partes.append(f"If you greet a group of staff, use «{sal},».")
    elif alcance == "analisis":
        partes.append(_EN_USTED)
    return " ".join(partes) + " "


def _nombre_sin_traducir(texto: str, fuente: str) -> str:
    """«the Maquita Foundation» / «Foundation Maquita» → ORG_NAME («Fundación Maquita»)."""
    org = nombre()
    figura, _, resto = org.partition(" ")
    traduccion = _TRADUCCION_FIGURA.get(figura.lower())
    if not traduccion or not resto:
        return texto
    patron = re.compile(
        r"\b(?:the\s+)?(?:"
        + re.escape(resto)
        + r"\s+"
        + traduccion
        + r"|"
        + traduccion
        + r"\s+(?:of\s+)?"
        + re.escape(resto)
        + r")\b",
        re.IGNORECASE,
    )

    # «The Maquita Foundation will…» → «Fundación Maquita will…»; lo citado de la fuente no.
    return patron.sub(
        lambda m: m.group(0) if m.group(0).lower() in fuente else org, texto
    )


def _sustituto(m: re.Match, ref: str) -> str:
    prep = m.group("prep") or ""
    sust = ref
    if prep and ref.lower().startswith("el "):  # «de el» → «del», «a el» → «al»
        sust = ref[3:]
        prep = {"de ": "del ", "a ": "al "}.get(prep.lower(), prep)
    nuevo = prep + sust
    if m.group(0)[0].isupper():  # «Nuestra empresa…» al empezar la oración
        nuevo = nuevo[0].upper() + nuevo[1:]
    return nuevo


def _corregir_tramo(tramo: str, ref: str, fuente: str, modo: str) -> str:
    tramo = _nombre_sin_traducir(tramo, fuente)
    org = nombre()
    if org and ref.lower() != org.lower():  # «nuestra Fundación X» → «la Fundación X»
        tramo = re.sub(
            r"\bnuestr[ao] " + re.escape(org) + r"\b",
            lambda m: (ref[0].upper() if m.group(0)[0].isupper() else ref[0]) + ref[1:],
            tramo,
            flags=re.IGNORECASE,
        )
    patrones = [_POSESIVO]
    if modo == "redaccion":
        patrones += [_ARTICULO_PRIMERA_PERSONA, _ARTICULO_TRAS_VERBO]
    for patron in patrones:

        def _rep(m):
            if m.group("frase").lower() in fuente:
                return m.group(0)
            return _sustituto(m, ref)

        tramo = patron.sub(_rep, tramo)
    saludo = organizacion.valor("AI_ORG_SALUDO_GRUPO", "").strip()
    if saludo and modo == "redaccion":
        tramo = _SALUDO_GRUPO.sub(lambda m: m.group("sangria") + saludo, tramo)
    return tramo


def institucionalizar(texto, fuente: str = "", modo: str = "redaccion"):
    """Corrige, con criterio conservador, cómo nombra el texto generado a la organización.

    texto:  SOLO la salida del modelo (nunca el correo original).
    fuente: el correo o texto de entrada; lo que aparece en él no se toca.
    modo:   «redaccion» (voz de la organización) o «analisis» (resúmenes y respuestas sobre
            el correo, donde solo se aplica la regla del posesivo).
    Primero se quitan las oraciones en otro alfabeto (siempre, haya o no ORG_NAME).
    Si no hay ORG_NAME configurado, o el texto no es una cadena, se devuelve tal cual.
    """
    texto = alfabeto.limpiar(texto)
    ref = referencia()
    if not ref or not isinstance(texto, str) or not texto:
        return texto
    fuente_min = (fuente or "").lower()
    salida, pos = [], 0
    for cita in _CITAS.finditer(texto):
        salida.append(_corregir_tramo(texto[pos : cita.start()], ref, fuente_min, modo))
        salida.append(cita.group(0))
        pos = cita.end()
    salida.append(_corregir_tramo(texto[pos:], ref, fuente_min, modo))
    return "".join(salida)


def institucionalizar_continuacion(
    previo: str, continuacion, fuente: str = "", para: str = ""
):
    """Posprocesado del autocompletado: `continuacion` sigue al texto `previo` de la persona.

    Si la persona dejó una palabra a medias («…\nEstimad»), se corrige esa línea unida a la
    continuación («Estimad» + «os compañeros:» → saludo configurado) y se devuelve solo la
    parte nueva. Con destinatarios del propio personal, el saludo lo fija `saludo_grupo`
    («para» son los destinatarios). Si la corrección cambiaría lo que la persona ya escribió, no se aplica a la
    línea unida: se corrige solo la continuación.
    """
    continuacion = alfabeto.limpiar(continuacion)
    if not isinstance(continuacion, str) or not continuacion:
        return continuacion
    continuacion = saludo_grupo.ajustar(previo, continuacion, para)
    linea = (previo or "").rsplit("\n", 1)[-1]
    if linea.strip() and not linea[-1].isspace() and not continuacion[0].isspace():
        unida = institucionalizar(linea + continuacion, fuente)
        if unida.startswith(linea):
            return unida[len(linea) :]
    return institucionalizar(continuacion, fuente)
