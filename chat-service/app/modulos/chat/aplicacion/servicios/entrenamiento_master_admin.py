# -*- coding: utf-8 -*-
"""
Modificaciones para que el Master Admin pueda entrenar a la IA
con sus respuestas correctas como conocimiento base.
"""

from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EntrenamientoMasterAdmin:
    """
    Sistema para que Master Admin entrene a IA Maquita.
    Las respuestas del admin se marcan como conocimiento base
    para fine-tuning y memoria vectorial.
    """
    
    def __init__(self, db_session):
        self.session = db_session
    
    def es_master_admin(self, usuario_id: int, usuario_rol: str) -> bool:
        """Verifica si el usuario es Master Admin."""
        return usuario_rol.lower() in ['master_admin', 'master', 'administrador', 'admin']
    
    def marcar_como_entrenamiento(self, mensaje_usuario: str, respuesta_ia: str, 
                                  usuario_id: int, conversacion_id: int, 
                                  confirmacion_admin: bool = False) -> dict:
        """
        Marca una interacción como entrenamiento si el usuario es Master Admin.
        
        Args:
            mensaje_usuario: Pregunta del usuario
            respuesta_ia: Respuesta que la IA dio
            usuario_id: ID del usuario
            conversacion_id: ID de la conversación
            confirmacion_admin: Si el admin confirmó que es correcto para entrenar
            
        Returns:
            Dict con resultado del procesamiento
        """
        try:
            # Primero verificar rol del usuario
            rol = self._obtener_rol_usuario(usuario_id)
            if not self.es_master_admin(usuario_id, rol):
                return {
                    'exito': False,
                    'mensaje': 'Usuario no autorizado para entrenar a la IA',
                    'es_entrenamiento': False
                }
            
            # Insertar en tabla de entrenamiento si se confirmó
            if confirmacion_admin:
                # Verificar si ya existe para evitar duplicados
                existente = self.session.execute(
                    text("""
                        SELECT id FROM datos_entrenamiento 
                        WHERE user_input = :pregunta
                        AND fuente_id = :usuario_id
                        LIMIT 1
                    """),
                    {
                        'pregunta': mensaje_usuario.strip(),
                        'usuario_id': usuario_id
                    }
                ).fetchone()
                
                if not existente:
                    # Insertar como datos de entrenamiento
                    self.session.execute(
                        text("""
                            INSERT INTO datos_entrenamiento
                            (tipo, system_prompt, user_input, assistant_output, fuente, 
                             fuente_id, categoria, calidad, usado_en_entrenamiento, fecha_entrenamiento)
                            VALUES
                            (:tipo, :system_prompt, :user_input, :assistant_output, :fuente,
                             :usuario_id, :categoria, :calidad, true, CURRENT_TIMESTAMP)
                        """),
                        {
                            'tipo': 'respuesta_admin',
                            'system_prompt': 'Entrenamiento Master Admin',
                            'user_input': mensaje_usuario.strip(),
                            'assistant_output': respuesta_ia.strip(),
                            'fuente': 'master_admin',
                            'usuario_id': usuario_id,
                            'categoria': 'conocimiento_maquita',
                            'calidad': 10
                        }
                    )
                    
                    self.session.commit()
                    logger.info(f"Entrenamiento guardado por Master Admin {usuario_id}")
                    
                    return {
                        'exito': True,
                        'mensaje': '✅ Respuesta guardada para entrenamiento de IA',
                        'es_entrenamiento': True,
                        'categoria': 'conocimiento_maquita',
                        'calidad': 10
                    }
                else:
                    return {
                        'exito': True,
                        'mensaje': 'ℹ️ Esta respuesta ya estaba guardada para entrenamiento',
                        'es_entrenamiento': True,
                        'actualizado': False
                    }
            
            # Solo marcar en memoria contextual sin confirmación
            self.session.execute(
                text("""
                    INSERT INTO memoria_contextual
                    (usuario_id, tipo, clave, valor, prioridad, fuente, created_at)
                    VALUES
                    (:usuario_id, 'respuesta_admin', :clave, :valor, 10, 'master_admin', CURRENT_TIMESTAMP)
                    ON CONFLICT (usuario_id, clave) DO UPDATE SET
                        valor = EXCLUDED.valor,
                        prioridad = EXCLUDED.prioridad,
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    'usuario_id': usuario_id,
                    'clave': f"admin_{hash(mensaje_usuario) % 100000}",
                    'valor': f"Q: {mensaje_usuario}\nA: {respuesta_ia}"
                }
            )
            
            self.session.commit()
            
            return {
                'exito': True,
                'mensaje': '📝 Respuesta registrada (esperando confirmación para entrenamiento)',
                'es_entrenamiento': False,
                'pendiente_confirmacion': True
            }
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error en entrenamiento Master Admin: {e}")
            return {
                'exito': False,
                'mensaje': f'Error procesando entrenamiento: {str(e)}',
                'es_entrenamiento': False
            }
    
    def _obtener_rol_usuario(self, usuario_id: int) -> str:
        """Obtiene el rol del usuario desde la BD."""
        try:
            # Primero buscar en tabla usuarios (donde está master_admin)
            result = self.session.execute(
                text("SELECT role FROM usuarios WHERE id = :usuario_id LIMIT 1"),
                {'usuario_id': usuario_id}
            ).fetchone()
            
            if result and result[0]:
                return result[0]
            
            # Si no encuentra, buscar en trabajadores
            result = self.session.execute(
                text("SELECT rol FROM trabajadores WHERE id = :usuario_id LIMIT 1"),
                {'usuario_id': usuario_id}
            ).fetchone()
            
            return result[0] if result else ''
        except Exception as e:
            logger.warning(f"Error obteniendo rol usuario {usuario_id}: {e}")
            return ''
    
    def obtener_pendientes_confirmacion(self, usuario_id: int = None) -> list:
        """Obtiene respuestas pendientes de confirmación de Master Admin."""
        try:
            where_clause = ""
            params = {}
            
            if usuario_id:
                where_clause = "WHERE de.usuario_entrenador_id = :usuario_id"
                params['usuario_id'] = usuario_id
            
            result = self.session.execute(
                text(f"""
                    SELECT de.id, de.pregunta, de.respuesta, 
                           de.usuario_entrenador_id, u.nombre_completo,
                           de.created_at
                    FROM datos_entrenamiento de
                    LEFT JOIN usuarios u ON de.usuario_entrenador_id = u.id
                    {where_clause}
                    AND de.status = 'pendiente_confirmacion'
                    ORDER BY de.created_at DESC
                    LIMIT 20
                """),
                params
            ).fetchall()
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error(f"Error obteniendo pendientes: {e}")
            return []
    
    def confirmar_entrenamiento(self, dato_id: int, usuario_id: int, 
                             accion: str = 'aprobar') -> dict:
        """
        Confirma o rechaza un dato de entrenamiento.
        
        Args:
            dato_id: ID del dato de entrenamiento
            usuario_id: ID del usuario que confirma
            accion: 'aprobar' o 'rechazar'
            
        Returns:
            Dict con resultado
        """
        try:
            # Verificar que es Master Admin
            rol = self._obtener_rol_usuario(usuario_id)
            if not self.es_master_admin(usuario_id, rol):
                return {
                    'exito': False,
                    'mensaje': 'No autorizado'
                }
            
            nuevo_status = 'aprobado' if accion == 'aprobar' else 'rechazado'
            
            self.session.execute(
                text("""
                    UPDATE datos_entrenamiento 
                    SET status = :status,
                        revisado_por = :usuario_id,
                        fecha_revision = CURRENT_TIMESTAMP
                    WHERE id = :dato_id
                """),
                {
                    'dato_id': dato_id,
                    'status': nuevo_status,
                    'usuario_id': usuario_id
                }
            )
            
            self.session.commit()
            
            return {
                'exito': True,
                'mensaje': f'✅ Entrenamiento {nuevo_status} correctamente'
            }
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error confirmando entrenamiento: {e}")
            return {
                'exito': False,
                'mensaje': f'Error: {str(e)}'
            }


# Frases de seguridad para detectar comandos de entrenamiento
FRASES_ENTRENAMIENTO = [
    "esto es correcto",
    "aprende esto",
    "guarda como verdad",
    "esta es la respuesta oficial",
    "recuerda esta información",
    "marcar como conocimiento",
    "entrena con esto",
    "guarda para fine-tuning"
]

def detectar_intencion_entrenamiento(mensaje: str, rol_usuario: str) -> tuple:
    """
    Detecta si el Master Admin quiere entrenar a la IA.
    
    Returns:
        tuple: (es_entrenamiento, confianza, frase_detectada)
    """
    if rol_usuario.lower() not in ['master_admin', 'master', 'administrador', 'admin']:
        return False, 0, None
    
    mensaje_lower = mensaje.lower()
    
    for frase in FRASES_ENTRENAMIENTO:
        if frase in mensaje_lower:
            # Buscar si hay una palabra de confirmación explícita
            if any(palabra in mensaje_lower for palabra in ['confirmar', 'guardar definitivamente', 'aprende ya']):
                return True, 1.0, frase
            return True, 0.8, frase
    
    return False, 0, None


def corregir_mensaje_admin(mensaje: str) -> str:
    """
    Corrige ortografía y gramática del mensaje del admin.
    Usa un modelo de lenguaje para corrección.
    """
    try:
        # Aquí podrías integrar un servicio de corrección
        # Por ahora, solo limpieza básica
        mensaje = mensaje.strip()
        
        # Corregir errores comunes
        correcciones = {
            'ala mente': 'alma',
            'alamcenar': 'almacenar',
            'impancable': 'importante',
            'carar': 'crear',
            'guaradar': 'guardar',
            'emvviar': 'enviar'
        }
        
        for error, correccion in correcciones.items():
            mensaje = mensaje.replace(error, correccion)
        
        return mensaje
        
    except:
        return mensaje