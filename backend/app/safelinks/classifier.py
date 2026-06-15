"""Clasificador anti-phishing de contenido de correo.

Asigna a un mensaje un veredicto {phishing | suspicious | clean} con un puntaje
0-100 y las razones. Funciona DE ENTRADA con heurísticas propias (no requiere
servicios externos) y, opcionalmente, consulta un clasificador externo agnóstico
(p. ej. un modelo propio servido por HTTP) si se configura por entorno.

Diseño:
  - Capa 1 (siempre activa): heurísticas locales — suplantación de remitente,
    dominios lookalike, palabras de cosecha de credenciales/urgencia, enlaces
    cuyo texto no coincide con el destino, pedidos de dinero/datos.
  - Capa 2 (opcional): si PHISH_CLASSIFIER_URL está definido, se hace POST de las
    señales a ese endpoint y se fusiona su veredicto (se toma el mayor puntaje).
    Es FAIL-OPEN: si el endpoint falla o no está configurado, se devuelve solo
    la capa 1; nunca bloquea el flujo de correo.

El endpoint externo es agnóstico de proveedor: cualquier servicio que reciba
{sender, subject, body, urls, signals} y responda {label, score, reasons}.
La URL y la clave viven en el .env (gitignored), nunca en el código.

Salida: {"label": str, "score": int, "reasons": [str], "source": str}
"""
import json
import os
import re
import unicodedata
import urllib.request
from email.utils import parseaddr


def _norm(s: str) -> str:
    """minúsculas sin acentos ni ñ (robusto a la evasión de quitar tildes)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()

try:
    from . import lookalike, checker
except Exception:  # uso fuera del paquete (tests sueltos)
    import lookalike
    import checker

# --- léxico de cosecha de credenciales / urgencia (ES + EN) ---
# Patrones en ASCII sin tildes: el texto se normaliza con _norm() antes de matchear.
_URGENCIA = re.compile(
    r"\b(urgente|inmediat\w+|de inmediato|antes de|expira|caduc\w+|suspendid\w+|"
    r"bloquead\w+|desactiv\w+|verifi\w+|confirm\w+|actualice|valide|ultim\w+ aviso|"
    r"accion requerida|urgent|immediately|verify|suspended|expired|act now|final notice)\b",
    re.I)
_CREDENCIALES = re.compile(
    r"\b(contrasen\w+|clave|usuari\w+ y contrasen\w+|datos bancari\w+|tarjeta de credito|"
    r"numero de cuenta|cedula|inicie sesion|inicia sesion|reactivar|reactive su cuenta|"
    r"password|log ?in|sign ?in|credentials|account details|banking)\b",
    re.I)
_DINERO = re.compile(
    r"\b(transferen\w+|pago pendiente|factura adjunta|"
    r"gift card|tarjeta de regalo|bitcoin|criptomoned\w+|wire transfer|invoice|payment)\b",
    re.I)
# estafa de adelanto de pago: premio/herencia/loteria (señal fuerte por sí sola)
_PREMIO = re.compile(
    r"\b(premio|herenci\w+|loteria|ganaste|has ganado|ganador|"
    r"reclam\w+ tu premio|millones|prize|winner|you won|inheritance)\b", re.I)
_SALUDO_GENERICO = re.compile(
    r"\b(estimad\w+ (cliente|usuari\w+)|dear (customer|user)|querido usuario)\b", re.I)

# texto de un enlace HTML: <a href="X">TEXTO</a>
_ANCHOR = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_URL = re.compile(r'https?://[^\s"\'<>)]+', re.I)


def _domain(addr_or_url: str) -> str:
    s = (addr_or_url or "").strip()
    if "@" in s and "://" not in s:
        s = s.split("@")[-1]
    s = re.sub(r"^https?://", "", s, flags=re.I).split("/")[0].split(":")[0]
    return s.lower().strip(". ")


def _extract_urls(body: str) -> list[str]:
    if not body:
        return []
    urls = [m.group(0) for m in _URL.finditer(body)]
    return list(dict.fromkeys(urls))[:50]


def score_message(sender: str = "", subject: str = "", body: str = "",
                  urls: list[str] | None = None, signals: dict | None = None,
                  protected: set | None = None) -> dict:
    """Veredicto de phishing para un mensaje. No bloquea: solo puntúa."""
    reasons: list[str] = []
    score = 0
    text = _norm(f"{subject}\n{body}")
    name, addr = parseaddr(sender or "")
    from_dom = _domain(addr)

    # 1) Display-name suplanta una marca pero el dominio no corresponde
    if name and from_dom:
        la_name = lookalike.check(_domain(name)) if "." in name else {"lookalike": False}
        brand_in_name = re.search(r"(banco|paypal|microsoft|google|sri|iess|gobierno|soporte|"
                                  r"seguridad|it|admin|cuenta)", name, re.I)
        if brand_in_name and from_dom and not any(
                from_dom == p or from_dom.endswith("." + p) for p in (protected or lookalike.PROTECTED_DOMAINS)):
            # marca en el nombre + dominio remitente genérico/gratuito
            if re.search(r"(gmail|outlook|hotmail|yahoo|proton|mail)\.", from_dom):
                score += 30
                reasons.append(f"El remitente dice ser «{name.strip()}» pero escribe desde {from_dom}")

    # 2) Dominio remitente es lookalike de uno protegido
    if from_dom:
        la = lookalike.check(from_dom, protected)
        if la.get("lookalike"):
            score += 45
            reasons.append(f"Dominio remitente suplantado: {la['reason']}")

    # 3) Léxico de urgencia + credenciales (la combinación es la señal fuerte)
    urg = bool(_URGENCIA.search(text))
    cred = bool(_CREDENCIALES.search(text))
    if urg and cred:
        score += 35
        reasons.append("Mensaje urgente que pide credenciales/datos sensibles")
    elif cred:
        score += 15
        reasons.append("Pide credenciales o datos sensibles")
    elif urg:
        score += 8
        reasons.append("Tono de urgencia / amenaza de cierre")
    if _DINERO.search(text):
        score += 15
        reasons.append("Pide dinero / transferencia")
    if _PREMIO.search(text):
        score += 30
        reasons.append("Estafa de premio/herencia/lotería (adelanto de pago)")
    if _SALUDO_GENERICO.search(text):
        score += 5
        reasons.append("Saludo genérico (no usa tu nombre)")

    # 4) Enlaces: texto que aparenta un dominio distinto al href real
    for href, anchor in _ANCHOR.findall(body or ""):
        atxt = re.sub(r"<[^>]+>", "", anchor).strip()
        if _URL.search(atxt):
            tdom = _domain(atxt)
            hdom = _domain(href)
            if tdom and hdom and tdom != hdom and not hdom.endswith("." + tdom):
                score += 30
                reasons.append(f"Un enlace muestra «{tdom}» pero lleva a {hdom}")
                break

    # 5) Veredicto de los URLs (reusa el checker de Safe Links + lookalike)
    all_urls = list(urls or []) + _extract_urls(body)
    for u in all_urls[:20]:
        v = checker.analyze(u)
        if v.get("verdict") == "suspicious":
            score += 12
            reasons.append(f"Enlace sospechoso: {v['reason']}")
            break
    for u in all_urls[:20]:
        d = _domain(u)
        if d and lookalike.check(d, protected).get("lookalike"):
            score += 25
            reasons.append(f"Enlace a dominio suplantado ({d})")
            break

    score = min(score, 100)
    label = "phishing" if score >= 70 else "suspicious" if score >= 40 else "clean"
    result = {"label": label, "score": score, "reasons": reasons, "source": "heuristica"}

    # 6) Capa externa opcional (agnóstica) — fusiona si está configurada
    ext = _external_classify(sender, subject, body, all_urls, signals)
    if ext:
        if ext.get("score", 0) > result["score"]:
            result["label"] = ext.get("label", result["label"])
            result["score"] = ext["score"]
        result["reasons"] = result["reasons"] + ext.get("reasons", [])
        result["source"] = "heuristica+externo"
    return result


def _external_classify(sender, subject, body, urls, signals) -> dict | None:
    """POST a un clasificador externo si PHISH_CLASSIFIER_URL está definido.
    Agnóstico de proveedor. Fail-open: cualquier error → None."""
    url = os.getenv("PHISH_CLASSIFIER_URL", "").strip()
    if not url:
        return None
    try:
        payload = json.dumps({
            "sender": sender, "subject": subject,
            "body": (body or "")[:20000], "urls": urls[:50],
            "signals": signals or {},
        }).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        key = os.getenv("PHISH_CLASSIFIER_KEY", "").strip()
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        timeout = float(os.getenv("PHISH_CLASSIFIER_TIMEOUT", "4"))
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return {"label": data.get("label"), "score": int(data.get("score", 0)),
                "reasons": list(data.get("reasons", []))}
    except Exception:
        return None
