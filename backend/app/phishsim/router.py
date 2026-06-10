"""Simulación de phishing — endpoints PÚBLICOS (sin login).

- GET  /api/phishtest/{token}            -> registra clic, muestra login falso
- POST /api/phishtest/{token}/submit     -> registra "entregó credenciales", muestra entrenamiento
- GET  /api/phishtest/{token}/pixel.gif  -> registra apertura (pixel)
NUNCA se guarda la contraseña escrita; solo se registra el evento.
"""
import base64
import html as html_lib

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from . import service

router = APIRouter(tags=["phishsim"])

_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


def _db(r: Request):
    return r.app.state.db_pool


@router.get("/api/phishtest/{token}/pixel.gif")
async def pixel(token: str, request: Request):
    await service.mark(_db(request), token, "opened")
    return Response(content=_PIXEL, media_type="image/gif")


@router.get("/api/phishtest/{token}", response_class=HTMLResponse)
async def landing(token: str, request: Request):
    db = _db(request)
    t = await service.get_target(db, token)
    if not t:
        return HTMLResponse(_training_html())
    await service.mark(db, token, "opened")
    await service.mark(db, token, "clicked")
    return HTMLResponse(_login_html(token, t["email"]))


@router.post("/api/phishtest/{token}/submit", response_class=HTMLResponse)
async def submit(token: str, request: Request):
    # No leemos ni guardamos lo que escribió; solo registramos el evento.
    await service.mark(_db(request), token, "submitted")
    return HTMLResponse(_training_html())


def _login_html(token: str, email: str) -> str:
    safe_email = html_lib.escape(email or "")
    return f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Iniciar sesión — Maquita</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center}}
 .box{{background:#fff;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.1);padding:34px;width:340px}}
 .logo{{text-align:center;font-size:20px;font-weight:700;color:#0078d4;margin-bottom:4px}}
 .sub{{text-align:center;color:#888;font-size:13px;margin-bottom:20px}}
 label{{font-size:13px;color:#444}}
 input{{width:100%;box-sizing:border-box;padding:11px;margin:6px 0 14px;border:1px solid #c8c6c4;border-radius:5px;font-size:15px}}
 button{{width:100%;background:#0078d4;color:#fff;border:0;padding:12px;border-radius:5px;font-size:15px;font-weight:600;cursor:pointer}}
</style></head><body>
<form class="box" method="post" action="/api/phishtest/{html_lib.escape(token)}/submit">
  <div class="logo">Maquita Mail</div>
  <div class="sub">Inicia sesión para continuar</div>
  <label>Correo</label>
  <input type="email" name="email" value="{safe_email}" />
  <label>Contraseña</label>
  <input type="password" name="password" autocomplete="off" />
  <button type="submit">Iniciar sesión</button>
</form>
</body></html>"""


def _training_html() -> str:
    return """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simulación de phishing — Maquita</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;background:#f3f2f1;margin:0;padding:24px;color:#323130}
 .card{max-width:600px;margin:30px auto;background:#fff;border-radius:12px;border-top:6px solid #ca5010;padding:34px;box-shadow:0 3px 14px rgba(0,0,0,.08)}
 .ico{font-size:52px;text-align:center}
 h1{text-align:center;color:#ca5010;font-size:24px;margin:8px 0 4px}
 .lead{text-align:center;color:#605e5c;margin-bottom:22px}
 .tip{background:#fff8f3;border:1px solid #f3d9c5;border-radius:8px;padding:14px 16px;margin:10px 0}
 .tip b{color:#ca5010}
 ul{margin:6px 0 0;padding-left:20px;line-height:1.6}
 .ok{background:#f1faf1;border:1px solid #c3e6c3;border-radius:8px;padding:14px 16px;margin-top:16px;color:#0b6a0b}
 .foot{text-align:center;color:#aaa;font-size:12px;margin-top:18px}
</style></head><body>
<div class="card">
  <div class="ico">🎣</div>
  <h1>¡Esto era una simulación de phishing!</h1>
  <p class="lead">Tranquilo: fue una prueba interna de <b>Tecnología de Maquita</b> para entrenarnos.
  No pasó nada malo y <b>no guardamos ninguna contraseña</b>. Pero en un ataque real, aquí habrían robado tus datos.</p>

  <div class="tip"><b>¿Cómo reconocerlo la próxima vez?</b>
    <ul>
      <li><b>Urgencia y miedo:</b> "tu cuenta se bloquea hoy", "buzón lleno". Buscan que actúes sin pensar.</li>
      <li><b>Revisa el enlace:</b> pasa el mouse por encima y mira a dónde apunta de verdad antes de hacer clic.</li>
      <li><b>Nunca escribas tu contraseña</b> en una página a la que llegaste desde un correo. Entra tú mismo a mail.example.org.</li>
      <li><b>Remitente sospechoso:</b> dominios raros o parecidos al oficial pero no iguales.</li>
    </ul>
  </div>

  <div class="ok"><b>✅ Si dudas, repórtalo:</b> usa el botón "Reportar phishing/spam" del correo o avisa a Tecnología.
  Reportar es la mejor acción — ¡así nos proteges a todos!</div>
  <div class="foot">Programa de concientización · Fundación Maquita</div>
</div>
</body></html>"""
