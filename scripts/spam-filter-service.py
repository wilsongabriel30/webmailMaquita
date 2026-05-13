#!/usr/bin/env python3
"""
Maquita Spam Filter Service v2
Funciona como content_filter de Postfix (pipe transport).
Recibe correo, analiza keywords + listas negras + heuristicas, agrega header X-Maquita-Spam, reinyecta.
NUNCA rechaza correos - siempre los entrega (a Inbox o Junk via sieve).
"""
import sys
import os
import email
import email.policy
import re
import logging
import smtplib
from datetime import datetime
from email.header import decode_header

# --- Configuración ---
KEYWORDS_FILE = "/etc/maquita-mail/spam-keywords.txt"
WHITELIST_FILE = "/etc/maquita-mail/whitelist-senders.txt"
BLACKLIST_DOMAINS_FILE = "/etc/maquita-mail/blacklist-domains.txt"
BLACKLIST_IPS_FILE = "/etc/maquita-mail/blacklist-ips.txt"
GREYLIST_DOMAINS_FILE = "/etc/maquita-mail/greylist-domains.txt"
LOG_FILE = "/var/log/maquita-spam-filter.log"
SCORE_THRESHOLD = 3
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


def get_sender_ip(msg):
    """Extrae la IP del servidor remitente desde Received headers."""
    received = msg.get_all("Received", [])
    if received:
        # El primer Received es el mas reciente (nuestro servidor)
        # El segundo es el del servidor remitente
        for header in received:
            match = re.search(r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]", header)
            if match:
                ip = match.group(1)
                # Ignorar IPs locales
                if not ip.startswith("127.") and not ip.startswith("10.") and not ip.startswith("192.168."):
                    return ip
    return ""


def ip_in_range(ip, cidr):
    """Verifica si una IP esta en un rango CIDR."""
    try:
        import ipaddress
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except (ValueError, ImportError):
        return ip == cidr


def check_blacklist_ip(ip, blacklist_ips):
    """Verifica si la IP esta en la lista negra."""
    if not ip:
        return False, ""
    for entry in blacklist_ips:
        if "/" in entry:
            if ip_in_range(ip, entry):
                return True, entry
        elif ip == entry:
            return True, entry
    return False, ""


def check_blacklist_domain(sender_domain, blacklist_domains):
    """Verifica si el dominio esta en la lista negra."""
    for bl_domain in blacklist_domains:
        if bl_domain == sender_domain or sender_domain.endswith("." + bl_domain):
            return True, bl_domain
    return False, ""


def check_heuristics(msg, subject, body, full_text):
    """Heuristicas avanzadas propias — como un banco evalua transacciones."""
    score = 0
    razones = []

    # --- 1. Muchos links (>10) = sospechoso ---
    links = re.findall(r"https?://", full_text)
    if len(links) > 15:
        score += 3
        razones.append(f"exceso-links({len(links)})(+3)")
    elif len(links) > 10:
        score += 2
        razones.append(f"muchos-links({len(links)})(+2)")

    # --- 2. Subject vacio ---
    if not subject.strip():
        score += 1
        razones.append("subject-vacio(+1)")

    # --- 3. Solo HTML, sin texto plano ---
    has_plain = False
    has_html = False
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                has_plain = True
            elif ct == "text/html":
                has_html = True
    if has_html and not has_plain:
        score += 1
        razones.append("solo-html(+1)")

    # --- 4. Ratio de mayusculas en subject ---
    if subject and len(subject) > 5:
        upper_ratio = sum(1 for c in subject if c.isupper()) / len(subject)
        if upper_ratio > 0.7:
            score += 2
            razones.append(f"subject-MAYUSCULAS({upper_ratio:.0%})(+2)")

    # --- 5. URLs sospechosas (IP en URL, URLs acortadas) ---
    ip_urls = re.findall(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", full_text)
    if ip_urls:
        score += 2
        razones.append(f"url-con-ip({len(ip_urls)})(+2)")

    short_urls = re.findall(r"https?://(bit\.ly|tinyurl|t\.co|goo\.gl|is\.gd|buff\.ly|ow\.ly|shorturl)", full_text)
    if len(short_urls) > 3:
        score += 2
        razones.append(f"urls-acortadas({len(short_urls)})(+2)")

    # --- 6. Adjuntos sospechosos ---
    suspicious_exts = {".exe", ".scr", ".bat", ".cmd", ".vbs", ".js", ".wsf", ".hta", ".pif", ".com"}
    if msg.is_multipart():
        for part in msg.walk():
            filename = part.get_filename("")
            if filename:
                ext = os.path.splitext(filename.lower())[1]
                if ext in suspicious_exts:
                    score += 5
                    razones.append(f"adjunto-peligroso({filename})(+5)")
                elif ext == ".zip" or ext == ".rar":
                    # Archivos comprimidos son sospechosos pero no definitivos
                    score += 1
                    razones.append(f"adjunto-comprimido({filename})(+1)")

    # --- 7. Reply-To diferente de From ---
    from_addr = get_sender(msg)
    reply_to = msg.get("Reply-To", "")
    if reply_to:
        reply_match = re.search(r"[\w.+-]+@[\w.-]+", reply_to)
        if reply_match:
            reply_domain = reply_match.group(0).split("@")[-1].lower()
            from_domain = from_addr.split("@")[-1] if "@" in from_addr else ""
            if from_domain and reply_domain != from_domain:
                score += 2
                razones.append(f"reply-to-diferente({reply_domain})(+2)")

    # --- 8. No tiene DKIM ni SPF (headers de autenticacion) ---
    auth_results = msg.get("Authentication-Results", "")
    if auth_results:
        has_dkim = "dkim=pass" in auth_results.lower()
        has_spf = "spf=pass" in auth_results.lower()
        if not has_dkim and not has_spf:
            score += 2
            razones.append("sin-dkim-spf(+2)")
        elif not has_dkim:
            score += 1
            razones.append("sin-dkim(+1)")

    # --- 9. Multiples destinatarios en BCC (probable spam masivo) ---
    to_header = msg.get("To", "")
    if to_header:
        to_count = len(re.findall(r"[\w.+-]+@[\w.-]+", to_header))
        if to_count > 20:
            score += 3
            razones.append(f"muchos-destinatarios({to_count})(+3)")
        elif to_count > 10:
            score += 1
            razones.append(f"varios-destinatarios({to_count})(+1)")

    # --- 10. Precedence: bulk (lista de correo / envio masivo) ---
    precedence = msg.get("Precedence", "").lower()
    if precedence == "bulk":
        score += 1
        razones.append("precedence-bulk(+1)")

    return score, razones


def check_spam(msg, keywords, whitelist, blacklist_domains, blacklist_ips, greylist_domains):
    sender = get_sender(msg)
    sender_domain = sender.split("@")[-1] if "@" in sender else ""
    sender_ip = get_sender_ip(msg)

    # === WHITELIST: siempre HAM ===
    for wl in whitelist:
        if wl in sender or wl in sender_domain:
            return False, 0, ["whitelist:" + wl], sender_ip

    subject = decode_subject(msg).lower()
    body = get_body_text(msg).lower()
    full_text = subject + " " + body

    score = 0
    razones = []

    # === LISTA NEGRA DE IPs ===
    is_bl_ip, bl_ip_match = check_blacklist_ip(sender_ip, blacklist_ips)
    if is_bl_ip:
        score += 8
        razones.append(f"blacklist-ip:{bl_ip_match}(+8)")

    # === LISTA NEGRA DE DOMINIOS ===
    is_bl_domain, bl_domain_match = check_blacklist_domain(sender_domain, blacklist_domains)
    if is_bl_domain:
        score += 10
        razones.append(f"blacklist-domain:{bl_domain_match}(+10)")

    # === LISTA GRIS DE DOMINIOS ===
    is_gl_domain, gl_domain_match = check_blacklist_domain(sender_domain, greylist_domains)
    if is_gl_domain:
        score += 4
        razones.append(f"greylist-domain:{gl_domain_match}(+4)")

    # === KEYWORDS ===
    for line in keywords:
        parts = line.split("|")
        keyword = parts[0].strip()
        weight = int(parts[1].strip()) if len(parts) > 1 else 1
        if keyword in full_text:
            score += weight
            razones.append(keyword + "(+" + str(weight) + ")")

    # === HEURISTICAS ===
    h_score, h_razones = check_heuristics(msg, subject, body, full_text)
    score += h_score
    razones.extend(h_razones)

    return score >= SCORE_THRESHOLD, score, razones, sender_ip


def main():
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

        # Cargar todas las listas (se leen en cada correo, sin reiniciar)
        keywords = load_file_lines(KEYWORDS_FILE)
        whitelist = load_file_lines(WHITELIST_FILE)
        blacklist_domains = load_file_lines(BLACKLIST_DOMAINS_FILE)
        blacklist_ips = load_file_lines(BLACKLIST_IPS_FILE)
        greylist_domains = load_file_lines(GREYLIST_DOMAINS_FILE)

        is_spam, score, razones, sender_ip = check_spam(
            msg, keywords, whitelist, blacklist_domains, blacklist_ips, greylist_domains
        )
        from_addr = get_sender(msg)
        subject = decode_subject(msg)

        # Agregar headers custom
        if is_spam:
            msg["X-Maquita-Spam"] = "YES"
        else:
            msg["X-Maquita-Spam"] = "NO"
        msg["X-Maquita-Spam-Score"] = str(score)
        if razones:
            msg["X-Maquita-Spam-Reasons"] = ", ".join(razones[:10])

        verdict = "SPAM" if is_spam else "HAM"
        razones_str = ", ".join(razones) if razones else "ninguna"
        rcpt_str = ",".join(recipients)
        ip_str = sender_ip or "desconocida"
        logging.info(
            "%s | score=%d/%d | ip=%s | from=%s | to=%s | subject=%s | razones=%s",
            verdict, score, SCORE_THRESHOLD, ip_str, from_addr, rcpt_str,
            subject[:80], razones_str
        )

        # Reinyectar el correo a Postfix vía SMTP en puerto 10025
        try:
            smtp = smtplib.SMTP(REINJECT_HOST, REINJECT_PORT)
            smtp.sendmail(sender or "", recipients, msg.as_bytes())
            smtp.quit()
        except Exception as smtp_err:
            logging.error("SMTP reinject failed: %s", str(smtp_err))
            sys.exit(75)  # EX_TEMPFAIL

        sys.exit(0)

    except Exception as e:
        logging.error("Error en filtro: %s", str(e))
        sys.exit(75)  # NUNCA perder correo


if __name__ == "__main__":
    main()
