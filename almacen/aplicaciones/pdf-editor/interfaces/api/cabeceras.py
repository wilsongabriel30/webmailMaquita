# -*- coding: utf-8 -*-
"""
Texto que va DENTRO de una cabecera HTTP, sin romper la respuesta.
=================================================================
El editor devuelve el PDF como cuerpo de la respuesta, así que los avisos para
el usuario («se usó una letra equivalente», «5 renglones se ajustaron») viajan
en una cabecera. Pero una cabecera no admite cualquier texto:

  * gunicorn solo deja pasar espacio, tabulador y los códigos 0x21-0xFF
    (`HEADER_VALUE_RE`); una letra griega, cirílica o vietnamita —que aparecen
    en los nombres traducidos de las tipografías que devuelve `fc-match`— hace
    que la respuesta ENTERA se descarte y el navegador reciba un 502;
  * un salto de línea permitiría colar cabeceras falsas.

Aquí se limpia una sola vez, y lo usan todos los sitios que ponen un aviso en
una cabecera. Las tildes y la eñe se conservan: caben de sobra en 0x21-0xFF.

Nació el 19-ago-2026, cuando editar un párrafo con Times New Roman devolvía
502 Bad Gateway.

Autoría: Equipo de Tecnología Maquita — 2026-08-19
"""

LARGO_MAXIMO = 400


def texto_seguro(aviso, largo_maximo=LARGO_MAXIMO):
    """El aviso tal cual, quitándole lo que una cabecera HTTP no admite."""
    if not aviso:
        return ''
    limpio = []
    for letra in str(aviso):
        codigo = ord(letra)
        if letra in ('\t', ' '):
            limpio.append(' ')
        elif 0x21 <= codigo <= 0xFF:
            limpio.append(letra)
        elif codigo in (0x0A, 0x0D):
            limpio.append(' ')
        # lo demás (griego, cirílico, emojis, mandos) sencillamente no va
    salida = ''.join(limpio).strip()
    while '  ' in salida:
        salida = salida.replace('  ', ' ')
    return salida[:largo_maximo]


def poner(respuesta, nombre, aviso, largo_maximo=LARGO_MAXIMO):
    """Pone el aviso en esa cabecera y la deja visible para el navegador.

    Devuelve True si quedó algo que decir. Si tras limpiarlo no queda texto, no
    se pone la cabecera: mejor sin aviso que con una respuesta rota.
    """
    valor = texto_seguro(aviso, largo_maximo)
    if not valor:
        return False
    respuesta.headers[nombre] = valor
    expuestas = respuesta.headers.get('Access-Control-Expose-Headers', '')
    nombres = [n.strip() for n in expuestas.split(',') if n.strip()]
    if nombre not in nombres:
        nombres.append(nombre)
    respuesta.headers['Access-Control-Expose-Headers'] = ', '.join(nombres)
    return True
