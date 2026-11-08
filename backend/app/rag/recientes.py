"""Indexado de lo que va llegando durante el día (08/11/2026).

La pasada nocturna (rag-indexacion) recorre todo el buzón, pero un correo recibido a las 9 de la
mañana no se podía preguntar al asistente hasta el día siguiente. Esta pasada corta corre cada
15 minutos (rag-recientes.timer) y, en cada buzón habilitado, mira solo la Bandeja de entrada y
Enviados: si el UIDNEXT creció desde la última vez, pide los UID nuevos (`UID SEARCH UID n:*`),
los lee y los indexa con las mismas reglas que la nocturna (texto, omisiones de spam/servidor/
publicidad). No recalcula borrados ni toca carpetas que la nocturna aún no visitó: eso sigue
siendo trabajo de la noche.

Uso: python -m app.rag.run --recientes   (RAG_RECIENTES_MAX_BUZON=300 correos por buzón y pasada,
RAG_RECIENTES_MINUTOS=12 de tope para toda la pasada).
"""

import logging
import os
import time

from app.config import get_settings
from app.rag import (
    almacen,
    carpetas,
    filtro_cabeceras,
    indexador,
    lectura_imap,
    omitidos,
    plan,
    texto,
)
from app.rag.embeddings import embed

logger = logging.getLogger(__name__)


def _ajustes() -> dict:
    cfg = indexador.ajustes()
    cfg["max_buzon"] = max(20, int(os.getenv("RAG_RECIENTES_MAX_BUZON", "300")))
    cfg["minutos"] = float(os.getenv("RAG_RECIENTES_MINUTOS", "12"))
    return cfg


def carpetas_del_dia(lista: list[dict]) -> list[dict]:
    """De las carpetas indexables, solo la Bandeja de entrada y Enviados."""
    salida = []
    for c in lista:
        nombre = c["name"]
        ultimo = nombre.split(c.get("delimiter") or ".")[-1]
        if (
            nombre.upper() == "INBOX"
            or carpetas.normalizar(ultimo) in carpetas._NOMBRES_ENVIADOS
        ):
            salida.append(c)
    return salida


def uids_nuevos(uids: list[int], desde: int | None) -> list[int]:
    """Los UID ≥ `desde` (el UIDNEXT guardado), del más reciente al más antiguo."""
    if desde is None:
        return []
    return sorted((u for u in uids if u >= desde), reverse=True)


async def _uids_desde(imap, desde: int) -> list[int]:
    resp = await imap.uid_search(f"UID {desde}:*", charset=None)
    if resp.result != "OK":
        raise RuntimeError("UID SEARCH falló")
    salida: list[int] = []
    for linea in lectura_imap._decode_lines(resp.lines):
        if "completed" in linea.lower():
            continue
        salida.extend(int(x) for x in linea.split() if x.isdigit())
    return salida


async def _carpeta(db, username, c, imap, cfg, prog, presupuesto) -> int:
    nombre = c["name"]
    guardado = await almacen.estado(db, username, nombre)
    if not guardado or guardado.get("uidnext") is None:
        return 0  # la nocturna aún no pasó por aquí: que la haga completa ella
    info = await lectura_imap.examinar(imap, c["imap_name"])
    if info is None or info.get("uidnext") is None:
        return 0
    if plan.accion(guardado, info, texto.FORMATO) == plan.REINICIAR:
        return 0  # cambió el UIDVALIDITY: trabajo de la nocturna
    if int(info["uidnext"]) <= int(guardado["uidnext"]):
        return 0
    desde = int(guardado["uidnext"])
    pendientes = uids_nuevos(await _uids_desde(imap, desde), desde)
    ya = {
        **await almacen.formatos(db, username, nombre),
        **await omitidos.formatos(db, username, nombre),
    }
    pendientes = [u for u in pendientes if u not in ya][: cfg["max_buzon"]]
    if not pendientes:
        await almacen.guardar_estado(
            db,
            username,
            nombre,
            info,
            int(guardado["indexados"]),
            bool(guardado["completa"]),
            int(guardado["formato"] or 0),
        )
        return 0
    etiqueta = carpetas.etiqueta(nombre, c.get("delimiter", "."))
    hechos = 0
    for i in range(0, len(pendientes), cfg["tanda"]):
        if presupuesto.vencido():
            break
        tanda = pendientes[i : i + cfg["tanda"]]
        leidos = await lectura_imap.leer_tanda(imap, tanda, cfg["cuerpo_chars"])
        prog["leidos"] += len(tanda)
        antes = prog.get("omitidos", 0)
        n = await indexador._indexar_tanda(
            db, username, nombre, etiqueta, leidos, cfg, embed, prog
        )
        hechos += n + (
            prog.get("omitidos", 0) - antes
        )  # lo omitido también queda resuelto
    todo = hechos >= len(pendientes)
    # Si alcanzó todo lo nuevo, el UIDNEXT guardado avanza y la nocturna no lo vuelve a pedir;
    # si no, se deja como estaba y la próxima pasada (o la noche) sigue desde ahí.
    if todo:
        await almacen.guardar_estado(
            db,
            username,
            nombre,
            info,
            int(guardado["indexados"]) + hechos,
            bool(guardado["completa"]),
            int(guardado["formato"] or 0),
        )
    return hechos


async def buzones_habilitados(db) -> list[str]:
    doms = [
        r["domain"]
        for r in await db.fetch("SELECT domain FROM rag_domains WHERE enabled=true")
    ]
    if not doms:
        return []
    return [
        r["username"]
        for r in await db.fetch(
            "SELECT username FROM mailbox WHERE active=true AND split_part(username,'@',2)=ANY($1::text[]) ORDER BY username",
            doms,
        )
    ]


async def correr(db, redis=None, registrar=print) -> dict:
    from app.mail.clients.imap_client import get_imap_connection

    s = get_settings()
    cfg = _ajustes()
    await almacen.asegurar_esquema(db)
    await omitidos.asegurar(db)
    cfg["dominios_casa"] = await filtro_cabeceras.dominios_casa(db)
    presupuesto = plan.Presupuesto.con_minutos(0, cfg["minutos"])
    t0 = time.time()
    total, con_nuevos, fallidos = 0, 0, 0
    buzones = await buzones_habilitados(db)
    for u in buzones:
        if presupuesto.vencido():
            registrar(
                f"  tope de {cfg['minutos']:.0f} min alcanzado; el resto en la próxima pasada"
            )
            break
        prog = {"leidos": 0, "indexed": 0, "errores": 0, "omitidos": 0}
        try:
            imap = await get_imap_connection(f"{u}*admin", s.master_password)
            try:
                for c in carpetas_del_dia(
                    carpetas.a_indexar(await lectura_imap.listar(imap))
                ):
                    await _carpeta(db, u, c, imap, cfg, prog, presupuesto)
            finally:
                try:
                    await imap.logout()
                except Exception:
                    pass
        except indexador.EmbeddingsCaidos:
            registrar("servicio de embeddings caído: se detiene la pasada")
            break
        except Exception as e:
            fallidos += 1
            registrar(f"  {u}: falló ({e})")
            continue
        if prog["indexed"] or prog["omitidos"]:
            con_nuevos += 1
            total += prog["indexed"]
            registrar(f"  {u}: +{prog['indexed']} nuevos, {prog['omitidos']} omitidos")
    r = {
        "buzones": len(buzones),
        "con_nuevos": con_nuevos,
        "indexados": total,
        "fallidos": fallidos,
        "segundos": round(time.time() - t0),
    }
    registrar(f"{time.strftime('%F %T')} recientes RAG: {r}")
    return r
