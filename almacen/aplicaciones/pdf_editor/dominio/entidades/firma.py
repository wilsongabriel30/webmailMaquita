# -*- coding: utf-8 -*-
"""
Entidad FirmaDigital - Gestión de firmas en PDFs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from ..value_objects.tipos_pdf import TipoFirma


@dataclass
class FirmaDigital:
    """
    Representa una firma digital en un documento PDF.

    Attributes:
        documento_id: ID del documento firmado
        usuario_id: ID del usuario firmante
        pagina: Página donde se ubica la firma
        tipo: Tipo de firma (visual, certificada, etc.)
        posicion: Posición de la firma en la página
        imagen_firma: Imagen de la firma (base64) para firmas visuales
        certificado_info: Información del certificado digital
        timestamp_servidor: Sello de tiempo del servidor
        valida: Indica si la firma es válida
    """

    documento_id: int
    usuario_id: int
    pagina: int
    tipo: TipoFirma
    posicion: Dict[str, float]
    id: Optional[int] = None
    imagen_firma: Optional[str] = None
    certificado_info: Optional[Dict[str, Any]] = None
    timestamp_servidor: Optional[datetime] = None
    valida: Optional[bool] = None
    motivo: Optional[str] = None
    ubicacion: Optional[str] = None
    contacto: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validaciones después de inicialización."""
        if self.pagina < 1:
            raise ValueError("El número de página debe ser al menos 1")

        # Validar que firmas certificadas tengan certificado
        if self.tipo == TipoFirma.CERTIFICADA and not self.certificado_info:
            raise ValueError("Las firmas certificadas requieren información de certificado")

    @property
    def es_visual(self) -> bool:
        """Indica si la firma tiene representación visual."""
        return self.tipo == TipoFirma.VISUAL or self.imagen_firma is not None

    @property
    def es_certificada(self) -> bool:
        """Indica si la firma está certificada digitalmente."""
        return self.tipo in (TipoFirma.CERTIFICADA, TipoFirma.PADES)

    @property
    def tiene_timestamp(self) -> bool:
        """Indica si la firma tiene sello de tiempo."""
        return self.timestamp_servidor is not None

    def establecer_imagen(self, imagen_base64: str) -> None:
        """Establece la imagen de la firma."""
        self.imagen_firma = imagen_base64

    def establecer_certificado(self, info: Dict[str, Any]) -> None:
        """
        Establece la información del certificado.

        Args:
            info: Diccionario con información del certificado
                - emisor: Entidad emisora
                - sujeto: Titular del certificado
                - valido_desde: Fecha inicio validez
                - valido_hasta: Fecha fin validez
                - numero_serie: Número de serie
        """
        self.certificado_info = info

    def establecer_timestamp(self, timestamp: datetime = None) -> None:
        """Establece el sello de tiempo."""
        self.timestamp_servidor = timestamp or datetime.now()

    def marcar_valida(self, valida: bool = True) -> None:
        """Marca el estado de validación de la firma."""
        self.valida = valida

    def obtener_resumen(self) -> Dict[str, Any]:
        """Obtiene un resumen de la firma para visualización."""
        resumen = {
            'tipo': self.tipo.value if isinstance(self.tipo, TipoFirma) else self.tipo,
            'pagina': self.pagina,
            'fecha': self.created_at.isoformat() if self.created_at else None,
            'valida': self.valida,
            'tiene_timestamp': self.tiene_timestamp
        }

        if self.certificado_info:
            resumen['firmante'] = self.certificado_info.get('sujeto', 'Desconocido')
            resumen['emisor'] = self.certificado_info.get('emisor', 'Desconocido')

        return resumen

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'usuario_id': self.usuario_id,
            'pagina': self.pagina,
            'tipo': self.tipo.value if isinstance(self.tipo, TipoFirma) else self.tipo,
            'posicion': self.posicion,
            'imagen_firma': self.imagen_firma,
            'certificado_info': self.certificado_info,
            'timestamp_servidor': self.timestamp_servidor.isoformat() if self.timestamp_servidor else None,
            'valida': self.valida,
            'motivo': self.motivo,
            'ubicacion': self.ubicacion,
            'contacto': self.contacto,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return f"FirmaDigital(id={self.id}, tipo={self.tipo}, valida={self.valida})"
