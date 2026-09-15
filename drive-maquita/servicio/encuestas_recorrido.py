"""Formularios del Almacén — qué secciones recorrió de verdad quien responde.

Con «Ir a la sección según la respuesta», quien contesta «Sí» salta a una
sección y quien contesta «No», a otra. Las preguntas de la sección que NO se
eligió no se ven, así que no pueden exigirse: antes el servidor validaba las
obligatorias de TODO el formulario y rechazaba el envío con «Falta responder…»
por una pregunta que la persona nunca llegó a ver (10/09/2026).

Aquí se rehace el camino con las mismas reglas que sigue la página pública
(`encuesta-responder.js`, funciones `destinoDe` y `destinoDeSeccion`):

  1. Manda la ÚLTIMA pregunta de la página con los saltos encendidos y un
     salto para la opción elegida.
  2. Si ninguna ramifica, manda el «Después de la sección…» de la sección que
     abre la página (o `destino_inicio` en la primera página).
  3. Si tampoco hay, se sigue en orden.

Se calcula con las respuestas que llegan, no con lo que diga el navegador:
quien responde puede mandar lo que quiera saltándose la página.
"""
import encuestas_modelo as modelo


def _elegido(pregunta, valor):
    """La clave de `saltos` que corresponde a lo elegido.

    Lo que no es ninguna de las opciones solo puede venir de «Otro», que
    guarda su salto con la clave `SALTO_OTRO` (10/09/2026).
    """
    if isinstance(valor, list):
        valor = valor[0] if valor else None
    if valor is None or valor == '':
        return None
    valor = str(valor)[:300]
    if valor in (pregunta.get('opciones') or []):
        return valor
    return modelo.SALTO_OTRO if pregunta.get('otro') else valor


def _destino_de(pagina, indice, definicion, respuestas):
    destino = None
    for elemento in pagina:
        if elemento.get('clase') != 'pregunta':
            continue
        saltos = elemento.get('saltos')
        if not saltos or not elemento.get('saltos_activos'):
            continue
        elegido = _elegido(elemento, respuestas.get(elemento['id']))
        if elegido is not None and saltos.get(elegido):
            destino = saltos[elegido]
    if destino:
        return destino
    primero = pagina[0] if pagina else None
    if primero and primero.get('clase') == 'seccion':
        destino = primero.get('destino')
    elif indice == 0:
        destino = definicion.get('destino_inicio')
    return destino if destino and destino != modelo.SALTO_SIGUIENTE else None


def paginas_recorridas(definicion, respuestas):
    """Índices de las páginas por las que pasa quien dio esas respuestas."""
    paginas = modelo.paginas(definicion)
    inicio = {}
    for numero, pagina in enumerate(paginas):
        if pagina and pagina[0].get('clase') == 'seccion':
            inicio[pagina[0]['id']] = numero

    recorridas, actual = [], 0
    # Un salto hacia atrás podría dar vueltas para siempre: una página ya
    # vista corta el recorrido.
    while 0 <= actual < len(paginas) and actual not in recorridas:
        recorridas.append(actual)
        destino = _destino_de(paginas[actual], actual, definicion, respuestas)
        if destino == modelo.SALTO_ENVIAR:
            break
        # Un salto a una sección que ya no existe sigue el orden normal, igual
        # que en la página.
        actual = inicio.get(destino, actual + 1) if destino else actual + 1
    return recorridas


def preguntas_visibles(definicion, respuestas):
    """Ids de las preguntas que quien responde llegó a ver."""
    paginas = modelo.paginas(definicion)
    ids = set()
    for numero in paginas_recorridas(definicion, respuestas):
        ids.update(e['id'] for e in paginas[numero]
                   if e.get('clase') == 'pregunta')
    return ids
