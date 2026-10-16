"""Lo que muestra la pantalla: configuración, cambio pendiente, IP bloqueadas por fail2ban y puertos
en escucha (para ver de un vistazo qué escucha el servidor y si el cortafuegos lo deja pasar)."""

import json
import os
import re
import subprocess

import config
import reglas
from aplicar import PENDIENTE


def _fail2ban():
    r = subprocess.run(["fail2ban-client", "status"], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        return []
    m = re.search(r"Jail list:\s*(.*)", r.stdout)
    jaulas = [j.strip() for j in (m.group(1).split(",") if m else []) if j.strip()]
    salida = []
    for j in jaulas:
        d = subprocess.run(["fail2ban-client", "status", j], capture_output=True, text=True, timeout=20).stdout
        ips = re.search(r"Banned IP list:\s*(.*)", d)
        total = re.search(r"Total banned:\s*(\d+)", d)
        salida.append({"jaula": j, "bloqueadas": (ips.group(1).split() if ips else []),
                       "total": int(total.group(1)) if total else 0})
    return salida


def _escuchando():
    r = subprocess.run(["ss", "-H", "-ltnu"], capture_output=True, text=True, timeout=20)
    puertos = set()
    for linea in r.stdout.splitlines():
        partes = linea.split()
        if len(partes) < 5:
            continue
        proto, local = partes[0], partes[4]
        direccion, _, puerto = local.rpartition(":")
        if direccion.startswith("127.") or direccion in ("[::1]", "::1") or direccion.startswith("127.0.0.5"):
            continue
        if puerto.isdigit():
            puertos.add((proto, int(puerto)))
    return [{"protocolo": p, "puerto": n} for p, n in sorted(puertos, key=lambda x: (x[1], x[0]))]


def _cadena_activa():
    return subprocess.run(["iptables", "-C", "INPUT", "-j", reglas.CADENA], capture_output=True).returncode == 0


def estado():
    pendiente = None
    if os.path.exists(PENDIENTE):
        with open(PENDIENTE) as f:
            pendiente = json.load(f).get("vence")
    return {
        "activo": _cadena_activa(),
        "configurado": os.path.exists(config.RUTA),
        "config": config.leer(),
        "servicios": config.SERVICIOS,
        "pendiente_hasta": pendiente,
        "fail2ban": _fail2ban(),
        "escuchando": _escuchando(),
    }


def desbloquear(jaula, ip):
    if not re.match(r"^[a-z0-9_-]{1,40}$", jaula):
        raise config.ErrorCortafuegos("vigilancia no válida")
    config.red(ip)
    r = subprocess.run(["fail2ban-client", "set", jaula, "unbanip", ip], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise config.ErrorCortafuegos((r.stderr or r.stdout).strip()[-200:] or "no se pudo desbloquear")
    return {"desbloqueada": ip, "jaula": jaula}
