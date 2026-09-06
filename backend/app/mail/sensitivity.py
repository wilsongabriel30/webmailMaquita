"""Etiquetas de sensibilidad de correo (Publica/Interna/Confidencial/Restringida).

A) Marca visible: banner en el cuerpo del correo.
B) Control de salida: Confidencial/Restringida no salen a destinatarios externos
   (el control real lo aplica el router /send con el motor DLP).
Autor: Wilson Arguello - Tecnologia, Fundacion Maquita. 2026-09-01.
"""

LABELS = {
    "Publica": {"ext_ok": True, "color": "#146138", "bg": "#e3f4ea", "text": "PUBLICA"},
    "Interna": {
        "ext_ok": True,
        "color": "#1f4f83",
        "bg": "#e7f0fb",
        "text": "INTERNA \u00b7 uso interno",
    },
    "Confidencial": {
        "ext_ok": False,
        "color": "#8a5510",
        "bg": "#fbf1e0",
        "text": "CONFIDENCIAL \u00b7 no reenviar fuera de la organizaci\u00f3n",
    },
    "Restringida": {
        "ext_ok": False,
        "color": "#8f2417",
        "bg": "#fbe9e7",
        "text": "RESTRINGIDA \u00b7 informaci\u00f3n sensible, circulaci\u00f3n limitada",
    },
}


def normalize(label: str) -> str:
    if not label:
        return ""
    s = str(label).strip().lower()
    for k in LABELS:
        if k.lower() == s:
            return k
    return ""


def blocks_external(label: str) -> bool:
    l = normalize(label)
    return bool(l) and not LABELS[l]["ext_ok"]


def banner_html(label: str) -> str:
    l = normalize(label)
    if not l:
        return ""
    c = LABELS[l]
    return (
        '<div style="margin:0 0 12px;padding:8px 14px;border-left:4px solid '
        + c["color"]
        + ";"
        "background:" + c["bg"] + ";color:" + c["color"] + ";"
        'font:600 13px Calibri,Segoe UI,sans-serif;border-radius:0 4px 4px 0">'
        "\U0001f512 " + c["text"] + "</div>"
    )
