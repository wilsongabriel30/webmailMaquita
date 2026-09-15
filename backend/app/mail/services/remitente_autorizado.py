"""Desde qué dirección puede salir un correo, y con qué buzón se guarda la copia.

Una persona puede enviar como:
  - su propia cuenta;
  - un alias que entregue en su buzón (tabla `alias`);
  - una identidad suya (`user_identities`);
  - una cuenta delegada con permiso de envío (`mail_delegation.can_send_as`).
Postfix aplica la misma lista en `smtpd_sender_login_maps`, así que aquí se decide lo mismo
que decidirá el servidor de salida: sin sorpresas a mitad del envío.

Si el remitente es una cuenta delegada, la copia de «Enviados» va al buzón de ESA cuenta
(abierto con el usuario maestro), para que quien la comparta vea lo que se mandó en su nombre.
"""

from fastapi import HTTPException

from app.config import get_settings
from app.mail.clients.imap_client import get_imap_connection
from app.mail.services.cuentas_delegadas import credenciales_maestras, puede_usar


async def _es_alias_o_identidad(db, username: str, email: str) -> bool:
    fila = await db.fetchrow("SELECT goto FROM alias WHERE address = $1 AND active = true", email)
    if fila and username.lower() in (fila["goto"] or "").lower():
        return True
    fila = await db.fetchrow(
        "SELECT 1 FROM user_identities WHERE username = $1 AND lower(email) = $2", username, email
    )
    return bool(fila)


async def resolver_remitente(db, username: str, from_email: str | None, display_name: str):
    """Devuelve (from_addr, display_name, imap_para_enviados | None, clave_smtp | None).

    Cuenta delegada: la copia va a SU Enviados (`imap_para_enviados`, abierto con el usuario
    maestro; quien llama debe cerrarlo) y el SMTP se autentica como esa cuenta con la clave
    maestra (`clave_smtp`): Dovecot entrega a Postfix el usuario real, así que el control de
    remitente (`smtpd_sender_login_maps`) ve `cuenta == From` y lo acepta.
    Lanza 403 si la persona no puede enviar desde esa dirección.
    """
    email = (from_email or "").strip().lower()
    if not email or email == username.lower():
        return username, display_name, None, None
    if await _es_alias_o_identidad(db, username, email):
        return email, display_name, None, None
    if await puede_usar(db, username, email, para_enviar=True):
        fila = await db.fetchrow("SELECT COALESCE(name, '') AS nombre FROM mailbox WHERE username = $1", email)
        nombre = (fila["nombre"] if fila else "") or display_name
        usuario, clave = credenciales_maestras(email, get_settings())
        try:
            imap = await get_imap_connection(usuario, clave)
        except Exception:
            imap = None  # se envía igual; la copia irá al Enviados propio
        return email, nombre, imap, clave
    raise HTTPException(status_code=403, detail=f"No tienes permiso para enviar como {email}")
