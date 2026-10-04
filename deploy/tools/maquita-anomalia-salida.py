#!/usr/bin/env python3
"""Detector de envío saliente anómalo (cuenta comprometida).

Corre por cron cada 2 minutos. Lee el registro del correo, cuenta los destinatarios por
cuenta autenticada dentro de la ventana configurada y, si una cuenta supera el umbral,
AVISA al administrador y a la persona y CONTIENE la cuenta (maquita-contener lock).
El correo institucional envía pocos mensajes al día: un envío masivo en minutos es señal
de cuenta robada. El objetivo es cortar antes de que la IP caiga en listas negras.

No lleva credenciales ni direcciones propias: la base sale de DATABASE_URL (backend/.env)
y el remitente y el destinatario de los avisos, de /etc/maquita-mail/organizacion.env
(ORG_REMITENTE_AVISOS, ORG_CORREOS_AVISOS) si el panel no tiene uno configurado.
"""
import re
import smtplib
import subprocess
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText

MAILLOG = "/var/log/mail.log"
LOG = "/var/log/maquita-anomalia.log"
ENV_BACKEND = "/opt/maquita-webmail/backend/.env"
ENV_ORG = "/etc/maquita-mail/organizacion.env"
CONTENER = "/usr/local/sbin/maquita-contener"
EXENTOS = "/etc/rspamd/maps.d/ratelimit_whitelist.map"

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
SASL_RE = re.compile(r"postfix/submission/smtpd\[\d+\]:\s+([0-9A-F]+):.*sasl_username=([^,\s]+)", re.I)
NRCPT_RE = re.compile(r"postfix/qmgr\[\d+\]:\s+([0-9A-F]+):\s+from=<[^>]*>,\s+size=\d+,\s+nrcpt=(\d+)")
CUENTA_RE = re.compile(r"^[a-z0-9._+-]+@[a-z0-9.-]+$")


def leer_env(ruta):
    datos = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    datos[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return datos


BACKEND = leer_env(ENV_BACKEND)
ORG = leer_env(ENV_ORG)
# psql no entiende el prefijo «+asyncpg» que usa la aplicación
DSN = re.sub(r"^postgresql\+\w+://", "postgresql://", BACKEND.get("DATABASE_URL", ""))


def q(sql, **variables):
    """Consulta con psql; los valores van como variables (:'nombre'), nunca pegados al SQL."""
    orden = ["psql", DSN, "-X", "-tA"]
    for k, v in variables.items():
        orden += ["-v", f"{k}={v}"]
    try:
        r = subprocess.run(orden, input=sql, capture_output=True, text=True, timeout=15)
        return r.stdout.strip()
    except Exception:
        return ""


def logline(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {msg}\n")


def remitente():
    dominio = BACKEND.get("MAIL_DOMAIN", "localhost")
    return ORG.get("ORG_REMITENTE_AVISOS") or f"postmaster@{dominio}"


def notify(admin, user, recips, mins, action):
    cuerpo = (
        f"AVISO DE SEGURIDAD: envío masivo anómalo detectado\n\n"
        f"Cuenta: {user}\n"
        f"Volumen: {recips} destinatarios en {mins} minutos (lo normal son pocos al día).\n"
        f"Acción automática: {'ENVÍO BLOQUEADO y cuenta contenida' if action == 'locked' else 'ALERTA (sin bloquear)'}.\n\n"
        f"Es muy probable que esta cuenta esté COMPROMETIDA.\n"
        f"Pasos a seguir de inmediato:\n"
        f"  1. Cambiar la contraseña de {user}.\n"
        f"  2. Activar la verificación en dos pasos (2FA).\n"
        f"  3. Revisar los envíos recientes por si se filtró información.\n\n"
        f"Cuando la cuenta esté asegurada, el administrador puede reactivarla desde el panel "
        f"(Protección de salida) o con: maquita-contener unlock {user}\n\n"
        f"-- Sistema de seguridad del correo\n"
    )
    msg = MIMEText(cuerpo, _charset="utf-8")
    msg["Subject"] = f"[SEGURIDAD] Envío masivo anómalo: {user}"
    msg["From"] = remitente()
    dests = [d for d in {admin, user} if d]
    msg["To"] = ", ".join(dests)
    ok = 0
    for d in dests:
        try:
            sm = smtplib.SMTP("127.0.0.1", 25, timeout=15)
            sm.sendmail(remitente(), [d], msg.as_string())
            sm.quit()
            ok += 1
        except Exception as e:
            logline(f"  aviso: no se pudo notificar a {d}: {e}")
    return ok > 0


def main():
    if not DSN:
        logline(f"ERROR: sin DATABASE_URL en {ENV_BACKEND}")
        return
    cfg = q(
        "SELECT enabled||'|'||window_minutes||'|'||threshold_recipients||'|'||action||'|'||notify_admin "
        "FROM outbound_anomaly_config WHERE id=1"
    )
    if not cfg:
        return
    en, win, thr, action, admin = cfg.split("|")
    if en.lower() not in ("t", "true"):
        return
    if not admin:
        admin = (ORG.get("ORG_CORREOS_AVISOS", "").replace(",", " ").split() or [""])[0]
    win, thr = int(win), int(thr)
    cutoff = datetime.now() - timedelta(minutes=win)

    try:
        lines = subprocess.run(
            ["tail", "-n", "20000", MAILLOG], capture_output=True, text=True, timeout=20
        ).stdout.splitlines()
    except Exception:
        return

    qid_user, qid_rcpt = {}, {}
    for ln in lines:
        m = TS_RE.match(ln)
        if not m:
            continue
        try:
            t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
        if t < cutoff:
            continue
        s = SASL_RE.search(ln)
        if s:
            qid_user[s.group(1)] = s.group(2).lower()
            continue
        n = NRCPT_RE.search(ln)
        if n:
            qid_rcpt[n.group(1)] = qid_rcpt.get(n.group(1), 0) + int(n.group(2))

    per_user, per_user_msgs = {}, {}
    for qid, user in qid_user.items():
        per_user[user] = per_user.get(user, 0) + qid_rcpt.get(qid, 1)
        per_user_msgs[user] = per_user_msgs.get(user, 0) + 1

    # Cuentas exentas (envío masivo legítimo): la misma lista que usa rspamd para el límite,
    # administrable desde el panel (Protección de salida).
    exentos = set()
    try:
        with open(EXENTOS, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip().lower()
                if ln and not ln.startswith("#"):
                    exentos.add(ln)
    except OSError:
        pass

    for user, recips in per_user.items():
        if recips < thr or user in exentos or not CUENTA_RE.match(user):
            continue
        # Si ya hay un evento reciente (< 2 ventanas) o la cuenta ya está inactiva, no se repite.
        reciente = q(
            "SELECT 1 FROM outbound_anomaly_events WHERE username = :'u' "
            "AND created_at > now() - (:'m' || ' minutes')::interval LIMIT 1",
            u=user, m=2 * win,
        )
        activo = q("SELECT active FROM mailbox WHERE username = :'u'", u=user)
        if reciente == "1" or activo == "f":
            continue
        msgs = per_user_msgs.get(user, 0)
        act = "locked" if action == "lock" else "alerted"
        # Avisar ANTES de bloquear: al bloquear, el buzón sale de la tabla virtual y el aviso rebota.
        notify(admin, user, recips, win, act)
        if action == "lock":
            time.sleep(3)
            try:
                subprocess.run([CONTENER, "lock", user], capture_output=True, text=True, timeout=60)
            except Exception as e:
                logline(f"  ERROR contener {user}: {e}")
                act = "alerted"
        detail = f"{recips} destinatarios / {msgs} mensajes en {win} min"
        q(
            "INSERT INTO outbound_anomaly_events (username, recipients, messages, window_minutes, action, detail) "
            "VALUES (:'u', :'r'::int, :'n'::int, :'w'::int, :'a', :'d')",
            u=user, r=recips, n=msgs, w=win, a=act, d=detail,
        )
        q(
            "INSERT INTO fraud_alerts (alert_type, severity, username, description, status) "
            "VALUES ('envio_masivo', 'critical', :'u', :'d', 'open')",
            u=user, d=f"Envío masivo anómalo: {detail}",
        )
        logline(f"ANOMALIA {user}: {detail} -> {act}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logline(f"ERROR general: {e}")
