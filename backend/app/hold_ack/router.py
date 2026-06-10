"""Aviso de retención legal — página pública de acuse de recibo (custodio).

El custodio recibe un correo con un enlace; abre esta página, lee el aviso y
confirma el acuse. Queda registrado quién y cuándo lo reconoció.
"""
import html as html_lib
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["hold-ack"])


def _db(r: Request):
    return r.app.state.db_pool


async def _load(db, token: str):
    return await db.fetchrow(
        """SELECT c.id, c.email, c.acknowledged_at, c.role,
                  cc.title, cc.reason
           FROM case_custodians c JOIN compliance_cases cc ON cc.id = c.case_id
           WHERE c.ack_token = $1""", token)


@router.post("/api/hold-ack/{token}")
async def ack(token: str, request: Request):
    db = _db(request)
    row = await _load(db, token)
    if not row:
        return {"ok": False, "status": "not_found"}
    if not row["acknowledged_at"]:
        await db.execute("UPDATE case_custodians SET acknowledged_at = now() WHERE ack_token = $1", token)
    return {"ok": True}


@router.get("/api/hold-ack/{token}", response_class=HTMLResponse)
async def page(token: str, request: Request):
    row = await _load(_db(request), token)
    if not row:
        return HTMLResponse(_wrap('<div class="card"><div class="ico">⚖️</div><h2>Aviso no válido</h2><p>Este enlace no es válido o expiró.</p></div>'))
    already = row["acknowledged_at"] is not None
    title = html_lib.escape(row["title"] or "")
    reason = html_lib.escape(row["reason"] or "")
    email = html_lib.escape(row["email"] or "")
    ack_block = (
        f'<div class="ok">✅ Acuse registrado. Gracias.</div>'
        if already else
        '<button id="ackbtn">Confirmo que recibí y entendí este aviso</button><div id="m" class="ok" style="display:none">✅ Acuse registrado. Gracias.</div>'
    )
    inner = f"""
    <div class="card" data-token="{html_lib.escape(token)}">
      <div class="ico">⚖️</div>
      <h2>Aviso de retención legal</h2>
      <p>Estimado/a <b>{email}</b>,</p>
      <p>Has sido designado/a <b>custodio</b> en el marco de un proceso de la Fundación Maquita.
      A partir de este aviso, <b>debes conservar toda la información de tu correo</b> relacionada
      con el asunto y <b>no eliminar</b> mensajes, hasta nuevo aviso.</p>
      <div class="box"><b>Caso:</b> {title or '(sin título)'}<br><b>Motivo:</b> {reason or '(no especificado)'}</div>
      <p style="color:#666;font-size:13px">Tu buzón ya está bajo retención automática: aunque intentes borrar, el sistema preserva los correos.</p>
      {ack_block}
    </div>"""
    return HTMLResponse(_wrap(inner))


def _wrap(inner: str) -> str:
    return f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aviso de retención legal — Maquita</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;padding:24px;color:#323130}}
 .card{{max-width:560px;margin:30px auto;background:#fff;border:1px solid #e1dfdd;border-top:5px solid #5b5fc7;border-radius:10px;padding:30px;box-shadow:0 2px 10px rgba(0,0,0,.07)}}
 .ico{{font-size:46px;text-align:center}} h2{{text-align:center;margin:6px 0 16px}}
 .box{{background:#f3f2fb;border-radius:6px;padding:12px 14px;margin:14px 0;font-size:15px}}
 button{{width:100%;background:#5b5fc7;color:#fff;border:0;border-radius:6px;padding:13px;font-size:15px;font-weight:600;cursor:pointer;margin-top:10px}}
 button:hover{{background:#4b4fb0}} button:disabled{{opacity:.6}}
 .ok{{background:#f1faf1;border:1px solid #c3e6c3;color:#0b6a0b;border-radius:6px;padding:12px;text-align:center;margin-top:12px}}
 .foot{{text-align:center;color:#aaa;font-size:12px;margin-top:16px}}
</style></head><body>{inner}
<div class="foot">Fundación Maquita · Cumplimiento legal</div>
<script>
 var b=document.getElementById('ackbtn');
 if(b){{b.onclick=async function(){{
   var t=document.querySelector('.card').getAttribute('data-token');
   b.disabled=true;
   try{{await fetch('/api/hold-ack/'+t,{{method:'POST'}}); b.style.display='none'; document.getElementById('m').style.display='block';}}
   catch(e){{b.disabled=false;}}
 }};}}
</script></body></html>"""
