"""Indexa TODAS las carpetas de un buzón (salvo Papelera, Spam y Borradores), por tandas.

Incremental y reanudable: lo pendiente se calcula siempre como «UID de la carpeta menos UID ya
indexados en el formato actual», así que si una ejecución se corta (límite de correos, hora
tope, caída del IMAP) la siguiente sigue donde quedó sin llevar ninguna marca aparte.
"""

import asyncio
import logging
import os

from app.rag import almacen, carpetas, lectura_imap, plan, texto
from app.rag.embeddings import embed

logger = logging.getLogger(__name__)

MAX_ERRORES_BUZON = (
    3  # fallos de IMAP seguidos en un buzón antes de dejarlo para otra vez
)
MAX_FALLOS_EMBEDDING = 20  # seguidos: el servicio de embeddings no responde


class EmbeddingsCaidos(RuntimeError):
    pass


def ajustes() -> dict:
    return {
        "tanda": max(20, int(os.getenv("RAG_INGEST_PAGE", "100"))),
        "cuerpo_chars": max(0, int(os.getenv("RAG_CUERPO_CHARS", "1500"))),
        "pausa_s": max(0, int(os.getenv("RAG_PAUSA_MS", "0"))) / 1000,
    }


async def _indexar_tanda(db, username, carpeta, etiqueta, leidos, cfg, embed_fn, prog):
    """Embeddings de una tanda ya leída del IMAP y guardado en un solo lote."""
    filas, fallos_seguidos = [], 0
    for m in leidos:
        contenido = texto.contenido(etiqueta, m, m.get("cuerpo", ""))
        emb = await embed_fn(contenido)
        if not emb:
            prog["errores"] += 1
            fallos_seguidos += 1
            if fallos_seguidos >= MAX_FALLOS_EMBEDDING:
                raise EmbeddingsCaidos("el servicio de embeddings no responde")
            continue
        fallos_seguidos = 0
        filas.append(
            (
                m["uid"],
                m.get("asunto", ""),
                m.get("de", ""),
                contenido,
                emb,
                texto.FORMATO,
            )
        )
    await almacen.guardar_lote(db, username, carpeta, filas)
    prog["indexed"] += len(filas)
    return len(filas)


async def _esperar(tarea):
    """Termina una lectura adelantada pendiente sin dejar la conexión IMAP a medias."""
    if tarea is None:
        return
    try:
        await tarea
    except Exception:
        pass


async def _carpeta(
    db, username, c, imap, cfg, presupuesto, limite_buzon, prog, publicar, embed_fn
) -> bool:
    """Indexa una carpeta. True si quedó completa."""
    nombre = c["name"]
    info = await lectura_imap.examinar(imap, c["imap_name"])
    if info is None:
        return True  # no se puede abrir (no seleccionable): nada que hacer
    guardado = await almacen.estado(db, username, nombre)
    que = plan.accion(guardado, info, texto.FORMATO)
    if que == plan.SALTAR:
        return True
    if que == plan.REINICIAR:
        n = await almacen.borrar_carpeta(db, username, nombre)
        logger.info(
            "RAG %s: «%s» cambió de UIDVALIDITY; se reindexa (%s quitados)",
            username,
            nombre,
            n,
        )
    indexados = (
        await almacen.formatos(db, username, nombre) if que != plan.REINICIAR else {}
    )
    uids_srv = await lectura_imap.uids(imap) if info["mensajes"] else []
    por_hacer, a_borrar = plan.pendientes(uids_srv, indexados, texto.FORMATO)
    if a_borrar:
        await almacen.borrar_uids(db, username, nombre, a_borrar)
    cupo = plan.cupo(presupuesto, limite_buzon, prog["indexed"])
    if cupo is not None:
        por_hacer_ahora = por_hacer[:cupo]
    else:
        por_hacer_ahora = por_hacer
    prog["pendientes"] = prog.get("pendientes", 0) + len(por_hacer)
    etiqueta = carpetas.etiqueta(nombre, c.get("delimiter", "."))
    errores_antes, hechos = prog["errores"], 0
    tandas = [
        por_hacer_ahora[i : i + cfg["tanda"]]
        for i in range(0, len(por_hacer_ahora), cfg["tanda"])
    ]

    def leer(uids):
        return asyncio.ensure_future(
            lectura_imap.leer_tanda(imap, uids, cfg["cuerpo_chars"])
        )

    # Mientras la IA calcula los embeddings de una tanda, Dovecot ya lee la siguiente: la
    # lectura en frío (≈ 44 ms por correo) y el embedding (≈ 35 ms) se solapan.
    siguiente = leer(tandas[0]) if tandas else None
    try:
        for k, tanda in enumerate(tandas):
            if k and presupuesto.vencido():
                break  # la lectura adelantada se descarta (se espera en el finally)
            leidos = await siguiente
            siguiente = None
            prog["leidos"] += len(tanda)
            if k + 1 < len(tandas) and not presupuesto.vencido():
                siguiente = leer(tandas[k + 1])
            n = await _indexar_tanda(
                db, username, nombre, etiqueta, leidos, cfg, embed_fn, prog
            )
            presupuesto.consumir(n)
            hechos += len(tanda)
            prog["pendientes"] -= len(tanda)
            await publicar()
            if siguiente is None:
                break
            if cfg["pausa_s"]:
                await asyncio.sleep(cfg["pausa_s"])
    finally:
        await _esperar(siguiente)
    # Si algún correo falló (embedding), la carpeta queda incompleta y se reintenta otro día.
    completa = hechos >= len(por_hacer) and prog["errores"] == errores_antes
    total = await almacen.contar(db, username, nombre)
    await almacen.guardar_estado(
        db, username, nombre, info, total, completa, texto.FORMATO
    )
    return completa


async def indexar_buzon(
    db,
    username,
    conectar,
    prog: dict,
    publicar,
    limite_buzon: int,
    presupuesto: plan.Presupuesto,
    embed_fn=embed,
    cfg=None,
) -> dict:
    """Recorre las carpetas del buzón. Devuelve {completo, carpetas, hechas}.

    `conectar` es una corrutina que abre el IMAP (se vuelve a llamar si la conexión cae).
    """
    cfg = cfg or ajustes()
    await almacen.asegurar_esquema(db)
    imap = await conectar()
    try:
        todas = await lectura_imap.listar(imap)
        lista = carpetas.a_indexar(todas)
        prog.update(carpetas_total=len(lista), carpetas_hechas=0, pendientes=0)
        if any(c["name"].upper() == "INBOX" for c in lista):
            await almacen.borrar_ausentes(db, username, [c["name"] for c in lista])
        completo, errores_imap = True, 0
        for c in lista:
            if presupuesto.agotado() or (
                limite_buzon and prog["indexed"] >= limite_buzon
            ):
                completo = False
                break
            prog["carpeta"] = carpetas.etiqueta(c["name"], c.get("delimiter", "."))
            try:
                if not await _carpeta(
                    db,
                    username,
                    c,
                    imap,
                    cfg,
                    presupuesto,
                    limite_buzon,
                    prog,
                    publicar,
                    embed_fn,
                ):
                    completo = False
                errores_imap = 0
            except EmbeddingsCaidos:
                raise
            except Exception as e:  # IMAP caído o respuesta rara: se anota y se sigue
                completo = False
                prog["errores"] += 1
                errores_imap += 1
                logger.warning("RAG %s: carpeta «%s» falló: %s", username, c["name"], e)
                if errores_imap >= MAX_ERRORES_BUZON:
                    break
                try:
                    await imap.logout()
                except Exception:
                    pass
                imap = await conectar()
            prog["carpetas_hechas"] += 1
            await publicar()
        return {"completo": completo, "carpetas": len(lista)}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
