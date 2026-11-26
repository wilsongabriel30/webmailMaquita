"""«Exportar» rehace entera la hoja de respuestas cuando su ORDEN de columnas
quedó atrás y la hoja no tiene trabajo propio de la persona.

Por qué (02/10/2026): «Exportar» sobre un Excel que ya existe solo añade filas
y respeta las columnas que encuentra; es lo correcto cuando la persona le puso
fórmulas, pestañas o retoques. Pero cuando cambia la forma de la hoja (la
«Puntuación» pasa a ser la última columna; sin «Quién» si hay pregunta de
nómina), un Excel que el sistema generó y nadie trabajó se quedaba con la forma
vieja para siempre: «el Excel que genero sigue igual que antes».

Se rehace SOLO si se cumplen todas:
- el archivo es solo la hoja de respuestas, sin fórmulas
  (`encuestas_hoja_reparar.se_puede_rehacer`);
- la hoja la alimenta solo este formulario;
- sus encabezados no coinciden, en orden, con los que tendría hoy.
En cualquier otro caso devuelve None y «Exportar» sigue por el camino de
siempre (añadir filas conservando).

Equipo de Tecnología Maquita — 2026-10-02
"""
import logging
import os

log = logging.getLogger('almacen.encuestas.hoja')


def si_cambio_el_orden(fila_encuesta, definicion, usuario, ruta_hoja):
    """El `.xlsx` rehecho (BytesIO) con el estado ya anotado, o None."""
    import encuestas_hoja as hoja_mod
    import encuestas_hoja_libro as libro_mod
    import encuestas_hoja_reparar as reparar
    import encuestas_hoja_xml as xml_mod
    import nucleo_archivos as nucleo
    try:
        fisica = nucleo.ruta_fisica(int(usuario), ruta_hoja)
        if not os.path.isfile(fisica):
            return None
        contenido = open(fisica, 'rb').read()
        if not reparar.se_puede_rehacer(contenido):
            return None
        if not libro_mod._hoja_de_un_solo_formulario(fila_encuesta, ruta_hoja):
            return None
        actuales, _ = xml_mod.leer_tabla(contenido)
        datos = hoja_mod.datos_de_hoja(fila_encuesta, definicion)
        esperadas = hoja_mod.orden_fisico(datos['cabeceras'])
        normal = libro_mod.normalizar
        if [normal(e) for e in actuales] == [normal(e) for e in esperadas]:
            return None
    except Exception as excepcion:
        log.warning('hoja %s: no se pudo comparar el orden (%s)', ruta_hoja, excepcion)
        return None

    memoria = hoja_mod.construir(fila_encuesta, definicion)
    if memoria is None:
        return None
    cabeceras, listado = datos['cabeceras'], datos['listado']
    desplazamiento = len(cabeceras) - len(listado)
    preguntas = {p['id']: {'form': cabeceras[desplazamiento + i],
                           'hoja': cabeceras[desplazamiento + i]}
                 for i, p in enumerate(listado)}
    if 'Puntuación' in cabeceras:
        preguntas[libro_mod.PREFIJO_FIJA + 'PUNTUACION'] = {
            'form': 'Puntuación', 'hoja': 'Puntuación'}
    if 'Correo' in cabeceras:
        preguntas[libro_mod.PREFIJO_FIJA + 'CORREO'] = {'form': 'Correo', 'hoja': 'Correo'}
    ultima = max([e for e in datos['enviadas'] if e] or [None], default=None)
    libro_mod.guardar_estado(definicion['id'], ultima, preguntas)
    log.info('hoja %s rehecha con el orden vigente de columnas', ruta_hoja)
    return memoria
