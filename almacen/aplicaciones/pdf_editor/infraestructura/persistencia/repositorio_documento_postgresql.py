# -*- coding: utf-8 -*-
"""
Repositorio PostgreSQL para Documentos PDF.

Implementación concreta del puerto IRepositorioDocumento.
"""

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...dominio.entidades.documento_pdf import DocumentoPDF
from ...dominio.repositorios.repositorio_documento import IRepositorioDocumento
from ...dominio.value_objects.tipos_pdf import EstadoDocumento
from .modelos.modelo_documento import ModeloDocumentoPDF


logger = logging.getLogger(__name__)


class RepositorioDocumentoPostgreSQL(IRepositorioDocumento):
    """
    Implementación PostgreSQL del repositorio de documentos.
    """

    def __init__(self, session: Session):
        """
        Inicializa el repositorio.

        Args:
            session: Sesión de SQLAlchemy
        """
        self.session = session

    def guardar(self, documento: DocumentoPDF) -> DocumentoPDF:
        """Guarda un documento (crear o actualizar)."""
        try:
            if documento.id:
                # Actualizar existente
                modelo = self.session.query(ModeloDocumentoPDF).filter_by(
                    id=documento.id
                ).first()

                if modelo:
                    modelo.actualizar_desde_entidad(documento)
                else:
                    modelo = ModeloDocumentoPDF.from_entidad(documento)
                    self.session.add(modelo)
            else:
                # Crear nuevo
                modelo = ModeloDocumentoPDF.from_entidad(documento)
                self.session.add(modelo)

            self.session.flush()
            documento.id = modelo.id

            self.session.commit()
            logger.info(f"Documento guardado: {documento.id}")

            return documento

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error guardando documento: {e}")
            raise

    def obtener_por_id(self, id: int) -> Optional[DocumentoPDF]:
        """Obtiene un documento por ID."""
        modelo = self.session.query(ModeloDocumentoPDF).filter_by(id=id).first()

        if modelo:
            return modelo.to_entidad()
        return None

    def obtener_por_usuario(
        self,
        usuario_id: int,
        incluir_eliminados: bool = False,
        limite: int = 100,
        offset: int = 0
    ) -> List[DocumentoPDF]:
        """Obtiene documentos de un usuario."""
        query = self.session.query(ModeloDocumentoPDF).filter_by(
            usuario_id=usuario_id
        )

        if not incluir_eliminados:
            query = query.filter(
                ModeloDocumentoPDF.estado != EstadoDocumento.ELIMINADO.value
            )

        query = query.order_by(ModeloDocumentoPDF.updated_at.desc())
        query = query.limit(limite).offset(offset)

        return [m.to_entidad() for m in query.all()]

    def buscar(
        self,
        usuario_id: int,
        termino: str,
        limite: int = 50
    ) -> List[DocumentoPDF]:
        """Busca documentos por texto."""
        query = self.session.query(ModeloDocumentoPDF).filter(
            ModeloDocumentoPDF.usuario_id == usuario_id,
            ModeloDocumentoPDF.estado != EstadoDocumento.ELIMINADO.value
        )

        # Buscar en nombre y texto extraído
        termino_like = f"%{termino}%"
        query = query.filter(
            or_(
                ModeloDocumentoPDF.nombre_original.ilike(termino_like),
                ModeloDocumentoPDF.texto_extraido.ilike(termino_like)
            )
        )

        query = query.order_by(ModeloDocumentoPDF.updated_at.desc())
        query = query.limit(limite)

        return [m.to_entidad() for m in query.all()]

    def eliminar(self, id: int) -> bool:
        """Elimina un documento (soft delete)."""
        try:
            modelo = self.session.query(ModeloDocumentoPDF).filter_by(id=id).first()

            if modelo:
                modelo.estado = EstadoDocumento.ELIMINADO.value
                self.session.commit()
                logger.info(f"Documento eliminado (soft): {id}")
                return True

            return False

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error eliminando documento: {e}")
            return False

    def eliminar_permanente(self, id: int) -> bool:
        """Elimina un documento permanentemente."""
        try:
            modelo = self.session.query(ModeloDocumentoPDF).filter_by(id=id).first()

            if modelo:
                self.session.delete(modelo)
                self.session.commit()
                logger.info(f"Documento eliminado permanentemente: {id}")
                return True

            return False

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error eliminando documento permanente: {e}")
            return False

    def contar_por_usuario(self, usuario_id: int) -> int:
        """Cuenta documentos de un usuario."""
        return self.session.query(func.count(ModeloDocumentoPDF.id)).filter(
            ModeloDocumentoPDF.usuario_id == usuario_id,
            ModeloDocumentoPDF.estado != EstadoDocumento.ELIMINADO.value
        ).scalar() or 0

    def obtener_estadisticas(self, usuario_id: int) -> Dict[str, Any]:
        """Obtiene estadísticas del usuario."""
        # Consulta agregada
        resultado = self.session.query(
            func.count(ModeloDocumentoPDF.id).label('total'),
            func.sum(ModeloDocumentoPDF.num_paginas).label('paginas'),
            func.sum(ModeloDocumentoPDF.tamano_bytes).label('espacio'),
            func.count(ModeloDocumentoPDF.id).filter(
                ModeloDocumentoPDF.tiene_ocr == True
            ).label('con_ocr')
        ).filter(
            ModeloDocumentoPDF.usuario_id == usuario_id,
            ModeloDocumentoPDF.estado != EstadoDocumento.ELIMINADO.value
        ).first()

        return {
            'total_documentos': resultado.total or 0,
            'total_paginas': resultado.paginas or 0,
            'espacio_usado_bytes': resultado.espacio or 0,
            'documentos_con_ocr': resultado.con_ocr or 0,
            'total_anotaciones': 0,  # Se calculará con otro repositorio
            'total_formularios': 0
        }

    def actualizar_metadata(self, id: int, metadata: Dict[str, Any]) -> bool:
        """Actualiza metadatos de un documento."""
        try:
            modelo = self.session.query(ModeloDocumentoPDF).filter_by(id=id).first()

            if modelo:
                modelo.metadatos = {**(modelo.metadatos or {}), **metadata}
                self.session.commit()
                return True

            return False

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error actualizando metadata: {e}")
            return False

    def marcar_ocr(self, id: int, texto: str = None) -> bool:
        """Marca un documento como procesado con OCR."""
        try:
            modelo = self.session.query(ModeloDocumentoPDF).filter_by(id=id).first()

            if modelo:
                modelo.tiene_ocr = True
                if texto:
                    modelo.texto_extraido = texto
                self.session.commit()
                return True

            return False

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error marcando OCR: {e}")
            return False
