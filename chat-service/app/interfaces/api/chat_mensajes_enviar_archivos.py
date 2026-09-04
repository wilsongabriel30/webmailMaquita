# -*- coding: utf-8 -*-
"""Mensajes: enviar CON ARCHIVOS adjuntos (multipart). Extraído de chat_mensajes_enviar.py (líneas 47-168) el 28/08/2026
sin cambios de lógica: el cuerpo del `if archivos:` pasó a enviar_con_archivos(), que devuelve (respuesta, código)."""
from interfaces.api.chat_base import *  # noqa: F401,F403


def enviar_con_archivos(conversacion_id, datos, archivos):
    """Guarda los adjuntos, refleja en Drive (T-18), registra huellas (T-32) y envía el mensaje con media."""
    import os
    from werkzeug.utils import secure_filename
    usuario_id = obtener_usuario_id()
    tipo_mensaje = datos.get('tipo', 'document')
    contenido = datos.get('contenido', '').strip()

    # Guardar en ruta servida por Nginx: /uploads/ -> interfaces/web/estaticos/uploads/
    base_upload = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'web', 'estaticos', 'uploads', 'chat', str(conversacion_id)
    )
    os.makedirs(base_upload, exist_ok=True)

    archivos_para_servicio = []
    media_list = []
    _para_drive = []
    for archivo in archivos:
        if archivo and archivo.filename:
            filename = secure_filename(archivo.filename)
            import time
            ts = int(time.time())
            filename = f"{ts}_{filename}"
            filepath = os.path.join(base_upload, filename)
            archivo.save(filepath)
            # T-18: reflejo en el Drive (emisor y receptores), en segundo plano tras enviar
            try:
                _para_drive.append((filepath, archivo.filename))
            except NameError:
                _para_drive = [(filepath, archivo.filename)]

            # Determinar tipo de media. PRIORIDAD: el tipo que indica el
            # cliente (mensaje_type) y el MIME; la extension es ultimo recurso.
            # (Evita que un audio de voz .webm se clasifique como video, o un
            #  gif como imagen generica.)
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            mime = (archivo.content_type or '').lower()
            tipo_cliente = (tipo_mensaje or '').lower()

            if tipo_cliente in ('audio', 'voice') or mime.startswith('audio/'):
                media_type = 'audio'
            elif tipo_cliente == 'gif' or ext == 'gif':
                media_type = 'image'  # los gif se muestran como imagen animada
            elif tipo_cliente == 'image' or mime.startswith('image/') or ext in ('jpg', 'jpeg', 'png', 'webp', 'bmp'):
                media_type = 'image'
            elif tipo_cliente == 'video' or mime.startswith('video/') or ext in ('mp4', 'mov', 'avi', 'mkv'):
                media_type = 'video'
            elif ext == 'webm':
                # webm sin pista clara: si el cliente no dijo video, tratar como audio
                media_type = 'video' if tipo_cliente == 'video' else 'audio'
            elif ext in ('mp3', 'ogg', 'wav', 'aac', 'm4a', 'opus'):
                media_type = 'audio'
            else:
                media_type = 'document'
            # El tipo del MENSAJE sigue al del primer archivo (coherencia UI)
            tipo_mensaje = media_type

            # URL pública servida por Nginx
            url_publica = f'/uploads/chat/{conversacion_id}/{filename}'
            tipo_mime = archivo.content_type or 'application/octet-stream'
            file_size = os.path.getsize(filepath)

            archivos_para_servicio.append({
                'ruta': url_publica,
                'nombre': archivo.filename,
                'tamanio': file_size,
                'tipo_mime': tipo_mime
            })
            media_list.append({
                'file_path': url_publica,
                'file_name': archivo.filename,
                'media_type': media_type,
                'file_size': file_size,
                'mime_type': tipo_mime
            })

    # Usar enviar_mensaje_con_archivos para crear registros en chat_message_media
    servicio = obtener_servicio_chat()
    # T-18: Archivos del chat → Drive de cada participante (dedup en el Almacén)
    try:
        from interfaces.api.drive_chat import reflejar_en_drive
        reflejar_en_drive(conversacion_id, usuario_id, _para_drive)
        # T-32: huella SHA-256 + una sola copia física por contenido
        from interfaces.api.adjuntos_dedup import registrar_archivos as _huellas
        _huellas(conversacion_id, usuario_id, _para_drive)
    except Exception as _e:
        print(f"[drive-chat] no se pudo programar el reflejo: {_e}")
    resultado = servicio.enviar_mensaje_con_archivos(
        conversacion_id=conversacion_id,
        remitente_id=usuario_id,
        archivos=archivos_para_servicio,
        tipo_media=tipo_mensaje,
        contenido=contenido or None
    )

    if resultado.exito and resultado.datos:
        mensaje_data = resultado.datos.get('mensaje', {})
        mensaje_data['remitente'] = {
            'id': usuario_id,
            'nombre': session.get('usuario_nombre', 'Usuario')
        }
        mensaje_data['archivos'] = media_list
        emitir_mensaje_nuevo(conversacion_id, mensaje_data)

    response_data = {
        'exito': resultado.exito,
        'success': resultado.exito,
        'mensaje': resultado.mensaje
    }
    if resultado.datos and resultado.datos.get('mensaje'):
        msg = resultado.datos['mensaje']
        response_data['message'] = {
            'id': msg.get('id'),
            'content': msg.get('contenido'),
            'message_type': tipo_mensaje,
            'sender_id': usuario_id,
            'created_at': msg.get('creado_en'),
            'is_own_message': True,
            'media': media_list
        }
    return jsonify(response_data), 200 if resultado.exito else 400
