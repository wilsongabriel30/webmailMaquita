"""
Formularios del Almacén — rutas de «una sola persona edita a la vez» (17/11/2026)
La lógica está en `encuestas_edicion.py`. Lo importa `api_encuestas_publico` al final.

Autoría: Equipo de Tecnología Maquita — 2026-11-17
"""
from flask import jsonify, request

import encuestas_edicion as edicion
from api_encuestas import _abrir, bp_encuestas, usuario_actual


def _sesion():
    cuerpo = request.get_json(silent=True, force=True) or {}
    return str(cuerpo.get("sesion") or "")[:64]


@bp_encuestas.route("/encuestas/edicion/latido", methods=["POST"])
def edicion_latido():
    datos, fallo = _abrir()
    if fallo:
        return fallo
    _usuario, _ruta, definicion = datos
    sesion = _sesion()
    if not sesion or not definicion.get("id"):
        return jsonify({"success": True, "editor": True, "base": edicion.base(definicion)})
    r = edicion.latido(definicion["id"], usuario_actual(), sesion)
    r.update({"success": True, "base": edicion.base(definicion)})
    return jsonify(r)


@bp_encuestas.route("/encuestas/edicion/soltar", methods=["POST"])
def edicion_soltar():
    datos, fallo = _abrir()
    if fallo:
        return fallo
    sesion = _sesion()
    if sesion and datos[2].get("id"):
        edicion.soltar(datos[2]["id"], sesion)
    return jsonify({"success": True})
