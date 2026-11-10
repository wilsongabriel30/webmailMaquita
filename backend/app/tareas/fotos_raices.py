"""Fotos de perfil desde Raíces (nómina) → `user_profiles` del correo (09/11/2026).

Lo llama app/tareas/jefes.py en cada sincronización (cron cada 10 min). Aplica la regla
«la foto de Raíces manda» (REGLA-WEBMAIL-FOTO-PERFIL-RAICES-MANDA) con la decisión pura de
app/contacts/foto_efectiva.py:

  1. Por cada persona activa con foto en Raíces se calcula una HUELLA de la imagen (HEAD a la URL:
     ETag, o tamaño + fecha; si falla, se conserva la huella anterior o, si no hay, la URL misma).
  2. Si la huella cambió respecto de la guardada (o no había), la foto de Raíces pasa a ser la
     efectiva y termina la foto propia que la persona hubiera puesto en el correo.
  3. Si no cambió y hay propia, la propia sigue siendo la efectiva.
  4. Si la persona ya no tiene foto en Raíces, se retira la de Raíces (queda la propia si la hay).

Devuelve los correos cuya foto efectiva cambió, para invalidar `avatar:<correo>` en Redis
(`invalidar_avatares`, con la configuración común del backend: app.redis_client).
"""

import asyncio
import logging

import httpx

from app.contacts.foto_efectiva import (
    Cambios,
    EstadoFoto,
    decidir,
    huella_desde_cabeceras,
)

log = logging.getLogger("tareas.fotos_raices")

TIEMPO_HEAD = 5.0
SIMULTANEOS = 8

SQL_LEER = """SELECT lower(user_email) AS email, COALESCE(photo_url,'') AS photo_url,
                     COALESCE(foto_raices_url,'') AS foto_raices_url, COALESCE(foto_raices_huella,'') AS foto_raices_huella,
                     COALESCE(foto_propia_url,'') AS foto_propia_url, COALESCE(foto_origen,'') AS foto_origen
              FROM user_profiles WHERE lower(user_email) = ANY($1::text[])"""

SQL_ESCRIBIR = """INSERT INTO user_profiles (user_email, photo_url, foto_raices_url, foto_raices_huella, foto_propia_url,
                                             foto_origen, fuente, updated_at)
                  VALUES ($1, $2, $3, $4, $5, $6, 'nomina', NOW())
                  ON CONFLICT (user_email) DO UPDATE SET photo_url = EXCLUDED.photo_url,
                      foto_raices_url = EXCLUDED.foto_raices_url, foto_raices_huella = EXCLUDED.foto_raices_huella,
                      foto_propia_url = EXCLUDED.foto_propia_url, foto_origen = EXCLUDED.foto_origen,
                      fuente = COALESCE(user_profiles.fuente, 'nomina'), updated_at = NOW()"""


def url_foto_raices(usuario, url_intranet: str) -> str:
    """URL pública de la foto de una fila de `usuarios` de Raíces (profile_picture o trabajadores.foto_perfil)."""
    pp = (usuario["profile_picture"] or "").strip()
    fp = (usuario["foto_perfil"] or "").strip()
    if pp.startswith("http"):
        return pp
    if pp:
        return (
            url_intranet
            + "/static/"
            + (pp if pp.startswith("uploads/") else "uploads/profiles/" + pp)
        )
    if fp:
        return url_intranet + "/static/" + fp
    return ""


async def huella_remota(cliente: httpx.AsyncClient, url: str) -> str:
    """Huella por HEAD; '' si la petición falla (el que llama decide el respaldo)."""
    try:
        r = await cliente.head(url, timeout=TIEMPO_HEAD, follow_redirects=True)
        if r.status_code >= 400:
            return ""
        return huella_desde_cabeceras(dict(r.headers), url)
    except Exception as e:  # noqa: BLE001
        log.debug("HEAD %s: %s", url, e)
        return ""


async def _huellas(urls: set[str]) -> dict[str, str]:
    sem = asyncio.Semaphore(SIMULTANEOS)
    salida: dict[str, str] = {}

    async with httpx.AsyncClient() as cliente:

        async def una(u: str) -> None:
            async with sem:
                salida[u] = await huella_remota(cliente, u)

        await asyncio.gather(*(una(u) for u in urls))
    return salida


async def _estados(db, correos: list[str]) -> dict[str, EstadoFoto]:
    filas = await db.fetch(SQL_LEER, correos)
    return {
        f["email"]: EstadoFoto(
            photo_url=f["photo_url"],
            foto_raices_url=f["foto_raices_url"],
            foto_raices_huella=f["foto_raices_huella"],
            foto_propia_url=f["foto_propia_url"],
            foto_origen=f["foto_origen"],
        )
        for f in filas
    }


async def _aplicar(db, correo: str, c: Cambios) -> None:
    await db.execute(
        SQL_ESCRIBIR,
        correo,
        c.photo_url,
        c.foto_raices_url,
        c.foto_raices_huella,
        c.foto_propia_url,
        c.foto_origen,
    )


async def sincronizar(
    db, usuarios_raices, activos_inst: set[str], url_intranet: str
) -> dict:
    """Sincroniza las fotos de Raíces con `user_profiles`.

    `activos_inst`: buzones institucionales de personal activo (ya sin los cruzados).
    Devuelve {"con_foto": n, "cambiados": n, "invalidar": {correos}}.
    """
    # correo → URL de Raíces (solo personal activo institucional)
    raices: dict[str, str] = {}
    for u in usuarios_raices:
        url = url_foto_raices(u, url_intranet)
        if not url:
            continue
        for correo in {(u["email"] or "").lower(), (u["email_inst"] or "").lower()}:
            if correo and correo in activos_inst:
                raices[correo] = url

    # Personas activas con foto de Raíces guardada que ya no la tienen → también se revisan
    estados = await _estados(db, sorted(activos_inst)) if activos_inst else {}
    revisar = set(raices) | {e for e, est in estados.items() if est.foto_raices_url}

    huellas = await _huellas(set(raices.values())) if raices else {}
    invalidar: set[str] = set()
    cambiados = 0
    for correo in sorted(revisar):
        estado = estados.get(correo, EstadoFoto())
        url = raices.get(correo, "")
        huella = huellas.get(url, "") if url else ""
        if url and not huella:
            # El HEAD falló: no se toma como cambio. Misma URL → se conserva la huella conocida.
            huella = (
                estado.foto_raices_huella
                if estado.foto_raices_url == url and estado.foto_raices_huella
                else "url:" + url
            )
        c = decidir(estado, url, huella)
        if c.vacio():
            continue
        await _aplicar(db, correo, c)
        cambiados += 1
        if c.invalidar_cache:
            invalidar.add(correo)
    return {"con_foto": len(raices), "cambiados": cambiados, "invalidar": invalidar}


async def limpiar_salidos(db, activos_inst: set[str]) -> list[str]:
    """Al salir la persona de nómina (o cambiar el buzón de persona) se limpia lo que puso la nómina.

    La foto propia (si la hubiera) se conserva como efectiva. Devuelve los correos tocados.
    """
    filas = await db.fetch(
        """UPDATE user_profiles
              SET display_name = NULL, title = '', department = '', office_location = '', mobile = '', phone = '',
                  photo_url = COALESCE(foto_propia_url, ''), foto_raices_url = '', foto_raices_huella = '',
                  foto_origen = CASE WHEN COALESCE(foto_propia_url, '') <> '' THEN 'propio' ELSE '' END,
                  fuente = NULL, updated_at = NOW()
            WHERE fuente = 'nomina' AND lower(user_email) <> ALL($1::text[]) RETURNING lower(user_email) AS email""",
        sorted(activos_inst),
    )
    return [f["email"] for f in filas]


async def invalidar_avatares(correos: set[str]) -> int:
    """Borra `avatar:<correo>` en el Redis del servicio (misma configuración que el backend, con o sin Sentinel)."""
    if not correos:
        return 0
    from app.redis_client import create_redis

    r = await create_redis()
    try:
        claves = [f"avatar:{c.lower()}" for c in sorted(correos)]
        borradas = 0
        for i in range(0, len(claves), 200):
            borradas += int(await r.delete(*claves[i : i + 200]) or 0)
        return borradas
    finally:
        try:
            await r.aclose()
        except Exception:  # noqa: BLE001
            pass
