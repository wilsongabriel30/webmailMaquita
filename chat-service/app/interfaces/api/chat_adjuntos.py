# -*- coding: utf-8 -*-
"""Adjuntos: subida de archivos, ubicación, contacto, GIF.
Extraído de controlador_chat.py (líneas 1364-1689) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# MENSAJES CON ARCHIVOS Y MULTIMEDIA
# =============================================================================

@bp_chat.route('/conversations/<int:conversacion_id>/messages/upload', methods=['POST'])
@requiere_autenticacion
def enviar_mensaje_con_archivos(conversacion_id: int):
    """
    Envia un mensaje con archivos multimedia.

    Form data:
        files: Archivos a subir (multipart)
        tipo: Tipo de media (image, video, audio, document)
        contenido: Texto opcional del mensaje

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    import os
    from werkzeug.utils import secure_filename

    try:
        # Obtener archivos - soportar ambos nombres: 'files' y 'file'
        archivos = []
        if 'files' in request.files:
            archivos = request.files.getlist('files')
        elif 'file' in request.files:
            archivos = [request.files['file']]

        if not archivos or (len(archivos) == 1 and archivos[0].filename == ''):
            return jsonify({
                'exito': False,
                'success': False,
                'mensaje': 'No se enviaron archivos',
                'error': 'No se enviaron archivos'
            }), 400

        # Soportar ambos nombres: 'tipo' y 'message_type'
        tipo_media = request.form.get('tipo') or request.form.get('message_type', 'document')
        contenido = request.form.get('contenido', '').strip() or request.form.get('content', '').strip() or None

        # Directorio de uploads
        upload_dir = os.path.join('static', 'uploads', 'chat', str(conversacion_id))
        os.makedirs(upload_dir, exist_ok=True)

        archivos_data = []
        _para_drive_up = []
        for archivo in archivos:
            if archivo.filename:
                nombre_seguro = secure_filename(archivo.filename)
                # Agregar timestamp para evitar colisiones
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S%f_')
                nombre_final = timestamp + nombre_seguro
                ruta = os.path.join(upload_dir, nombre_final)

                # Guardar archivo
                archivo.save(ruta)
                _para_drive_up.append((os.path.abspath(ruta), archivo.filename))

                # Obtener info del archivo
                tamanio = os.path.getsize(ruta)
                tipo_mime = archivo.content_type or 'application/octet-stream'

                archivos_data.append({
                    'ruta': ruta.replace('\\', '/'),
                    'nombre': archivo.filename,
                    'tamanio': tamanio,
                    'tipo_mime': tipo_mime
                })

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        # T-18: Archivos del chat → Drive de cada participante (dedup en el Almacén), en segundo plano
        try:
            from interfaces.api.drive_chat import reflejar_en_drive
            reflejar_en_drive(conversacion_id, usuario_id, _para_drive_up)
            # T-32: huella SHA-256 + una sola copia física por contenido
            from interfaces.api.adjuntos_dedup import registrar_archivos as _huellas
            _huellas(conversacion_id, usuario_id, _para_drive_up)
        except Exception as _e:
            print(f"[drive-chat] no se pudo programar el reflejo: {_e}")
        resultado = servicio.enviar_mensaje_con_archivos(
            conversacion_id=conversacion_id,
            remitente_id=usuario_id,
            archivos=archivos_data,
            tipo_media=tipo_media,
            contenido=contenido
        )

        status = 200 if resultado.exito else 400

        # Preparar respuesta compatible con frontend
        response_data = {
            'exito': resultado.exito,
            'success': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }

        # Incluir mensaje en formato esperado por frontend
        if resultado.datos and resultado.datos.get('mensaje'):
            msg = resultado.datos['mensaje']
            response_data['message'] = {
                'id': msg.get('id'),
                'content': msg.get('contenido'),
                'message_type': tipo_media,
                'sender_id': usuario_id,
                'created_at': msg.get('creado_en'),
                'is_own_message': True,
                'media': [
                    {
                        'file_path': a.get('ruta'),
                        'media_type': tipo_media,
                        'file_name': a.get('nombre'),
                        'file_size': a.get('tamanio')
                    }
                    for a in msg.get('archivos', [])
                ]
            }

            # Emitir via WebSocket para tiempo real
            mensaje_data = msg.copy()
            mensaje_data['remitente'] = {
                'id': usuario_id,
                'nombre': session.get('usuario_nombre', 'Usuario')
            }
            emitir_mensaje_nuevo(conversacion_id, mensaje_data)

        return jsonify(response_data), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/messages/location', methods=['POST'])
@requiere_autenticacion
def enviar_ubicacion(conversacion_id: int):
    """
    Envia un mensaje con ubicacion.

    Request:
        {
            "latitud": float,
            "longitud": float,
            "nombre": "Nombre del lugar" (opcional),
            "direccion": "Direccion" (opcional)
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({
                'exito': False,
                'mensaje': 'Datos no proporcionados'
            }), 400

        if 'latitud' not in datos or 'longitud' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'latitud y longitud son requeridos'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.enviar_ubicacion(
            conversacion_id=conversacion_id,
            remitente_id=obtener_usuario_id(),
            latitud=float(datos['latitud']),
            longitud=float(datos['longitud']),
            nombre=datos.get('nombre'),
            direccion=datos.get('direccion')
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except ValueError as e:
        return jsonify({
            'exito': False,
            'mensaje': 'Coordenadas invalidas'
        }), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/messages/contact', methods=['POST'])
@requiere_autenticacion
def enviar_contacto(conversacion_id: int):
    """
    Envia un mensaje con informacion de contacto.

    Request:
        {
            "nombre": "Nombre del contacto",
            "telefono": "+593999999999" (opcional si hay email),
            "email": "correo@ejemplo.com" (opcional si hay telefono),
            "organizacion": "Empresa" (opcional),
            "cargo": "Cargo" (opcional)
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({
                'exito': False,
                'mensaje': 'Datos no proporcionados'
            }), 400

        if 'nombre' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'nombre es requerido'
            }), 400

        if not datos.get('telefono') and not datos.get('email'):
            return jsonify({
                'exito': False,
                'mensaje': 'Se requiere al menos telefono o email'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.enviar_contacto(
            conversacion_id=conversacion_id,
            remitente_id=obtener_usuario_id(),
            nombre=datos['nombre'],
            telefono=datos.get('telefono'),
            email=datos.get('email'),
            organizacion=datos.get('organizacion'),
            cargo=datos.get('cargo')
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/messages/gif', methods=['POST'])
@requiere_autenticacion
def enviar_gif(conversacion_id: int):
    """
    Envia un mensaje con GIF.

    Request:
        {
            "url": "https://media.giphy.com/...",
            "contenido": "Texto opcional"
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos or 'url' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'url del GIF es requerida'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.enviar_gif(
            conversacion_id=conversacion_id,
            remitente_id=obtener_usuario_id(),
            url_gif=datos['url'],
            contenido=datos.get('contenido')
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500

