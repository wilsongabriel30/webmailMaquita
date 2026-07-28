"""Reenvio de correos rebotados.

Cuando un correo no se puede entregar, Postfix lo reintenta durante 5 dias y luego lo
devuelve al remitente (DSN / "Undelivered Mail Returned to Sender"). Ese mensaje ya no
esta en la cola: para reenviarlo hay que recuperar el original del buzon de Enviados del
remitente y reinyectarlo. Este modulo automatiza ese trabajo desde el panel.

Origen: incidente del 2026-07-28 (Zimbra devolvia correos a clientes por un timeout mal
configurado y habia que rescatarlos a mano por consola).

Modulos:
  bounce_scan   -> que cuentas tuvieron rebotes recientes (lee el log de Postfix)
  mailbox_read  -> lee los rebotes de un buzon y localiza el mensaje original (doveadm)
  reinject      -> reinyecta el original a los destinatarios elegidos (sendmail)
  router        -> endpoints HTTP del panel
"""
