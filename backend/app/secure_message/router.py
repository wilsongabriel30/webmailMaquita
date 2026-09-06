"""Router de mensajes seguros (OME).

- Autenticado (usuario webmail): crear/enviar, listar enviados, revocar, estado.
- Público (destinatario externo): portal HTML, pedir código, verificar y leer.
"""
import base64
import html as html_lib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

from . import service

# ── Router autenticado ──────────────────────────────────────────────────────
auth_router = APIRouter(prefix="/api/mail/secure", tags=["secure-message"])


class SecureAttachment(BaseModel):
    filename: str
    content_b64: str
    content_type: str = "application/octet-stream"


class SecureSendRequest(BaseModel):
    to: list[str]
    subject: str = ""
    html_body: str = ""
    attachments: list[SecureAttachment] | None = None


@auth_router.get("/config")
async def secure_config(request: Request, username: str = Depends(get_current_user)):
    cfg = await service.get_config(request.app.state.db_pool)
    return {"enabled": bool(cfg["enabled"]), "expire_days": cfg["expire_days"]}


@auth_router.post("/send")
async def secure_send(body: SecureSendRequest, request: Request,
                      username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    cfg = await service.get_config(db)
    if not cfg["enabled"]:
        raise HTTPException(status_code=403, detail="El correo cifrado está desactivado")
    recipients = [r.strip() for r in (body.to or []) if r.strip()]
    if not recipients:
        raise HTTPException(status_code=400, detail="Indica al menos un destinatario")

    display_name = ""
    row = await db.fetchrow("SELECT display_name FROM user_preferences WHERE username = $1", username)
    if row and row["display_name"]:
        display_name = row["display_name"]

    files = []
    for a in (body.attachments or []):
        try:
            files.append({"filename": a.filename,
                          "content_type": a.content_type or "application/octet-stream",
                          "content": base64.b64decode(a.content_b64)})
        except Exception:
            continue

    res = await service.create_and_notify(db, username, display_name, body.subject,
                                          recipients, body.html_body, files)
    return {"ok": True, **res}


@auth_router.get("/sent")
async def secure_sent(request: Request, username: str = Depends(get_current_user), limit: int = 50):
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT token, subject, recipients, created_at, expires_at, revoked, view_count "
        "FROM secure_messages WHERE sender = $1 ORDER BY created_at DESC LIMIT $2",
        username, max(1, min(limit, 200)))
    out = []
    for r in rows:
        rec = r["recipients"]
        if isinstance(rec, str):
            try: rec = json.loads(rec)
            except ValueError: rec = []
        out.append({"token": r["token"], "subject": r["subject"], "recipients": rec,
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                    "revoked": r["revoked"], "view_count": r["view_count"]})
    return {"messages": out}


@auth_router.post("/{token}/revoke")
async def secure_revoke(token: str, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    res = await db.execute("UPDATE secure_messages SET revoked = true WHERE token = $1 AND sender = $2",
                           token, username)
    if res.endswith("0"):
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return {"ok": True}


# ── Router público (sin login) ──────────────────────────────────────────────
public_router = APIRouter(tags=["secure-message-public"])


class OtpRequest(BaseModel):
    email: str


class VerifyRequest(BaseModel):
    email: str
    code: str


def _ip(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "")


@public_router.post("/api/secure/{token}/request-otp")
async def request_otp(token: str, body: OtpRequest, request: Request):
    return await service.send_otp(request.app.state.db_pool, token, body.email, _ip(request))


@public_router.post("/api/secure/{token}/verify")
async def verify(token: str, body: VerifyRequest, request: Request):
    return await service.verify_and_read(request.app.state.db_pool, token, body.email, body.code, _ip(request))


@public_router.get("/secure/{token}", response_class=HTMLResponse)
async def portal(token: str, request: Request):
    m = await service.meta(request.app.state.db_pool, token)
    return HTMLResponse(_portal_html(token, m))


def _portal_html(token: str, m: dict) -> str:
    status = m.get("status")
    subject = html_lib.escape(m.get("subject") or "")
    sender = html_lib.escape(m.get("sender_name") or "")
    msg_map = {
        "not_found": "Este enlace no es válido.",
        "revoked": "Este mensaje fue revocado por el remitente.",
        "expired": "Este mensaje ha caducado.",
        "exhausted": "Este mensaje alcanzó su límite de aperturas.",
    }
    if status and status != "ok":
        inner = f'<div class="card"><div class="ico">🔒</div><h2>No disponible</h2><p>{msg_map.get(status, "No disponible")}</p></div>'
        return _page(inner)

    inner = f"""
    <div class="card" id="app" data-token="{html_lib.escape(token)}">
      <div class="ico">🔒</div>
      <h2>Mensaje seguro</h2>
      <p class="muted">De <b>{sender}</b></p>
      <p class="subj"><b>Asunto:</b> {subject or "(sin asunto)"}</p>

      <div id="step-email">
        <p>Para abrir el mensaje, confirma tu correo. Te enviaremos un código.</p>
        <input id="email" type="email" placeholder="tu-correo@ejemplo.com" autocomplete="email" />
        <button id="btn-otp">Enviarme el código</button>
      </div>

      <div id="step-code" style="display:none">
        <p>Te enviamos un código a <b id="email-echo"></b>. Escríbelo aquí:</p>
        <input id="code" inputmode="numeric" maxlength="6" placeholder="123456" />
        <button id="btn-verify">Ver mensaje</button>
        <p class="muted small"><a href="#" id="resend">Reenviar código</a></p>
      </div>

      <div id="msg" class="error"></div>

      <div id="content" style="display:none">
        <hr/>
        <div id="body"></div>
        <div id="files"></div>
      </div>
    </div>"""
    return _page(inner)


def _page(inner: str) -> str:
    return f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mensaje seguro — Maquita</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;padding:24px;color:#323130}}
 .wrap{{max-width:560px;margin:0 auto}}
 .card{{background:#fff;border:1px solid #e1dfdd;border-radius:10px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
 .ico{{font-size:40px;text-align:center}}
 h2{{text-align:center;margin:6px 0 16px}}
 .muted{{color:#888}} .small{{font-size:13px}}
 .subj{{background:#f7f7f8;border-radius:6px;padding:10px 12px;margin:14px 0}}
 input{{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #c8c6c4;border-radius:6px;font-size:15px;margin:8px 0}}
 button{{width:100%;background:#0078d4;color:#fff;border:0;border-radius:6px;padding:12px;font-size:15px;font-weight:600;cursor:pointer}}
 button:hover{{background:#106ebe}} button:disabled{{opacity:.6;cursor:default}}
 .error{{color:#d13438;font-size:14px;margin-top:10px;min-height:18px;text-align:center}}
 #body{{line-height:1.5;overflow-wrap:break-word}} #body img{{max-width:100%;height:auto;border-radius:4px}} #body table{{max-width:100%;border-collapse:collapse}} hr{{border:none;border-top:1px solid #edebe9;margin:18px 0}}
 .file{{display:block;background:#f3f2f1;border:1px solid #e1dfdd;border-radius:6px;padding:10px 12px;margin:8px 0;text-decoration:none;color:#0078d4}}
 .foot{{text-align:center;color:#aaa;font-size:12px;margin-top:16px}}
</style></head><body><div class="wrap">{inner}
<div class="foot">Protegido por Maquita · El contenido viaja cifrado</div>
</div>
<script>
(function(){{
 var app=document.getElementById('app'); if(!app) return;
 var token=app.getAttribute('data-token');
 var $=function(id){{return document.getElementById(id)}};
 function show(id,v){{$(id).style.display=v?'':'none'}}
 function err(t){{$('msg').textContent=t||''}}
 var EMAP={{not_recipient:'Ese correo no está autorizado para este mensaje.',code_expired:'El código venció. Pide uno nuevo.',bad_code:'Código incorrecto.',too_many:'Demasiados intentos. Pide un código nuevo.',revoked:'El mensaje fue revocado.',expired:'El mensaje caducó.',exhausted:'Se alcanzó el límite de aperturas.'}};
 async function post(url,data){{var r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});return r.json()}}
 $('btn-otp').onclick=async function(){{
   err(''); var email=$('email').value.trim(); if(!email){{err('Escribe tu correo');return}}
   $('btn-otp').disabled=true; $('btn-otp').textContent='Enviando...';
   var res=await post('/api/secure/'+token+'/request-otp',{{email:email}});
   $('btn-otp').disabled=false; $('btn-otp').textContent='Enviarme el código';
   if(res.ok){{ $('email-echo').textContent=email; show('step-email',false); show('step-code',true); }}
   else err(EMAP[res.status]||'No se pudo enviar el código');
 }};
 $('resend').onclick=function(e){{e.preventDefault(); show('step-code',false); show('step-email',true); err('');}};
 $('btn-verify').onclick=async function(){{
   err(''); var email=$('email').value.trim(), code=$('code').value.trim();
   if(!code){{err('Escribe el código');return}}
   $('btn-verify').disabled=true;
   var res=await post('/api/secure/'+token+'/verify',{{email:email,code:code}});
   $('btn-verify').disabled=false;
   if(!res.ok){{err(EMAP[res.status]||'No se pudo abrir');return}}
   show('step-code',false); $('msg').textContent='';
   $('body').innerHTML=res.html||''; show('content',true);
   var fc=$('files'); fc.innerHTML='';
   (res.files||[]).forEach(function(f){{
     var a=document.createElement('a'); a.className='file'; a.textContent='📎 '+f.filename;
     a.href='data:'+(f.content_type||'application/octet-stream')+';base64,'+f.content_b64;
     a.download=f.filename; fc.appendChild(a);
   }});
 }};
}})();
</script></body></html>"""
