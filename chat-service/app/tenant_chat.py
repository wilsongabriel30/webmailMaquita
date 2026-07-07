# -*- coding: utf-8 -*-
"""
Aislamiento por dominio (multi-empresa) para el chat.

La configuracion se administra desde el panel del correo y se lee del endpoint
publico del webmail (/api/chat-config): { domain_isolation: bool, domain_groups: [[..],..] }.
Cada grupo es un conjunto de dominios que SI pueden chatear entre si. Un dominio
que no esta en ningun grupo queda aislado (solo chatea dentro de su mismo dominio).
Solo afecta al CHAT; el correo (email) no se toca.
"""
import os
import time
import json
import urllib.request

_URL = os.getenv("WEBMAIL_CONFIG_URL", "http://127.0.0.1:8000/api/chat-config")
_TTL = 60
_C = {"t": 0.0, "iso": False, "groups": []}


def _refresh():
    now = time.time()
    if now - _C["t"] < _TTL:
        return
    _C["t"] = now
    try:
        with urllib.request.urlopen(_URL, timeout=3) as r:
            d = json.loads(r.read().decode())
        _C["iso"] = bool(d.get("domain_isolation"))
        gs = d.get("domain_groups") or []
        _C["groups"] = [set((x or "").strip().lower() for x in g if x) for g in gs if g]
    except Exception:
        pass  # ante fallo, se mantiene lo ultimo conocido


def dominio(email):
    return (email or "").split("@")[-1].strip().lower()


def _grupo(dom):
    for g in _C["groups"]:
        if dom in g:
            return g
    return None


def aislamiento_activo():
    _refresh()
    return _C["iso"]


def permite_dominios(da, db):
    _refresh()
    if not _C["iso"]:
        return True
    if not da or not db or da == db:
        return True
    g = _grupo(da)
    return g is not None and db in g


def dominios_permitidos(email):
    """Set de dominios con los que puede chatear, o None si no hay aislamiento."""
    _refresh()
    if not _C["iso"]:
        return None
    da = dominio(email)
    g = _grupo(da)
    return set(g) if g else {da}


def emails_por_ids(db_session, ids):
    if not ids:
        return {}
    try:
        from infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario
        rows = db_session.query(ModeloUsuario.id, ModeloUsuario.email).filter(
            ModeloUsuario.id.in_(list(ids))
        ).all()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def primer_bloqueado(db_session, uid_caller, uids_otros):
    """Primer uid de uids_otros que NO puede chatear con el caller, o None."""
    if not aislamiento_activo():
        return None
    otros = [u for u in uids_otros if u]
    mails = emails_por_ids(db_session, set([uid_caller] + otros))
    da = dominio(mails.get(uid_caller, ""))
    for u in otros:
        if not permite_dominios(da, dominio(mails.get(u, ""))):
            return u
    return None
