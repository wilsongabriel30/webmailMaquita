"""Disponibilidad de cada sitio: cada 5 minutos (temporizador sitios-disponibilidad) se pide la portada por
HTTPS (por HTTP si el sitio aún no tiene certificado) y se anota el código, el tiempo de respuesta y los días que
le quedan al certificado.

La petición va a este mismo servidor (DESTINO, 127.0.0.1) con el nombre del sitio (SNI y Host): comprueba
nginx, PHP y la aplicación sin depender del DNS ni del NAT, que darían falsas alarmas. El certificado se
verifica de verdad (nombre y caducidad): uno caducado o que no corresponde cuenta como fallo.

Tras FALLOS_PARA_AVISAR fallos seguidos se avisa por correo al dueño, y otra vez cuando vuelve. El destino es
el correo del administrador de la aplicación (meta «app_correo») o, si no hay, ORG_CORREOS_AVISOS de
/etc/maquita-mail/organizacion.env; el remitente y el envío salen de lib-avisos.sh de los vigilantes si está
instalado. Como mucho TOPE_AVISOS_DIA avisos por sitio y día (un sitio que sube y baja no inunda el buzón).

Estado e historial corto (HISTORIAL comprobaciones, 24 h) en DATOS/<dominio>.json.
"""

import concurrent.futures
import fcntl
import http.client
import json
import os
import socket
import ssl
import subprocess
import time

from comun import leer_meta, todos_los_meta

DATOS = "/var/lib/maquita-sitios/disponibilidad"
DESTINO = "127.0.0.1"
TIEMPO = 15
HISTORIAL = 288
FALLOS_PARA_AVISAR = 2
TOPE_AVISOS_DIA = 6
ORGANIZACION = "/etc/maquita-mail/organizacion.env"
LIB_AVISOS = "/usr/local/lib/maquita-vigilantes/lib-avisos.sh"
SENDMAIL = "/usr/sbin/sendmail"


def _ruta(dominio):
    return os.path.join(DATOS, f"{dominio}.json")


def _leer(dominio):
    try:
        with open(_ruta(dominio)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"historial": [], "fallos_seguidos": 0, "caido": False, "avisos": []}


def _guardar(dominio, estado):
    os.makedirs(DATOS, mode=0o700, exist_ok=True)
    tmp = _ruta(dominio) + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(estado, f, ensure_ascii=False)
    os.replace(tmp, _ruta(dominio))


def comprobar_url(dominio, https=True, destino=None, tiempo=TIEMPO):
    """Una petición a la portada. Devuelve {ok, codigo, ms, dias_certificado, motivo}."""
    destino = destino or DESTINO
    inicio = time.monotonic()
    resultado = {"ok": False, "codigo": None, "ms": None, "dias_certificado": None, "motivo": None}
    try:
        if https:
            contexto = ssl.create_default_context()
            crudo = socket.create_connection((destino, 443), timeout=tiempo)
            conexion = contexto.wrap_socket(crudo, server_hostname=dominio)
            caduca = ssl.cert_time_to_seconds(conexion.getpeercert()["notAfter"])
            resultado["dias_certificado"] = int((caduca - time.time()) // 86400)
            http_ = http.client.HTTPSConnection(dominio, 443, timeout=tiempo, context=contexto)
            http_.sock = conexion
        else:
            http_ = http.client.HTTPConnection(destino, 80, timeout=tiempo)
        http_.request("GET", "/", headers={"Host": dominio, "User-Agent": "maquita-sitios-disponibilidad/1.0",
                                           "Connection": "close"})
        respuesta = http_.getresponse()
        respuesta.read(65536)
        http_.close()
        resultado["codigo"] = respuesta.status
        # Una redirección, un 401/403 (carpeta privada) o un 404 en la portada siguen siendo un servidor que responde.
        resultado["ok"] = respuesta.status < 500
        if not resultado["ok"]:
            resultado["motivo"] = f"el servidor responde con error {respuesta.status}"
    except ssl.SSLCertVerificationError as e:
        resultado["motivo"] = "certificado no válido: " + (e.verify_message or "no se pudo verificar")
    except (OSError, http.client.HTTPException, ssl.SSLError) as e:
        resultado["motivo"] = "sin respuesta: " + (str(e) or type(e).__name__)[:150]
    resultado["ms"] = int((time.monotonic() - inicio) * 1000)
    return resultado


def _destinatarios(meta):
    if meta.get("app_correo"):
        return [meta["app_correo"]]
    try:
        with open(ORGANIZACION) as f:
            for linea in f:
                clave, _, valor = linea.strip().partition("=")
                if clave == "ORG_CORREOS_AVISOS":
                    lista = valor.strip().strip("'\"").replace(",", " ").split()
                    if lista:
                        return lista
    except OSError:
        pass
    return []  # lib-avisos.sh decide (panel o postmaster@dominio)


def enviar(asunto, cuerpo, destinos):
    """Por lib-avisos.sh de los vigilantes (mismo remitente y formato); si no está, sendmail directo."""
    if os.path.isfile(LIB_AVISOS):
        guion = ('. "$1"; d="$3"; [ -n "$d" ] || d=$(vig_destinos); vig_enviar "$2" "$d"')
        orden = ["bash", "-c", guion, "_", LIB_AVISOS, asunto, " ".join(destinos)]
    elif destinos:
        cuerpo = (f"To: {', '.join(destinos)}\nSubject: {asunto}\nContent-Type: text/plain; charset=UTF-8\n"
                  f"Auto-Submitted: auto-generated\n\n{cuerpo}")
        orden = [SENDMAIL, "-t"]
    else:
        return False
    r = subprocess.run(orden, input=cuerpo, text=True, capture_output=True, timeout=60)
    return r.returncode == 0


def _avisar(meta, estado, asunto, cuerpo, ahora, enviar_fn):
    hoy = time.strftime("%Y-%m-%d", time.localtime(ahora))
    estado["avisos"] = [a for a in estado.get("avisos", []) if a.get("dia") == hoy]
    if len(estado["avisos"]) >= TOPE_AVISOS_DIA:
        estado["silenciados"] = estado.get("silenciados", 0) + 1
        return False
    if len(estado["avisos"]) == TOPE_AVISOS_DIA - 1:
        cuerpo += f"\n\nEste es el último aviso de hoy para {meta['dominio']} (tope de {TOPE_AVISOS_DIA} al día)."
    enviado = enviar_fn(asunto, cuerpo, _destinatarios(meta))
    estado["avisos"].append({"dia": hoy, "hora": time.strftime("%H:%M", time.localtime(ahora)), "asunto": asunto,
                             "enviado": bool(enviado)})
    return True


def registrar(meta, resultado, ahora=None, enviar_fn=None):
    """Anota una comprobación y avisa si toca. Devuelve el estado guardado."""
    ahora = ahora or time.time()
    enviar_fn = enviar_fn or enviar
    dominio = meta["dominio"]
    estado = _leer(dominio)
    entrada = {"hora": time.strftime("%Y-%m-%d %H:%M", time.localtime(ahora)), **resultado}
    estado["historial"] = (estado.get("historial", []) + [entrada])[-HISTORIAL:]
    if resultado["ok"]:
        if estado.get("caido"):
            caido_desde = estado.get("caido_desde") or "?"
            _avisar(meta, estado, f"El sitio {dominio} vuelve a responder",
                    f"El sitio {dominio} vuelve a responder (código {resultado['codigo']}, {resultado['ms']} ms).\n"
                    f"Estuvo sin servicio desde {caido_desde}.", ahora, enviar_fn)
        estado.update(fallos_seguidos=0, caido=False, caido_desde=None)
    else:
        estado["fallos_seguidos"] = estado.get("fallos_seguidos", 0) + 1
        if not estado.get("caido") and estado["fallos_seguidos"] >= FALLOS_PARA_AVISAR:
            estado.update(caido=True, caido_desde=entrada["hora"])
            _avisar(meta, estado, f"El sitio {dominio} no responde",
                    f"El sitio {dominio} no responde desde {entrada['hora']} ({estado['fallos_seguidos']} "
                    f"comprobaciones seguidas, cada 5 minutos).\nMotivo: {resultado['motivo']}\n\n"
                    "Se avisará otra vez cuando vuelva a responder.", ahora, enviar_fn)
    estado["ultima"] = entrada
    _guardar(dominio, estado)
    return estado


def comprobar_todos(comprobar_fn=None, enviar_fn=None, cerrojo=True):
    comprobar_fn = comprobar_fn or comprobar_url
    metas = todos_los_meta()
    os.makedirs(DATOS, mode=0o700, exist_ok=True)
    with open(os.path.join(DATOS, ".cerrojo"), "w") as candado:
        if cerrojo:
            try:
                fcntl.flock(candado, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return {"omitido": "otra comprobación sigue en curso"}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as hilos:
            resultados = list(hilos.map(lambda m: comprobar_fn(m["dominio"], https=bool(m.get("ssl"))), metas))
        caidos = []
        for meta, resultado in zip(metas, resultados):
            if registrar(meta, resultado, enviar_fn=enviar_fn).get("caido"):
                caidos.append(meta["dominio"])
    return {"comprobados": len(metas), "caidos": caidos}


def ver(dominio):
    meta = leer_meta(dominio)
    estado = _leer(dominio)
    historial = estado.get("historial", [])
    correctas = sum(1 for h in historial if h.get("ok"))
    return {"dominio": dominio, "https": bool(meta.get("ssl")), "caido": bool(estado.get("caido")),
            "caido_desde": estado.get("caido_desde"), "ultima": estado.get("ultima"),
            "porcentaje": round(100 * correctas / len(historial), 2) if historial else None,
            "historial": historial[-HISTORIAL:], "avisos": estado.get("avisos", []),
            "destinatarios": _destinatarios(meta) or ["(los avisos generales del servidor)"]}


def quitar(dominio):
    for ruta in (_ruta(dominio), _ruta(dominio) + ".tmp"):
        if os.path.lexists(ruta):
            os.remove(ruta)


def huerfanos(dominios):
    """Estados de sitios que ya no existen (los deja una baja anterior a esta versión)."""
    quitados = []
    if os.path.isdir(DATOS):
        for n in os.listdir(DATOS):
            if n.endswith(".json") and n[:-5] not in dominios:
                os.remove(os.path.join(DATOS, n))
                quitados.append(n[:-5])
    return quitados

