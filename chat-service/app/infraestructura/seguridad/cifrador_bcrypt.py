# -*- coding: utf-8 -*-
"""
Adaptador: Cifrador Bcrypt - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El código real está en: modulos/autenticacion/infraestructura/seguridad/cifrador_bcrypt.py

Para nuevo código, usar:
    from modulos.autenticacion import CifradorBcrypt

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-04
"""

# Re-exportar desde la nueva ubicación
from modulos.autenticacion.infraestructura.seguridad.cifrador_bcrypt import CifradorBcrypt

__all__ = ['CifradorBcrypt']
