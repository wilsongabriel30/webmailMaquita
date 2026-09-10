"""
Búsqueda avanzada — Maquita Webmail
====================================
Parser de operadores estilo Gmail para IMAP SEARCH.
Soporta: from:, to:, subject:, has:attachment, before:, after:, is:unread, is:flagged, label:, larger:, smaller:
"""

import re
from datetime import datetime, timedelta

# Atajos de fecha: lo que uno recuerda de un correo suele ser «era de esta semana».
_ATAJOS_FECHA = {
    "hoy": 0,
    "ayer": 1,
    "semana": 7,
    "mes": 30,
    "trimestre": 90,
    "ano": 365,
    "año": 365,
}


def _entrecomillar(valor: str) -> str:
    """Una cadena para IMAP, con lo que hay que escapar escapado (RFC 3501).

    Sin esto, una comilla en lo que escribe la persona cierra la cadena antes de tiempo y lo que
    viene detrás lo lee IMAP como criterio: `dominio:x" ALL "` acababa en `FROM "@x" ALL "`, y ese
    ALL devuelve el buzon entero en vez de lo que se pidio.

    Se quitan tambien los caracteres de control: no aportan nada a una busqueda y son justo los
    que separan ordenes en el protocolo.
    """
    limpio = "".join(c for c in valor if c >= " " and c != "\x7f")
    return '"' + limpio.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_search_query(query: str, buscar_en_contenido: bool = False) -> list[str]:
    """
    Parse a search query with operators into IMAP SEARCH criteria.

    Supported operators:
      from:name          → FROM "name"
      to:name            → TO "name"
      subject:text       → SUBJECT "text"
      has:attachment      → NOT BODY "Content-Disposition: inline" (approximate)
      before:2026-03-01  → BEFORE 01-Mar-2026
      after:2026-03-01   → SINCE 01-Mar-2026
      is:unread          → UNSEEN
      is:read            → SEEN
      is:flagged         → FLAGGED
      is:unflagged       → UNFLAGGED
      larger:1M          → LARGER 1048576
      smaller:500K       → SMALLER 512000
      "exact phrase"     → TEXT "exact phrase"
      plain text         → OR FROM/SUBJECT/BODY (like current)
    """
    q = query.strip()
    if not q:
        return ["ALL"]

    criteria = []
    remaining_words = []

    # Extract quoted strings first, replace with placeholders
    quotes = {}

    def replace_quote(m):
        key = f"__Q{len(quotes)}__"
        quotes[key] = m.group(1)
        return key

    q = re.sub(r'"([^"]+)"', replace_quote, q)

    # Alias en español → operadores canónicos
    _ES = {
        "de:": "from:",
        "para:": "to:",
        "copia:": "cc:",
        "asunto:": "subject:",
        "cuerpo:": "body:",
        "antes:": "before:",
        "despues:": "after:",
        "después:": "after:",
        "etiqueta:": "label:",
        "mayor:": "larger:",
        "menor:": "smaller:",
        "contenido:": "body:",
        "dominio:": "domain:",
        "de-dominio:": "fromdomain:",
        "entre:": "between:",
    }
    _ES_EXACT = {
        "tiene:adjunto": "has:attachment",
        "con:adjunto": "has:attachment",
        "adjunto:si": "has:attachment",
        "adjunto:sí": "has:attachment",
        "es:noleido": "is:unread",
        "es:noleído": "is:unread",
        "es:marcado": "is:flagged",
    }

    def _traducir(t: str) -> str:
        low = t.lower()
        if low in _ES_EXACT:
            return _ES_EXACT[low]
        for es, en in _ES.items():
            if low.startswith(es):
                return en + t[len(es) :]
        return t

    tokens = [_traducir(t) for t in q.split()]
    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Restore quotes
        for k, v in quotes.items():
            token = token.replace(k, v)

        # Acotar por dominio: es cabecera, sale al instante y es lo que uno recuerda cuando
        # no sabe el remitente exacto («era alguien de Andes»).
        if token.lower().startswith("domain:"):
            dom = token[7:].strip('"').lstrip("@")
            if dom:
                criteria.extend(
                    [
                        "OR",
                        "FROM",
                        _entrecomillar("@" + dom),
                        "TO",
                        _entrecomillar("@" + dom),
                    ]
                )
        elif token.lower().startswith("fromdomain:"):
            dom = token[11:].strip('"').lstrip("@")
            if dom:
                criteria.extend(["FROM", _entrecomillar("@" + dom)])
        # Un rango de fechas de una vez, en vez de after: y before: por separado.
        elif token.lower().startswith("between:"):
            # La coma es el separador bueno: nginx bloquea cualquier «..» en la URL como
            # defensa contra path traversal, asi que un rango con «..» no llega ni a entrar.
            # Se admite igualmente por si alguien lo escribe de memoria.
            crudo = token[8:].strip('"')
            trozos = crudo.split(",") if "," in crudo else crudo.split("..")
            if len(trozos) == 2:
                desde = _parse_date(trozos[0].strip())
                hasta = _parse_date(trozos[1].strip())
                if desde:
                    criteria.extend(["SINCE", desde])
                if hasta:
                    criteria.extend(["BEFORE", hasta])
        elif token.lower() in _ATAJOS_FECHA:
            desde = (
                datetime.now() - timedelta(days=_ATAJOS_FECHA[token.lower()])
            ).strftime("%d-%b-%Y")
            criteria.extend(["SINCE", desde])
        elif token.lower().startswith("from:"):
            val = token[5:].strip('"')
            criteria.extend(["FROM", _entrecomillar(val)])
        elif token.lower().startswith("to:"):
            val = token[3:].strip('"')
            criteria.extend(["TO", _entrecomillar(val)])
        elif token.lower().startswith("cc:"):
            val = token[3:].strip('"')
            criteria.extend(["CC", _entrecomillar(val)])
        elif token.lower().startswith("subject:"):
            val = token[8:].strip('"')
            criteria.extend(["SUBJECT", _entrecomillar(val)])
        elif token.lower().startswith("body:"):
            val = token[5:].strip('"')
            criteria.extend(["BODY", _entrecomillar(val)])
        elif token.lower() == "has:attachment":
            # IMAP doesn't have a direct "has attachment" filter
            # Use HEADER Content-Type multipart/mixed as approximation
            criteria.extend(["HEADER", "Content-Type", '"multipart/mixed"'])
        elif token.lower().startswith("before:"):
            date_str = token[7:]
            imap_date = _parse_date(date_str)
            if imap_date:
                criteria.extend(["BEFORE", imap_date])
        elif token.lower().startswith("after:"):
            date_str = token[6:]
            imap_date = _parse_date(date_str)
            if imap_date:
                criteria.extend(["SINCE", imap_date])
        elif token.lower().startswith("since:"):
            date_str = token[6:]
            imap_date = _parse_date(date_str)
            if imap_date:
                criteria.extend(["SINCE", imap_date])
        elif token.lower() == "is:unread":
            criteria.append("UNSEEN")
        elif token.lower() == "is:read":
            criteria.append("SEEN")
        elif token.lower() == "is:flagged":
            criteria.append("FLAGGED")
        elif token.lower() == "is:unflagged":
            criteria.append("UNFLAGGED")
        elif token.lower() == "is:starred":
            criteria.append("FLAGGED")
        elif token.lower().startswith("larger:"):
            size = _parse_size(token[7:])
            if size:
                criteria.extend(["LARGER", str(size)])
        elif token.lower().startswith("smaller:"):
            size = _parse_size(token[8:])
            if size:
                criteria.extend(["SMALLER", str(size)])
        else:
            remaining_words.append(token)

        i += 1

    # Free text: search in FROM, SUBJECT, BODY (OR combination)
    if remaining_words:
        text = " ".join(remaining_words)
        # Restore any remaining quotes
        for k, v in quotes.items():
            text = text.replace(k, v)

        # El texto suelto NO entra en el cuerpo. Medido en un buzon de 20 GB: por cabeceras
        # responde en menos de 0,1 s; anadir BODY lo llevaba a 93 s, porque hay que abrir y
        # descifrar los mensajes uno a uno. Quien quiera buscar dentro del texto lo pide con
        # `contenido:` o con el boton de la interfaz, y entonces sabe por que espera.
        libre = [
            "OR",
            "OR",
            "FROM " + _entrecomillar(text),
            "TO " + _entrecomillar(text),
            "SUBJECT " + _entrecomillar(text),
        ]
        if buscar_en_contenido:
            libre = ["OR"] + libre + ["BODY " + _entrecomillar(text)]
        if criteria:
            criteria.extend(libre)
        else:
            criteria = libre

    # Red de debajo: entrar en el cuerpo sin acotar por fecha es la operacion mas cara que
    # existe aqui -hay que abrir y descifrar los mensajes uno a uno- y la interfaz lo limita a
    # tres meses, pero la interfaz se puede saltar. Si nadie acoto, se acota al ultimo ano.
    if buscar_en_contenido and not any(
        c in ("SINCE", "BEFORE", "ON")
        or str(c).startswith(("SINCE ", "BEFORE ", "ON "))
        for c in criteria
    ):
        desde = (datetime.now() - timedelta(days=365)).strftime("%d-%b-%Y")
        criteria = ["SINCE", desde] + criteria

    return criteria if criteria else ["ALL"]


def _parse_date(date_str: str) -> str | None:
    """Convert date string to IMAP format (01-Mar-2026)."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d-%b-%Y")
        except ValueError:
            continue
    return None


def _parse_size(size_str: str) -> int | None:
    """Parse size string like 1M, 500K, 1024 into bytes."""
    m = re.match(r"(\d+)\s*([KkMmGg])?[Bb]?", size_str)
    if not m:
        return None
    num = int(m.group(1))
    unit = (m.group(2) or "").upper()
    if unit == "K":
        return num * 1024
    elif unit == "M":
        return num * 1024 * 1024
    elif unit == "G":
        return num * 1024 * 1024 * 1024
    return num


def get_search_suggestions() -> list[dict]:
    """Return available search operators for the UI."""
    return [
        {
            "operator": "from:",
            "description": "Buscar por remitente",
            "example": "from:juan",
        },
        {
            "operator": "to:",
            "description": "Buscar por destinatario",
            "example": "to:maria",
        },
        {
            "operator": "subject:",
            "description": "Buscar en asunto",
            "example": "subject:factura",
        },
        {
            "operator": "has:attachment",
            "description": "Con adjuntos",
            "example": "has:attachment",
        },
        {
            "operator": "before:",
            "description": "Antes de fecha",
            "example": "before:2026-03-01",
        },
        {
            "operator": "after:",
            "description": "Después de fecha",
            "example": "after:2026-01-01",
        },
        {"operator": "is:unread", "description": "No leídos", "example": "is:unread"},
        {
            "operator": "is:flagged",
            "description": "Con bandera",
            "example": "is:flagged",
        },
        {
            "operator": "larger:",
            "description": "Más grande que",
            "example": "larger:5M",
        },
        {
            "operator": "smaller:",
            "description": "Más pequeño que",
            "example": "smaller:1M",
        },
    ]
