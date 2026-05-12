#!/usr/bin/env python3
"""
Maquita Spam Filter Service
Funciona como content_filter de Postfix (pipe transport).
Recibe correo, analiza keywords, agrega header X-Maquita-Spam, reinyecta.
NUNCA rechaza correos - siempre los entrega (a Inbox o Junk via sieve).
"""
import sys
import os
import email
import email.policy
import re
import logging
import subprocess
import smtplib
from datetime import datetime
from email.header import decode_header

# --- Configuración ---
KEYWORDS_FILE = "/etc/maquita-mail/spam-keywords.txt"
WHITELIST_FILE = "/etc/maquita-mail/whitelist-senders.txt"
LOG_FILE = "/var/log/maquita-spam-filter.log"
SCORE_THRESHOLD = 3
SENDMAIL = "/usr/sbin/sendmail"
REINJECT_HOST = "127.0.0.1"
REINJECT_PORT = 10025

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def load_file_lines(filepath):
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    lines.append(line.lower())
    except FileNotFoundError:
        pass
    return lines


def decode_subject(msg):
    subject = msg.get("Subject", "")
    if not subject:
        return ""
    decoded_parts = decode_header(subject)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def get_body_text(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    body += payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    pass
            elif ct == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    body += re.sub(r"<[^>]+>", " ", html)
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            pass
    return body


def get_sender(msg):
    from_header = msg.get("From", "")
    match = re.search(r"[\w.+-]+@[\w.-]+", from_header)
    return match.group(0).lower() if match else from_header.lower()


def check_spam(msg, keywords, whitelist):
    sender = get_sender(msg)
    sender_domain = sender.split("@")[-1] if "@" in sender else ""

    # Whitelist check
    for wl in whitelist:
        if wl in sender or wl in sender_domain:
            return False, 0, ["whitelist:" + wl]

    subject = decode_subject(msg).lower()
    body = get_body_text(msg).lower()
    full_text = subject + " " + body

    score = 0
    razones = []

    for line in keywords:
        parts = line.split("|")
        keyword = parts[0].strip()
        weight = int(parts[1].strip()) if len(parts) > 1 else 1
        if keyword in full_text:
            score += weight
            razones.append(keyword + "(+" + str(weight) + ")")

    # Heurísticas adicionales
    links = re.findall(r"https?://", full_text)
    if len(links) > 10:
        score += 2
        razones.append("muchos-links(+2)")

    if not subject.strip():
        score += 1
        razones.append("subject-vacio(+1)")

    return score >= SCORE_THRESHOLD, score, razones


def main():
    # Postfix pipe transport: -f sender -- recipient1 recipient2 ...
    sender = None
    recipients = []
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "-f":
            i += 1
            if i < len(args):
                sender = args[i]
        elif args[i] == "--":
            recipients.extend(args[i + 1:])
            break
        else:
            recipients.append(args[i])
        i += 1

    try:
        raw = sys.stdin.buffer.read()
        msg = email.message_from_bytes(raw, policy=email.policy.compat32)

        keywords = load_file_lines(KEYWORDS_FILE)
        whitelist = load_file_lines(WHITELIST_FILE)

        is_spam, score, razones = check_spam(msg, keywords, whitelist)
        from_addr = get_sender(msg)
        subject = decode_subject(msg)

        # Agregar headers custom (no modificar el correo original de otra forma)
        if is_spam:
            msg["X-Maquita-Spam"] = "YES"
        else:
            msg["X-Maquita-Spam"] = "NO"
        msg["X-Maquita-Spam-Score"] = str(score)
        if razones:
            msg["X-Maquita-Spam-Reasons"] = ", ".join(razones[:5])

        verdict = "SPAM" if is_spam else "HAM"
        razones_str = ", ".join(razones) if razones else "ninguna"
        rcpt_str = ",".join(recipients)
        logging.info(
            "%s | score=%d/%d | from=%s | to=%s | subject=%s | razones=%s",
            verdict, score, SCORE_THRESHOLD, from_addr, rcpt_str,
            subject[:80], razones_str
        )

        # Reinyectar el correo a Postfix vía SMTP en puerto 10025 (sin content_filter)
        try:
            smtp = smtplib.SMTP(REINJECT_HOST, REINJECT_PORT)
            smtp.sendmail(sender or "", recipients, msg.as_bytes())
            smtp.quit()
        except Exception as smtp_err:
            logging.error("SMTP reinject failed: %s", str(smtp_err))
            sys.exit(75)  # EX_TEMPFAIL - Postfix reintentará

        sys.exit(0)

    except Exception as e:
        logging.error("Error en filtro: %s", str(e))
        # NUNCA perder correo - temp fail para que Postfix reintente
        sys.exit(75)


if __name__ == "__main__":
    main()
