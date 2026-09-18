"""Varias cuentas en una sesión: buzones delegados abiertos con el usuario maestro.

Pedido (15/09/2026): que una persona vea en la barra lateral las cuentas de correo que
tiene a su cargo (ventas@, info@...), lea cada bandeja y envíe desde la que elija, sin
abrir varios navegadores.

Cómo funciona:
- La tabla `mail_delegation (mailbox, delegate, can_send_as)` dice qué cuentas puede usar
  cada persona. La llena el panel de administración (Buzones compartidos) o el propio dueño
  desde el webmail (`/api/mail/delegation/grant`).
- Las carpetas de una cuenta delegada se nombran de forma virtual:
      Compartidos/<cuenta>/<carpeta real>      p. ej. Compartidos/ventas@maquitaturismo.com/INBOX
  Cuando una petición trae una carpeta así, la sesión abre IMAP como `<cuenta>*admin` con la
  contraseña maestra de Dovecot (la misma que usa la impersonación del panel) y trabaja sobre
  la carpeta real. La contraseña maestra nunca sale del servidor.
- Por qué no el namespace `shared` de Dovecot: con separador «.» (Maildir++) y usuarios con
  puntos en el dominio, Dovecot 2.4 corta el dueño en el primer punto y no lista nada; cambiar
  el separador afectaría a los 488 buzones, a los clientes de escritorio y a las reglas sieve.
"""

from __future__ import annotations

# Separador «,»: no puede ser «/» porque las rutas de la API llevan la carpeta como un solo
# segmento (un %2F se decodifica y rompe el enrutado), ni «.» porque es la jerarquía IMAP.
PREFIJO = "Compartidos,"
SEP = ","
USUARIO_MAESTRO = "admin"


def separar(folder: str | None) -> tuple[str | None, str]:
    """'Compartidos,ventas@x.com,INBOX' -> ('ventas@x.com', 'INBOX'). Sin prefijo -> (None, folder)."""
    if not folder or not folder.startswith(PREFIJO):
        return None, folder or ""
    resto = folder[len(PREFIJO) :]
    cuenta, _, carpeta = resto.partition(SEP)
    cuenta = cuenta.strip().lower()
    if "@" not in cuenta:
        return None, folder
    return cuenta, (carpeta or "INBOX")


def carpeta_virtual(cuenta: str, carpeta_real: str) -> str:
    return f"{PREFIJO}{cuenta}{SEP}{carpeta_real}"


def carpeta_real(folder: str) -> str:
    """Nombre que entiende Dovecot. Las carpetas propias vuelven tal cual."""
    return separar(folder)[1]


async def cuentas_de(db, username: str) -> list[dict]:
    """Cuentas que esta persona puede usar, además de la suya."""
    filas = await db.fetch(
        """
        SELECT d.mailbox AS email, COALESCE(m.name, '') AS nombre, COALESCE(d.can_send_as, false) AS puede_enviar
          FROM mail_delegation d
          JOIN mailbox m ON m.username = d.mailbox AND m.active = true
         WHERE lower(d.delegate) = lower($1)
         ORDER BY d.mailbox
        """,
        username,
    )
    return [dict(f) for f in filas]


async def puede_usar(db, username: str, cuenta: str, para_enviar: bool = False) -> bool:
    """¿Puede `username` leer (o enviar como) `cuenta`? La propia cuenta siempre."""
    if not cuenta:
        return False
    if cuenta.lower() == username.lower():
        return True
    fila = await db.fetchrow(
        "SELECT can_send_as FROM mail_delegation d JOIN mailbox m ON m.username = d.mailbox AND m.active "
        "WHERE lower(d.mailbox) = lower($1) AND lower(d.delegate) = lower($2)",
        cuenta,
        username,
    )
    if not fila:
        return False
    return bool(fila["can_send_as"]) if para_enviar else True


def credenciales_maestras(cuenta: str, settings) -> tuple[str, str]:
    """Usuario y clave IMAP para abrir la cuenta delegada con el usuario maestro."""
    return f"{cuenta}*{USUARIO_MAESTRO}", settings.master_password


async def cuenta_de_la_peticion(request, username: str) -> str | None:
    """Si la petición apunta a una carpeta virtual de una cuenta delegada válida, la devuelve.

    Se mira el parámetro de ruta `folder`. El resultado se guarda en `request.state`
    para no consultar la base dos veces en la misma petición.
    """
    cache = getattr(request.state, "cuenta_delegada", "sin-calcular")
    if cache != "sin-calcular":
        return cache
    cuenta = None
    folder = (
        (request.path_params or {}).get("folder")
        if hasattr(request, "path_params")
        else None
    )
    posible, _ = separar(folder)
    if posible:
        db = request.app.state.db_pool
        if not await puede_usar(db, username, posible):
            # Carpeta virtual de una cuenta que NO le han delegado: se corta aquí, antes de
            # que el nombre se traduzca y termine abriendo la carpeta propia del mismo nombre.
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403, detail=f"No tienes acceso a la cuenta {posible}"
            )
        cuenta = posible
    request.state.cuenta_delegada = cuenta
    return cuenta
