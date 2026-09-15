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

VERSION = '20260911-vivo5'

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
    '<script src="/static/js/almacen/editor-contraste.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-colores-cf.js?v={v}"></script>\n'
    '<!-- Los colores de las reglas que aplican a ESTA celda, para el desplegable (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-colores-de-la-celda.js?v={v}"></script>\n'
    '<!-- Quitar de verdad una lista y sus colores en el 9.4 (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-lista-quitar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-aplicar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-criterios.js?v={v}"></script>\n'
    '<!-- Los valores de una lista por intervalo, leídos de sus celdas (también en hojas ocultas) (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-lista-valores-intervalo.js?v={v}"></script>\n'
    '<!-- El globo del gráfico al pasar el cursor, como en Google (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-grafico-globo.js?v={v}"></script>\n'
    '<!-- El panel «Editar gráfico», con las mismas opciones que el de Google (07/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-grafico-controles.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-elegir.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-piezas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-api.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-titulos.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-formato.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-aspecto.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-ejes-api.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-series-api.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-texto.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-tipos.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-datos.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-estilo.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-titulos.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-serie.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-leyenda.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-ejes.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-sec-cuadricula.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-panel.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-grafico-boton.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-elegir-rango.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-panel.js?v={v}"></script>\n'
    '<!-- Listas de «Personas con acceso» (nómina): hoja oculta + intervalo, y el panel que las rellena (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-lista-personas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-lista-panel-personas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-formato-celda.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-formato-panel.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-vista-filtro.js?v={v}"></script>\n'
    '<!-- La barra verde y el menú de vistas de filtro, como en Google (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-vista-filtro-barra.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-vista-filtro-menu.js?v={v}"></script>\n'
    '<!-- Proteger hojas e intervalos con permisos por persona, como en Google (02/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-proteger-aplicar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-proteger-personas.js?v={v}"></script>\n'
    '<!-- Borrar la celda se lleva también su lista; y «@» ofrece a quien tiene acceso (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-borrar-lista.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-arroba-personas.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-proteger-permisos.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-proteger-panel.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-hoja-protegida-candado.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-listas-desplegables.js?v={v}"></script>\n'
    '<!-- Inmovilizar filas y columnas desde el clic derecho, como en Google (10/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-inmovilizar.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-inmovilizar-menu.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-desplegable-aspecto.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-pastillas-todas.js?v={v}"></script>\n'
    '<!-- La pastilla dibujada EN EL LIENZO del editor, parte de la celda (03/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-pastilla-lienzo.js?v={v}"></script>\n'
    '<!-- Un solo botón para abrir la lista: el del editor, apagado (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-boton-nativo-lista.js?v={v}"></script>\n'
    '<!-- «Descargar como → Excel» sale por el Drive: guarda primero y traduce listas y colores (04/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-descarga-drive.js?v={v}"></script>\n'
    '<!-- La pastilla DE COLOR en HTML: respaldo si el editor no admite el lienzo. -->\n'
    '<script src="/static/js/almacen/editor-pastilla-color.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-pastilla-celda.js?v={v}"></script>\n'
    '<!-- Funciones de Excel 365 que el editor no trae: REGEXTEST, REGEXEXTRACT, REGEXREPLACE,\n'
    '     VALUETOTEXT, ENCODEURL, PERCENTOF, TRIMRANGE e INFO (03/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-funciones-excel.js?v={v}"></script>\n'
    # «Crear formulario» desde una hoja: sus respuestas llegan a una
    # hoja de este mismo libro (09/09/2026).
    '<script src="/static/js/almacen/editor-crear-formulario.js?v={v}"></script>\n'
    # Puente con el COMPLEMENTO de OnlyOffice (10/09/2026): recibe el aviso
    # del boton de Extensiones y lanza la creacion desde esta pagina, que es la
    # que conoce la ruta y tiene la sesion.
    '<script src="/static/js/almacen/editor-formulario-complemento.js?v={v}"></script>\n'
    '<!-- Respuestas en vivo: alimenta al complemento residente que escribe en el libro abierto (11/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-respuestas-vivo.js?v={v}"></script>\n'
    '<!-- Latido sobre las matrices ASC: guardado forzado para que el consolidado abierto de otro se actualice en segundos (11/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-consolidado-latido.js?v={v}"></script>\n'
    '<!-- QUERY de Google, para los libros migrados desde Google Sheets (07/09/2026). -->\n'
    '<script src="/static/js/almacen/editor-funcion-query.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-funciones-motor.js?v={v}"></script>\n'
    '<script src="/static/js/almacen/editor-query-derrame.js?v={v}"></script>\n'
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
