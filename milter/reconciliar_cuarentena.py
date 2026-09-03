#!/opt/maquita-webmail/backend/venv/bin/python
"""Reconciliador de la cola de cuarentena diferida (B2).

Cuando el milter no puede registrar una cuarentena en la BD (BD caida), deja un
marcador JSON en la cola. Este script (cron cada ~7 min) los reinserta cuando la BD
vuelve, archiva los procesados, y avisa por correo al admin — TODO fuera del milter,
sin recursion. Solo notifica si hay algo que reportar (nunca en vacio)."""
import os
import json
import glob
import socket
import smtplib
from email.message import EmailMessage

import psycopg2

COLA = os.getenv("MILTER_COLA_CUARENTENA", "/var/lib/maquita-admin/cola-cuarentena")
PROCESADOS = os.path.join(COLA, "procesados")
ADMIN = os.getenv("MILTER_ALERTA_ADMIN", "gestiontecnologia@maquita.com.ec")


def _dsn():
    try:
        for line in open("/opt/maquita-webmail/backend/.env"):
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.getenv("DATABASE_URL", "")


def _avisar(asunto, cuerpo):
    try:
        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"] = "milter@%s" % socket.gethostname()
        msg["To"] = ADMIN
        msg.set_content(cuerpo)
        with smtplib.SMTP("127.0.0.1", 25, timeout=10) as smtp:
            smtp.send_message(msg)
    except Exception:
        pass


def main():
    marcadores = sorted(glob.glob(os.path.join(COLA, "*.json")))
    if not marcadores:
        return  # nada pendiente: no se notifica en vacio
    try:
        conn = psycopg2.connect(_dsn())
    except Exception:
        _avisar("[Maquita] Cuarentena: BD no disponible, %d marcador(es) pendiente(s)" % len(marcadores),
                "La cola de evidencia de cuarentena tiene marcadores pendientes y la BD no "
                "responde. Se reintenta en el proximo ciclo. Revisar la BD.")
        return
    reinsertados = 0
    fallidos = 0
    os.makedirs(PROCESADOS, exist_ok=True)
    try:
        with conn.cursor() as cur:
            for m in marcadores:
                try:
                    r = json.load(open(m, encoding="utf-8"))
                    cur.execute(
                        "INSERT INTO attachment_scans (message_id, filename, content_type, size, "
                        "scan_result, threats_found, scanned_by, scanned_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s::jsonb,'milter-reconciliado', to_timestamp(%s))",
                        (r.get("message_id"), r.get("filename"), r.get("content_type"), r.get("size"),
                         r.get("scan_result", "quarantined"), json.dumps([r.get("reason", "")]),
                         float(r.get("ts") or 0)))
                    conn.commit()
                    os.replace(m, os.path.join(PROCESADOS, os.path.basename(m)))
                    reinsertados += 1
                except Exception:
                    conn.rollback()
                    fallidos += 1
    finally:
        conn.close()
    _avisar("[Maquita] Cuarentena reconciliada: %d reinsertado(s), %d con error" % (reinsertados, fallidos),
            "La evidencia de cuarentena diferida se reinserto en la BD.\n"
            "Reinsertados: %d\nCon error (quedan en la cola): %d\n"
            "Esto ocurre cuando el INSERT del milter fallo antes (BD caida)." % (reinsertados, fallidos))


if __name__ == "__main__":
    main()
