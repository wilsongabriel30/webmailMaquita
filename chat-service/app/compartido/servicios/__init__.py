# -*- coding: utf-8 -*-
"""
Servicios Compartidos - Sistema FARO

Servicios transversales utilizados por múltiples módulos.

CAPA: compartido/servicios

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-05
"""

from compartido.servicios.auditoria import AuditService, audit_service
from compartido.servicios.extractor_archivos import ExtractorArchivosService, extractor_archivos

__all__ = [
    'AuditService',
    'audit_service',
    'ExtractorArchivosService',
    'extractor_archivos',
]
