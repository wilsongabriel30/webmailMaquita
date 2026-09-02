# -*- coding: utf-8 -*-
"""Los arreglos de Maquita sobre el editor de hojas, en TODAS sus puertas.

Responsabilidad ÚNICA: decidir qué añadidos lleva una página que abre el editor
(OnlyOffice) y ponerlos, venga esa página de donde venga.

POR QUÉ ASÍ, Y NO EN LAS PLANTILLAS
El editor se abre desde cinco páginas distintas —el Almacén, su enlace público,
y las tres de la Nube antigua (el editor, el enlace público y el visor de un
archivo compartido)— y mañana pueden ser más. Escribir los `<script>` en cada
plantilla obligaba a acordarse de todas, y además una de ellas
(`editor_onlyoffice.html`) se revierte sola cada cierto tiempo y se llevaba el
cambio por delante (31/08/2026).

Aquí se hace UNA vez: cualquier respuesta HTML que arranque el editor recibe los
añadidos. Da igual el archivo, la ruta o quién entre.

NUNCA ROMPE: si algo falla al insertarlos, la página se entrega tal cual. El
editor tiene que abrir siempre, aunque sea sin los añadidos.
"""

import logging

log = logging.getLogger('almacen.arreglos_editor')

VERSION = '20260902-colorcf2'

# Arreglos que van SIEMPRE.
#   editor-ventanas  → la base: alcanza la ventana del editor y avisa al resto.
#                      Va primera.
#   seleccion-total  → con TODO seleccionado (la esquinita), el alto de fila y
#                      el ancho de columna se aplican a toda la hoja.
# (editor-seleccion-hasta-el-final.js queda APAGADO, 01/09/2026: mandaba la
#  selección al extremo de un salto, y eso rompía el avance POR BLOQUES —que es
#  justo lo que se quería—. El archivo sigue ahí por si hiciera falta.)
ARREGLOS = (
    '<!-- Arreglos de Maquita sobre el editor de hojas (01/09/2026):\n'
    '     · con todo seleccionado, alto y ancho se aplican a toda la hoja;\n'
    '     · Ctrl+Shift+flecha selecciona hasta el final de la hoja. -->\n'
    '<script src="/static/js/almacen/editor-ventanas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-diagnostico.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-seleccion-total.js?v={v}"></script>\n'
    '<!-- Listas desplegables desde el clic derecho, con color por valor,'
    ' como en Google Sheets (01/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-menu-cerrar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-rango-a1.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-colores-cf.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-aplicar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-criterios.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-elegir-rango.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-panel.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-formato-celda.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-formato-panel.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-vista-filtro.js?v={v}"></script>\n'
    '<!-- Proteger hojas e intervalos con permisos por persona, como en Google (02/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-proteger-aplicar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-proteger-personas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-proteger-permisos.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-proteger-panel.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-hoja-protegida-candado.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-listas-desplegables.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-desplegable-aspecto.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-pastillas-todas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-pastilla-celda.js?v={v}"></script>\n'
).format(v=VERSION)

# La tarjeta al pulsar un enlace. Se enciende y se apaga aparte (decisión de
# Wilson, 01/09/2026): el resto de arreglos no depende de ella.
TARJETA_DE_ENLACES = True
TARJETA = (
    '<!-- Al pulsar un enlace sale una tarjeta con la informacion, en vez de\n'
    '     saltar al enlace de inmediato (31/08/2026). -->\n'
    '<script src="/static/js/almacen/editor-enlaces.js?v=20260901-enl9"></script>\n'
)

# Marca por la que se reconoce que una página YA los lleva.
_MARCA = 'editor-ventanas.js'

# Lo que delata que una página abre el editor: es quien lo arranca.
_ABRE_EL_EDITOR = 'DocsAPI'


def anadidos() -> str:
    return ARREGLOS + (TARJETA if TARJETA_DE_ENLACES else '')


def poner_en(html: str) -> str:
    """Devuelve el HTML con los añadidos; tal cual si no procede o no se puede."""
    try:
        if not html or _MARCA in html or '</body>' not in html:
            return html
        return html.replace('</body>', anadidos() + '</body>', 1)
    except Exception as excepcion:
        log.warning('No se pudieron anadir los arreglos del editor: %s', excepcion)
        return html


def registrar(app):
    """Engancha los añadidos a CUALQUIER página que arranque el editor.

    Se mira solo el HTML, y solo el que trae `DocsAPI`: una descarga, un JSON o
    una página normal no se tocan.
    """
    @app.after_request
    def _arreglos_del_editor(respuesta):
        try:
            if respuesta.direct_passthrough:
                return respuesta                 # descarga en streaming
            if 'text/html' not in (respuesta.content_type or ''):
                return respuesta
            cuerpo = respuesta.get_data()
            if (_ABRE_EL_EDITOR.encode() not in cuerpo
                    or _MARCA.encode() in cuerpo
                    or b'</body>' not in cuerpo):
                return respuesta
            respuesta.set_data(
                cuerpo.replace(b'</body>', anadidos().encode('utf-8') + b'</body>', 1))
        except Exception as excepcion:
            # La página se entrega igual: el editor tiene que abrir siempre.
            log.warning('Arreglos del editor no aplicados: %s', excepcion)
        return respuesta

    log.info('Arreglos del editor de hojas: activos en todas sus puertas')
    return app
