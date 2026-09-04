"""Antepone `sudo` a las órdenes que lo necesitan, en un solo sitio.

Fase 2 del hallazgo A-15. El panel dejó de correr como root: ahora corre como
`maquita-admin`, que por sí mismo no puede reiniciar servicios ni hablar con
Dovecot. Lo poco que necesita se concede en /etc/sudoers.d/maquita-admin, orden
por orden y sin comodines en las unidades.

POR QUÉ ESTÁ AQUÍ Y NO REPARTIDO POR EL CÓDIGO
El panel tiene diez funciones de ejecución distintas y más de cuarenta puntos de
llamada a binarios privilegiados. Anteponer `sudo` a mano en cada uno habría
significado cuarenta oportunidades de olvidarse de uno, y ningún sitio donde
mirar para saber qué se ejecuta con privilegio. Con esto la lista está en un
único lugar y se puede contrastar con el sudoers de un vistazo.

LO QUE ESTA FUNCIÓN NO HACE
No valida los argumentos. Esa es responsabilidad de quien llama, y se auditó
punto por punto el 2026-09-04 antes de conceder ningún sudo: el buzón, la
carpeta y la consulta de búsqueda llegan de la petición HTTP y ahora se validan
en `wrappers/doveadm.py`. Un sudoers impecable sobre una orden que interpola
datos del usuario es la misma vulnerabilidad que ya tuvimos dos veces, con otra
ropa.

SI EL PANEL VUELVE A CORRER COMO ROOT
`sudo` como root funciona igual, así que dejar esto puesto no rompe la marcha
atrás.
"""

import os
import shutil

# Binarios que el usuario del panel NO puede ejecutar por sí mismo.
# Esta lista debe coincidir con /etc/sudoers.d/maquita-admin. Si añades uno
# aquí sin añadirlo allí, la orden fallará con «sudo: a password is required».
_REQUIEREN_SUDO = {
    "systemctl",
    "journalctl",
    "doveadm",
    "sievec",
    "postconf",
    "postqueue",
    "postsuper",
    "fail2ban-client",
    "nginx",
}

_SUDO = shutil.which("sudo") or "/usr/bin/sudo"


def _somos_root() -> bool:
    return os.geteuid() == 0


def con_sudo(*cmd: str) -> tuple[str, ...]:
    """Devuelve la orden, con `sudo` delante si hace falta.

    Si ya somos root no se antepone nada: evita una capa inútil y hace que la
    marcha atrás a `User=root` funcione sin tocar código.
    """
    if not cmd:
        return cmd
    if _somos_root():
        return cmd
    binario = os.path.basename(cmd[0])
    if binario in _REQUIEREN_SUDO:
        return (_SUDO, "-n") + cmd
    return cmd
