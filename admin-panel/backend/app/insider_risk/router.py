"""Insider Risk — puntaje de riesgo por usuario combinando señales ya existentes.

Fuentes (con username/email): dlp_violations, fraud_alerts, user_activity_log
(login_failed), comm_flags y phish_targets. No requiere tablas nuevas; se calcula
en vivo sobre una ventana de 30 días (phishing: histórico).

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
from fastapi import APIRouter, Request, Depends
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/insider-risk", tags=["insider-risk"])
WINDOW = "30 days"


def _db(r: Request):
    return r.app.state.db


def _level(score: int) -> str:
    if score >= 30: return "critico"
    if score >= 15: return "alto"
    if score >= 6: return "medio"
    if score > 0: return "bajo"
    return "ninguno"


async def _scores(db) -> dict:
    users: dict[str, dict] = {}

    def U(name):
        name = (name or "").strip().lower()
        if not name:
            return None
        return users.setdefault(name, {"user": name, "score": 0, "factors": []})

    def add(name, pts, label):
        u = U(name)
        if u and pts:
            u["score"] += pts
            u["factors"].append({"label": label, "points": pts})

    # DLP
    for r in await db.fetch(f"""SELECT username, count(*) n,
            count(*) FILTER (WHERE action='block') blk, count(*) FILTER (WHERE overridden) ovr
            FROM dlp_violations WHERE created_at > now() - interval '{WINDOW}' GROUP BY username"""):
        pts = r["n"] * 3 + r["blk"] * 4 + r["ovr"] * 2
        add(r["username"], pts, f"{r['n']} alerta(s) de fuga de datos (DLP)")

    # Alertas de cuenta (compromiso / envío masivo)
    for r in await db.fetch("SELECT username, count(*) n FROM fraud_alerts WHERE status='open' GROUP BY username"):
        add(r["username"], r["n"] * 10, f"{r['n']} alerta(s) de cuenta comprometida")

    # Logins fallidos
    for r in await db.fetch(f"""SELECT username, count(*) n FROM user_activity_log
            WHERE action='login_failed' AND created_at > now() - interval '{WINDOW}' GROUP BY username"""):
        cnt = min(r["n"], 20)
        add(r["username"], cnt, f"{r['n']} intento(s) de acceso fallido(s)")

    # Communication Compliance
    for r in await db.fetch(f"""SELECT username, count(*) n, count(*) FILTER (WHERE status='escalated') esc
            FROM comm_flags WHERE created_at > now() - interval '{WINDOW}' GROUP BY username"""):
        add(r["username"], r["n"] * 2 + r["esc"] * 4, f"{r['n']} marca(s) de cumplimiento")

    # Simulación de phishing
    for r in await db.fetch("""SELECT email username,
            count(*) FILTER (WHERE submitted) sub, count(*) FILTER (WHERE clicked) clk,
            count(*) FILTER (WHERE reported) rep FROM phish_targets GROUP BY email"""):
        pts = r["sub"] * 10 + r["clk"] * 4 - r["rep"] * 3
        if r["sub"]:
            add(r["username"], r["sub"] * 10, f"Entregó su contraseña en {r['sub']} simulación(es) de phishing")
        if r["clk"]:
            add(r["username"], r["clk"] * 4, f"Hizo clic en {r['clk']} simulación(es) de phishing")
        if r["rep"]:
            add(r["username"], -r["rep"] * 3, f"Reportó {r['rep']} phishing (buena conducta) 👍")

    return users


@router.get("/users")
async def list_users(request: Request, admin: dict = Depends(get_current_admin)):
    users = await _scores(_db(request))
    out = []
    for u in users.values():
        u["score"] = max(0, u["score"])
        u["level"] = _level(u["score"])
        if u["score"] > 0:
            out.append(u)
    out.sort(key=lambda x: x["score"], reverse=True)
    counts = {"critico": 0, "alto": 0, "medio": 0, "bajo": 0}
    for u in out:
        counts[u["level"]] = counts.get(u["level"], 0) + 1
    return {"users": out, "counts": counts, "window": WINDOW}


@router.get("/users/{email}")
async def user_detail(email: str, request: Request, admin: dict = Depends(get_current_admin)):
    users = await _scores(_db(request))
    u = users.get((email or "").strip().lower())
    if not u:
        return {"user": email, "score": 0, "level": "ninguno", "factors": []}
    u["score"] = max(0, u["score"])
    u["level"] = _level(u["score"])
    return u
