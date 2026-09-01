# -*- coding: utf-8 -*-
"""
Aviso al servicio de chat cuando el usuario toca su carpeta «Archivos del chat» (T-18 fase 2).
Dispara y olvida: nunca bloquea al Almacén. Variables: ALMACEN_CHAT_URL, ALMACEN_CHAT_SECRETO.
"""
import os
import threading

CARPETA = '/archivos del chat/'


def es_de_chat(ruta) -> bool:
    return ('/' + str(ruta or '').strip().strip('/') + '/').lower().startswith(CARPETA)


def _enviar(cuerpo):
    url = os.getenv('ALMACEN_CHAT_URL', 'http://193.16.0.136:8790/api/chat/drive/evento')
    secreto = os.getenv('ALMACEN_CHAT_SECRETO', '')
    if not secreto:
        return
    try:
        import requests
        requests.post(url, json=cuerpo, headers={'X-Notif-Secret': secreto}, timeout=4)
    except Exception:
        pass


def avisar_chat(usuario_id, ruta, evento):
    """evento: papelera | restaurado | eliminado. Solo para rutas dentro de /Archivos del chat/."""
    if not es_de_chat(ruta):
        return
    threading.Thread(target=_enviar, args=({'usuario_id': int(usuario_id), 'ruta': ruta, 'evento': evento},), daemon=True).start()
