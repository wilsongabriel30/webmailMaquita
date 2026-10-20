"""Aplicar, confirmar y deshacer cambios del cortafuegos; carga al arrancar.

Cada cambio desde el panel se aplica con vuelta atrás automática: si en 60 segundos nadie lo
confirma (porque, por ejemplo, la regla nueva dejó fuera a quien la puso), se restaura la
configuración anterior. Además, el panel no deja aplicar una configuración que cierre el panel a la
IP desde la que se está usando.
"""

import ipaddress
import os
import subprocess
import time

import config
import reglas

PENDIENTE = os.path.join(config.DIR, "pendiente.json")
ANTERIOR = os.path.join(config.DIR, "anterior.json")
UNIDAD = "cortafuegos-vuelta-atras"
SEGUNDOS = 60


def _cmd(args, entrada=None):
    r = subprocess.run(args, input=entrada, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise config.ErrorCortafuegos(f"{args[0]}: " + (detalle[-1][:300] if detalle else f"código {r.returncode}"))
    return r.stdout


def _cargar_reglas(conf):
    """Carga atómica de la cadena propia en IPv4 e IPv6 y asegura el salto desde INPUT (al final)."""
    for v6, restore, tabla in ((False, "iptables-restore", "iptables"), (True, "ip6tables-restore", "ip6tables")):
        _cmd([restore, "--noflush"], entrada=reglas.texto(conf, v6=v6))
        if subprocess.run([tabla, "-C", "INPUT", "-j", reglas.CADENA], capture_output=True).returncode != 0:
            _cmd([tabla, "-A", "INPUT", "-j", reglas.CADENA])


def _permite(conf, ip, servicio):
    """¿Esta IP podría seguir usando este servicio con la configuración nueva?"""
    origen = conf["servicios"].get(servicio)
    if origen == "todos":
        return True
    if origen == "cerrado" or not ip:
        return False
    direccion = ipaddress.ip_address(ip)
    return any(direccion in ipaddress.ip_network(a) for a in conf["admin"])


def aplicar(datos, ip_solicitante):
    conf = config.validar(datos)
    if ip_solicitante:
        try:
            ipaddress.ip_address(ip_solicitante)
        except ValueError:
            raise config.ErrorCortafuegos("IP de quien aplica no válida")
        if not _permite(conf, ip_solicitante, "panel"):
            raise config.ErrorCortafuegos(
                f"esta configuración le cerraría el panel a usted ({ip_solicitante}): añada su IP o su red a «IP de administración»")
    _cancelar_temporizador()
    actual = config.leer() if os.path.exists(config.RUTA) else None
    if not os.path.exists(PENDIENTE):
        if actual is not None:
            config.guardar(actual, ANTERIOR)
        elif os.path.exists(ANTERIOR):
            os.remove(ANTERIOR)  # primera vez: deshacer = quitar el cortafuegos
    _cargar_reglas(conf)
    config.guardar(conf)
    vence = int(time.time()) + SEGUNDOS
    config.guardar({"vence": vence}, PENDIENTE)
    _cmd(["systemd-run", f"--unit={UNIDAD}", f"--on-active={SEGUNDOS}", "--timer-property=AccuracySec=1s",
          "/usr/local/sbin/maquita-cortafuegos", "revertir"])
    return {"aplicado": True, "confirmar_antes": vence, "segundos": SEGUNDOS}


def confirmar():
    _cancelar_temporizador()
    if os.path.exists(PENDIENTE):
        os.remove(PENDIENTE)
    return {"confirmado": True}


def revertir():
    """Lo llama el temporizador (o el panel con «Deshacer»): vuelve a la configuración anterior."""
    _cancelar_temporizador()
    if not os.path.exists(PENDIENTE):
        return {"revertido": False, "motivo": "no había cambios pendientes"}
    if os.path.exists(ANTERIOR):
        anterior = config.leer_ruta(ANTERIOR)
        _cargar_reglas(anterior)
        config.guardar(anterior)
    else:
        quitar()
        os.remove(config.RUTA)
    os.remove(PENDIENTE)
    return {"revertido": True}


def quitar():
    """Desactiva el cortafuegos propio (deja INPUT como estaba antes de instalarlo)."""
    for tabla in ("iptables", "ip6tables"):
        while subprocess.run([tabla, "-D", "INPUT", "-j", reglas.CADENA], capture_output=True).returncode == 0:
            pass
        subprocess.run([tabla, "-F", reglas.CADENA], capture_output=True)
        subprocess.run([tabla, "-X", reglas.CADENA], capture_output=True)


def cargar_al_arrancar():
    if not os.path.exists(config.RUTA):
        return {"cargado": False, "motivo": "sin configuración"}
    if os.path.exists(PENDIENTE):
        # Se reinició con un cambio sin confirmar: se arranca con la configuración anterior.
        if os.path.exists(ANTERIOR):
            config.guardar(config.leer_ruta(ANTERIOR))
        os.remove(PENDIENTE)
    _cargar_reglas(config.leer())
    return {"cargado": True}


def _cancelar_temporizador():
    # Solo el temporizador: el servicio que lanza es justamente «revertir», y pararlo desde dentro
    # lo mataría antes de deshacer el cambio.
    subprocess.run(["systemctl", "stop", f"{UNIDAD}.timer"], capture_output=True)
    subprocess.run(["systemctl", "reset-failed", f"{UNIDAD}.timer"], capture_output=True)
