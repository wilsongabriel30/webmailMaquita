"""Comprobación de la propagación de una zona, vista desde Internet.

Se consulta por DNS sobre HTTPS (dns.google) y no con el resolutor local: el del servidor (o el de su
red) puede responder con datos propios y dar por buena una zona que fuera todavía no existe.
"""

import json
import urllib.parse
import urllib.request

import zona as Z

DOH = "https://dns.google/resolve"


def _consultar(nombre, tipo, cd=False):
    q = urllib.parse.urlencode({"name": nombre, "type": tipo, "cd": "1" if cd else "0"})
    pet = urllib.request.Request(f"{DOH}?{q}", headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(pet, timeout=15) as r:
            datos = json.load(r)
    except Exception as e:
        return None, f"sin respuesta ({type(e).__name__})"
    if datos.get("Status") != 0:
        return [], {2: "SERVFAIL", 3: "no existe (NXDOMAIN)"}.get(datos.get("Status"), f"estado {datos.get('Status')}")
    return [a.get("data", "").rstrip(".").lower().strip('"') for a in datos.get("Answer", [])], None


def comprobar(zona):
    z = Z.leer(zona)
    regs = z["registros"]
    ns_esperados = sorted(r["valor"].rstrip(".") for r in regs if r["tipo"] == "NS" and r["nombre"] == "@")
    ip_mail = next((r["valor"] for r in regs if r["nombre"] == "mail" and r["tipo"] == "A"), None)
    ip_web = next((r["valor"] for r in regs if r["nombre"] == "@" and r["tipo"] == "A"), None)
    mx = next((r["valor"].rstrip(".") for r in regs if r["tipo"] == "MX"), None)

    pruebas = []

    def anotar(clave, titulo, obtenido, error, correcto, que_hacer):
        pruebas.append({"clave": clave, "titulo": titulo, "ok": bool(correcto),
                        "obtenido": error or ", ".join(obtenido or []) or "(vacío)", "que_hacer": "" if correcto else que_hacer})

    ns, err = _consultar(zona, "NS", cd=True)
    anotar("delegacion", "Delegación en el registrador (NS)", ns, err, ns and sorted(ns) == ns_esperados,
           "En el registrador del dominio, cambie los servidores de nombres por: " + ", ".join(ns_esperados)
           + " (con sus IP como registros de enlace o «glue»).")
    soa, err = _consultar(zona, "SOA")
    anotar("respuesta", "La zona responde desde Internet", soa, err, bool(soa),
           "Espere a que propague la delegación (hasta 24 h) y que los puertos 53 UDP/TCP lleguen a este servidor.")
    if ip_mail:
        a, err = _consultar(f"mail.{zona}", "A")
        anotar("correo", f"mail.{zona} apunta a este servidor", a, err, a and ip_mail in a, "Depende de la delegación.")
    if mx:
        m, err = _consultar(zona, "MX")
        anotar("mx", "MX (recepción de correo)", m, err, m and any(x.endswith(mx) for x in m), "Depende de la delegación.")
    if ip_web:
        w, err = _consultar(zona, "A")
        anotar("web", "El sitio web apunta a este servidor", w, err, w and ip_web in w, "Depende de la delegación.")
    return {"zona": zona, "lista": all(p["ok"] for p in pruebas), "pruebas": pruebas}
