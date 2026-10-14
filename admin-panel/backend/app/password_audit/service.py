"""Auditoría de contraseñas de los buzones (panel de administración).

Detecta cuentas cuya clave en la tabla `mailbox` (la única fuente que consulta
Dovecot) es inservible: vacía, en texto plano o con un formato que Dovecot no
puede usar. Así un importador nunca deja buzones rotos en silencio.

No detecta el caso «hash válido pero distinto al que la persona conoce» (no hay
forma sin la clave en claro); para eso están la verificación IMAP al asignar una
clave y el restablecimiento con clave temporal.
"""

import re

_SCHEME = re.compile(r"^\{([A-Za-z0-9.\-]+)\}")
_CRYPT = re.compile(r"^\$[0-9a-z]+\$")
_PLAIN_SCHEMES = {"PLAIN", "CLEARTEXT", "CLEAR", "PLAIN-TRUNC"}


def classify(pw: str | None) -> str:
    """Devuelve ok | empty | plaintext | invalid según el hash guardado."""
    pw = (pw or "").strip()
    if not pw:
        return "empty"
    m = _SCHEME.match(pw)
    if m:
        return "plaintext" if m.group(1).upper() in _PLAIN_SCHEMES else "ok"
    if _CRYPT.match(pw):
        return "ok"
    return "invalid"


async def audit(db) -> dict:
    rows = await db.fetch(
        "SELECT username, password, active FROM mailbox ORDER BY username"
    )
    ok = 0
    empty: list[dict] = []
    plaintext: list[dict] = []
    invalid: list[dict] = []
    for r in rows:
        cat = classify(r["password"])
        item = {"username": r["username"], "active": r["active"]}
        if cat == "ok":
            ok += 1
        elif cat == "empty":
            empty.append(item)
        elif cat == "plaintext":
            plaintext.append(item)
        else:
            invalid.append(item)
    flagged = empty + plaintext + invalid
    return {
        "total": len(rows),
        "ok": ok,
        "flagged_count": len(flagged),
        "empty": empty,
        "plaintext": plaintext,
        "invalid_format": invalid,
    }
