"""Órdenes de «Mi sitio web» que llegan con la v1.11, juntas para que portal.py no crezca con cada una.

- ordenes_dominios.py: alias de dominio de un sitio;
- ordenes_propias.py:  aplicaciones Node.js, Python y estáticas;
- ordenes_git.py:      despliegue desde git de los sitios PHP;
- ordenes_servidor.py: CPU y memoria de un sitio e información del servidor;
- ordenes_ddns.py:     fichas del DNS dinámico de una zona.
Las órdenes sin sesión (el gancho de git y la actualización del DNS dinámico) están en publico.py.
"""

import ordenes_ddns
import ordenes_dominios
import ordenes_git
import ordenes_propias
import ordenes_servidor

ORDENES = {
    **ordenes_dominios.ORDENES,
    **ordenes_propias.ORDENES,
    **ordenes_git.ORDENES,
    **ordenes_servidor.ORDENES,
    **ordenes_ddns.ORDENES,
}
