"""Avisar al webmail de que acaba de reinyectarse un correo para estos destinatarios (11/11/2026).

Así el destinatario lo ve en segundos en lugar de esperar la consulta periódica de 45 s. Es un aviso
de cortesía: nunca debe frenar ni tumbar el filtro de correo, por eso tiene un tope de medio segundo
y se traga cualquier error. No envía nada del mensaje, solo las direcciones.
"""
import json
import urllib.request

URL = "http://127.0.0.1:8000/api/interno/correo-en-camino"
TOPE_S = 0.5


def avisar(destinatarios):
    try:
        direcciones = [str(d) for d in (destinatarios or [])][:200]
        if not direcciones:
            return False
        peticion = urllib.request.Request(
            URL,
            data=json.dumps({"destinatarios": direcciones}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=TOPE_S) as r:
            return r.status == 200
    except Exception:
        return False
