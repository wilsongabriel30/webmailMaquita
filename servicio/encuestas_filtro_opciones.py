"""Formularios del Almacén — listas que dependen de otra respuesta (11/11/2026).

Un desplegable puede llevar `filtro_opciones`:

    {"pregunta": "provincia", "mapa": {"Napo": ["Archidona", "Tena", …], …}}

«pregunta» es el NOMBRE de otra pregunta del formulario y «mapa» dice qué opciones
de esta se ofrecen según lo que se respondió en aquella. Así el cantón muestra solo
los de la provincia elegida y la parroquia solo las del cantón, sin consultar nada
en línea: sirve en la web y en el teléfono sin señal.

Si la otra pregunta está sin responder, o su respuesta no está en el mapa, se
ofrecen todas las opciones. Una versión de la app que no conozca esta clave la
ignora y muestra la lista completa: nada se rompe.

Lo ponen «Añadir provincia, cantón y parroquia» (encuesta-territorio.js); lo
aplican encuesta-filtro-opciones.js (web) y FiltroOpciones.kt (app).
"""
CLAVE = 'filtro_opciones'
TIPOS = ('desplegable',)
VALORES_MAX = 2000
TEXTO_MAX = 300


def limpiar(pregunta, bruto):
    """Copia a la pregunta ya limpia el filtro que venga, reducido a opciones que existen."""
    crudo = bruto.get(CLAVE)
    if pregunta.get('tipo') not in TIPOS or not isinstance(crudo, dict):
        return pregunta
    padre, mapa = crudo.get('pregunta'), crudo.get('mapa')
    if not isinstance(padre, str) or not padre.strip() or not isinstance(mapa, dict):
        return pregunta
    existen = set(pregunta.get('opciones') or [])
    limpio = {}
    for valor, lista in list(mapa.items())[:VALORES_MAX]:
        if not isinstance(valor, str) or not isinstance(lista, list):
            continue
        quedan = [o for o in lista if isinstance(o, str) and o in existen]
        if valor.strip() and quedan:
            limpio[valor.strip()[:TEXTO_MAX]] = quedan
    if limpio:
        pregunta[CLAVE] = {'pregunta': padre.strip()[:64], 'mapa': limpio}
    return pregunta


def coherencia(elementos):
    """Con todos los elementos ya nombrados: un filtro que apunta a una pregunta que ya no
    existe (o a sí misma) se quita, y la lista vuelve a ofrecer todo. No es un error:
    borrar «Provincia» no debe impedir guardar el formulario."""
    nombres = {e.get('nombre') for e in elementos if e.get('clase') == 'pregunta'}
    for e in elementos:
        filtro = e.get(CLAVE)
        if filtro and (filtro['pregunta'] not in nombres or filtro['pregunta'] == e.get('nombre')):
            del e[CLAVE]
    return elementos
