# -*- coding: utf-8 -*-
"""
Formularios del Almacén — modo cuestionario: calificación

Decide, para cada pregunta con clave, si la respuesta acierta y cuántos puntos
suma. Está en su propio módulo porque aquí viven las decisiones delicadas: qué
cuenta como acertar y qué NO se puede decidir sin una persona delante.

Reglas, y el porqué de cada una:

- **Opción única y desplegable:** acierta si lo elegido está entre las
  correctas. Todo o nada.
- **Casillas:** hay que marcar exactamente las correctas. Ni de menos ni de
  más: dar la mitad de los puntos por marcarlo todo premiaría no saberlo.
- **Respuesta corta:** se compara sin distinguir mayúsculas, tildes ni espacios
  de sobra, contra la lista de respuestas admitidas. Escribir «Quito» donde se
  esperaba «quito» es acertar; el resto de matices los ve una persona.
- **Párrafo, escala, fecha y hora:** NO se califican solas. Quedan pendientes de
  revisión, y sus puntos solo cuentan cuando alguien los otorga. Adivinar si un
  texto largo «acierta» sería inventarse una nota.

Autoría: Equipo de Tecnología Maquita — 2026-08-25
"""
import unicodedata

import encuestas_modelo as modelo


def _normalizar(texto):
    """Para comparar respuestas cortas: sin tildes, sin mayúsculas, sin
    espacios de más. Lo que separa «Quito » de «quito» no es conocimiento."""
    texto = str(texto if texto is not None else '').strip().lower()
    texto = ' '.join(texto.split())
    descompuesto = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in descompuesto
                   if unicodedata.category(c) != 'Mn')


def calificar(definicion, respuestas):
    """Califica una entrega completa.

    Devuelve:
        {
          'puntos': lo obtenido automáticamente,
          'puntos_max': el total posible del cuestionario,
          'pendientes': cuántas preguntas necesitan revisión de una persona,
          'detalle': { id_pregunta: {...} }
        }
    """
    detalle = {}
    obtenidos = 0.0
    maximos = 0.0
    pendientes = 0

    for pregunta in modelo.preguntas(definicion):
        clave = pregunta.get('clave') or {}
        puntos = clave.get('puntos') or 0
        if not puntos:
            continue                    # sin puntos no entra en la nota

        maximos += puntos
        valor = respuestas.get(pregunta['id'])

        if not clave.get('autocalificable'):
            detalle[pregunta['id']] = {
                'estado': 'pendiente', 'puntos': 0, 'posibles': puntos,
            }
            pendientes += 1
            continue

        acierta = _acierta(pregunta, clave, valor)
        ganados = puntos if acierta else 0
        obtenidos += ganados
        detalle[pregunta['id']] = {
            'estado': 'correcta' if acierta else 'incorrecta',
            'puntos': ganados, 'posibles': puntos,
        }

    return {
        'puntos': _entero_si_procede(obtenidos),
        'puntos_max': _entero_si_procede(maximos),
        'pendientes': pendientes,
        'detalle': detalle,
    }


def _acierta(pregunta, clave, valor):
    correctas = clave.get('correctas') or []
    if not correctas:
        # Con puntos pero sin clave marcada no se puede acertar nada; se trata
        # como incorrecta en vez de regalar los puntos.
        return False

    tipo = pregunta['tipo']

    if tipo == 'casillas':
        marcadas = valor if isinstance(valor, list) else ([valor] if valor else [])
        return set(_normalizar(v) for v in marcadas) == \
            set(_normalizar(v) for v in correctas)

    if tipo in ('opcion_unica', 'desplegable'):
        if isinstance(valor, list):
            valor = valor[0] if valor else None
        return _normalizar(valor) in set(_normalizar(v) for v in correctas) \
            if valor is not None else False

    if tipo == 'texto_corto':
        if valor is None or valor == '':
            return False
        return _normalizar(valor) in set(_normalizar(v) for v in correctas)

    return False


def _entero_si_procede(numero):
    return int(numero) if float(numero) == int(numero) else round(float(numero), 2)


def total_posible(definicion):
    """Puntos que reparte el cuestionario, para mostrarlo en el editor."""
    total = 0.0
    for pregunta in modelo.preguntas(definicion):
        total += (pregunta.get('clave') or {}).get('puntos') or 0
    return _entero_si_procede(total)


def para_quien_responde(definicion, calificacion, ajustes):
    """Lo que se le enseña a quien acaba de entregar, según lo configurado.

    Se construye a medida en vez de mandar la calificación entera: si el
    cuestionario no comparte las respuestas correctas, esas respuestas no deben
    salir del servidor, ni siquiera «ocultas» en el JSON.
    """
    if not ajustes.get('ver_puntuacion') and not ajustes.get('ver_falladas') \
            and not ajustes.get('ver_correctas'):
        return None

    salida = {'pendientes': calificacion['pendientes']}

    if ajustes.get('ver_puntuacion'):
        salida['puntos'] = calificacion['puntos']
        salida['puntos_max'] = calificacion['puntos_max']

    if ajustes.get('ver_falladas') or ajustes.get('ver_correctas'):
        preguntas = []
        for pregunta in modelo.preguntas(definicion):
            dato = calificacion['detalle'].get(pregunta['id'])
            if not dato:
                continue
            clave = pregunta.get('clave') or {}
            ficha = {
                'id': pregunta['id'],
                'titulo': pregunta['titulo'],
                'estado': dato['estado'],
                'posibles': dato['posibles'],
            }
            if ajustes.get('ver_puntuacion'):
                ficha['puntos'] = dato['puntos']
            if ajustes.get('ver_correctas'):
                ficha['correctas'] = clave.get('correctas') or []
            # El comentario del profesor sí acompaña siempre al resultado: es
            # la parte que enseña algo.
            comentario = (clave.get('comentario_correcto')
                          if dato['estado'] == 'correcta'
                          else clave.get('comentario_incorrecto'))
            if comentario:
                ficha['comentario'] = comentario
            preguntas.append(ficha)

        # Si solo se comparten las falladas, las acertadas no se envían.
        if not ajustes.get('ver_correctas'):
            preguntas = [p for p in preguntas if p['estado'] != 'correcta']
        salida['preguntas'] = preguntas

    return salida
