# -*- coding: utf-8 -*-
"""
Presentación del editor en línea (OnlyOffice): idioma, región y funciones visibles.
====================================================================================
Lo que la CONFIGURACIÓN del editor permite ajustar sin tocar el servidor de documentos.
Lo usan las dos configuraciones (`/onlyoffice/config` y `/onlyoffice/config-public`).

- Idioma de la interfaz: `editorConfig.lang = 'es'` (ya estaba).
- Región (`editorConfig.region`): formato de moneda y fechas en las hojas de cálculo y
  unidades de medida. Sin fijarla, el editor la deduce del idioma.
- Idioma del documento: un documento nuevo sin idioma declarado se muestra como
  «English – United States» en la barra de estado, aunque la interfaz esté en español.
  `plantillas_office` usa `idioma_documento()` para declarar el idioma en los documentos
  y presentaciones en blanco.
- Pestaña «AI»: `customization.ai.disabled`. Queda oculta salvo que la instalación tenga
  un proveedor configurado en el servidor de documentos y lo declare aquí.

Lo que NO se puede cambiar desde aquí (hace falta la edición Developer del servidor de
documentos o intervenir el propio servidor): el logotipo del editor, la ventana
«Acerca de» y la disposición de pestañas (`customization.logo`, `about`, `layout`).

Variables de entorno (opcionales):
  ALMACEN_ONLYOFFICE_REGION   p. ej. es-EC, es-PE, es-CO. Por defecto es-ES.
  ALMACEN_ONLYOFFICE_IA       1 para mostrar la pestaña «AI». Por defecto, oculta.
"""
import os
import re

REGION_POR_DEFECTO = 'es-ES'
_FORMA_REGION = re.compile(r'[a-z]{2}-[A-Z]{2}')
_AFIRMATIVOS = ('1', 'true', 'si', 'sí', 'yes', 'on')


def region() -> str:
    """Región del editor ('es-EC'...). Un valor mal escrito no rompe el editor: se ignora."""
    valor = os.getenv('ALMACEN_ONLYOFFICE_REGION', '').strip()
    return valor if _FORMA_REGION.fullmatch(valor) else REGION_POR_DEFECTO


def idioma_documento() -> str:
    """Idioma que se declara en los documentos nuevos (el mismo de la región)."""
    return region()


def ia_visible() -> bool:
    return os.getenv('ALMACEN_ONLYOFFICE_IA', '').strip().lower() in _AFIRMATIVOS


def personalizacion() -> dict:
    """Claves que se añaden a `editorConfig.customization`."""
    return {'ai': {'disabled': not ia_visible()}}


# Identificador del complemento «AI» del servidor de documentos (el mismo en todas las instalaciones).
COMPLEMENTO_IA = 'asc.{9DC93CDB-B576-4F0C-B55E-FCC9C48DD007}'


def complementos() -> dict:
    """Contenido de `editorConfig.plugins`; vacío si no hay nada que desactivar.

    `customization.ai.disabled` solo lo entienden los servidores de documentos recientes; en uno anterior
    la pestaña seguía a la vista (reprueba de Andes, 15/11/2026). La lista `plugins.disable` es la forma
    larga de lo mismo y se envía también. En un servidor que no admita ninguna de las dos, la pestaña se
    quita en el propio servidor de documentos (ver almacen/README.md).
    """
    return {} if ia_visible() else {'disable': [COMPLEMENTO_IA]}
