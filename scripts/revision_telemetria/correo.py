"""Envío del informe por el sendmail local (Postfix) desde TELEMETRIA_REMITENTE (organizacion.env)."""
import subprocess
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import config


def enviar(asunto, cuerpo, destino=None):
    msg = EmailMessage()
    msg['From'] = f'Revisión de telemetría del webmail <{config.REMITENTE_CORREO}>'
    msg['To'] = destino or config.DESTINO_CORREO
    msg['Subject'] = asunto
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=config.URL_CORREO.split('//')[-1].split('/')[0] or None)
    msg['Auto-Submitted'] = 'auto-generated'
    msg.set_content(cuerpo, charset='utf-8')
    proc = subprocess.run([config.SENDMAIL, '-t', '-oi', '-f', config.REMITENTE_CORREO],
                          input=msg.as_bytes(), capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f'sendmail devolvió {proc.returncode}: {proc.stderr.decode(errors="replace")[:300]}')
    return msg['Message-ID']
