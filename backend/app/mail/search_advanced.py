"""
Búsqueda avanzada — Maquita Webmail
====================================
Parser de operadores estilo Gmail para IMAP SEARCH.
Soporta: from:, to:, subject:, has:attachment, before:, after:, is:unread, is:flagged, label:, larger:, smaller:
"""

import re
from datetime import datetime


def parse_search_query(query: str) -> list[str]:
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

        if token.lower().startswith("from:"):
            val = token[5:].strip('"')
            criteria.extend(["FROM", f'"{val}"'])
        elif token.lower().startswith("to:"):
            val = token[3:].strip('"')
            criteria.extend(["TO", f'"{val}"'])
        elif token.lower().startswith("cc:"):
            val = token[3:].strip('"')
            criteria.extend(["CC", f'"{val}"'])
        elif token.lower().startswith("subject:"):
            val = token[8:].strip('"')
            criteria.extend(["SUBJECT", f'"{val}"'])
        elif token.lower().startswith("body:"):
            val = token[5:].strip('"')
            criteria.extend(["BODY", f'"{val}"'])
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

        if criteria:
            # Add OR search for free text on top of existing criteria
            criteria.extend(
                ["OR", "OR", f'FROM "{text}"', f'SUBJECT "{text}"', f'BODY "{text}"']
            )
        else:
            criteria = [
                "OR",
                "OR",
                f'FROM "{text}"',
                f'SUBJECT "{text}"',
                f'BODY "{text}"',
            ]

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
