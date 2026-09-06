#!/usr/bin/env python3
"""
Maquita Spam Filter Service v2 — HARDENED
Funciona como content_filter de Postfix (pipe transport).
Recibe correo, analiza keywords + listas negras + heuristicas, agrega header X-Maquita-Spam, reinyecta.
NUNCA rechaza correos - siempre los entrega (a Inbox o Junk via sieve).

Medidas de seguridad agregadas:
  1. Limite de tamaño de email (50MB) — emails grandes pasan sin análisis
  2. Protección de timeout en regex — evita catastrophic backtracking
  3. Patrones regex seguros — revisados contra ReDoS
  4. Protección contra zip bombs — máximo 1MB de texto extraído del body
  5. Protección contra header injection — sanitización de valores en headers
  6. Timeout global del proceso — máximo 60 segundos por email
  7. Limite de memoria — resource.setrlimit para evitar consumo excesivo
  8. Aislamiento de errores — excepciones en heurísticas no crashean el filtro
"""
import sys
import os
import email
import email.policy
import re
import logging
import smtplib
import signal
import resource
import subprocess
import time
import tempfile

# Neurona de spam (advisory, patron INFINITO) — carga aislada, nunca rompe el filtro
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import neurona_spam as _neurona
except Exception as _e:
    _neurona = None
from datetime import datetime
from email.header import decode_header

# --- Configuración ---
KEYWORDS_FILE = "/etc/maquita-mail/spam-keywords.txt"
WHITELIST_FILE = "/etc/maquita-mail/whitelist-senders.txt"
BLACKLIST_DOMAINS_FILE = "/etc/maquita-mail/blacklist-domains.txt"
BLACKLIST_IPS_FILE = "/etc/maquita-mail/blacklist-ips.txt"
GREYLIST_DOMAINS_FILE = "/etc/maquita-mail/greylist-domains.txt"
LOG_FILE = "/var/log/maquita-spam-filter.log"
SCORE_THRESHOLD = 3  # (se sobreescribe con FILTRO_CFG['umbral'] mas abajo)
REINJECT_HOST = "127.0.0.1"
REINJECT_PORT = 10025

# --- Limites de seguridad ---
MAX_EMAIL_SIZE = 50 * 1024 * 1024   # HARDENING #1: 50MB máximo para análisis
MAX_BODY_TEXT = 1 * 1024 * 1024     # HARDENING #4: 1MB máximo de texto extraído
REGEX_TIMEOUT_SECS = 5              # HARDENING #2: timeout para operaciones regex
PROCESS_TIMEOUT_SECS = 60           # HARDENING #6: timeout global del proceso
MEMORY_LIMIT_MB = 512               # HARDENING #7: limite de memoria en MB

# --- Config afinable desde el panel (/etc/maquita-mail/filtro-avanzado.json) ---
FILTRO_CFG_PATH = "/etc/maquita-mail/filtro-avanzado.json"


def _cargar_filtro_cfg():
    import json
    base = {"umbral": 3, "macro_score": 2, "neurona_peso": 0,
            "extensiones_extra": [], "depuracion_dias": 35}
    try:
        with open(FILTRO_CFG_PATH, encoding="utf-8") as fh:
            base.update({k: v for k, v in json.load(fh).items() if k in base})
    except Exception:
        pass
    return base


FILTRO_CFG = _cargar_filtro_cfg()
SCORE_THRESHOLD = int(FILTRO_CFG.get("umbral", 3) or 3)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


# ============================================================================
# HARDENING #6: Timeout global del proceso — máximo 60 segundos por email.
# Si el filtro tarda más, se interrumpe y el email pasa sin análisis.
# ============================================================================
class ProcessTimeoutError(Exception):
    pass


def _process_timeout_handler(signum, frame):
    raise ProcessTimeoutError("Proceso excedió el timeout global de %d segundos" % PROCESS_TIMEOUT_SECS)


# ============================================================================
# HARDENING #2: Timeout para operaciones regex.
# Protege contra catastrophic backtracking (ReDoS).
# Usa signal.alarm para interrumpir regex que tarden demasiado.
# ============================================================================
class RegexTimeoutError(Exception):
    pass


def _regex_timeout_handler(signum, frame):
    raise RegexTimeoutError("Regex excedió el timeout de %d segundos" % REGEX_TIMEOUT_SECS)


def safe_regex_findall(pattern, text, timeout=REGEX_TIMEOUT_SECS):
    """
    HARDENING #2: Ejecuta re.findall con protección de timeout.
    Si el regex tarda más del timeout, retorna lista vacía en vez de bloquear.
    """
    old_handler = signal.signal(signal.SIGALRM, _regex_timeout_handler)
    signal.alarm(timeout)
    try:
        result = re.findall(pattern, text)
        signal.alarm(0)
        return result
    except RegexTimeoutError:
        logging.warning("Regex timeout en patrón: %s (posible ReDoS)", pattern[:80])
        return []
    except re.error as e:
        logging.warning("Regex error en patrón %s: %s", pattern[:80], str(e))
        return []
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def safe_regex_search(pattern, text, timeout=REGEX_TIMEOUT_SECS):
    """
    HARDENING #2: Ejecuta re.search con protección de timeout.
    Retorna None si el regex tarda demasiado.
    """
    old_handler = signal.signal(signal.SIGALRM, _regex_timeout_handler)
    signal.alarm(timeout)
    try:
        result = re.search(pattern, text)
        signal.alarm(0)
        return result
    except RegexTimeoutError:
        logging.warning("Regex timeout en patrón: %s (posible ReDoS)", pattern[:80])
        return None
    except re.error as e:
        logging.warning("Regex error en patrón %s: %s", pattern[:80], str(e))
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# ============================================================================
# HARDENING #5: Sanitización de headers.
# Previene header injection eliminando newlines y caracteres de control.
# ============================================================================
def sanitize_header_value(value):
    """
    HARDENING #5: Elimina newlines y caracteres de control de valores de headers.
    Esto previene header injection attacks donde un valor malicioso podría
    inyectar headers adicionales usando \\r\\n.
    """
    if not isinstance(value, str):
        value = str(value)
    # Eliminar CR, LF, y combinaciones (prevenir header injection)
    value = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    # Eliminar caracteres de control (excepto espacio y tab para folding legítimo)
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Truncar a longitud razonable (998 chars según RFC 2822)
    return value[:998]


# ============================================================================
# HARDENING #7: Limite de memoria.
# Previene que el proceso consuma toda la RAM del servidor.
# ============================================================================
def set_memory_limit():
    """
    HARDENING #7: Establece un límite de memoria para el proceso.
    Si se excede, Python lanzará MemoryError que se captura en main().
    """
    try:
        limit_bytes = MEMORY_LIMIT_MB * 1024 * 1024
        # RLIMIT_AS limita el espacio de direcciones virtuales
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except (ValueError, resource.error) as e:
        logging.warning("No se pudo establecer limite de memoria: %s", str(e))


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
    try:
        decoded_parts = decode_header(subject)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)
    except Exception:
        # HARDENING #8: Si decode_header falla, retornar el subject raw
        return str(subject)


def get_body_text(msg):
    """
    Extrae texto del cuerpo del email.
    HARDENING #4: Limita la cantidad de texto extraído a MAX_BODY_TEXT (1MB).
    Esto protege contra zip bombs donde el contenido decodificado (base64)
    podría expandirse a tamaños enormes.
    """
    body = ""
    total_extracted = 0

    if msg.is_multipart():
        for part in msg.walk():
            # HARDENING #4: No extraer más de MAX_BODY_TEXT en total
            if total_extracted >= MAX_BODY_TEXT:
                logging.info("Limite de texto alcanzado (%d bytes), omitiendo partes restantes", total_extracted)
                break

            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    # HARDENING #4: Limitar tamaño del payload decodificado
                    if len(payload) > MAX_BODY_TEXT - total_extracted:
                        payload = payload[:MAX_BODY_TEXT - total_extracted]
                        logging.info("Payload text/plain truncado a %d bytes (zip bomb protection)", len(payload))
                    text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    body += text
                    total_extracted += len(text)
                except Exception:
                    pass
            elif ct == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    # HARDENING #4: Limitar tamaño del payload decodificado
                    if len(payload) > MAX_BODY_TEXT - total_extracted:
                        payload = payload[:MAX_BODY_TEXT - total_extracted]
                        logging.info("Payload text/html truncado a %d bytes (zip bomb protection)", len(payload))
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    # HARDENING #3: Patrón regex seguro para strip HTML tags.
                    # Original: r"<[^>]+>" — es seguro (sin backtracking catastrófico),
                    # pero limitamos el tamaño del input como doble protección.
                    text = re.sub(r"<[^>]+>", " ", html)
                    body += text
                    total_extracted += len(text)
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload is not None:
                # HARDENING #4: Limitar tamaño del payload
                if len(payload) > MAX_BODY_TEXT:
                    payload = payload[:MAX_BODY_TEXT]
                    logging.info("Payload único truncado a %d bytes (zip bomb protection)", MAX_BODY_TEXT)
                body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            pass
    return body


def get_sender(msg):
    from_header = msg.get("From", "")
    # HARDENING #3: Patrón seguro — [\w.+-] y [\w.-] son clases de caracteres
    # simples sin alternancia ni backtracking anidado.
    match = safe_regex_search(r"[\w.+-]+@[\w.-]+", from_header)
    return match.group(0).lower() if match else from_header.lower()


def get_sender_ip(msg):
    """Extrae la IP del servidor remitente desde Received headers."""
    received = msg.get_all("Received", [])
    if received:
        for header in received:
            # HARDENING #3: Patrón seguro para extraer IPs.
            # r"\[(\d{1,3}\.…)\]" — cuantificadores acotados, sin backtracking.
            match = safe_regex_search(r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]", header)
            if match:
                ip = match.group(1)
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


BONO_WHITELIST_DOMINIO = 3   # puntos que resta un dominio de confianza

# --- Antivirus ---
CLAMAV_TIMEOUT_SECS = 25          # margen dentro de PROCESS_TIMEOUT_SECS (60)
PENALIZACION_NO_ESCANEADO = 2     # puntos si el antivirus no pudo analizar.
# Deliberadamente POR DEBAJO del umbral (3): que el antivirus caiga no puede,
# por si solo, mandar a Junk todo el correo entrante. Solo acerca al umbral a
# un correo que ya tenia indicios.


def evaluar_whitelist(sender, sender_domain, whitelist):
    """Decide que hace la lista blanca con este remitente.

    Devuelve ("exime", entrada) | ("bono", entrada) | (None, "").

      - Direccion completa (tiene "@"): coincidencia EXACTA -> exime del analisis.
        Es una decision deliberada sobre una persona concreta.
      - Dominio: coincide el dominio exacto o un subdominio suyo -> NO exime,
        resta BONO_WHITELIST_DOMINIO puntos y el correo se sigue analizando.
        Asi un proveedor generico deja de ser una puerta abierta.
      - Entrada que empieza por "!": exime aunque sea un dominio. Escotilla
        explicita para casos concretos; usese poco y a conciencia.

    La comparacion es exacta a proposito, igual que en check_blacklist_domain:
    con subcadenas, "gob.ec" casaba con cualquier dominio que la contuviera.
    """
    bono = None
    for wl in whitelist:
        entrada = (wl or "").strip().lower()
        if not entrada:
            continue
        forzado = entrada.startswith("!")
        if forzado:
            entrada = entrada[1:].strip()
            if not entrada:
                continue
        if "@" in entrada:
            if sender == entrada:
                return "exime", entrada
            continue
        if sender_domain == entrada or sender_domain.endswith("." + entrada):
            if forzado:
                return "exime", entrada
            if bono is None:
                bono = entrada
    if bono:
        return "bono", bono
    return None, ""


def check_blacklist_domain(sender_domain, blacklist_domains):
    """Verifica si el dominio esta en la lista negra."""
    for bl_domain in blacklist_domains:
        if bl_domain == sender_domain or sender_domain.endswith("." + bl_domain):
            return True, bl_domain
    return False, ""


# ============================================================================
# Inspeccion DENTRO de comprimidos (zip/rar/7z/tar...) con 7z: solo LISTA, no
# extrae -> sin riesgo de zip-bomb. Marca 'peligroso' si hay ejecutables dentro
# y 'no-inspeccionable' si 7z no puede abrirlo (cifrado/corrupto/RAR ilegible),
# que es la tecnica usada por el malware .vbs-en-.rar (incidente 2026-06-08).
# ============================================================================
# --- Conjuntos de extensiones peligrosas (incidente 2026-06-08 ampliado) ---
EXEC_SCRIPT_EXTS = {
    ".exe", ".scr", ".bat", ".cmd", ".com", ".pif", ".vbs", ".vbe", ".js",
    ".jse", ".wsf", ".wsh", ".wsc", ".hta", ".jar", ".lnk", ".ps1", ".ps2",
    ".psc1", ".psc2", ".psm1", ".psd1", ".msi", ".msp", ".mst", ".msc",
    ".reg", ".cpl", ".scf", ".sct", ".shb", ".shs", ".inf", ".ins", ".isp",
    ".job", ".ws", ".vb", ".vbscript", ".gadget", ".application",
    ".appref-ms", ".url", ".chm", ".jnlp", ".xll", ".wll", ".one", ".dll",
}
DISK_IMAGE_EXTS = {".iso", ".img", ".vhd", ".vhdx", ".udf", ".vmdk", ".wim"}
MACRO_OFFICE_EXTS = {
    ".docm", ".xlsm", ".pptm", ".dotm", ".xltm", ".potm", ".xlsb",
    ".ppam", ".xlam",
}
ARCHIVE_EXTS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".cab", ".ace", ".lzh",
    ".arj", ".z", ".lzma", ".xz", ".bz2", ".zipx", ".deb", ".rpm", ".cpio",
}
EXEC_SCRIPT_EXTS |= {
    ("." + str(e).lstrip(".").lower()) for e in FILTRO_CFG.get("extensiones_extra", []) if e
}

SEVENZIP_BIN = "/usr/bin/7z"
ARCHIVE_INSPECT_MAX = 15 * 1024 * 1024
ARCHIVE_INSPECT_TIMEOUT = 12
DANGEROUS_IN_ARCHIVE = EXEC_SCRIPT_EXTS | DISK_IMAGE_EXTS


def inspect_archive(part, ext, safe_name):
    """Lista (sin extraer) el contenido de un comprimido con 7z.
    Retorna 'peligroso', 'no-inspeccionable' o None. Aislado: nunca propaga."""
    tmp_path = None
    hallazgo_macro = False
    try:
        if not os.path.exists(SEVENZIP_BIN):
            return None
        payload = part.get_payload(decode=True)
        if not payload:
            return None
        if len(payload) > ARCHIVE_INSPECT_MAX:
            logging.info("Comprimido %s >%dB, no inspeccionado", safe_name, ARCHIVE_INSPECT_MAX)
            return None
        with tempfile.NamedTemporaryFile(prefix="maqarch_", suffix=ext, delete=False) as tf:
            tf.write(payload)
            tmp_path = tf.name
        proc = subprocess.run(
            [SEVENZIP_BIN, "l", "-y", tmp_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=ARCHIVE_INSPECT_TIMEOUT, text=True, errors="replace",
        )
        if proc.returncode != 0:
            logging.info("7z no abrio %s (rc=%d) -> no-inspeccionable", safe_name, proc.returncode)
            return "no-inspeccionable"
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            inner = os.path.splitext(line.split()[-1].lower())[1]
            if inner in DANGEROUS_IN_ARCHIVE:
                logging.warning("Ejecutable dentro de %s: %s", safe_name, line.split()[-1])
                return "peligroso"
            if inner in MACRO_OFFICE_EXTS:
                hallazgo_macro = True
        return "macro" if hallazgo_macro else None
    except subprocess.TimeoutExpired:
        logging.info("7z timeout en %s -> no-inspeccionable", safe_name)
        return "no-inspeccionable"
    except Exception as e:
        logging.warning("inspect_archive fallo (%s): %s", safe_name, str(e))
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def check_heuristics(msg, subject, body, full_text):
    """
    Heuristicas avanzadas propias — como un banco evalua transacciones.

    HARDENING #8: Cada heurística está envuelta en try/except individual.
    Si una falla, las demás siguen ejecutándose. Esto aísla errores para
    que un input malicioso no evada todas las heurísticas a la vez.
    """
    score = 0
    razones = []

    # --- 1. Muchos links (>10) = sospechoso ---
    # HARDENING #3: Patrón simple sin backtracking — solo busca "https?://"
    try:
        links = safe_regex_findall(r"https?://", full_text)
        if len(links) > 15:
            score += 3
            razones.append(f"exceso-links({len(links)})(+3)")
        elif len(links) > 10:
            score += 2
            razones.append(f"muchos-links({len(links)})(+2)")
    except Exception as e:
        logging.warning("Heurística 'links' falló: %s", str(e))

    # --- 2. Subject vacio ---
    try:
        if not subject.strip():
            score += 1
            razones.append("subject-vacio(+1)")
    except Exception as e:
        logging.warning("Heurística 'subject-vacio' falló: %s", str(e))

    # --- 3. Solo HTML, sin texto plano ---
    try:
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
    except Exception as e:
        logging.warning("Heurística 'solo-html' falló: %s", str(e))

    # --- 4. Ratio de mayusculas en subject ---
    try:
        if subject and len(subject) > 5:
            upper_ratio = sum(1 for c in subject if c.isupper()) / len(subject)
            if upper_ratio > 0.7:
                score += 2
                razones.append(f"subject-MAYUSCULAS({upper_ratio:.0%})(+2)")
    except Exception as e:
        logging.warning("Heurística 'mayúsculas' falló: %s", str(e))

    # --- 5. URLs sospechosas (IP en URL, URLs acortadas) ---
    try:
        # HARDENING #3: Patrón seguro — cuantificadores acotados {1,3}
        ip_urls = safe_regex_findall(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", full_text)
        if ip_urls:
            score += 2
            razones.append(f"url-con-ip({len(ip_urls)})(+2)")
    except Exception as e:
        logging.warning("Heurística 'ip-urls' falló: %s", str(e))

    try:
        # HARDENING #3: Patrón seguro — alternancia simple de literales, sin anidamiento.
        short_urls = safe_regex_findall(
            r"https?://(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|buff\.ly|ow\.ly|shorturl\.at)",
            full_text
        )
        if len(short_urls) > 3:
            score += 2
            razones.append(f"urls-acortadas({len(short_urls)})(+2)")
    except Exception as e:
        logging.warning("Heurística 'short-urls' falló: %s", str(e))

    # --- 6. Adjuntos sospechosos (incl. inspeccion dentro de comprimidos) ---
    try:
        if msg.is_multipart():
            for part in msg.walk():
                filename = part.get_filename("")
                if not filename:
                    continue
                ext = os.path.splitext(filename.lower())[1]
                safe_name = sanitize_header_value(filename[:50])
                if ext in EXEC_SCRIPT_EXTS or ext in DISK_IMAGE_EXTS:
                    score += 5
                    razones.append(f"adjunto-peligroso({safe_name})(+5)")
                elif ext in MACRO_OFFICE_EXTS:
                    # Suave/configurable (panel). Marca pero NO manda a Junk solo.
                    _ms = int(FILTRO_CFG.get("macro_score", 2) or 0)
                    score += _ms
                    razones.append(f"office-con-macros({safe_name})(+{_ms})")
                elif ext in ARCHIVE_EXTS:
                    score += 1
                    razones.append(f"adjunto-comprimido({safe_name})(+1)")
                    verdict = inspect_archive(part, ext, safe_name)
                    if verdict == "peligroso":
                        score += 6
                        razones.append(f"ejecutable-en-comprimido({safe_name})(+6)")
                    elif verdict == "macro":
                        score += 3
                        razones.append(f"office-macros-en-comprimido({safe_name})(+3)")
                    elif verdict == "no-inspeccionable":
                        score += 4
                        razones.append(f"comprimido-no-inspeccionable({safe_name})(+4)")
    except Exception as e:
        logging.warning("Heuristica 'adjuntos' fallo: %s", str(e))

    # --- 7. Reply-To diferente de From ---
    try:
        from_addr = get_sender(msg)
        reply_to = msg.get("Reply-To", "")
        if reply_to:
            reply_match = safe_regex_search(r"[\w.+-]+@[\w.-]+", reply_to)
            if reply_match:
                reply_domain = reply_match.group(0).split("@")[-1].lower()
                from_domain = from_addr.split("@")[-1] if "@" in from_addr else ""
                if from_domain and reply_domain != from_domain:
                    score += 2
                    razones.append(f"reply-to-diferente({reply_domain})(+2)")
    except Exception as e:
        logging.warning("Heurística 'reply-to' falló: %s", str(e))

    # --- 8. No tiene DKIM ni SPF (headers de autenticacion) ---
    try:
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
    except Exception as e:
        logging.warning("Heurística 'auth-results' falló: %s", str(e))

    # --- 9. Multiples destinatarios en BCC (probable spam masivo) ---
    try:
        to_header = msg.get("To", "")
        if to_header:
            to_count = len(safe_regex_findall(r"[\w.+-]+@[\w.-]+", to_header))
            if to_count > 20:
                score += 3
                razones.append(f"muchos-destinatarios({to_count})(+3)")
            elif to_count > 10:
                score += 1
                razones.append(f"varios-destinatarios({to_count})(+1)")
    except Exception as e:
        logging.warning("Heurística 'destinatarios' falló: %s", str(e))

    # --- 10. Precedence: bulk (lista de correo / envio masivo) ---
    try:
        precedence = msg.get("Precedence", "").lower()
        if precedence == "bulk":
            score += 1
            razones.append("precedence-bulk(+1)")
    except Exception as e:
        logging.warning("Heurística 'precedence' falló: %s", str(e))

    # --- 11. Neurona de spam (advisory): registra/aprende, suma segun NEURONA_PESO ---
    try:
        if _neurona is not None:
            v = _neurona.decidir(razones, subject or "", body or "", permitir_llm=False)
            extra = _neurona.ajuste_score(v)
            if extra:
                score += extra
            razones.append(f"neurona({v['etiqueta']},{v['confianza']},{v['fuente']})(+{extra})")
            logging.info("Neurona: %s conf=%s fuente=%s +%d",
                         v["etiqueta"], v["confianza"], v["fuente"], extra)
    except Exception as e:
        logging.warning("Heuristica 'neurona' fallo: %s", str(e))

    return score, razones


def _clamav_verdict(msg):
    """Escanea el correo con clamd.

    Devuelve una tupla (estado, detalle) con estado en:
      "limpio"       -> clamd analizo el correo y no encontro nada
      "virus"        -> clamd encontro una firma; detalle es su nombre
      "no_escaneado" -> clamd NO pudo analizarlo; detalle es el motivo

    Sigue siendo fail-open a proposito: si el antivirus no responde NO se
    rechaza el correo, porque cortar la entrega de toda la organizacion es
    peor que entregar sin analizar. Lo que cambia es que un fallo ya no se
    confunde con un escaneo limpio: se registra como error (no como aviso),
    suma puntuacion y queda anotado en las razones del correo.
    """
    try:
        raw = msg.as_bytes()
    except Exception as e:
        return "no_escaneado", "serializacion:" + type(e).__name__

    motivo = None
    # Un solo reintento, y solo para fallos rapidos (error o caida del socket).
    # Si fue agotamiento de tiempo no se reintenta: gastaria otro turno completo
    # y el proceso tiene un limite global de PROCESS_TIMEOUT_SECS.
    for intento in (1, 2):
        try:
            r = subprocess.run(["clamdscan", "--fdpass", "--no-summary", "-"],
                               input=raw, capture_output=True,
                               timeout=CLAMAV_TIMEOUT_SECS)
            salida = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace")
            if r.returncode == 1:
                for line in salida.splitlines():
                    if line.strip().endswith("FOUND"):
                        return "virus", (line.split(":")[-1]
                                         .replace("FOUND", "").strip() or "virus")
                return "virus", "virus"
            if r.returncode == 0:
                return "limpio", None
            primera = (salida.strip().splitlines() or [""])[0][:120]
            motivo = "codigo_%d:%s" % (r.returncode, primera)
        except subprocess.TimeoutExpired:
            motivo = "tiempo_agotado_%ds" % CLAMAV_TIMEOUT_SECS
            break
        except Exception as e:
            motivo = type(e).__name__ + ":" + str(e)[:100]
        if intento == 1:
            time.sleep(0.5)

    logging.error("ANTIVIRUS NO ANALIZO EL CORREO (entregado sin escanear): %s", motivo)
    return "no_escaneado", motivo


def check_spam(msg, keywords, whitelist, blacklist_domains, blacklist_ips, greylist_domains):
    sender = get_sender(msg)
    sender_domain = sender.split("@")[-1] if "@" in sender else ""
    sender_ip = get_sender_ip(msg)

    # === ANTIVIRUS (ClamAV): un virus SIEMPRE va a Junk, ignora whitelist ===
    _av_estado, _av_detalle = _clamav_verdict(msg)
    if _av_estado == "virus":
        return True, 100, ["virus:" + _av_detalle], sender_ip
    # Un correo que no se pudo escanear no es lo mismo que uno limpio: se
    # entrega igual, pero deja rastro y pesa en la puntuacion.
    _av_aviso = ("antivirus:no_escaneado(+%d)" % PENALIZACION_NO_ESCANEADO
                 if _av_estado == "no_escaneado" else None)

    # === LISTA BLANCA ===
    # Antes esto era `if wl in sender` (SUBCADENA) y devolvia HAM con score 0,
    # saltandose keywords, listas negras y todas las heuristicas. Dos agujeros:
    #   1. Subcadena: "gob.ec" casaba con "aviso.gob.ec.dominio-falso.com".
    #   2. La lista trae proveedores genericos (gmail, outlook, yahoo...), y la
    #      cabecera From no esta autenticada aqui, asi que bastaba escribir
    #      From: quien-sea@gmail.com para desactivar el filtro por completo.
    # Ahora: coincidencia exacta, y solo una direccion COMPLETA (o una entrada
    # marcada con "!") exime del analisis; un dominio solo resta puntos.
    _wl_tipo, _wl_entrada = evaluar_whitelist(sender, sender_domain, whitelist)
    if _wl_tipo == "exime":
        _r = ["whitelist:" + _wl_entrada]
        if _av_aviso:
            _r.append(_av_aviso)
        return False, 0, _r, sender_ip

    subject = decode_subject(msg).lower()
    body = get_body_text(msg).lower()
    full_text = subject + " " + body

    score = 0
    razones = []

    if _av_aviso:
        score += PENALIZACION_NO_ESCANEADO
        razones.append(_av_aviso)

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
    # HARDENING #8: check_heuristics ya tiene aislamiento interno,
    # pero lo envolvemos también por si falla algo inesperado.
    try:
        h_score, h_razones = check_heuristics(msg, subject, body, full_text)
        score += h_score
        razones.extend(h_razones)
    except Exception as e:
        logging.error("check_heuristics falló completamente: %s", str(e))

    # Descuento por dominio de confianza: baja la puntuacion, no anula el analisis.
    if _wl_tipo == "bono":
        score = max(0, score - BONO_WHITELIST_DOMINIO)
        razones.append("whitelist-dominio:" + _wl_entrada)

    return score >= SCORE_THRESHOLD, score, razones, sender_ip


def main():
    # HARDENING #7: Establecer limite de memoria antes de procesar
    set_memory_limit()

    # HARDENING #6: Timeout global del proceso.
    # Si el filtro tarda más de 60 segundos, se interrumpe y el email
    # se reinyecta sin análisis para no perder correos.
    old_alarm_handler = signal.signal(signal.SIGALRM, _process_timeout_handler)
    signal.alarm(PROCESS_TIMEOUT_SECS)

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

    raw = None
    try:
        raw = sys.stdin.buffer.read()

        # ================================================================
        # HARDENING #1: Limite de tamaño de email (50MB).
        # Emails muy grandes pasan directamente sin análisis de spam.
        # Esto previene consumo excesivo de CPU/memoria en emails con
        # adjuntos grandes que probablemente no son spam.
        # ================================================================
        if len(raw) > MAX_EMAIL_SIZE:
            logging.info(
                "Email demasiado grande (%d bytes > %d). Pasando sin análisis.",
                len(raw), MAX_EMAIL_SIZE
            )
            msg = email.message_from_bytes(raw, policy=email.policy.compat32)
            # Marcar como no analizado
            msg["X-Maquita-Spam"] = sanitize_header_value("NO")
            msg["X-Maquita-Spam-Score"] = sanitize_header_value("0")
            msg["X-Maquita-Spam-Reasons"] = sanitize_header_value("email-oversize-skipped")
            # Reinyectar sin análisis
            try:
                smtp = smtplib.SMTP(REINJECT_HOST, REINJECT_PORT)
                smtp.sendmail(sender or "", recipients, msg.as_bytes())
                smtp.quit()
            except Exception as smtp_err:
                logging.error("SMTP reinject failed (oversize): %s", str(smtp_err))
                sys.exit(75)
            sys.exit(0)

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

        # HARDENING #5: Sanitizar todos los valores antes de agregarlos como headers.
        # Previene header injection donde un valor con \r\n podría inyectar
        # headers adicionales al email.
        if is_spam:
            msg["X-Maquita-Spam"] = sanitize_header_value("YES")
        else:
            msg["X-Maquita-Spam"] = sanitize_header_value("NO")
        msg["X-Maquita-Spam-Score"] = sanitize_header_value(str(score))
        if razones:
            msg["X-Maquita-Spam-Reasons"] = sanitize_header_value(", ".join(razones[:10]))

        # Cancelar el alarm global ya que vamos a reinyectar
        signal.alarm(0)

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

    except ProcessTimeoutError:
        # HARDENING #6: Si el proceso excedió el timeout, intentar reinyectar
        # el email sin procesar para no perderlo.
        logging.error("TIMEOUT GLOBAL: proceso excedió %d segundos", PROCESS_TIMEOUT_SECS)
        if raw is not None:
            try:
                msg_raw = email.message_from_bytes(raw, policy=email.policy.compat32)
                msg_raw["X-Maquita-Spam"] = sanitize_header_value("NO")
                msg_raw["X-Maquita-Spam-Score"] = sanitize_header_value("0")
                msg_raw["X-Maquita-Spam-Reasons"] = sanitize_header_value("timeout-skipped")
                smtp = smtplib.SMTP(REINJECT_HOST, REINJECT_PORT)
                smtp.sendmail(sender or "", recipients, msg_raw.as_bytes())
                smtp.quit()
                sys.exit(0)
            except Exception:
                pass
        sys.exit(75)  # EX_TEMPFAIL — Postfix reintentará

    except MemoryError:
        # HARDENING #7: Si se excedió el limite de memoria, reinyectar sin análisis.
        logging.error("MEMORY LIMIT: proceso excedió %d MB", MEMORY_LIMIT_MB)
        if raw is not None:
            try:
                msg_raw = email.message_from_bytes(raw, policy=email.policy.compat32)
                msg_raw["X-Maquita-Spam"] = sanitize_header_value("NO")
                msg_raw["X-Maquita-Spam-Score"] = sanitize_header_value("0")
                msg_raw["X-Maquita-Spam-Reasons"] = sanitize_header_value("memory-limit-skipped")
                smtp = smtplib.SMTP(REINJECT_HOST, REINJECT_PORT)
                smtp.sendmail(sender or "", recipients, msg_raw.as_bytes())
                smtp.quit()
                sys.exit(0)
            except Exception:
                pass
        sys.exit(75)

    except Exception as e:
        logging.error("Error en filtro: %s", str(e))
        # HARDENING #8: En cualquier error, intentar reinyectar el email crudo
        # para que NUNCA se pierda correo.
        if raw is not None:
            try:
                smtp = smtplib.SMTP(REINJECT_HOST, REINJECT_PORT)
                smtp.sendmail(sender or "", recipients, raw)
                smtp.quit()
                sys.exit(0)
            except Exception:
                pass
        sys.exit(75)  # NUNCA perder correo — Postfix reintentará

    finally:
        # Limpiar alarm
        signal.alarm(0)


if __name__ == "__main__":
    main()
