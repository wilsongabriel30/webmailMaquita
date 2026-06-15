"""Detección de dominios lookalike (suplantación / typosquatting / homoglyphs).

Compara el dominio remitente contra una lista de dominios protegidos (propios +
marcas sensibles) y detecta intentos de suplantación:
  - typosquatting:   maqulta.org  ~ maquita.org   (1 edición)
  - homoglyphs/IDN:  bancopichіncha.com (cirílica) ~ bancopichincha.com
  - inserción TLD:   maquita-org.com, maquita.org.secure-login.com

No bloquea por sí solo: produce un veredicto para que el motor anti-phishing /
Safe Links lo use (subir score, avisar, cuarentena).
"""
import unicodedata

# Dominios propios + marcas sensibles (ampliar por instalación / .env).
PROTECTED_DOMAINS = {
    "maquita.org", "maquita.com.ec", "mcch.com.ec", "fundmcch.com.ec",
    "maquitaturismo.com", "relacc-la.org", "alimentaelcambio.com.ec",
    "invertiagro.com", "productoresdema.com",
    # marcas frecuentemente suplantadas (Ecuador / globales)
    "bancopichincha.com", "bancoguayaquil.com", "produbanco.com",
    "bancodelpacifico.com", "google.com", "microsoft.com", "paypal.com",
    "office365.com", "outlook.com",
}

# Homoglyphs comunes -> carácter ASCII canónico
_CONFUSABLES = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s",
    "rn": "m", "vv": "w",
}


def _skeleton(s: str) -> str:
    """Normaliza un dominio a su 'esqueleto' para comparar confundibles."""
    # quitar acentos/unicode -> ASCII aproximado (homoglyphs IDN cirílicos, etc.)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    for bad, good in _CONFUSABLES.items():
        s = s.replace(bad, good)
    return s


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def check(domain: str, protected: set | None = None) -> dict:
    """Devuelve {'lookalike': bool, 'target': str|None, 'reason': str}."""
    protected = protected or PROTECTED_DOMAINS
    d = (domain or "").strip().lower().rstrip(".")
    if not d:
        return {"lookalike": False, "target": None, "reason": ""}
    # IDN -> punycode/ascii para detectar homoglyphs
    try:
        d_ascii = d.encode("idna").decode("ascii")
    except Exception:  # noqa: BLE001
        d_ascii = d
    if d in protected:
        return {"lookalike": False, "target": None, "reason": "dominio legítimo"}

    sk = _skeleton(d)
    for p in protected:
        if d == p:
            return {"lookalike": False, "target": None, "reason": "legítimo"}
        # 1) homoglyph: el esqueleto coincide con un protegido pero el dominio no
        if sk == _skeleton(p) and d != p:
            return {"lookalike": True, "target": p,
                    "reason": f"homoglyph/confundible de {p}"}
        # 2) un protegido aparece como subdominio/sufijo engañoso
        core = p.split(".")[0]
        if core in d and not d.endswith(p) and len(core) >= 4:
            return {"lookalike": True, "target": p,
                    "reason": f"usa '{core}' fuera de {p} (subdominio engañoso)"}
        # 3) typosquatting: distancia de edición pequeña sobre el dominio completo
        if abs(len(d) - len(p)) <= 2:
            dist = _levenshtein(sk, _skeleton(p))
            if 0 < dist <= 2:
                return {"lookalike": True, "target": p,
                        "reason": f"typosquatting de {p} (distancia {dist})"}
    return {"lookalike": False, "target": None, "reason": ""}
