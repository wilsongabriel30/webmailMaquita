"""Cuenta activa: varias cuentas de correo dentro de una misma sesión (estilo Outlook).

Pedido (01/10/2026): quien maneja varias cuentas (ventas@, gerencia@, la de un compañero que
salió...) las ve en la barra lateral, elige una y lee, responde y gestiona como esa cuenta, sin
abrir un navegador por cuenta. La sesión sigue siendo de la PERSONA: su Drive, chat,
calendario, contactos, presencia y segundo factor no cambian; solo el CORREO cambia de cuenta.

Cómo funciona:
- El webmail manda la cabecera `X-Cuenta-Activa: <cuenta>` en cada petición.
- Solo cuenta en las rutas de correo, firmas y filtros (`RUTAS`); en el resto se ignora.
- Si la cuenta está asignada a la persona en `mail_delegation`, la dependencia central
  (`get_current_user`) devuelve ESA cuenta en lugar de la persona. Así las cachés
  (`folders:`, `uids:`...), etiquetas, firma y filtros quedan separados por cuenta sin tocar
  cada router. La persona real queda en `request.state.persona`.
- La credencial IMAP/SMTP de la cuenta es la del usuario maestro de Dovecot
  (`cuentas_delegadas.credenciales_maestras`); nunca sale del servidor.
- Se comprueba contra la base en CADA petición: quitar la asignación corta el acceso al instante.
- `can_send_as = false` es solo lectura: se rechaza todo lo que no sea consultar.
- Nunca se abre la cuenta de un superadministrador, ni desde una sesión de impersonación o
  delegada (las variantes anteriores).
"""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException, Request

log = logging.getLogger(__name__)

CABECERA = "x-cuenta-activa"

# Respaldo para lo que el navegador pide sin poder poner cabeceras (enlaces de descarga,
# imágenes, adjuntos). Solo se acepta en consultas (GET/HEAD): enviar, mover o borrar exigen la
# cabecera, que es por pestaña. Si la cabecera viene (aunque sea "propia"), manda la cabecera.
COOKIE = "cuenta_activa"

# Rutas donde la cuenta activa reemplaza a la persona.
# Firmas: /api/settings/signature y /api/settings/signatures* (cada cuenta tiene la suya); el
# resto de /api/settings (tema, idioma...) sigue siendo de la persona.
RUTAS = ("/api/mail/", "/api/firmas", "/api/sieve", "/api/settings/signature")

# Dentro de esas rutas, lo que sigue siendo de la persona: la lista de sus cuentas, la gestión
# de delegaciones (quien revisa una cuenta no puede repartirla) y servicios ligados a la persona.
EXCLUIDAS = (
    "/api/mail/cuentas",
    "/api/mail/delegation",
    "/api/mail/shared",
    "/api/mail/dlp",
    "/api/mail/secure",
    "/api/mail/transcribe",
)

METODOS_LECTURA = frozenset({"GET", "HEAD", "OPTIONS"})

# Consultas que van por POST pero no cambian nada (se permiten con solo lectura).
POST_DE_CONSULTA = ("/api/mail/search", "/api/mail/recall/check")

# Tipos de sesión desde los que se puede cambiar de cuenta.
SESIONES_PERMITIDAS = frozenset({"normal", "oidc"})


def aplica(ruta: str) -> bool:
    """¿La cuenta activa cuenta en esta ruta?"""
    return ruta.startswith(RUTAS) and not ruta.startswith(EXCLUIDAS)


def es_escritura(metodo: str, ruta: str) -> bool:
    if metodo.upper() in METODOS_LECTURA:
        return False
    return not ruta.startswith(POST_DE_CONSULTA)


async def _asignacion(db, persona: str, cuenta: str):
    """Fila de la asignación vigente, o None. La cuenta debe estar activa y no ser de un
    superadministrador."""
    return await db.fetchrow(
        """
        SELECT COALESCE(d.can_send_as, false) AS completo
          FROM mail_delegation d
          JOIN mailbox m ON lower(m.username) = lower(d.mailbox) AND m.active = true
         WHERE lower(d.mailbox) = lower($1) AND lower(d.delegate) = lower($2)
           AND NOT EXISTS (SELECT 1 FROM admin a
                            WHERE lower(a.username) = lower($1) AND a.superadmin = true)
        """,
        cuenta,
        persona,
    )


def _ip(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    return ip if ip and ip[0].isdigit() else None


async def _auditar(request: Request, persona: str, cuenta: str, accion: str) -> None:
    """Primer uso de la cuenta en la sesión (`cuenta_activa_acceso`, una vez cada 12 h) y cada
    envío como esa cuenta (`cuenta_activa_envio`). La auditoría no debe impedir trabajar."""
    try:
        if accion == "cuenta_activa_acceso":
            sid = getattr(request.state, "sid", "")
            nueva = await request.app.state.redis.set(
                f"cuenta_activa:auditada:{sid}:{cuenta}", "1", ex=43200, nx=True
            )
            if not nueva:
                return
        await request.app.state.db_pool.execute(
            "INSERT INTO audit_log (admin_user, action, target, details, ip_address) "
            "VALUES ($1, $2, $3, $4::jsonb, $5::inet)",
            persona,
            accion,
            cuenta,
            json.dumps({"persona": persona, "cuenta": cuenta, "ruta": request.url.path}),
            _ip(request),
        )
    except Exception as exc:
        log.warning("%s sin auditoría (%s -> %s): %s", accion, persona, cuenta, exc)


async def resolver(request: Request, persona: str) -> str:
    """Usuario con el que trabaja esta petición: la persona o la cuenta activa que eligió."""
    request.state.persona = persona
    pedida = request.headers.get(CABECERA)
    if pedida is None and request.method.upper() in METODOS_LECTURA:
        pedida = request.cookies.get(COOKIE)
    pedida = (pedida or "").strip().lower()
    ruta = request.url.path
    # Sin cuenta, "propia" o la misma persona: su propio buzón.
    if "@" not in pedida or pedida == persona.lower() or not aplica(ruta):
        return persona

    if getattr(request.state, "session_kind", "normal") not in SESIONES_PERMITIDAS:
        raise HTTPException(
            status_code=403,
            detail="Esta sesión no puede abrir otras cuentas",
        )
    fila = await _asignacion(request.app.state.db_pool, persona, pedida)
    if not fila:
        raise HTTPException(
            status_code=403,
            detail={"detail": f"No tienes acceso a la cuenta {pedida}", "cuenta_revocada": pedida},
        )
    if not fila["completo"] and es_escritura(request.method, ruta):
        raise HTTPException(
            status_code=403,
            detail=f"La cuenta {pedida} está asignada solo para lectura",
        )

    request.state.cuenta_activa = pedida
    await _auditar(request, persona, pedida, "cuenta_activa_acceso")
    if request.method.upper() == "POST" and ruta.rstrip("/") == "/api/mail/send":
        await _auditar(request, persona, pedida, "cuenta_activa_envio")
    return pedida
