"""Aviso de ingreso desde un dispositivo nuevo (seguridad de la cuenta de correo).

Cuando una persona abre su correo desde un EQUIPO que la cuenta no había usado antes, se le avisa
para que lo note y pueda reaccionar si no fue ella:

1. Un CORREO breve (SMTP local, como los demás avisos del sistema), tratando de USTED, con el nombre
   del dispositivo, la fecha y la red/ubicación aproximada, e indicaciones para cerrar la sesión y
   cambiar la contraseña si no reconoce el ingreso.
2. Si la persona tiene teléfono(s) registrado(s) para avisos, un aviso por el MISMO canal ntfy que usan
   los avisos de correo nuevo (`app/mobile/avisos_correo.py`). El aviso al teléfono NO lleva datos
   sensibles: solo «hubo un ingreso nuevo» y la cuenta; el detalle se mira en el correo o en la app.

Qué NO dispara aviso:
- Renovaciones de sesión (refresh): el equipo ya es conocido.
- Equipos ya conocidos (los que ya visitaron la cuenta): solo se actualiza su «último visto».

Preferencia de la persona: configurable y ENCENDIDA por omisión. Se guarda en `auth_aviso_sesion_pref`.
Equipos conocidos: `auth_equipos_conocidos`. Ambas tablas se crean aquí de forma idempotente
(`asegurar_tablas`), con el mismo estilo asyncpg de `app/auth/sesiones.py` (db.execute/fetchval/fetch).

Reutiliza, sin modificarlos, los mecanismos que YA existen en el backend:
- Correo: SMTP local 127.0.0.1:25 con aiosmtplib (igual que `app/tareas/avisos.py::_correo`).
- Push al teléfono: el ntfy propio y la tabla `mobile_devices` de `app/mobile/avisos_correo.py`
  (se reutiliza `disponible()` y la misma configuración `NTFY_URL_INTERNO`/`NTFY_TOKEN`).

Todo es de «mejor esfuerzo»: un fallo al avisar NUNCA rompe ni retrasa el inicio de sesión. Por eso la
sesión principal debe invocar `avisar_ingreso_nuevo(...)` en segundo plano (ver CABLEADO al final).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from html import escape

import httpx

from app import organizacion
from app.branding.service import marca_corta

log = logging.getLogger("seguridad.aviso_sesion_nueva")

# --------------------------------------------------------------------------- tablas
_DDL = """
CREATE TABLE IF NOT EXISTS auth_equipos_conocidos (
    username     varchar(255) NOT NULL,
    equipo_id    varchar(128) NOT NULL,
    nombre       varchar(200) NOT NULL DEFAULT '',
    primer_visto timestamptz  NOT NULL DEFAULT now(),
    ultimo_visto timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (username, equipo_id)
);
CREATE INDEX IF NOT EXISTS auth_equipos_conocidos_username
    ON auth_equipos_conocidos (username);

CREATE TABLE IF NOT EXISTS auth_aviso_sesion_pref (
    username   varchar(255) PRIMARY KEY,
    activado   boolean      NOT NULL DEFAULT true,
    updated_at timestamptz  NOT NULL DEFAULT now()
);
"""
_tablas_ok = False


async def asegurar_tablas(db) -> None:
    """Crea (idempotente) las tablas de equipos conocidos y de preferencia. La sesión principal la
    llama una vez al arrancar. Es seguro llamarla varias veces."""
    global _tablas_ok
    if _tablas_ok:
        return
    await db.execute(_DDL)
    # Los identificadores del primer día salían del navegador y se compartían entre equipos: no valen
    # como «equipo conocido». Se retiran; el siguiente ingreso de cada cuenta vuelve a registrar el suyo.
    await db.execute(
        "DELETE FROM auth_equipos_conocidos WHERE equipo_id ~ '^nav-[0-9a-f]{16}$'"
    )
    _tablas_ok = True


def aviso_disponible() -> bool:
    """Interruptor general de Tecnología: `AVISO_INGRESO_NUEVO=0` en el entorno lo apaga para todos."""
    return os.environ.get("AVISO_INGRESO_NUEVO", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


async def tiene_equipos(db, username: str) -> bool:
    """¿La cuenta ya tiene algún equipo registrado?"""
    try:
        return bool(
            await db.fetchval(
                "SELECT 1 FROM auth_equipos_conocidos WHERE lower(username) = lower($1) LIMIT 1",
                username,
            )
        )
    except Exception:
        return True


async def _nombre_de_la_persona(db, username: str) -> str:
    try:
        return (
            await db.fetchval(
                "SELECT name FROM mailbox WHERE lower(username) = lower($1)", username
            )
            or ""
        ).strip()
    except Exception:
        return ""


async def _donde(redis, ip: str | None) -> str:
    """«Quito, Ecuador (IP 203.0.113.7)», «Red interna de la organización» o «desconocida»."""
    ip = (ip or "").strip()
    if not ip:
        return "desconocida"
    try:
        from app.risky_login.geoip import geolocate

        geo = await geolocate(redis, ip) or {}
    except Exception:
        geo = {}
    if geo.get("internal"):
        return "Red interna de la organización"
    lugar = ", ".join(x for x in (geo.get("city"), geo.get("country")) if x)
    return f"{lugar} (IP {ip})" if lugar else f"IP {ip}"


# --------------------------------------------------------------------------- preferencia
async def aviso_activado(db, username: str) -> bool:
    """¿La persona quiere avisos de ingreso desde un dispositivo nuevo? ENCENDIDO por omisión:
    si no hay fila, se entiende que sí. Ante un fallo de lectura, también se entiende que sí
    (es un aviso de seguridad: mejor avisar de más que de menos)."""
    try:
        await asegurar_tablas(db)
        valor = await db.fetchval(
            "SELECT activado FROM auth_aviso_sesion_pref WHERE lower(username) = lower($1)",
            username,
        )
    except Exception as exc:
        log.warning(
            "preferencia de aviso de ingreso no legible (%s): %s", username, exc
        )
        return True
    return True if valor is None else bool(valor)


async def fijar_preferencia(db, username: str, activado: bool) -> None:
    """Enciende o apaga el aviso para la persona. La sesión principal la cablea a un endpoint de
    preferencias (ver CABLEADO). Guardar el username en minúsculas unificado por la cuenta.
    """
    await asegurar_tablas(db)
    await db.execute(
        """INSERT INTO auth_aviso_sesion_pref (username, activado, updated_at)
           VALUES (lower($1), $2, now())
           ON CONFLICT (username) DO UPDATE
             SET activado = EXCLUDED.activado, updated_at = now()""",
        username,
        bool(activado),
    )


# --------------------------------------------------------------------------- equipos conocidos
async def equipo_conocido(db, redis, username: str, equipo_id: str) -> bool:
    """¿Esta cuenta ya había entrado desde este equipo? No registra nada (solo consulta).
    `redis` se acepta por simetría con el resto del flujo; hoy no se usa aquí."""
    if not username or not equipo_id:
        return False
    try:
        await asegurar_tablas(db)
        fila = await db.fetchval(
            """SELECT 1 FROM auth_equipos_conocidos
                WHERE lower(username) = lower($1) AND equipo_id = $2""",
            username,
            equipo_id[:128],
        )
    except Exception as exc:
        # Fallo cerrado hacia «no avisar»: si no se puede saber, se trata como conocido para no
        # molestar con falsos avisos ante un problema de base. El riesgo es solo dejar de avisar.
        log.warning("equipo_conocido no verificable (%s): %s", username, exc)
        return True
    return bool(fila)


async def marcar_conocido(
    db, username: str, equipo_id: str, nombre_equipo: str | None = None
) -> None:
    """Registra el equipo como conocido (o actualiza su «último visto» y su nombre)."""
    if not username or not equipo_id:
        return
    await asegurar_tablas(db)
    await db.execute(
        """INSERT INTO auth_equipos_conocidos (username, equipo_id, nombre, primer_visto, ultimo_visto)
           VALUES (lower($1), $2, $3, now(), now())
           ON CONFLICT (username, equipo_id) DO UPDATE
             SET ultimo_visto = now(),
                 nombre = COALESCE(NULLIF(EXCLUDED.nombre, ''), auth_equipos_conocidos.nombre)""",
        username,
        equipo_id[:128],
        (nombre_equipo or "")[:200],
    )


# --------------------------------------------------------------------------- correo
_REMITENTE = organizacion.remitente("ORG_REMITENTE_SEGURIDAD", "Seguridad", "seguridad")


def _texto_cuando(cuando: datetime | None) -> str:
    c = cuando or datetime.now(timezone.utc)
    if c.tzinfo is None:
        c = c.replace(tzinfo=timezone.utc)
    return c.astimezone().strftime("%d/%m/%Y %H:%M")


async def _enviar_correo(
    cuenta: str,
    *,
    nombre_persona: str,
    nombre_equipo: str,
    ubicacion: str,
    cuando_txt: str,
) -> None:
    """Correo breve de seguridad, tratando de USTED. SMTP local, igual que los demás avisos."""
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.utils import formatdate, make_msgid

        import aiosmtplib

        base = organizacion.url_correo()
        saludo = (
            f"Estimado/a {nombre_persona}," if nombre_persona else "Estimado/a usuario,"
        )
        asunto = "Se abrió su correo en un dispositivo nuevo"
        lineas = [
            f"Dispositivo: {nombre_equipo}",
            f"Fecha y hora: {cuando_txt}",
            f"Red/ubicación: {ubicacion}",
        ]
        aviso = (
            "Si fue usted, no debe hacer nada. "
            "Si no reconoce este ingreso, cierre esa sesión y cambie su contraseña cuanto antes."
        )
        enlace = f"{base}/webmail/settings?tab=security"

        msg = MIMEMultipart("alternative")
        msg["From"] = _REMITENTE
        msg["To"] = cuenta
        msg["Subject"] = asunto
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=organizacion.dominio_principal())
        msg["Auto-Submitted"] = "auto-generated"

        cuerpo_txt = (
            f"{saludo}\n\n"
            "Se abrió su correo desde un dispositivo que esta cuenta no había usado antes:\n\n"
            + "\n".join(lineas)
            + "\n\n"
            + aviso
            + "\n\n"
            f"Revise sus sesiones y su seguridad aquí: {enlace}\n"
        )
        filas_html = "".join(
            f'<tr><td style="padding:2px 12px 2px 0;color:#667">{escape(k)}</td>'
            f'<td style="padding:2px 0;font-weight:600">{escape(v)}</td></tr>'
            for k, v in (
                ("Dispositivo", nombre_equipo),
                ("Fecha y hora", cuando_txt),
                ("Red/ubicación", ubicacion),
            )
        )
        cuerpo_html = (
            '<div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#233">'
            f"<p>{escape(saludo)}</p>"
            "<p>Se abrió su correo desde un dispositivo que esta cuenta no había usado antes:</p>"
            f'<table style="border-collapse:collapse;margin:10px 0">{filas_html}</table>'
            f"<p>{escape(aviso)}</p>"
            f'<p><a href="{escape(enlace)}" style="background:#1b7f4a;color:#ffffff !important;'
            'padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">'
            '<span style="color:#ffffff !important">Revisar mis sesiones</span></a></p>'
            "</div>"
        )
        msg.attach(MIMEText(cuerpo_txt, "plain", "utf-8"))
        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))
        await aiosmtplib.send(
            msg, hostname="127.0.0.1", port=25, start_tls=False, timeout=15
        )
    except Exception as exc:
        log.warning("correo de aviso de ingreso nuevo no enviado (%s): %s", cuenta, exc)


# --------------------------------------------------------------------------- push al teléfono
# Se reutiliza el ntfy propio de los avisos de correo (mismas variables de entorno y temas de
# `app/mobile/avisos_correo.py`). El aviso NO lleva datos sensibles: ni dispositivo, ni IP, ni
# ubicación, ni contraseña. Solo «hubo un ingreso nuevo» y la cuenta (igual que `correo_nuevo`).
_NTFY_URL = os.environ.get("NTFY_URL_INTERNO", "http://127.0.0.1:2586")
_NTFY_TOKEN = os.environ.get("NTFY_TOKEN", "")


def _cuerpo_push(cuenta: str) -> bytes:
    return json.dumps(
        {"tipo": "ingreso_nuevo", "cuenta": cuenta, "v": 1}, separators=(",", ":")
    ).encode()


async def _avisar_telefonos(db, redis, cuenta: str) -> int:
    """Publica el aviso de ingreso nuevo en los teléfonos activos de la cuenta. Mejor esfuerzo."""
    # `disponible()` del módulo de avisos de correo nos dice si hay ntfy configurado.
    try:
        from app.mobile import avisos_correo

        if not avisos_correo.disponible():
            return 0
    except Exception:
        if not _NTFY_TOKEN:
            return 0
    try:
        filas = await db.fetch(
            """SELECT push_topic FROM mobile_devices
                WHERE lower(user_email) = lower($1) AND is_active AND avisos
                  AND push_topic IS NOT NULL
                LIMIT 200""",
            cuenta,
        )
    except Exception as exc:
        log.warning(
            "teléfonos para aviso de ingreso nuevo no legibles (%s): %s", cuenta, exc
        )
        return 0
    if not filas:
        return 0
    enviados = 0
    async with httpx.AsyncClient(timeout=4.0) as cli:
        for f in filas:
            tema = f["push_topic"]
            try:
                r = await cli.post(
                    f"{_NTFY_URL}/{tema}",
                    content=_cuerpo_push(cuenta),
                    headers={
                        "Authorization": f"Bearer {_NTFY_TOKEN}",
                        "Priority": "high",
                        "Title": marca_corta(),
                        "X-Tags": "warning",
                        "Cache": "yes",
                    },
                )
                if r.status_code < 300:
                    enviados += 1
            except Exception:
                log.debug(
                    "aviso push de ingreso nuevo falló tema=%s…", (tema or "")[:18]
                )
    return enviados


# --------------------------------------------------------------------------- orquestación
async def avisar_ingreso_nuevo(
    db,
    redis,
    username: str,
    *,
    equipo_id: str,
    nombre_equipo: str,
    ip: str | None = None,
    ubicacion: str | None = None,
    cuando: datetime | None = None,
    nombre_persona: str | None = None,
) -> dict:
    """Punto de entrada. Para un inicio de sesión recién creado:

    1. Si la preferencia está apagada, no hace nada (y de todos modos marca el equipo como conocido,
       para no acumular equipos sin registrar).
    2. Si el equipo YA es conocido, solo actualiza su «último visto». No avisa.
    3. Si el equipo es NUEVO, envía el correo y (si hay teléfonos) el aviso push, y lo marca conocido.

    Mejor esfuerzo: captura sus propios errores y nunca los propaga. Devuelve un pequeño resumen
    (sin datos sensibles) útil para pruebas: {'avisado', 'motivo', 'correo', 'telefonos'}.
    """
    resultado = {"avisado": False, "motivo": "", "correo": False, "telefonos": 0}
    try:
        if not username or not equipo_id:
            resultado["motivo"] = "faltan_datos"
            return resultado

        await asegurar_tablas(db)
        conocido = await equipo_conocido(db, redis, username, equipo_id)

        if conocido:
            await marcar_conocido(db, username, equipo_id, nombre_equipo)
            resultado["motivo"] = "equipo_conocido"
            return resultado

        # Primer equipo que se le registra a la cuenta: no hay con qué compararlo, así que no es un
        # «ingreso desde un equipo nuevo». Se anota sin avisar. Evita además que, al estrenar la función,
        # toda la organización reciba un aviso por su equipo de siempre.
        if not await tiene_equipos(db, username):
            await marcar_conocido(db, username, equipo_id, nombre_equipo)
            resultado["motivo"] = "primer_equipo"
            return resultado

        if not aviso_disponible():
            await marcar_conocido(db, username, equipo_id, nombre_equipo)
            resultado["motivo"] = "aviso_apagado_por_tecnologia"
            return resultado

        # Equipo nuevo: se registra SIEMPRE como conocido (haya o no aviso), para no repetir avisos.
        if not await aviso_activado(db, username):
            await marcar_conocido(db, username, equipo_id, nombre_equipo)
            resultado["motivo"] = "aviso_desactivado"
            return resultado

        cuando_txt = _texto_cuando(cuando)
        ubic = (ubicacion or "").strip() or await _donde(redis, ip)
        if not (nombre_persona or "").strip():
            nombre_persona = await _nombre_de_la_persona(db, username)
        nombre_eq = (
            nombre_equipo or "dispositivo desconocido"
        ).strip() or "dispositivo desconocido"

        await _enviar_correo(
            username,
            nombre_persona=(nombre_persona or "").strip(),
            nombre_equipo=nombre_eq,
            ubicacion=ubic,
            cuando_txt=cuando_txt,
        )
        resultado["correo"] = True
        resultado["telefonos"] = await _avisar_telefonos(db, redis, username)

        await marcar_conocido(db, username, equipo_id, nombre_equipo)
        resultado["avisado"] = True
        resultado["motivo"] = "equipo_nuevo"
        # No se registran datos personales ni el equipo en el log: solo el hecho.
        log.info(
            "AVISO_INGRESO_NUEVO user=%s telefonos=%s", username, resultado["telefonos"]
        )
        return resultado
    except Exception as exc:
        log.warning("avisar_ingreso_nuevo falló (%s): %s", username, str(exc)[:160])
        return resultado


def programar_aviso_ingreso_nuevo(db, redis, username: str, **kwargs) -> None:
    """Ayuda opcional: lanza `avisar_ingreso_nuevo` en segundo plano (no bloquea el login).
    La sesión principal puede usar esto o un BackgroundTask de FastAPI, lo que prefiera.
    """
    if db is None or not username:
        return

    async def _tarea():
        try:
            await avisar_ingreso_nuevo(db, redis, username, **kwargs)
        except Exception:
            log.warning("tarea de aviso de ingreso nuevo falló", exc_info=True)

    t = asyncio.create_task(_tarea())
    _tareas_fondo.add(t)
    t.add_done_callback(_tareas_fondo.discard)


_tareas_fondo: set = set()


# =============================================================================================
# CABLEADO (lo hace la sesión principal): llamar avisar_ingreso_nuevo(...) tras crear_sesion en
# /login y /login/2fa, en segundo plano (no bloquear el login).
#
# Al arrancar (p. ej. en el startup de app/main.py, junto a las demás tablas):
#     from app.auth import aviso_sesion_nueva
#     await aviso_sesion_nueva.asegurar_tablas(request.app.state.db_pool)   # o el pool disponible
#
# En el flujo de /login y /login/2fa, DESPUÉS de crear la sesión (crear_sesion) y de decidir el
# `equipo_id` (p. ej. derivado del dispositivo de confianza, del device_id de la app, o un hash
# estable de user-agent + pistas del equipo), lanzar el aviso SIN esperar:
#
#     aviso_sesion_nueva.programar_aviso_ingreso_nuevo(
#         request.app.state.db_pool,
#         request.app.state.redis,
#         username,                      # cuenta de correo (la misma que recibe el correo)
#         equipo_id=equipo_id,           # identificador estable del equipo (<=128)
#         nombre_equipo=nombre_equipo,   # «Chrome en Windows», modelo del teléfono, etc.
#         ip=ip,                         # IP de la petición (va solo en el correo)
#         ubicacion=ubicacion,          # red/ubicación aproximada (va solo en el correo)
#         cuando=None,                   # None = ahora
#         nombre_persona=nombre_real,    # opcional, para el saludo del correo
#     )
#
#   - O bien, con BackgroundTasks de FastAPI:
#       background_tasks.add_task(aviso_sesion_nueva.avisar_ingreso_nuevo, db, redis, username,
#                                 equipo_id=equipo_id, nombre_equipo=nombre_equipo, ip=ip,
#                                 ubicacion=ubicacion)
#
# IMPORTANTE: NO llamar en /refresh ni al prorrogar: esas NO son entradas nuevas de equipo.
# Solo tras crear_sesion en el login inicial (usuario+contraseña) y en el paso de segundo factor.
#
# Preferencia (encender/apagar) para un endpoint de ajustes de seguridad:
#     activado = await aviso_sesion_nueva.aviso_activado(db, username)
#     await aviso_sesion_nueva.fijar_preferencia(db, username, nuevo_valor)
# =============================================================================================
