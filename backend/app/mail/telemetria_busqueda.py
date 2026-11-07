"""Telemetría de las búsquedas del correo (05/11/2026).

Hasta hoy el registro del servidor guardaba solo la ruta (sin la consulta) y el cliente no enviaba
ningún evento al buscar, así que cuando alguien decía «el buscador no me encuentra X» no había
forma de saber qué escribió. Cada búsqueda con texto deja un evento `busqueda` (módulo `correo`)
en `app_telemetria`: quién, qué escribió, en qué carpeta, cuántos resultados y cuánto tardó.
Se consulta en el panel de telemetría (resumen interno) o directo en la tabla:
    SELECT recibido, usuario, detalle, extra FROM app_telemetria WHERE evento='busqueda' ORDER BY 1 DESC;
Nunca bloquea la respuesta: si falla la escritura, solo se anota en el registro.
"""

import json
import logging

log = logging.getLogger(
    "maquita.webmail.busqueda"
)  # hijo del logger configurado (05/11/2026)

CARPETA_TODO = "Virtual.Todo"


async def registrar(
    pool,
    usuario: str,
    carpeta: str,
    texto: str,
    resultados,
    ms: int,
    en_contenido: bool,
    pagina: int,
):
    texto = (texto or "").strip()
    if not texto:
        return
    extra = {
        "carpeta": carpeta,
        "ambito": "todo_el_correo" if carpeta == CARPETA_TODO else "carpeta",
        "resultados": resultados,
        "ms": ms,
        "en_contenido": en_contenido,
        "pagina": pagina,
    }
    log.info(
        "busqueda user=%s carpeta=%s texto=%r resultados=%s ms=%s",
        usuario,
        carpeta,
        texto,
        resultados,
        ms,
    )
    try:
        await pool.execute(
            """INSERT INTO app_telemetria (ocurrido, usuario, evento, nivel, modulo, url, detalle, extra)
               VALUES (NOW(), $1, 'busqueda', 'info', 'correo', $2, $3, $4::jsonb)""",
            (usuario or "").lower()[:120],
            f"/api/mail/messages/{carpeta}"[:300],
            texto[:4000],
            json.dumps(extra, ensure_ascii=False, default=str),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("no se pudo guardar la telemetría de búsqueda: %s", e)
