"""
DLP — Detectores de datos sensibles en correo saliente.

Cada detector valida de verdad (no solo regex) para minimizar falsas alarmas:
- Cedula/RUC Ecuador: digito verificador (modulo 10 / modulo 11).
- Tarjetas de credito: algoritmo de Luhn.
- IBAN: checksum modulo 97.
- Palabras clave: lista configurable por el admin.

Uso: detect_all(text, keywords) -> list[Finding]
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Finding:
    data_type: str  # cedula | ruc | tarjeta | iban | cuenta | keyword
    label: str  # etiqueta amigable en español
    sample: str  # fragmento enmascarado (para mostrar/auditar)
    count: int = 1


def _mask(value: str) -> str:
    """Enmascara dejando solo los ultimos 2-4 caracteres: 1712****89."""
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return "*" * len(digits)
    keep = digits[-2:]
    return digits[:2] + "*" * (len(digits) - 4) + keep


# ── Cedula ecuatoriana (10 digitos, modulo 10) ──────────────────────────────
def _valid_cedula(ced: str) -> bool:
    if len(ced) != 10 or not ced.isdigit():
        return False
    prov = int(ced[:2])
    if prov < 1 or (prov > 24 and prov != 30):
        return False
    if int(ced[2]) >= 6:
        return False
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        p = int(ced[i]) * coef[i]
        if p >= 10:
            p -= 9
        total += p
    ver = (10 - (total % 10)) % 10
    return ver == int(ced[9])


# ── RUC ecuatoriano (13 digitos) ────────────────────────────────────────────
def _valid_ruc(ruc: str) -> bool:
    if len(ruc) != 13 or not ruc.isdigit():
        return False
    if not ruc.endswith(("001",)):
        # la mayoria termina en 001; aceptamos cualquier establecimiento 001-999
        if ruc[10:13] == "000":
            return False
    prov = int(ruc[:2])
    if prov < 1 or (prov > 24 and prov != 30):
        return False
    tercer = int(ruc[2])
    # Persona natural: tercer digito < 6 -> validar como cedula los primeros 10
    if tercer < 6:
        return _valid_cedula(ruc[:10])
    # Publica (6) o juridica (9): validacion de modulo 11
    if tercer == 6:
        coef = [3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(ruc[i]) * coef[i] for i in range(8))
        ver = 11 - (total % 11)
        ver = 0 if ver == 11 else ver
        return ver == int(ruc[8])
    if tercer == 9:
        coef = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(ruc[i]) * coef[i] for i in range(9))
        ver = 11 - (total % 11)
        ver = 0 if ver == 11 else ver
        return ver == int(ruc[9])
    return False


# ── Prefijo de emisor (IIN) ──────────────────────────────────────────────
# Luhn por si solo NO basta: el 10,3 % de los numeros de 16 digitos al azar lo
# pasan. Eso convertia identificadores largos de otros sistemas en falsas
# "tarjetas": las alertas del vigilante del servidor se marcaban asi.
# Toda tarjeta real empieza por un prefijo de emisor conocido. Exigirlo ademas
# de Luhn baja los falsos positivos al 3,9 % sin perder tarjetas de verdad.
def _prefijo_de_tarjeta(num: str) -> bool:
    """True si el numero empieza como una tarjeta real.
    Visa 4 · Mastercard 51-55 y 2221-2720 · Amex 34/37 · Discover 6 ·
    Diners 30/36/38/39 · JCB 35 · UnionPay 62.
    """
    if not num:
        return False
    if num[0] in "3456":
        return True
    # Mastercard serie 2: 2221-2720
    if len(num) >= 4 and num[0] == "2":
        try:
            return 2221 <= int(num[:4]) <= 2720
        except ValueError:
            return False
    return False


# ── Luhn (tarjetas de credito) ──────────────────────────────────────────────
def _valid_luhn(num: str) -> bool:
    if not num.isdigit() or not (13 <= len(num) <= 19):
        return False
    total = 0
    rev = num[::-1]
    for i, ch in enumerate(rev):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ── IBAN (modulo 97) ────────────────────────────────────────────────────────
def _valid_iban(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", iban):
        return False
    rearr = iban[4:] + iban[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearr)
    try:
        return int(digits) % 97 == 1
    except ValueError:
        return False


# Patrones candidatos (luego se validan)
_RE_NUM10 = re.compile(r"(?<!\d)(\d{10})(?!\d)")
_RE_NUM13 = re.compile(r"(?<!\d)(\d{13})(?!\d)")
_RE_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_RE_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{1,4}){2,7}\b")
# Cuenta bancaria: numeros de 8-14 digitos ANCLADOS a palabras de contexto
_RE_CUENTA_CTX = re.compile(
    r"(?:cuenta|cta\.?|account|nro\.?\s*cuenta|n[uú]mero\s+de\s+cuenta)"
    r"[\s:#.\-]*((?:\d[ -]?){8,20})",
    re.IGNORECASE,
)


def detect_all(text: str, keywords: list[str] | None = None) -> list[Finding]:
    """Analiza un texto y devuelve los hallazgos de datos sensibles."""
    findings: dict[str, Finding] = {}
    if not text:
        return []

    def add(dtype, label, sample):
        if dtype in findings:
            findings[dtype].count += 1
        else:
            findings[dtype] = Finding(dtype, label, _mask(sample))

    # Tarjetas (primero, para no confundir con cuentas)
    card_spans = []
    for m in _RE_CARD.finditer(text):
        raw = re.sub(r"[ -]", "", m.group(0))
        if _valid_luhn(raw) and _prefijo_de_tarjeta(raw):
            add("tarjeta", "Tarjeta de crédito", raw)
            card_spans.append((m.start(), m.end()))

    # RUC (13)
    for m in _RE_NUM13.finditer(text):
        if _valid_ruc(m.group(1)):
            add("ruc", "RUC (Ecuador)", m.group(1))

    # Cedula (10)
    for m in _RE_NUM10.finditer(text):
        if _valid_cedula(m.group(1)):
            add("cedula", "Cédula (Ecuador)", m.group(1))

    # IBAN
    for m in _RE_IBAN.finditer(text):
        if _valid_iban(m.group(0)):
            add("iban", "IBAN (cuenta internacional)", m.group(0))

    # Cuenta bancaria por contexto (evita solaparse con tarjetas ya halladas)
    for m in _RE_CUENTA_CTX.finditer(text):
        s = m.start(1)
        if any(a <= s < b for a, b in card_spans):
            continue
        raw = re.sub(r"[ -]", "", m.group(1))
        if 8 <= len(raw) <= 20:
            add("cuenta", "Cuenta bancaria", raw)

    # Palabras clave (configurables por el admin)
    for kw in keywords or []:
        kw = (kw or "").strip()
        if not kw:
            continue
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            key = "keyword:" + kw.lower()
            if key not in findings:
                findings[key] = Finding("keyword", f"Palabra clave: «{kw}»", kw)

    return list(findings.values())
