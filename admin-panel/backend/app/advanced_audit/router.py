"""Auditoría avanzada — visor unificado de TODA la actividad del sistema.

Combina admin_audit (acciones del panel), user_activity_log (actividad de usuarios:
logins, envíos, eDiscovery, etc.) y threat_actions (acciones de seguridad), con
búsqueda, filtros, estadísticas, exportación CSV y retención configurable.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import csv
import io
import json
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/advanced-audit", tags=["advanced-audit"])

# Subconsulta unificada y normalizada de las 3 fuentes
UNIFIED = """
SELECT created_at AS ts, 'admin' AS source, admin_username AS actor, action,
       'admin'::text AS category, target, ip_address::text AS ip, NULL::text AS risk,
       details::text AS details
FROM admin_audit
UNION ALL
SELECT created_at, 'usuario', username, action, COALESCE(category,'general'),
       target, ip_address::text, risk_level, details::text
FROM user_activity_log
UNION ALL
SELECT created_at, 'seguridad', actor, action, 'seguridad', target, NULL::text,
       NULL::text, json_build_object('detail', detail, 'auto', auto)::text
FROM threat_actions
"""


def _db(r: Request):
    return r.app.state.db


def _filters(args: dict):
    """Construye (where_sql, params) a partir de los filtros."""
    conds, params = [], []
    def add(cond, val):
        params.append(val)
        conds.append(cond.replace("?", f"${len(params)}"))
    if args.get("q"):
        params.append(f"%{args['q'].lower()}%")
        i = len(params)
        conds.append(f"(lower(actor) LIKE ${i} OR lower(action) LIKE ${i} OR lower(coalesce(target,'')) LIKE ${i} OR lower(coalesce(details,'')) LIKE ${i})")
    if args.get("source"):
        add("source = ?", args["source"])
    if args.get("action"):
        add("action = ?", args["action"])
    if args.get("category"):
        add("category = ?", args["category"])
    if args.get("risk"):
        add("risk = ?", args["risk"])
    if args.get("actor"):
        add("lower(actor) = ?", args["actor"].lower())
    if args.get("date_from"):
        add("ts >= ?::timestamptz", args["date_from"])
    if args.get("date_to"):
        add("ts <= ?::timestamptz", args["date_to"])
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    return where, params


@router.get("/search")
async def search(request: Request, admin: dict = Depends(get_current_admin),
                 q: str = "", source: str = "", action: str = "", category: str = "",
                 risk: str = "", actor: str = "", date_from: str = "", date_to: str = "",
                 page: int = 1, per_page: int = 50):
    args = {"q": q, "source": source, "action": action, "category": category,
            "risk": risk, "actor": actor, "date_from": date_from, "date_to": date_to}
    where, params = _filters(args)
    per_page = max(1, min(per_page, 200))
    offset = (max(1, page) - 1) * per_page
    db = _db(request)
    total = await db.fetchval(f"SELECT count(*) FROM ({UNIFIED}) u{where}", *params)
    rows = await db.fetch(
        f"SELECT * FROM ({UNIFIED}) u{where} ORDER BY ts DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}",
        *params, per_page, offset)
    return {"total": total or 0, "page": page, "per_page": per_page,
            "entries": [{"ts": r["ts"].isoformat() if r["ts"] else None, "source": r["source"],
                         "actor": r["actor"], "action": r["action"], "category": r["category"],
                         "target": r["target"], "ip": r["ip"], "risk": r["risk"],
                         "details": r["details"]} for r in rows]}


@router.get("/summary")
async def summary(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    total = await db.fetchval(f"SELECT count(*) FROM ({UNIFIED}) u")
    by_source = await db.fetch(f"SELECT source, count(*) n FROM ({UNIFIED}) u GROUP BY source ORDER BY n DESC")
    failed = await db.fetchval(f"SELECT count(*) FROM ({UNIFIED}) u WHERE action='login_failed' AND ts > now()-interval '30 days'")
    critical = await db.fetchval(f"SELECT count(*) FROM ({UNIFIED}) u WHERE risk='high' AND ts > now()-interval '30 days'")
    top_actors = await db.fetch(f"SELECT actor, count(*) n FROM ({UNIFIED}) u WHERE actor<>'' AND ts > now()-interval '30 days' GROUP BY actor ORDER BY n DESC LIMIT 8")
    return {"total": total or 0,
            "by_source": [{"source": r["source"], "n": r["n"]} for r in by_source],
            "failed_logins": failed or 0, "critical": critical or 0,
            "top_actors": [{"actor": r["actor"], "n": r["n"]} for r in top_actors]}


@router.get("/facets")
async def facets(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    actions = await db.fetch(f"SELECT action, count(*) n FROM ({UNIFIED}) u GROUP BY action ORDER BY n DESC LIMIT 60")
    cats = await db.fetch(f"SELECT DISTINCT category FROM ({UNIFIED}) u WHERE category IS NOT NULL ORDER BY category")
    return {"actions": [r["action"] for r in actions],
            "categories": [r["category"] for r in cats],
            "sources": ["admin", "usuario", "seguridad"],
            "risks": ["low", "medium", "high"]}


@router.get("/export")
async def export(request: Request, admin: dict = Depends(require_role("superadmin", "admin")),
                 q: str = "", source: str = "", action: str = "", category: str = "",
                 risk: str = "", actor: str = "", date_from: str = "", date_to: str = ""):
    args = {"q": q, "source": source, "action": action, "category": category,
            "risk": risk, "actor": actor, "date_from": date_from, "date_to": date_to}
    where, params = _filters(args)
    rows = await _db(request).fetch(f"SELECT * FROM ({UNIFIED}) u{where} ORDER BY ts DESC LIMIT 20000", *params)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fecha", "origen", "actor", "accion", "categoria", "objetivo", "ip", "riesgo", "detalles"])
    for r in rows:
        w.writerow([r["ts"].isoformat() if r["ts"] else "", r["source"], r["actor"], r["action"],
                    r["category"], r["target"] or "", r["ip"] or "", r["risk"] or "", r["details"] or ""])
    return {"csv": buf.getvalue(), "rows": len(rows)}


# ── Retención ───────────────────────────────────────────────────────────────
class RetentionIn(BaseModel):
    retention_days: int = 0


@router.get("/retention")
async def get_retention(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow("SELECT retention_days FROM audit_retention_config WHERE id=1")
    return {"retention_days": row["retention_days"] if row else 0}


@router.put("/retention")
async def set_retention(body: RetentionIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    days = max(0, min(int(body.retention_days), 3650))
    await _db(request).execute(
        "INSERT INTO audit_retention_config (id, retention_days, updated_at) VALUES (1,$1,now()) "
        "ON CONFLICT (id) DO UPDATE SET retention_days=EXCLUDED.retention_days, updated_at=now()", days)
    return {"ok": True}


@router.post("/retention/purge")
async def purge(request: Request, admin: dict = Depends(require_role("superadmin"))):
    """Borra registros más antiguos que la retención configurada (>0). Solo superadmin."""
    db = _db(request)
    days = await db.fetchval("SELECT retention_days FROM audit_retention_config WHERE id=1") or 0
    if days <= 0:
        return {"ok": False, "reason": "Retención en 0 (conservar siempre). No se borró nada."}
    deleted = 0
    for tbl in ("admin_audit", "user_activity_log", "threat_actions"):
        res = await db.execute(f"DELETE FROM {tbl} WHERE created_at < now() - interval '{days} days'")
        try:
            deleted += int(res.split()[-1])
        except (ValueError, IndexError):
            pass
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "audit_purge", f"{deleted} registros (>{days}d)",
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "deleted": deleted}
