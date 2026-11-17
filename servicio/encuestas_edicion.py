"""
Formularios del Almacén — una sola persona edita a la vez (17/11/2026)
=====================================================================
Cada guardado del editor manda la encuesta ENTERA. Si dos personas la editaban a la
vez, la que guardaba última borraba en silencio lo que hizo la otra (caso IIEM,
17/11/2026). Decisión de Wilson: «una a la vez».

  · Quien abre el editor pide la edición con un latido cada ~25 s. Si nadie la
    tiene (o el último latido tiene más de 150 s), se la queda; si otra pestaña la
    tiene, esa persona ve la encuesta en SOLO LECTURA con el nombre de quien edita.
  · Red de seguridad al guardar: se rechaza (409) un guardado de otra pestaña que no
    tiene la edición, o uno hecho sobre una versión que ya cambió en disco («base»).
    Así nunca se pisa nada en silencio.

    POST /api/almacen/encuestas/edicion/latido?ruta=…  {sesion} → {editor, quien, desde, base}
    POST /api/almacen/encuestas/edicion/soltar?ruta=…  {sesion}  (al cerrar la pestaña)

Autoría: Equipo de Tecnología Maquita — 2026-11-17
"""
import hashlib
import json
import logging

import almacen_bd as bd

log = logging.getLogger("almacen.encuestas.edicion")

CADUCA_SEGUNDOS = 150
_instalado = False


def _instalar():
    global _instalado
    if _instalado:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS encuesta_editando (
            encuesta_id TEXT PRIMARY KEY,
            usuario_id  INTEGER NOT NULL,
            sesion      TEXT NOT NULL,
            desde       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            latido      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _instalado = True


def base(definicion):
    """Huella de la encuesta tal como está en disco: la «versión» sobre la que se edita."""
    if definicion is None:
        return None
    texto = json.dumps(definicion, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


def _nombre(usuario_id):
    try:
        filas = bd.consultar("""
            SELECT COALESCE(t.nombres ||   || t.apellidos, u.full_name, u.username) AS nombre
            FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id WHERE u.id = %s
        """, (usuario_id,), nomina=True)
        return filas[0]["nombre"] if filas else "otra persona"
    except Exception:
        return "otra persona"


def _titular(encuesta_id):
    """Quién tiene hoy la edición (latido reciente), o None."""
    _instalar()
    filas = bd.consultar(
        "SELECT usuario_id, sesion, desde FROM encuesta_editando "
        "WHERE encuesta_id = %s AND latido > NOW() - make_interval(secs => %s)",
        (encuesta_id, CADUCA_SEGUNDOS))
    return filas[0] if filas else None


def _describir(t, usuario_id):
    misma = t["usuario_id"] == usuario_id
    return {"quien": "usted mismo en otra pestaña o ventana" if misma else _nombre(t["usuario_id"]),
            "misma_persona": misma,
            "desde": t["desde"].astimezone().strftime("%H:%M") if t.get("desde") else None}


def latido(encuesta_id, usuario_id, sesion):
    """Pide o renueva la edición. Devuelve {editor: True} o {editor: False, quien, desde}."""
    _instalar()
    filas = bd.consultar("""
        INSERT INTO encuesta_editando AS e (encuesta_id, usuario_id, sesion) VALUES (%s, %s, %s)
        ON CONFLICT (encuesta_id) DO UPDATE SET
            usuario_id = EXCLUDED.usuario_id,
            desde = CASE WHEN e.sesion = EXCLUDED.sesion THEN e.desde ELSE NOW() END,
            sesion = EXCLUDED.sesion, latido = NOW()
        WHERE e.sesion = EXCLUDED.sesion OR e.latido <= NOW() - make_interval(secs => %s)
        RETURNING sesion
    """, (encuesta_id, usuario_id, sesion, CADUCA_SEGUNDOS))
    if filas:
        return {"editor": True}
    t = _titular(encuesta_id)
    if not t:                       # se liberó justo ahora: otro intento
        return latido(encuesta_id, usuario_id, sesion)
    return dict({"editor": False}, **_describir(t, usuario_id))


def soltar(encuesta_id, sesion):
    """Al cerrar o recargar la pestaña: la edición queda libre en ~8 s, no al instante. Así, si solo
    se recargó (F5), la misma pestaña la recupera antes de que otra se la quede."""
    _instalar()
    bd.ejecutar("UPDATE encuesta_editando SET latido = NOW() - make_interval(secs => %s) "
                "WHERE encuesta_id = %s AND sesion = %s", (CADUCA_SEGUNDOS - 8, encuesta_id, sesion))


def comprobar_guardado(encuesta_id, usuario_id, sesion, base_cliente, previa):
    """None si se puede guardar; si no, (mensaje, datos) para responder 409."""
    t = _titular(encuesta_id)
    if t and t["sesion"] != (sesion or ""):
        d = _describir(t, usuario_id)
        return ("No se guardó: esta encuesta la está editando %s (desde las %s). Para no pisar sus cambios, "
                "solo se puede ver hasta que la cierre." % (d["quien"], d["desde"]), dict({"conflicto": "ocupada"}, **d))
    if base_cliente and base_cliente != base(previa):
        return ("No se guardó: la encuesta cambió mientras usted la tenía abierta (otra persona o pestaña la editó). "
                "Recargue la página para ver la versión actual y repita su último cambio.", {"conflicto": "cambiada"})
    if sesion and not t:
        latido(encuesta_id, usuario_id, sesion)
    return None
