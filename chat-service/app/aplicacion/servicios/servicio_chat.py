# -*- coding: utf-8 -*-
"""
Servicio de Aplicacion: Chat

Orquesta las operaciones del chat institucional.
Coordina repositorios, entidades de dominio y logica de negocio.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass

from modulos.chat.dominio.entidades.conversacion import Conversacion, Participante
from modulos.chat.dominio.entidades.mensaje import Mensaje, ArchivoMensaje, ReaccionMensaje
from modulos.chat.dominio.value_objects.tipos_chat import (
    TipoConversacion,
    TipoMensaje,
    TipoMedia,
    RolParticipante,
    ConstantesChat,
    AccionUsuario,
    UbicacionMensaje,
    ContactoMensaje
)
from modulos.chat.dominio.repositorios.repositorio_chat import (
    RepositorioConversacion,
    RepositorioParticipante,
    RepositorioMensaje,
    RepositorioArchivoMensaje,
    RepositorioReaccion,
    RepositorioPresencia,
    RepositorioBloqueo,
    RepositorioIndicadorAccion
)


# =============================================================================
# DTOs DE RESPUESTA
# =============================================================================

@dataclass
class RespuestaChat:
    """Respuesta generica del servicio de chat."""
    exito: bool
    mensaje: str
    datos: Optional[Dict[str, Any]] = None


@dataclass
class ConversacionDTO:
    """DTO para conversacion."""
    id: int
    public_id: str
    tipo: str
    nombre: Optional[str]
    descripcion: Optional[str]
    avatar_ruta: Optional[str]
    ultimo_mensaje_en: Optional[str]
    ultimo_mensaje_preview: Optional[str]
    mensajes_no_leidos: int = 0
    participantes: List[Dict[str, Any]] = None

    @classmethod
    def desde_entidad(cls, conv: Conversacion, no_leidos: int = 0) -> 'ConversacionDTO':
        return cls(
            id=conv.id,
            public_id=str(conv.public_id),
            tipo=conv.tipo.value,
            nombre=conv.nombre,
            descripcion=conv.descripcion,
            avatar_ruta=conv.avatar_ruta,
            ultimo_mensaje_en=conv.ultimo_mensaje_en.isoformat() if conv.ultimo_mensaje_en else None,
            ultimo_mensaje_preview=conv.ultimo_mensaje_preview,
            mensajes_no_leidos=no_leidos
        )


@dataclass
class MensajeDTO:
    """DTO para mensaje."""
    id: int
    public_id: str
    conversacion_id: int
    remitente_id: int
    contenido: Optional[str]
    tipo: str
    respuesta_a_id: Optional[int]
    editado: bool
    eliminado: bool
    creado_en: str
    archivos: List[Dict[str, Any]] = None
    reacciones: Dict[str, List[int]] = None
    remitente: Optional[Dict[str, Any]] = None
    gif_url: Optional[str] = None  # URL del GIF para mensajes tipo gif

    @classmethod
    def desde_entidad(cls, msg: Mensaje) -> 'MensajeDTO':
        archivos = [a.to_dict() for a in msg.archivos] if msg.archivos else []
        reacciones = msg.obtener_reacciones_agrupadas() if msg.reacciones else {}

        # Extraer gif_url de metadata si es un mensaje GIF
        gif_url = None
        if msg.es_gif() and msg.metadata:
            gif_url = msg.metadata.get('gif_url')

        return cls(
            id=msg.id,
            public_id=str(msg.public_id),
            conversacion_id=msg.conversacion_id,
            remitente_id=msg.remitente_id,
            contenido=msg.contenido if not msg.eliminado else None,
            tipo=msg.tipo.value,
            respuesta_a_id=msg.respuesta_a_id,
            editado=msg.editado,
            eliminado=msg.eliminado,
            # Asegurar formato ISO con timezone para correcta conversión en cliente
            creado_en=msg.creado_en.isoformat() if msg.creado_en else None,  # isoformat() incluye +00:00 si tiene timezone
            archivos=archivos,
            reacciones=reacciones,
            remitente={
                'id': msg.remitente_id,
                'nombre': msg.remitente_nombre,
                'avatar': msg.remitente_avatar
            } if msg.remitente_nombre else None,
            gif_url=gif_url
        )


# =============================================================================
# SERVICIO CHAT
# =============================================================================

import re as _re_gif

_RE_GIF_LOCAL = _re_gif.compile(r'^/static/gifs/[A-Za-z0-9._-]{1,120}$')


def _url_gif_local(url) -> bool:
    """[A-1] True solo si la URL apunta a la galeria local de GIF del propio chat."""
    u = (url or '').strip()
    return bool(_RE_GIF_LOCAL.match(u)) and '..' not in u


class ServicioChat:
    """
    Servicio principal del chat institucional.

    Orquesta todas las operaciones del chat:
    - Conversaciones (crear, listar, buscar)
    - Mensajes (enviar, editar, eliminar)
    - Participantes (agregar, eliminar, roles)
    - Reacciones
    - Presencia
    - Bloqueos
    - Indicadores de accion (escribiendo, grabando, etc.)
    """

    def __init__(
        self,
        repo_conversacion: RepositorioConversacion,
        repo_participante: RepositorioParticipante,
        repo_mensaje: RepositorioMensaje,
        repo_archivo: RepositorioArchivoMensaje,
        repo_reaccion: RepositorioReaccion,
        repo_presencia: RepositorioPresencia,
        repo_bloqueo: RepositorioBloqueo,
        repo_indicador: RepositorioIndicadorAccion = None
    ):
        self._repo_conversacion = repo_conversacion
        self._repo_participante = repo_participante
        self._repo_mensaje = repo_mensaje
        self._repo_archivo = repo_archivo
        self._repo_reaccion = repo_reaccion
        self._repo_presencia = repo_presencia
        self._repo_bloqueo = repo_bloqueo
        self._repo_indicador = repo_indicador

    # =========================================================================
    # CONVERSACIONES
    # =========================================================================

    def obtener_conversaciones(
        self,
        usuario_id: int,
        limite: int = 20,
        offset: int = 0
    ) -> List[ConversacionDTO]:
        """Obtiene las conversaciones del usuario."""
        conversaciones = self._repo_conversacion.obtener_conversaciones_usuario(
            usuario_id, limite, offset
        )

        resultado = []
        for conv in conversaciones:
            # Obtener participantes
            participantes = self._repo_participante.obtener_participantes(conv.id)
            conv.participantes = participantes

            # Obtener no leidos
            participante = self._repo_participante.buscar_en_conversacion(
                conv.id, usuario_id
            )
            no_leidos = participante.mensajes_no_leidos if participante else 0

            dto = ConversacionDTO.desde_entidad(conv, no_leidos)

            # Agregar participantes al DTO
            dto.participantes = [
                {'usuario_id': p.usuario_id, 'rol': p.rol.value if hasattr(p.rol, 'value') else p.rol}
                for p in participantes
            ] if participantes else []

            # Para conversaciones directas, obtener info del otro usuario
            if conv.es_directa():
                otro = conv.obtener_otro_participante(usuario_id)
                if otro:
                    dto.nombre = f"Usuario {otro.usuario_id}"  # Se reemplaza en listar_conversaciones

            resultado.append(dto)

        return resultado

    def listar_conversaciones(
        self,
        usuario_id: int,
        limite: int = 50,
        offset: int = 0
    ) -> RespuestaChat:
        """
        Lista conversaciones del usuario con nombres resueltos.

        Este método es el punto de entrada para el WebSocket.
        Obtiene las conversaciones y reemplaza los IDs de usuario por nombres reales.

        Args:
            usuario_id: ID del usuario actual
            limite: Máximo de conversaciones a retornar
            offset: Offset para paginación

        Returns:
            RespuestaChat con lista de conversaciones serializadas
        """
        try:
            # Obtener conversaciones
            conversaciones = self.obtener_conversaciones(usuario_id, limite, offset)

            # Recopilar IDs de usuarios que necesitamos resolver
            user_ids_to_resolve = set()
            for conv in conversaciones:
                if conv.participantes:
                    for p in conv.participantes:
                        user_ids_to_resolve.add(p.get('usuario_id'))

            # Obtener nombres de usuarios desde la BD
            user_names = {}
            if user_ids_to_resolve and hasattr(self, '_db_session'):
                try:
                    from sqlalchemy import text
                    result = self._db_session.execute(
                        text("SELECT id, full_name, username FROM usuarios WHERE id = ANY(:ids)"),
                        {'ids': list(user_ids_to_resolve)}
                    )
                    for row in result:
                        user_names[row[0]] = row[1] or row[2] or f"Usuario {row[0]}"
                except Exception as e:
                    print(f"[WARN] Error obteniendo nombres de usuarios: {e}")

            # Serializar conversaciones y reemplazar nombres
            result_list = []
            for conv in conversaciones:
                conv_dict = {
                    'id': conv.id,
                    'public_id': conv.public_id,
                    'tipo': conv.tipo,
                    'nombre': conv.nombre,
                    'descripcion': conv.descripcion,
                    'avatar_ruta': conv.avatar_ruta,
                    'ultimo_mensaje_en': conv.ultimo_mensaje_en,
                    'ultimo_mensaje_preview': conv.ultimo_mensaje_preview,
                    'mensajes_no_leidos': conv.mensajes_no_leidos,
                    'participantes': conv.participantes or []
                }

                # Para conversaciones directas, reemplazar "Usuario X" con nombre real
                if conv.tipo == 'directa' and conv.nombre and conv.nombre.startswith('Usuario '):
                    try:
                        other_user_id = int(conv.nombre.split(' ')[1])
                        if other_user_id in user_names:
                            conv_dict['nombre'] = user_names[other_user_id]
                    except (ValueError, IndexError):
                        pass

                # Agregar nombres a participantes
                if conv_dict['participantes']:
                    for p in conv_dict['participantes']:
                        uid = p.get('usuario_id')
                        if uid in user_names:
                            p['nombre'] = user_names[uid]

                result_list.append(conv_dict)

            return RespuestaChat(
                exito=True,
                mensaje="OK",
                datos={'conversaciones': result_list}
            )

        except Exception as e:
            print(f"[ERROR] Error listando conversaciones: {e}")
            import traceback
            traceback.print_exc()
            return RespuestaChat(
                exito=False,
                mensaje=str(e),
                datos={'conversaciones': []}
            )

    def obtener_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> Optional[ConversacionDTO]:
        """Obtiene una conversacion por ID."""
        conv = self._repo_conversacion.buscar_por_id(conversacion_id)
        if not conv:
            return None

        # Verificar que el usuario es participante
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, usuario_id
        )
        if not participante or not participante.activo:
            return None

        # Cargar participantes
        participantes = self._repo_participante.obtener_participantes(conv.id)
        conv.participantes = participantes

        return ConversacionDTO.desde_entidad(conv, participante.mensajes_no_leidos)

    def crear_conversacion_directa(
        self,
        usuario1_id: int,
        usuario2_id: int
    ) -> RespuestaChat:
        """Crea o recupera una conversacion directa entre dos usuarios."""
        # Verificar bloqueos (con manejo de error si la tabla no existe)
        try:
            if self._repo_bloqueo.hay_bloqueo_mutuo(usuario1_id, usuario2_id):
                return RespuestaChat(
                    exito=False,
                    mensaje="No puedes iniciar conversacion con este usuario"
                )
        except Exception as e:
            # Si hay error al verificar bloqueos, continuar (la tabla puede no existir)
            print(f"[WARN] Error verificando bloqueos: {e}")

        # Buscar conversacion existente
        conv_existente = self._repo_conversacion.buscar_directa(usuario1_id, usuario2_id)
        if conv_existente:
            return RespuestaChat(
                exito=True,
                mensaje="Conversacion existente",
                datos={'conversacion': ConversacionDTO.desde_entidad(conv_existente).__dict__}
            )

        # Crear nueva conversacion
        conversacion = Conversacion.crear_directa(usuario1_id, usuario2_id)
        conversacion = self._repo_conversacion.crear(conversacion)

        # Agregar participantes
        self._repo_participante.agregar(Participante(
            id=None,
            conversacion_id=conversacion.id,
            usuario_id=usuario1_id,
            rol=RolParticipante.MIEMBRO,
            activo=True,
            unido_en=datetime.now()
        ))
        self._repo_participante.agregar(Participante(
            id=None,
            conversacion_id=conversacion.id,
            usuario_id=usuario2_id,
            rol=RolParticipante.MIEMBRO,
            activo=True,
            unido_en=datetime.now()
        ))

        return RespuestaChat(
            exito=True,
            mensaje="Conversacion creada",
            datos={'conversacion': ConversacionDTO.desde_entidad(conversacion).__dict__}
        )

    def crear_grupo(
        self,
        creador_id: int,
        nombre: str,
        miembros_ids: List[int],
        descripcion: Optional[str] = None
    ) -> RespuestaChat:
        """Crea un grupo de chat."""
        # Validar nombre
        if not nombre or len(nombre.strip()) == 0:
            return RespuestaChat(exito=False, mensaje="El nombre es requerido")

        if len(nombre) > ConstantesChat.MAX_NOMBRE_GRUPO:
            return RespuestaChat(
                exito=False,
                mensaje=f"El nombre no puede exceder {ConstantesChat.MAX_NOMBRE_GRUPO} caracteres"
            )

        # Validar miembros
        if len(miembros_ids) > ConstantesChat.MAX_PARTICIPANTES_GRUPO - 1:
            return RespuestaChat(
                exito=False,
                mensaje=f"Maximo {ConstantesChat.MAX_PARTICIPANTES_GRUPO} participantes"
            )

        # Crear grupo
        conversacion = Conversacion.crear_grupo(nombre, creador_id, descripcion)
        conversacion = self._repo_conversacion.crear(conversacion)

        # Agregar creador como admin
        self._repo_participante.agregar(Participante(
            id=None,
            conversacion_id=conversacion.id,
            usuario_id=creador_id,
            rol=RolParticipante.ADMIN,
            activo=True,
            unido_en=datetime.now()
        ))

        # Agregar miembros
        for miembro_id in miembros_ids:
            if miembro_id != creador_id:
                self._repo_participante.agregar(Participante(
                    id=None,
                    conversacion_id=conversacion.id,
                    usuario_id=miembro_id,
                    rol=RolParticipante.MIEMBRO,
                    activo=True,
                    unido_en=datetime.now()
                ))

        # Mensaje de sistema
        mensaje_sistema = Mensaje.crear_sistema(
            conversacion.id,
            f"Grupo '{nombre}' creado"
        )
        self._repo_mensaje.crear(mensaje_sistema)

        return RespuestaChat(
            exito=True,
            mensaje="Grupo creado",
            datos={'conversacion': ConversacionDTO.desde_entidad(conversacion).__dict__}
        )

    # =========================================================================
    # MENSAJES
    # =========================================================================

    def obtener_mensajes(
        self,
        conversacion_id: int,
        usuario_id: int,
        limite: int = 50,
        antes_de_id: Optional[int] = None
    ) -> RespuestaChat:
        """Obtiene los mensajes de una conversacion."""
        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, usuario_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso a esta conversacion")

        mensajes = self._repo_mensaje.obtener_mensajes(
            conversacion_id, limite, antes_de_id
        )

        # Cargar reacciones (con manejo de error si la tabla no existe)
        mensajes_dto = []
        for msg in mensajes:
            try:
                reacciones = self._repo_reaccion.obtener_reacciones_mensaje(msg.id)
                msg.reacciones = reacciones
            except Exception as e:
                # Si falla la carga de reacciones (tabla no existe, etc.), continuar sin ellas
                msg.reacciones = []
            mensajes_dto.append(MensajeDTO.desde_entidad(msg).__dict__)

        return RespuestaChat(
            exito=True,
            mensaje="OK",
            datos={'mensajes': mensajes_dto}
        )

    def enviar_mensaje(
        self,
        conversacion_id: int,
        remitente_id: int,
        contenido: str,
        tipo: str = 'text',
        respuesta_a_id: Optional[int] = None,
        client_id: Optional[str] = None
    ) -> RespuestaChat:
        """Envia un mensaje a una conversacion."""
        # Verificar idempotencia si hay client_id
        if client_id:
            existente = self._repo_mensaje.buscar_por_client_id(client_id)
            if existente:
                return RespuestaChat(
                    exito=True,
                    mensaje="Mensaje ya enviado (idempotente)",
                    datos={'mensaje': MensajeDTO.desde_entidad(existente).__dict__}
                )

        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, remitente_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso a esta conversacion")

        # Validar contenido
        if contenido and len(contenido) > ConstantesChat.MAX_LONGITUD_MENSAJE:
            return RespuestaChat(
                exito=False,
                mensaje=f"Mensaje muy largo (max {ConstantesChat.MAX_LONGITUD_MENSAJE})"
            )

        # Crear mensaje
        mensaje = Mensaje.crear_texto(
            conversacion_id,
            remitente_id,
            contenido,
            respuesta_a_id
        )
        # Asignar client_id si existe
        if client_id:
            mensaje.client_id = client_id
        mensaje = self._repo_mensaje.crear(mensaje)

        # DEBUG: Confirmar que el mensaje se creó
        print(f"[DEBUG-SAVE] Mensaje creado: ID={mensaje.id}, conv={conversacion_id}, contenido='{contenido[:50]}...' client_id={client_id}")

        # Actualizar ultimo mensaje de la conversacion
        self._repo_conversacion.actualizar_ultimo_mensaje(
            conversacion_id,
            contenido,
            mensaje.creado_en
        )

        # Incrementar no leidos para otros participantes
        self._incrementar_no_leidos(conversacion_id, remitente_id)

        return RespuestaChat(
            exito=True,
            mensaje="Mensaje enviado",
            datos={'mensaje': MensajeDTO.desde_entidad(mensaje).__dict__}
        )

    def editar_mensaje(
        self,
        mensaje_id: int,
        usuario_id: int,
        nuevo_contenido: str
    ) -> RespuestaChat:
        """Edita un mensaje existente."""
        mensaje = self._repo_mensaje.buscar_por_id(mensaje_id)
        if not mensaje:
            return RespuestaChat(exito=False, mensaje="Mensaje no encontrado")

        if not mensaje.puede_editar(usuario_id):
            return RespuestaChat(exito=False, mensaje="No puedes editar este mensaje")

        if len(nuevo_contenido) > ConstantesChat.MAX_LONGITUD_MENSAJE:
            return RespuestaChat(
                exito=False,
                mensaje=f"Mensaje muy largo (max {ConstantesChat.MAX_LONGITUD_MENSAJE})"
            )

        mensaje.editar(nuevo_contenido)
        self._repo_mensaje.actualizar(mensaje)

        return RespuestaChat(
            exito=True,
            mensaje="Mensaje editado",
            datos={'mensaje': MensajeDTO.desde_entidad(mensaje).__dict__}
        )

    def eliminar_mensaje(
        self,
        mensaje_id: int,
        usuario_id: int,
        para_todos: bool = False
    ) -> RespuestaChat:
        """Elimina un mensaje."""
        mensaje = self._repo_mensaje.buscar_por_id(mensaje_id)
        if not mensaje:
            return RespuestaChat(exito=False, mensaje="Mensaje no encontrado")

        # Verificar si es moderador
        participante = self._repo_participante.buscar_en_conversacion(
            mensaje.conversacion_id, usuario_id
        )
        es_moderador = participante and participante.es_moderador()

        if not mensaje.puede_eliminar(usuario_id, es_moderador):
            return RespuestaChat(exito=False, mensaje="No puedes eliminar este mensaje")

        self._repo_mensaje.eliminar(mensaje_id, para_todos)

        return RespuestaChat(exito=True, mensaje="Mensaje eliminado")

    def marcar_leido(
        self,
        conversacion_id: int,
        usuario_id: int,
        hasta_mensaje_id: Optional[int] = None
    ) -> RespuestaChat:
        """Marca mensajes como leidos."""
        if not hasta_mensaje_id:
            # Obtener ultimo mensaje
            mensajes = self._repo_mensaje.obtener_mensajes(conversacion_id, 1)
            if mensajes:
                hasta_mensaje_id = mensajes[0].id

        if hasta_mensaje_id:
            self._repo_participante.marcar_leido(
                conversacion_id, usuario_id, hasta_mensaje_id
            )

        return RespuestaChat(exito=True, mensaje="Marcado como leido")

    def enviar_mensaje_con_archivos(
        self,
        conversacion_id: int,
        remitente_id: int,
        archivos: List[Dict[str, Any]],
        tipo_media: str,
        contenido: Optional[str] = None
    ) -> RespuestaChat:
        """
        Envia un mensaje con archivos multimedia.

        Args:
            conversacion_id: ID de la conversacion
            remitente_id: ID del remitente
            archivos: Lista de archivos con estructura:
                [{'ruta': str, 'nombre': str, 'tamanio': int, 'tipo_mime': str,
                  'ancho': int (opcional), 'alto': int (opcional),
                  'duracion': int (opcional), 'miniatura_ruta': str (opcional)}]
            tipo_media: Tipo de media (image, video, audio, document, gif)
            contenido: Texto opcional del mensaje

        Returns:
            RespuestaChat con el mensaje creado
        """
        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, remitente_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso a esta conversacion")

        # Validar cantidad de archivos
        if len(archivos) > ConstantesChat.MAX_ARCHIVOS_POR_MENSAJE:
            return RespuestaChat(
                exito=False,
                mensaje=f"Maximo {ConstantesChat.MAX_ARCHIVOS_POR_MENSAJE} archivos por mensaje"
            )

        # Mapear tipo
        tipo_media_enum = {
            'image': TipoMedia.IMAGEN,
            'video': TipoMedia.VIDEO,
            'audio': TipoMedia.AUDIO,
            'document': TipoMedia.DOCUMENTO,
            'sticker': TipoMedia.STICKER,
            'gif': TipoMedia.GIF
        }.get(tipo_media, TipoMedia.DOCUMENTO)

        # Crear mensaje
        mensaje = Mensaje.crear_con_archivos(
            conversacion_id,
            remitente_id,
            tipo_media_enum,
            contenido
        )
        mensaje = self._repo_mensaje.crear(mensaje)

        # Agregar archivos
        archivos_creados = []
        for i, archivo_data in enumerate(archivos):
            archivo = ArchivoMensaje(
                id=None,
                mensaje_id=mensaje.id,
                tipo=tipo_media_enum,
                ruta=archivo_data['ruta'],
                nombre=archivo_data['nombre'],
                tamanio=archivo_data['tamanio'],
                tipo_mime=archivo_data['tipo_mime'],
                ancho=archivo_data.get('ancho'),
                alto=archivo_data.get('alto'),
                duracion=archivo_data.get('duracion'),
                miniatura_ruta=archivo_data.get('miniatura_ruta'),
                orden=i
            )
            archivo = self._repo_archivo.crear(archivo)
            archivos_creados.append(archivo)

        mensaje.archivos = archivos_creados

        # Preview para ultimo mensaje
        previews = {
            TipoMedia.IMAGEN: "Imagen",
            TipoMedia.VIDEO: "Video",
            TipoMedia.AUDIO: "Audio",
            TipoMedia.DOCUMENTO: "Documento",
            TipoMedia.STICKER: "Sticker",
            TipoMedia.GIF: "GIF"
        }
        preview = previews.get(tipo_media_enum, "Archivo")
        if contenido:
            preview = f"{preview}: {contenido[:50]}"

        # Actualizar ultimo mensaje
        self._repo_conversacion.actualizar_ultimo_mensaje(
            conversacion_id,
            preview,
            mensaje.creado_en
        )

        # Incrementar no leidos
        self._incrementar_no_leidos(conversacion_id, remitente_id)

        return RespuestaChat(
            exito=True,
            mensaje="Mensaje enviado",
            datos={'mensaje': mensaje.to_dict()}
        )

    def enviar_ubicacion(
        self,
        conversacion_id: int,
        remitente_id: int,
        latitud: float,
        longitud: float,
        nombre: Optional[str] = None,
        direccion: Optional[str] = None
    ) -> RespuestaChat:
        """
        Envia un mensaje con ubicacion.

        Args:
            conversacion_id: ID de la conversacion
            remitente_id: ID del remitente
            latitud: Latitud de la ubicacion
            longitud: Longitud de la ubicacion
            nombre: Nombre del lugar (opcional)
            direccion: Direccion formateada (opcional)

        Returns:
            RespuestaChat con el mensaje creado
        """
        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, remitente_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso a esta conversacion")

        try:
            ubicacion = UbicacionMensaje(
                latitud=latitud,
                longitud=longitud,
                nombre=nombre,
                direccion=direccion
            )
        except ValueError as e:
            return RespuestaChat(exito=False, mensaje=str(e))

        # Crear mensaje
        mensaje = Mensaje.crear_ubicacion(
            conversacion_id,
            remitente_id,
            ubicacion
        )
        mensaje = self._repo_mensaje.crear(mensaje)

        # Preview para ultimo mensaje
        preview = f"Ubicacion: {nombre or direccion or 'Compartida'}"

        # Actualizar ultimo mensaje
        self._repo_conversacion.actualizar_ultimo_mensaje(
            conversacion_id,
            preview,
            mensaje.creado_en
        )

        # Incrementar no leidos
        self._incrementar_no_leidos(conversacion_id, remitente_id)

        return RespuestaChat(
            exito=True,
            mensaje="Ubicacion enviada",
            datos={'mensaje': mensaje.to_dict()}
        )

    def enviar_contacto(
        self,
        conversacion_id: int,
        remitente_id: int,
        nombre: str,
        telefono: Optional[str] = None,
        email: Optional[str] = None,
        organizacion: Optional[str] = None,
        cargo: Optional[str] = None
    ) -> RespuestaChat:
        """
        Envia un mensaje con informacion de contacto.

        Args:
            conversacion_id: ID de la conversacion
            remitente_id: ID del remitente
            nombre: Nombre del contacto
            telefono: Telefono (opcional, pero requerido si no hay email)
            email: Email (opcional, pero requerido si no hay telefono)
            organizacion: Organizacion (opcional)
            cargo: Cargo (opcional)

        Returns:
            RespuestaChat con el mensaje creado
        """
        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, remitente_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso a esta conversacion")

        try:
            contacto = ContactoMensaje(
                nombre=nombre,
                telefono=telefono,
                email=email,
                organizacion=organizacion,
                cargo=cargo
            )
        except ValueError as e:
            return RespuestaChat(exito=False, mensaje=str(e))

        # Crear mensaje
        mensaje = Mensaje.crear_contacto(
            conversacion_id,
            remitente_id,
            contacto
        )
        mensaje = self._repo_mensaje.crear(mensaje)

        # Preview para ultimo mensaje
        preview = f"Contacto: {nombre}"

        # Actualizar ultimo mensaje
        self._repo_conversacion.actualizar_ultimo_mensaje(
            conversacion_id,
            preview,
            mensaje.creado_en
        )

        # Incrementar no leidos
        self._incrementar_no_leidos(conversacion_id, remitente_id)

        return RespuestaChat(
            exito=True,
            mensaje="Contacto enviado",
            datos={'mensaje': mensaje.to_dict()}
        )

    def enviar_gif(
        self,
        conversacion_id: int,
        remitente_id: int,
        url_gif: str,
        contenido: Optional[str] = None
    ) -> RespuestaChat:
        """
        Envia un mensaje con GIF.

        Args:
            conversacion_id: ID de la conversacion
            remitente_id: ID del remitente
            url_gif: URL del GIF (puede ser de Giphy, Tenor, etc.)
            contenido: Texto opcional

        Returns:
            RespuestaChat con el mensaje creado
        """
        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, remitente_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso a esta conversacion")

        if not url_gif:
            return RespuestaChat(exito=False, mensaje="URL del GIF es requerida")

        # [A-1] La URL se acepta tal cual y luego el cliente la mete en el HTML del
        # mensaje. Una URL con comillas rompia el atributo y ejecutaba codigo en el
        # navegador de TODOS los participantes, en el mismo dominio del correo.
        # Solo se admite la galeria LOCAL: desde que se quito Tenor, no hay motivo
        # para aceptar direcciones externas.
        if not _url_gif_local(url_gif):
            return RespuestaChat(exito=False, mensaje="Origen del GIF no permitido")

        # Crear mensaje
        mensaje = Mensaje.crear_gif(
            conversacion_id,
            remitente_id,
            url_gif,
            contenido
        )
        mensaje = self._repo_mensaje.crear(mensaje)

        # DEBUG: Confirmar que el GIF se creó
        print(f"[DEBUG-SAVE-GIF] GIF creado: ID={mensaje.id}, conv={conversacion_id}, url={url_gif[:60]}...")

        # Preview para ultimo mensaje
        preview = "GIF"
        if contenido:
            preview = f"GIF: {contenido[:50]}"

        # Actualizar ultimo mensaje
        self._repo_conversacion.actualizar_ultimo_mensaje(
            conversacion_id,
            preview,
            mensaje.creado_en
        )

        # Incrementar no leidos
        self._incrementar_no_leidos(conversacion_id, remitente_id)

        return RespuestaChat(
            exito=True,
            mensaje="GIF enviado",
            datos={'mensaje': mensaje.to_dict()}
        )

    # =========================================================================
    # REACCIONES
    # =========================================================================

    def agregar_reaccion(
        self,
        mensaje_id: int,
        usuario_id: int,
        emoji: str
    ) -> RespuestaChat:
        """Agrega una reaccion a un mensaje."""
        mensaje = self._repo_mensaje.buscar_por_id(mensaje_id)
        if not mensaje:
            return RespuestaChat(exito=False, mensaje="Mensaje no encontrado")

        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            mensaje.conversacion_id, usuario_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso")

        reaccion = ReaccionMensaje(
            id=None,
            mensaje_id=mensaje_id,
            usuario_id=usuario_id,
            emoji=emoji
        )
        self._repo_reaccion.agregar(reaccion)

        return RespuestaChat(exito=True, mensaje="Reaccion agregada")

    def eliminar_reaccion(
        self,
        mensaje_id: int,
        usuario_id: int
    ) -> RespuestaChat:
        """Elimina la reaccion de un usuario a un mensaje."""
        self._repo_reaccion.eliminar(mensaje_id, usuario_id)
        return RespuestaChat(exito=True, mensaje="Reaccion eliminada")

    def obtener_reacciones_mensaje(self, mensaje_id: int) -> RespuestaChat:
        """Obtiene las reacciones agrupadas de un mensaje."""
        try:
            reacciones = self._repo_reaccion.obtener_reacciones_mensaje(mensaje_id)

            # Agrupar por emoji
            reacciones_agrupadas = {}
            for r in reacciones:
                emoji = r.emoji
                if emoji not in reacciones_agrupadas:
                    reacciones_agrupadas[emoji] = {
                        'emoji': emoji,
                        'count': 0,
                        'user_ids': []
                    }
                reacciones_agrupadas[emoji]['count'] += 1
                reacciones_agrupadas[emoji]['user_ids'].append(r.usuario_id)

            return RespuestaChat(
                exito=True,
                mensaje="Reacciones obtenidas",
                datos={'reacciones': list(reacciones_agrupadas.values())}
            )
        except Exception as e:
            return RespuestaChat(exito=False, mensaje=f"Error: {str(e)}")

    # =========================================================================
    # PARTICIPANTES
    # =========================================================================

    def agregar_participante(
        self,
        conversacion_id: int,
        admin_id: int,
        usuario_id: int
    ) -> RespuestaChat:
        """Agrega un participante a un grupo."""
        conv = self._repo_conversacion.buscar_por_id(conversacion_id)
        if not conv or not conv.es_grupo():
            return RespuestaChat(exito=False, mensaje="Grupo no encontrado")

        # Verificar permisos del admin
        # [A-5] `activo`: un participante EXPULSADO seguia pasando esta comprobacion,
        # porque la busqueda no miraba si continuaba en el grupo.
        admin = self._repo_participante.buscar_en_conversacion(conversacion_id, admin_id)
        if not admin or not admin.activo or not admin.puede_agregar_miembros():
            return RespuestaChat(exito=False, mensaje="No tienes permisos")

        # Verificar bloqueos
        if self._repo_bloqueo.hay_bloqueo_mutuo(admin_id, usuario_id):
            return RespuestaChat(exito=False, mensaje="No puedes agregar a este usuario")

        # Verificar limite
        participantes = self._repo_participante.obtener_participantes(conversacion_id)
        if len(participantes) >= ConstantesChat.MAX_PARTICIPANTES_GRUPO:
            return RespuestaChat(exito=False, mensaje="Grupo lleno")

        # Verificar si ya es participante
        existente = self._repo_participante.buscar_en_conversacion(conversacion_id, usuario_id)
        if existente and existente.activo:
            return RespuestaChat(exito=False, mensaje="Ya es miembro del grupo")

        if existente:
            # Reactivar
            existente.activo = True
            existente.unido_en = datetime.now()
            self._repo_participante.actualizar(existente)
        else:
            # Agregar nuevo
            self._repo_participante.agregar(Participante(
                id=None,
                conversacion_id=conversacion_id,
                usuario_id=usuario_id,
                rol=RolParticipante.MIEMBRO,
                activo=True,
                unido_en=datetime.now()
            ))

        # Mensaje de sistema
        self._repo_mensaje.crear(Mensaje.crear_sistema(
            conversacion_id,
            f"Usuario agregado al grupo"
        ))

        return RespuestaChat(exito=True, mensaje="Participante agregado")

    def eliminar_participante(
        self,
        conversacion_id: int,
        admin_id: int,
        usuario_id: int
    ) -> RespuestaChat:
        """Elimina un participante de un grupo."""
        # [A-5] Igual que al agregar: quien ya no esta en el grupo no expulsa a nadie.
        admin = self._repo_participante.buscar_en_conversacion(conversacion_id, admin_id)
        if not admin or not admin.activo or not admin.puede_expulsar_miembros():
            return RespuestaChat(exito=False, mensaje="No tienes permisos")

        # No puede expulsarse a si mismo
        if admin_id == usuario_id:
            return RespuestaChat(exito=False, mensaje="Usa 'salir del grupo'")

        self._repo_participante.desactivar(conversacion_id, usuario_id)

        # Mensaje de sistema
        self._repo_mensaje.crear(Mensaje.crear_sistema(
            conversacion_id,
            "Un usuario fue eliminado del grupo"
        ))

        return RespuestaChat(exito=True, mensaje="Participante eliminado")

    def salir_de_grupo(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> RespuestaChat:
        """El usuario sale del grupo."""
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, usuario_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No eres miembro del grupo")

        self._repo_participante.desactivar(conversacion_id, usuario_id)

        # Mensaje de sistema
        self._repo_mensaje.crear(Mensaje.crear_sistema(
            conversacion_id,
            "Un usuario salio del grupo"
        ))

        return RespuestaChat(exito=True, mensaje="Has salido del grupo")

    # =========================================================================
    # PRESENCIA
    # =========================================================================

    def actualizar_presencia(self, usuario_id: int, en_linea: bool = True) -> None:
        """Actualiza la presencia del usuario."""
        self._repo_presencia.actualizar_presencia(usuario_id, en_linea)

    def obtener_presencia(self, usuario_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Obtiene la presencia de multiples usuarios."""
        return self._repo_presencia.obtener_presencia_multiple(usuario_ids)

    # =========================================================================
    # BLOQUEOS
    # =========================================================================

    def bloquear_usuario(
        self,
        bloqueador_id: int,
        bloqueado_id: int,
        razon: Optional[str] = None
    ) -> RespuestaChat:
        """Bloquea a un usuario."""
        if bloqueador_id == bloqueado_id:
            return RespuestaChat(exito=False, mensaje="No puedes bloquearte a ti mismo")

        resultado = self._repo_bloqueo.bloquear(bloqueador_id, bloqueado_id, razon)
        if resultado:
            return RespuestaChat(exito=True, mensaje="Usuario bloqueado")
        return RespuestaChat(exito=False, mensaje="El usuario ya esta bloqueado")

    def desbloquear_usuario(
        self,
        bloqueador_id: int,
        bloqueado_id: int
    ) -> RespuestaChat:
        """Desbloquea a un usuario."""
        resultado = self._repo_bloqueo.desbloquear(bloqueador_id, bloqueado_id)
        if resultado:
            return RespuestaChat(exito=True, mensaje="Usuario desbloqueado")
        return RespuestaChat(exito=False, mensaje="El usuario no estaba bloqueado")

    def obtener_bloqueados(self, usuario_id: int) -> List[int]:
        """Obtiene la lista de usuarios bloqueados."""
        return self._repo_bloqueo.obtener_bloqueados(usuario_id)

    # =========================================================================
    # INDICADORES DE ACCION (ESCRIBIENDO, GRABANDO, ETC.)
    # =========================================================================

    def establecer_accion(
        self,
        conversacion_id: int,
        usuario_id: int,
        accion: str
    ) -> RespuestaChat:
        """
        Establece la accion actual del usuario en una conversacion.

        Acciones validas:
        - typing: Escribiendo mensaje de texto
        - recording_audio: Grabando mensaje de voz
        - recording_video: Grabando video
        - uploading: Subiendo archivo
        - taking_photo: Tomando foto
        - choosing_sticker: Eligiendo sticker
        - none: Sin accion (limpia el estado)

        Args:
            conversacion_id: ID de la conversacion
            usuario_id: ID del usuario
            accion: Tipo de accion

        Returns:
            RespuestaChat con el resultado
        """
        if not self._repo_indicador:
            return RespuestaChat(exito=False, mensaje="Indicadores no disponibles")

        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, usuario_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso")

        # Validar accion
        acciones_validas = [a.value for a in AccionUsuario]
        if accion not in acciones_validas:
            return RespuestaChat(exito=False, mensaje=f"Accion invalida: {accion}")

        # Si es "none", limpiar
        if accion == AccionUsuario.NINGUNA.value:
            self._repo_indicador.limpiar_accion(conversacion_id, usuario_id)
        else:
            self._repo_indicador.establecer_accion(conversacion_id, usuario_id, accion)

        return RespuestaChat(exito=True, mensaje="OK")

    def limpiar_accion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> RespuestaChat:
        """Limpia la accion del usuario (deja de escribir/grabar)."""
        if not self._repo_indicador:
            return RespuestaChat(exito=False, mensaje="Indicadores no disponibles")

        self._repo_indicador.limpiar_accion(conversacion_id, usuario_id)
        return RespuestaChat(exito=True, mensaje="OK")

    def obtener_acciones_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> RespuestaChat:
        """
        Obtiene las acciones activas en una conversacion.

        Retorna quienes estan escribiendo, grabando, etc.
        Excluye al usuario actual de la lista.

        Returns:
            RespuestaChat con lista de acciones:
            {
                'acciones': [
                    {'usuario_id': 1, 'accion': 'typing', 'usuario_nombre': '...'},
                    {'usuario_id': 2, 'accion': 'recording_audio', 'usuario_nombre': '...'}
                ]
            }
        """
        if not self._repo_indicador:
            return RespuestaChat(
                exito=True,
                mensaje="OK",
                datos={'acciones': []}
            )

        # Verificar participacion
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, usuario_id
        )
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="No tienes acceso")

        acciones = self._repo_indicador.obtener_acciones_conversacion(
            conversacion_id,
            excepto_usuario_id=usuario_id
        )

        resultado = []
        for user_id, accion, inicio in acciones:
            resultado.append({
                'usuario_id': user_id,
                'accion': accion,
                'inicio': inicio.isoformat() if inicio else None
            })

        return RespuestaChat(
            exito=True,
            mensaje="OK",
            datos={'acciones': resultado}
        )

    def obtener_texto_accion(self, accion: str, nombre_usuario: str = None) -> str:
        """
        Obtiene el texto descriptivo de una accion.

        Args:
            accion: Tipo de accion
            nombre_usuario: Nombre del usuario (opcional)

        Returns:
            Texto descriptivo como "Juan esta escribiendo..."
        """
        textos = {
            'typing': 'escribiendo...',
            'recording_audio': 'grabando audio...',
            'recording_video': 'grabando video...',
            'uploading': 'subiendo archivo...',
            'taking_photo': 'tomando foto...',
            'choosing_sticker': 'eligiendo sticker...',
        }

        texto = textos.get(accion, 'activo...')

        if nombre_usuario:
            return f"{nombre_usuario} esta {texto}"
        return texto.capitalize()

    # =========================================================================
    # MENSAJES FIJADOS (PIN)
    # =========================================================================

    def fijar_mensaje(self, mensaje_id: int, usuario_id: int) -> RespuestaChat:
        """Fija un mensaje en la conversacion (maximo 3)."""
        mensaje = self._repo_mensaje.buscar_por_id(mensaje_id)
        if not mensaje:
            return RespuestaChat(exito=False, mensaje="Mensaje no encontrado")

        participante = self._repo_participante.buscar_en_conversacion(
            mensaje.conversacion_id, usuario_id)
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="Sin acceso")

        fijados = self._repo_mensaje.obtener_fijados(mensaje.conversacion_id)
        if len(fijados) >= 3:
            return RespuestaChat(exito=False, mensaje="Maximo 3 mensajes fijados")

        self._repo_mensaje.fijar_mensaje(mensaje_id, usuario_id)
        return RespuestaChat(exito=True, mensaje="Mensaje fijado", datos={'mensaje_id': mensaje_id})

    def desfijar_mensaje(self, mensaje_id: int, usuario_id: int) -> RespuestaChat:
        """Desfija un mensaje."""
        mensaje = self._repo_mensaje.buscar_por_id(mensaje_id)
        if not mensaje:
            return RespuestaChat(exito=False, mensaje="Mensaje no encontrado")

        participante = self._repo_participante.buscar_en_conversacion(
            mensaje.conversacion_id, usuario_id)
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="Sin acceso")

        self._repo_mensaje.desfijar_mensaje(mensaje_id)
        return RespuestaChat(exito=True, mensaje="Mensaje desfijado")

    def obtener_mensajes_fijados(self, conversacion_id: int, usuario_id: int) -> RespuestaChat:
        """Obtiene los mensajes fijados de una conversacion."""
        participante = self._repo_participante.buscar_en_conversacion(
            conversacion_id, usuario_id)
        if not participante or not participante.activo:
            return RespuestaChat(exito=False, mensaje="Sin acceso")

        fijados = self._repo_mensaje.obtener_fijados(conversacion_id)
        return RespuestaChat(
            exito=True,
            mensaje="OK",
            datos={'pinned': [m.to_dict() for m in fijados]}
        )

    # =========================================================================
    # UTILIDADES PRIVADAS
    # =========================================================================

    def _incrementar_no_leidos(self, conversacion_id: int, excepto_usuario_id: int) -> None:
        """Incrementa el contador de no leidos para todos excepto el remitente."""
        participantes = self._repo_participante.obtener_participantes(conversacion_id)
        for p in participantes:
            if p.usuario_id != excepto_usuario_id:
                p.mensajes_no_leidos = (p.mensajes_no_leidos or 0) + 1
                self._repo_participante.actualizar(p)
