"""Safe Links — pasarela de clic. Verifica la firma, evalúa el destino y:
- seguro  -> redirige
- sospechoso -> página de aviso con opción de continuar
- bloqueado -> página de bloqueo (sin continuar)
Enlace sin firma válida -> siempre aviso (evita redirector abierto).
"""
import html as html_lib

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from . import service, rewriter

router = APIRouter(tags=["safelinks"])


def _ip(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "")


@router.get("/api/safelink")
async def safelink(request: Request, u: str = "", s: str = "", go: int = 0):
    db = request.app.state.db_pool
    ip = _ip(request)
    try:
        # unescape defensivo: los enlaces firmados antes de 2026-08-05 llevan
        # las entidades HTML sin deshacer (&amp;) y se abrian sin sus parametros.
        url = html_lib.unescape(rewriter.decode_url(u))
    except Exception:
        return HTMLResponse(_warn_page("", "Enlace inválido", "blocked", None), status_code=400)

    trusted = rewriter.verify(u, s)
    if not trusted:
        await service.log_click(db, "", url, "", "untrusted", False, ip)
        return HTMLResponse(_warn_page(url, "No pudimos verificar este enlace. Procede con cuidado.", "suspicious", u + ":" + s))

    res = await service.check_url(db, url, request.app.state.redis)
    verdict = res["verdict"]

    if verdict == "safe":
        return RedirectResponse(url, status_code=302)

    if go == 1 and verdict != "blocked":
        await service.log_click(db, "", url, res["host"], verdict, True, ip)
        return RedirectResponse(url, status_code=302)

    await service.log_click(db, "", url, res["host"], verdict, False, ip)
    token = (u + ":" + s) if verdict != "blocked" else None
    return HTMLResponse(_warn_page(url, res["reason"], verdict, token))


def _warn_page(url: str, reason: str, verdict: str, proceed_token: str | None) -> str:
    safe_url = html_lib.escape(url)
    short = html_lib.escape(url[:80] + ("…" if len(url) > 80 else ""))
    reason_h = html_lib.escape(reason or "")
    blocked = verdict == "blocked"
    color = "#d13438" if blocked else "#ca5010"
    title = "Enlace bloqueado" if blocked else "Atención: enlace sospechoso"
    icon = "🚫" if blocked else "⚠️"
    proceed = ""
    if proceed_token and not blocked:
        u, s = proceed_token.split(":", 1)
        proceed = f"""<a class="go" href="/api/safelink?u={html_lib.escape(u)}&s={html_lib.escape(s)}&go=1">Entiendo el riesgo, continuar de todos modos</a>"""
    return f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verificación de enlace — Maquita</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;padding:24px;color:#323130}}
 .card{{max-width:540px;margin:40px auto;background:#fff;border:1px solid #e1dfdd;border-top:5px solid {color};border-radius:10px;padding:30px;box-shadow:0 2px 10px rgba(0,0,0,.07)}}
 .ico{{font-size:46px;text-align:center}}
 h1{{text-align:center;font-size:21px;margin:8px 0 6px;color:{color}}}
 .reason{{background:#faf3f2;border-radius:6px;padding:12px 14px;margin:16px 0;font-size:15px}}
 .url{{background:#f7f7f8;border-radius:6px;padding:10px 12px;font-family:Consolas,monospace;font-size:13px;word-break:break-all;color:#605e5c}}
 .actions{{margin-top:22px;text-align:center}}
 .back{{display:inline-block;background:#0078d4;color:#fff;text-decoration:none;padding:11px 26px;border-radius:6px;font-weight:600}}
 .go{{display:block;margin-top:14px;color:#888;font-size:13px;text-decoration:underline}}
 .foot{{text-align:center;color:#aaa;font-size:12px;margin-top:18px}}
</style></head><body>
<div class="card">
  <div class="ico">{icon}</div>
  <h1>{title}</h1>
  <p style="text-align:center;color:#605e5c">Maquita revisó este enlace antes de abrirlo.</p>
  <div class="reason"><b>Motivo:</b> {reason_h or 'Posible riesgo'}</div>
  <p style="font-size:13px;color:#888;margin-bottom:4px">El enlace apunta a:</p>
  <div class="url">{short}</div>
  <div class="actions">
    <a class="back" href="javascript:history.back()">Volver, no abrir</a>
    {proceed}
  </div>
</div>
<div class="foot">Protección de enlaces de Maquita · No ingreses contraseñas si no estás seguro</div>
</body></html>"""


# =====================================================
# Clasificación de phishing on-demand (autenticada)
# =====================================================
from fastapi import Depends, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from app.auth.dependencies import get_current_user  # noqa: E402
from . import classifier  # noqa: E402


class ClassifyRequest(BaseModel):
    message_id: str | None = None
    folder: str = "INBOX"
    sender: str = ""
    subject: str = ""
    body: str = ""


@router.post("/api/safelinks/classify")
async def classify_phishing(payload: ClassifyRequest, request: Request,
                            user: str = Depends(get_current_user)):
    """Clasifica un correo como phishing/suspicious/clean (heuristica + capa externa).
    Acepta {message_id, folder} (lo trae por IMAP) o {sender, subject, body} directos."""
    sender, subject, body = payload.sender, payload.subject, payload.body
    if payload.message_id:
        from app.ai.router import _fetch_message
        try:
            msg = await _fetch_message(request, user, payload.folder, int(payload.message_id))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail="No se pudo obtener el mensaje")
        sender = msg.get("from", "") or sender
        subject = msg.get("subject", "") or subject
        body = (msg.get("html_body") or msg.get("text_body")
                or msg.get("snippet") or body)
    if not (sender or subject or body):
        raise HTTPException(status_code=400, detail="Falta message_id o sender/subject/body")
    return await run_in_threadpool(classifier.score_message,
                                   sender=sender, subject=subject, body=body)
