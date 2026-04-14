#!/usr/bin/env python3
"""Test de entregabilidad MIME — ejecutar ANTES de cualquier cambio en smtp_client.py.

Verifica que los correos cumplen todas las reglas anti-spam.
Si algún test falla, NO hacer deploy — el correo irá a spam.

Uso:
    cd /opt/maquita-webmail
    source backend/venv/bin/activate
    python3 backend/tests/test_mime_deliverability.py

Score actual verificado: 10/10 en mail-tester.com (14-Abril-2026)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.mail.clients.smtp_client import (
    build_mime_message, OutgoingEmail, _html_to_text, _wrap_html,
    _FORBIDDEN_HEADERS, _assert_no_forbidden_headers,
)

passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  \033[32m[PASS]\033[0m {name}")
    else:
        failed += 1
        errors.append(name)
        print(f"  \033[31m[FAIL]\033[0m {name}" + (f" — {detail}" if detail else ""))


def get_parts(msg):
    return [p.get_content_type() for p in msg.walk()
            if not p.get_content_type().startswith("multipart")]


def get_part_content(msg, content_type):
    for p in msg.walk():
        if p.get_content_type() == content_type:
            return p.get_payload(decode=True).decode("utf-8", errors="replace")
    return None


# ═══════════════════════════════════════════════════════════════
# REGLA 1: text/plain SIEMPRE presente y con contenido real
# Sin esto: MPART_ALT_DIFF (+0.79), MIME_HTML_ONLY (+0.1)
# ═══════════════════════════════════════════════════════════════
print("\n\033[1m=== REGLA 1: text/plain siempre real ===\033[0m")

msg = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<p>Hola <b>mundo</b></p>"
))
parts = get_parts(msg)
check("HTML-only genera text/plain", "text/plain" in parts, str(parts))

txt = get_part_content(msg, "text/plain")
check("text/plain no está vacío", txt and len(txt.strip()) > 0, f"len={len(txt or '')}")
check("text/plain tiene contenido real del HTML", txt and "Hola" in txt, repr(txt[:50] if txt else ""))

msg2 = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<ul><li>A</li><li>B</li><li>C</li></ul>"
))
txt2 = get_part_content(msg2, "text/plain")
check("Listas HTML se convierten a texto", txt2 and "A" in txt2 and "B" in txt2)

# ═══════════════════════════════════════════════════════════════
# REGLA 2: HTML siempre con DOCTYPE + <html> + <body>
# Sin esto: HTML_MIME_NO_HTML_TAG (+0.377)
# ═══════════════════════════════════════════════════════════════
print("\n\033[1m=== REGLA 2: HTML con estructura completa ===\033[0m")

msg3 = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<p>Fragmento simple</p>"
))
html = get_part_content(msg3, "text/html")
check("Fragmento tiene DOCTYPE", html and "<!DOCTYPE" in html)
check("Fragmento tiene <html>", html and "<html" in html)
check("Fragmento tiene <body>", html and "<body" in html)
check("Fragmento tiene </html>", html and "</html>" in html)

msg4 = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<!DOCTYPE html><html><body><p>Ya completo</p></body></html>"
))
html4 = get_part_content(msg4, "text/html")
check("HTML completo no duplica DOCTYPE", html4 and html4.count("<!DOCTYPE") == 1)

# ═══════════════════════════════════════════════════════════════
# REGLA 3: SIN headers que causan spam
# X-Priority: MISSING_MID (+0.14), outlook-style spam trigger
# ═══════════════════════════════════════════════════════════════
print("\n\033[1m=== REGLA 3: Sin headers spam ===\033[0m")

msg5 = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<p>Test</p>"
))
raw = msg5.as_string()
check("Sin X-Priority", "X-Priority" not in raw)
check("Sin X-MSMail-Priority", "X-MSMail-Priority" not in raw)
check("Sin Importance", "\nImportance:" not in raw)
check("Sin X-MimeOLE", "X-MimeOLE" not in raw)
check("Tiene X-Mailer correcto", "Maquita Webmail/1.0" in raw)
check("Tiene Organization", "Organization: Maquita" in raw)

# Validar que _assert_no_forbidden_headers funciona
from email.mime.multipart import MIMEMultipart
bad_msg = MIMEMultipart()
bad_msg["X-Priority"] = "1"
try:
    _assert_no_forbidden_headers(bad_msg)
    check("Guard detecta X-Priority", False, "no lanzó excepción")
except ValueError as e:
    check("Guard detecta X-Priority", "PROHIBIDO" in str(e))

# ═══════════════════════════════════════════════════════════════
# REGLA 4: Content-Type correcto
# ═══════════════════════════════════════════════════════════════
print("\n\033[1m=== REGLA 4: Content-Type correcto ===\033[0m")

check("HTML -> multipart/alternative", msg5.get_content_type() == "multipart/alternative")

msg_text = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    text_body="Solo texto"
))
check("Text-only -> multipart/alternative", msg_text.get_content_type() == "multipart/alternative")

msg_att = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<p>Con adjunto</p>",
    attachments=[__import__("app.mail.clients.smtp_client", fromlist=["EmailAttachment"]).EmailAttachment(
        filename="test.txt", content=b"hello", content_type="text/plain"
    )]
))
check("Con adjuntos -> multipart/mixed", msg_att.get_content_type() == "multipart/mixed")
att_parts = get_parts(msg_att)
check("Con adjuntos tiene text/plain", "text/plain" in att_parts)

# ═══════════════════════════════════════════════════════════════
# REGLA 5: Charset UTF-8
# ═══════════════════════════════════════════════════════════════
print("\n\033[1m=== REGLA 5: Charset UTF-8 ===\033[0m")

msg6 = build_mime_message(OutgoingEmail(
    from_addr="test@maquita.org", to=["x@x.com"], subject="T",
    html_body="<p>Año señor García niño José</p>"
))
txt6 = get_part_content(msg6, "text/plain")
check("UTF-8 en text/plain (ñ)", txt6 and "ñ" in txt6)
check("UTF-8 en text/plain (é)", txt6 and "é" in txt6)

for p in msg6.walk():
    if p.get_content_type() == "text/html":
        ct = str(p.get("Content-Type", ""))
        check("HTML declara charset=utf-8", "utf-8" in ct, ct)
    if p.get_content_type() == "text/plain":
        ct = str(p.get("Content-Type", ""))
        check("text/plain declara charset=utf-8", "utf-8" in ct, ct)

# ═══════════════════════════════════════════════════════════════
# REGLA 6: Funciones auxiliares
# ═══════════════════════════════════════════════════════════════
print("\n\033[1m=== REGLA 6: Funciones auxiliares ===\033[0m")

check("_html_to_text no vacío", _html_to_text("<p>Hola</p>") == "Hola")
check("_html_to_text decode &amp;", "&" in _html_to_text("<p>&amp;</p>"))
check("_html_to_text decode &lt;", "<" in _html_to_text("<p>&lt;</p>"))
check("_html_to_text decode &gt;", ">" in _html_to_text("<p>&gt;</p>"))
check("_html_to_text strips tags", "<" not in _html_to_text("<b>bold</b>"))

check("_wrap_html agrega DOCTYPE", "<!DOCTYPE" in _wrap_html("<p>x</p>"))
check("_wrap_html no duplica DOCTYPE", _wrap_html("<!DOCTYPE html><html>x</html>").count("<!DOCTYPE") == 1)
check("_FORBIDDEN_HEADERS tiene X-Priority", "X-Priority" in _FORBIDDEN_HEADERS)

# ═══════════════════════════════════════════════════════════════
# RESULTADO
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
if failed == 0:
    print(f"\033[32m✓ {passed} TESTS PASSED — MIME seguro para producción\033[0m")
    sys.exit(0)
else:
    print(f"\033[31m✗ {failed} TESTS FAILED — NO HACER DEPLOY\033[0m")
    for e in errors:
        print(f"  - {e}")
    print(f"\nSi se hace deploy con tests fallidos, los correos irán a SPAM.")
    sys.exit(1)
