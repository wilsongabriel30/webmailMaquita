# -*- coding: utf-8 -*-
"""
Punto de entrada de la API del chat (bp_chat). PARTIDO el 28/08/2026 en módulos por responsabilidad:
#   chat_base.py  (1-155): Blueprint bp_chat, imports comunes, sesión de BD, autenticación y utilidades
#   chat_conversaciones.py  (156-541): Conversaciones: listar, detalle, directa, crear grupo
#   chat_mensajes.py  (542-1363): Mensajes: listar, enviar, editar, eliminar, limpiar, marcar leído
#   chat_adjuntos.py  (1364-1689): Adjuntos: subida de archivos, ubicación, contacto, GIF
#   chat_reacciones.py  (1690-1858): Reacciones a mensajes
#   chat_participantes.py  (1859-1990): Participantes de grupos: agregar, quitar, salir
#   chat_presencia_bloqueos.py  (1991-2183): Presencia en línea y bloqueos
#   chat_usuarios.py  (2184-2438): Búsqueda de usuarios, trabajadores activos, no leídos
#   chat_acciones.py  (2439-2621): Acciones en conversación (escribiendo, grabando…)
#   chat_reenvio_fijados.py  (2622-2779): Reenviar, fijar/desfijar, marcar todo leído, fijados
#   chat_llamadas.py  (2780-3030): Token LiveKit/TURN e historial de llamadas
#   chat_grabaciones.py  (3031-3253): Grabación de llamadas (LiveKit Egress)
#   chat_archivar_admin.py  (3254-3389): Archivar/vaciar/eliminar conversación y panel admin
#   chat_buscar.py  (3390-3456): Búsqueda de mensajes
Copia íntegra previa: /root/backups-chat/controlador_chat.py.20260828-0935
Todo lo que antes se importaba desde aquí (bp_chat, obtener_servicio_chat, obtener_usuario_id, requiere_autenticacion,
_livekit_jwt, …) sigue disponible: se reexporta desde los módulos.
"""
from interfaces.api.chat_base import *  # noqa: F401,F403
from interfaces.api.chat_base import bp_chat, obtener_servicio_chat, obtener_usuario_id, requiere_autenticacion, obtener_foto_usuario_con_fallback  # noqa: F401
# Registrar las rutas de cada módulo (el orden es el del archivo original)
import interfaces.api.chat_conversaciones  # noqa: F401,E402
import interfaces.api.chat_mensajes  # noqa: F401,E402
import interfaces.api.chat_adjuntos  # noqa: F401,E402
import interfaces.api.chat_reacciones  # noqa: F401,E402
import interfaces.api.chat_participantes  # noqa: F401,E402
import interfaces.api.chat_presencia_bloqueos  # noqa: F401,E402
import interfaces.api.chat_usuarios  # noqa: F401,E402
import interfaces.api.chat_acciones  # noqa: F401,E402
import interfaces.api.chat_reenvio_fijados  # noqa: F401,E402
import interfaces.api.chat_llamadas  # noqa: F401,E402
import interfaces.api.chat_estado  # noqa: F401,E402  (T-48 estados de presencia)
import interfaces.api.chat_favoritos  # noqa: F401,E402  (T-50 conversaciones favoritas)
import interfaces.api.llamadas_seccion_api  # noqa: F401,E402  (T-46: sección Llamadas)
import interfaces.api.chat_grabaciones  # noqa: F401,E402
import interfaces.api.chat_archivar_admin  # noqa: F401,E402
import interfaces.api.chat_buscar  # noqa: F401,E402
from interfaces.api.chat_llamadas import _livekit_jwt, _turn_ice_servers  # noqa: F401,E402  (los usan otros módulos)
from interfaces.api.chat_grabaciones import _egress_twirp, _usuario_en_sala  # noqa: F401,E402
from interfaces.api.chat_reenvio_fijados import _conv_de_mensaje  # noqa: F401,E402
from interfaces.api.chat_archivar_admin import _es_master  # noqa: F401,E402
