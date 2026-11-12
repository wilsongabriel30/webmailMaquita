"""Formularios del Almacén — traductor de fórmulas de ODK/Kobo (XPath) a reglas propias (Fase 1, 10/11/2026).

Sirve para traer las encuestas de ODK y Kobo sin reescribirlas a mano: cada
`calculate`, `relevant` y `constraint` del XForm se convierte en un árbol de
`encuestas_reglas`. Lo que no sabe traducir lo dice con `NoTraducible`, para que
el importador lo marque y alguien lo revise; nunca inventa una regla.

Cubre lo que usan nuestros formularios (inventario del 10/11/2026: if,
string-length, number, selected, regex, concat) y lo más común de XLSForm:
count-selected, coalesce, round, int, not, true/false, today, sum, y los
operadores or, and, =, !=, <, <=, >, >=, +, -, *, div, mod y el menos unario.

Las rutas (/data/seccion/p01, ${p01}, ../p01) se convierten en la referencia
al nombre de la pregunta (el último tramo), que en XLSForm es único.
"""
import html
import re

import encuestas_reglas as reglas


class NoTraducible(ValueError):
    pass


_TOKENS = re.compile(r"""
    \s*(?:
      (?P<num>\d+\.\d*|\.\d+|\d+)
     |(?P<txt>'[^']*'|"[^"]*")
     |(?P<var>\$\{[A-Za-z_][\w.\-]*\})
     |(?P<op>!=|<=|>=|=|<|>|\+|-|\*|\(|\)|,)
     |(?P<ruta>(?:\.\.?/|/)?[A-Za-z_][\w.\-]*(?::[A-Za-z_][\w.\-]*)?(?:/(?:\.\.|[A-Za-z_][\w.\-]*))*|\.\.|\.)
    )""", re.X)

# «y», «o» en español (10/11/2026): las fórmulas del editor se pueden escribir así.
_PALABRAS = {'and', 'or', 'div', 'mod', 'y', 'o'}
_PRECEDENCIA = {'or': 1, 'o': 1, 'and': 2, 'y': 2, '=': 3, '!=': 3, '<': 4, '<=': 4, '>': 4, '>=': 4,
                '+': 5, '-': 5, '*': 6, 'div': 6, 'mod': 6}
_OP_PROPIO = {'or': 'o', 'and': 'y', 'div': '/', 'mod': 'mod', 'y': 'y', 'o': 'o'}

# función XPath → (función propia, cuántos argumentos admite)
_FUNCIONES = {
    'if': 'si', 'string-length': 'longitud', 'number': 'numero', 'selected': 'incluye',
    'count-selected': 'cuantos', 'regex': 'patron', 'concat': 'concatenar', 'coalesce': 'primero_lleno',
    'round': 'redondear', 'int': 'entero', 'today': 'hoy', 'sum': 'suma',
    # Sobre repeticiones (10/11/2026): count(${miembros}), max(${edad}), min(${edad}).
    'count': 'contar', 'max': 'maximo', 'min': 'minimo',
}
# Las funciones también por su nombre en español: si(), suma(), redondear(),
# vacio(), lleno(), edad(), dias_entre(), cedula_valida()… (10/11/2026).
_FUNCIONES.update({f: f for f in reglas.FUNCIONES})


def _tokens(texto):
    pos, salida = 0, []
    texto = texto.strip()
    while pos < len(texto):
        m = _TOKENS.match(texto, pos)
        if not m or m.end() == pos:
            raise NoTraducible(f'No se entiende «{texto[pos:pos + 20]}».')
        pos = m.end()
        tipo = m.lastgroup
        valor = m.group(tipo)
        if tipo == 'ruta' and valor in _PALABRAS:
            tipo = 'op'
        salida.append((tipo, valor))
    return salida


def _nombre(ruta):
    if ruta.startswith('${'):
        return ruta[2:-1]
    if ruta == '.':
        return '.'
    partes = [p for p in ruta.split('/') if p and p not in ('.', '..')]
    if not partes:
        raise NoTraducible(f'Ruta no válida: {ruta}.')
    return partes[-1]


class _Lector:
    def __init__(self, texto):
        self.t = _tokens(texto)
        self.i = 0

    def ver(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def tomar(self, esperado=None):
        tk = self.ver()
        if esperado is not None and tk[1] != esperado:
            raise NoTraducible(f'Se esperaba «{esperado}».')
        self.i += 1
        return tk

    def expresion(self, minimo=0):
        izq = self.unario()
        while True:
            tipo, op = self.ver()
            if tipo != 'op' or op not in _PRECEDENCIA or _PRECEDENCIA[op] <= minimo:
                return izq
            self.tomar()
            der = self.expresion(_PRECEDENCIA[op])
            propio = _OP_PROPIO.get(op, op)
            if propio in ('y', 'o') and izq.get('op') == propio:
                izq['args'].append(der)          # a y b y c → una sola «y» con tres partes
            else:
                izq = {'op': propio, 'args': [izq, der]}

    def unario(self):
        tipo, v = self.ver()
        if tipo == 'op' and v == '-':
            self.tomar()
            return {'op': '-', 'args': [{'num': 0}, self.unario()]}
        return self.primario()

    def primario(self):
        tipo, v = self.tomar()
        if tipo == 'num':
            return {'num': float(v) if '.' in v else int(v)}
        if tipo == 'txt':
            return {'txt': v[1:-1]}
        if tipo == 'var':
            return {'ref': _nombre(v)}
        if tipo == 'op' and v == '(':
            e = self.expresion()
            self.tomar(')')
            return e
        if tipo == 'ruta':
            if self.ver()[1] == '(':           # llamada a función
                self.tomar('(')
                args = []
                if self.ver()[1] != ')':
                    args.append(self.expresion())
                    while self.ver()[1] == ',':
                        self.tomar(',')
                        args.append(self.expresion())
                self.tomar(')')
                return _funcion(v, args)
            return {'ref': _nombre(v)}
        raise NoTraducible(f'No se entiende «{v}».')


def _funcion(nombre, args):
    if nombre in ('true', 'verdadero') and not args:
        return {'bool': True}
    if nombre in ('false', 'falso') and not args:
        return {'bool': False}
    if nombre in ('not', 'no') and len(args) == 1:
        return {'op': 'no', 'args': args}
    propio = _FUNCIONES.get(nombre)
    if not propio:
        raise NoTraducible(f'La función «{nombre}» todavía no se traduce.')
    if propio == 'patron' and not (len(args) == 2 and 'txt' in args[1]):
        raise NoTraducible('regex() con un patrón que no es un texto fijo.')
    return {'fn': propio, 'args': args}


def traducir(expresion):
    """Árbol de reglas equivalente a la expresión XPath. Lanza NoTraducible."""
    if expresion is None or not str(expresion).strip():
        return None
    lector = _Lector(html.unescape(str(expresion)))
    arbol = lector.expresion()
    if lector.i != len(lector.t):
        raise NoTraducible(f'Sobra «{lector.ver()[1]}» al final.')
    try:
        reglas.validar(arbol)
    except reglas.ReglaInvalida as e:
        raise NoTraducible(str(e))
    return arbol
