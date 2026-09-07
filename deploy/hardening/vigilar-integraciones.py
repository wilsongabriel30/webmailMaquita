#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vigilar-integraciones — cada hora comprueba que las integraciones con clave compartida
FUNCIONAN, no solo que el servicio está «activo».

Lección de N-15 (07/09/2026): la clave del webmail hacia la pasarela de IA dejó de coincidir
tras una rotación y Smart Reply devolvió 502 en silencio durante cuatro días. Ningún servicio
estaba caído; ninguna alerta saltó. Una clave que deja de coincidir tiene que notarse en una
hora, no en cuatro días.

Sondas (todas sin efectos secundarios):
  ia            POST a la pasarela con la clave real y un prompt mínimo (401/403 = clave;
                5xx o tiempo agotado = servicio). Además compara la clave del panel (ai_config)
                con la del .env.
  chat          POST /api/chat/sesion/revocar con X-Notif-Secret y cuerpo vacío: 400 «Falta
                user» = clave aceptada; 403 = clave; otro = servicio. Y el sentido inverso:
                GET /api/auth/sesion-servicio del correo con el mismo secreto (400 = ok).
  onlyoffice    POST CommandService.ashx del Document Server con un JWT firmado con el secreto
                del almacén: error 0 = ok; error 6 = clave; otro = servicio.
  secretos      Las copias de SECRET_KEY, ADMIN_JWT_SECRET y CREDENTIAL_ENCRYPTION_KEY que viven
                en varios .env del mismo servidor (backend, almacén, panel, apps del Drive)
                tienen que ser idénticas.

Aviso por correo local (sendmail) al canal de alertas cuando algo pasa a fallar y cuando se
recupera; entre medias, silencio (estado en /var/lib/maquita-admin). `--probar` imprime el
resultado sin enviar nada y sale con 1 si hay fallos.
"""
import hashlib
import json
import os
import socket
import subprocess
import sys
import time

RAIZ = os.getenv("MAQ_APP_DIR", "/opt/maquita-webmail")
ESTADO = os.getenv("MAQ_ESTADO_INTEGRACIONES", "/var/lib/maquita-admin/estado-vigilancia-integraciones.json")
DESTINOS = os.getenv("MAQ_ALERTAS_DESTINOS", "gestiontecnologia@maquita.org gestiontecnologia@maquita.com.ec").split()
REMITENTE = os.getenv("MAQ_ALERTAS_REMITENTE", "postmaster@maquita.org")
TIEMPO = 25


def leer_env(ruta):
    d = {}
    try:
        for l in open(ruta, encoding="utf-8"):
            l = l.strip()
            if not l or l.startswith("#") or "=" not in l:
                continue
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return d


def clasificar(codigo, ok=(200,), desajuste=(401, 403)):
    """Estado de una sonda HTTP: 'ok', 'desajuste' (secreto que no coincide) o 'servicio' (None = sin respuesta)."""
    if codigo is None:
        return "servicio"
    if codigo in ok:
        return "ok"
    if codigo in desajuste:
        return "desajuste"
    return "servicio"


def _post_json(url, payload, headers, tiempo=TIEMPO):
    import requests

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=tiempo)
        return r.status_code, r.text[:300]
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"[:200]


def _get(url, headers, tiempo=TIEMPO):
    import requests

    try:
        r = requests.get(url, headers=headers, timeout=tiempo)
        return r.status_code, r.text[:300]
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"[:200]


# ------------------------------------------------------------------ sondas
def sonda_ia(be):
    """Usa el mismo camino que el backend (`_call_llm` con su venv, su .env y el override del
    panel en `ai_config`): lo que falle aquí falla para las personas."""
    if not (be.get("IA_BASE_URL") or be.get("OLLAMA_URL")):
        return ("ia", "no_configurada", "sin IA_BASE_URL")
    codigo = (
        "import asyncio, logging, sys\n"
        "errores = []\n"
        "class H(logging.Handler):\n"
        "    def emit(self, r): errores.append(r.getMessage()[:160])\n"
        "logging.getLogger('app.ai.router').addHandler(H())\n"
        "from app.ai.router import _call_llm\n"
        "try:\n"
        "    t = asyncio.run(_call_llm('Responde solo: ok', system='Responde con una palabra', temperature=0, max_tokens=4))\n"
        "    print('OK ' + t.strip()[:40].replace(chr(10), ' '))\n"
        "except Exception as e:\n"
        "    print('ERROR ' + ' | '.join(errores)[:300] + ' :: ' + str(e)[:120])\n"
    )
    try:
        r = subprocess.run([f"{RAIZ}/backend/venv/bin/python", "-c", codigo], cwd=f"{RAIZ}/backend",
                           capture_output=True, text=True, timeout=150)
        salida = (r.stdout.strip().splitlines() or [""])[-1]
    except subprocess.TimeoutExpired:
        return ("ia", "servicio", "sin respuesta del modelo en 150 s")
    if salida.startswith("OK "):
        return ("ia", "ok", f"el modelo responde ({salida[3:30]!r})")
    if "401" in salida or "403" in salida or "Unauthorized" in salida:
        return ("ia", "desajuste", "la pasarela rechaza la clave del webmail (401/403): " + salida[6:200])
    return ("ia", "servicio", salida[:200] or (r.stderr.strip()[-200:] if r else "sin salida"))


def sonda_chat(be):
    sec = be.get("NOTIF_SECRET", "")
    chat = (be.get("CHAT_INTERNAL_URL") or "").rstrip("/")
    if not sec or not chat:
        return ("chat", "no_configurada", "sin NOTIF_SECRET o CHAT_INTERNAL_URL")
    # cuerpo vacío: si el secreto vale, el chat contesta 400 «Falta user» sin tocar a nadie
    c1, t1 = _post_json(f"{chat}/api/chat/sesion/revocar", {}, {"X-Notif-Secret": sec})
    e1 = clasificar(c1, ok=(400,), desajuste=(401, 403))
    if e1 != "ok":
        return ("chat", e1, f"correo->chat revocar -> {c1} {t1[:80]}")
    c2, t2 = _get("http://127.0.0.1:8000/api/auth/sesion-servicio", {"X-Notif-Secret": sec})
    e2 = clasificar(c2, ok=(400,), desajuste=(401, 403))
    return ("chat", e2, f"correo->chat 400 ok; chat->correo sesion-servicio -> {c2}" + ("" if e2 == "ok" else f" {t2[:80]}"))


def sonda_onlyoffice(al):
    secreto, url = al.get("ALMACEN_ONLYOFFICE_SECRET", ""), al.get("ALMACEN_ONLYOFFICE_URL_INTERNA", "")
    try:  # config_kv del panel manda sobre el .env, como en api_onlyoffice._cfg
        import psycopg2

        with psycopg2.connect(host=al["ALMACEN_DB_HOST"], dbname=al["ALMACEN_DB_NAME"], user=al["ALMACEN_DB_USER"], password=al["ALMACEN_DB_PASSWORD"], connect_timeout=10) as con, con.cursor() as cur:
            cur.execute("SELECT clave, valor FROM config_kv WHERE clave IN ('onlyoffice_secret','onlyoffice_url_interna','onlyoffice_url_publica')")
            kv = dict(cur.fetchall())
        secreto = kv.get("onlyoffice_secret") or secreto
        url = kv.get("onlyoffice_url_interna") or kv.get("onlyoffice_url_publica") or url
    except Exception:
        pass
    if not secreto or not url:
        return ("onlyoffice", "no_configurada", "sin secreto o URL del Document Server")
    import jwt

    cuerpo = {"c": "version"}
    token = jwt.encode(cuerpo, secreto, algorithm="HS256")
    codigo, texto = _post_json(f"{url.rstrip('/')}/coauthoring/CommandService.ashx", dict(cuerpo, token=token), {"Authorization": f"Bearer {token}"})
    if codigo != 200:
        return ("onlyoffice", "servicio", f"CommandService -> {codigo} {texto[:80]}")
    try:
        err = json.loads(texto).get("error")
    except ValueError:
        return ("onlyoffice", "servicio", f"respuesta no JSON: {texto[:80]}")
    if err == 0:
        return ("onlyoffice", "ok", "JWT aceptado por el Document Server")
    if err == 6:
        return ("onlyoffice", "desajuste", "el Document Server rechaza el JWT (error 6): secreto distinto")
    return ("onlyoffice", "servicio", f"CommandService error {err}")


def sonda_secretos(be, al, pa, extras):
    """Copias del mismo secreto en distintos .env del servidor: deben ser idénticas."""
    fallos = []

    def h(v):
        return hashlib.sha256((v or "").encode()).hexdigest()[:10] if v else "(vacío)"

    grupos = {
        "SECRET_KEY": [("backend", be.get("SECRET_KEY")), ("almacen", al.get("WEBMAIL_SECRET_KEY")), ("panel", pa.get("WEBMAIL_SECRET_KEY"))]
        + [(n, e.get("WEBMAIL_SECRET_KEY")) for n, e in extras],
        "ADMIN_JWT_SECRET": [("backend", be.get("ADMIN_JWT_SECRET")), ("panel", pa.get("ADMIN_JWT_SECRET")), ("panel/WEBMAIL_ADMIN_JWT_SECRET", pa.get("WEBMAIL_ADMIN_JWT_SECRET"))],
        "CREDENTIAL_ENCRYPTION_KEY": [("backend", be.get("CREDENTIAL_ENCRYPTION_KEY")), ("panel", pa.get("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY"))],
    }
    for nombre, copias in grupos.items():
        presentes = [(n, v) for n, v in copias if v]
        if len({v for _, v in presentes}) > 1:
            fallos.append(nombre + ": " + ", ".join(f"{n}={h(v)}" for n, v in presentes))
    if fallos:
        return ("secretos", "desajuste", "; ".join(fallos))
    return ("secretos", "ok", "copias idénticas en backend, almacén y panel")


def sondear():
    be = leer_env(f"{RAIZ}/backend/.env")
    al = leer_env(f"{RAIZ}/almacen/.env")
    pa = leer_env(f"{RAIZ}/admin-panel/backend/.env")
    extras = []
    for app in ("bi", "pdf_editor"):
        r = f"{RAIZ}/almacen/aplicaciones/{app}/.env"
        if os.path.exists(r):
            extras.append((app, leer_env(r)))
    resultados = []
    for f, args in ((sonda_ia, (be,)), (sonda_chat, (be,)), (sonda_onlyoffice, (al,)), (sonda_secretos, (be, al, pa, extras))):
        try:
            resultados.append(f(*args))
        except Exception as e:
            resultados.append((f.__name__.replace("sonda_", ""), "servicio", f"la sonda falló: {type(e).__name__}: {e}"[:160]))
    return resultados


# ------------------------------------------------------------------ aviso
def avisar(asunto, cuerpo):
    for d in DESTINOS:
        msg = f"Subject: {asunto}\nFrom: {REMITENTE}\nTo: {d}\nAuto-Submitted: auto-generated\n\n{cuerpo}\n"
        try:
            subprocess.run(["/usr/sbin/sendmail", "-f", REMITENTE, d], input=msg.encode(), timeout=30, check=False)
        except Exception as e:
            print(f"no se pudo enviar el aviso a {d}: {e}", file=sys.stderr)


def main(argv):
    probar = "--probar" in argv
    servidor = socket.getfqdn()
    resultados = sondear()
    fallando = {n: (e, d) for n, e, d in resultados if e in ("desajuste", "servicio")}
    for n, e, d in resultados:
        print(f"[{e.upper():14}] {n}: {d}")
    if probar:
        return 1 if fallando else 0
    try:
        previo = json.load(open(ESTADO))
    except Exception:
        previo = {}
    nuevos = {n: v for n, v in fallando.items() if n not in previo}
    recuperados = [n for n in previo if n not in fallando]
    if nuevos:
        lineas = "\n".join(f"  - {n} [{e}]: {d}" for n, (e, d) in nuevos.items())
        avisar(f"[{servidor}] ALERTA: integración con clave compartida fallando ({', '.join(nuevos)})",
               "«Activo» no es «sano»: el servicio responde, pero la integración no funciona.\n"
               "desajuste = el secreto compartido ya no coincide (rotación a medias); servicio = no responde o error.\n\n"
               f"{lineas}\n\nSondas: deploy/hardening/vigilar-integraciones.py (cada hora). Lección de N-15.")
    if recuperados:
        avisar(f"[{servidor}] Recuperado: integraciones ({', '.join(recuperados)})",
               "Vuelven a funcionar: " + ", ".join(recuperados) + f"\nFecha: {time.strftime('%Y-%m-%d %H:%M')}")
    try:
        os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
        json.dump({n: e for n, (e, _) in fallando.items()}, open(ESTADO, "w"))
    except Exception as e:
        print(f"no se pudo guardar el estado: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
