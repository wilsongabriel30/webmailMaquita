"""Formularios del Almacén — reglas y cálculos de las preguntas (Fase 1, 10/11/2026).

Las reglas («Mostrar si…», «Obligatoria si…», validaciones) y los cálculos se
guardan como un árbol JSON cerrado, nunca como código. El mismo árbol lo
evalúan, con resultados idénticos:

  · este módulo (servidor: vuelve a calcular y validar todo lo que llega),
  · `js/almacen/encuesta-reglas.js` (editor, vista previa y enlace web),
  · la app Android (Fase 3), sin señal.

Los tres pasan el mismo juego de casos: `pruebas/reglas-casos.json`.
Si cambias una regla aquí, cámbiala allá y agrega el caso.

Nodos (un dict con UNA clave de tipo):

  {"num": 3.5}  {"txt": "si"}  {"bool": true}  {"nulo": true}
  {"ref": "<id de pregunta>"}      valor de otra pregunta (vacío = nulo)
  {"ref": "."}                     la pregunta que se valida
  {"op": "+", "args": [a, b, ...]}   + - * / mod   = != > >= < <=   y o no
  {"fn": "<nombre>", "args": [...]}  funciones de FUNCIONES

Reglas de valores (iguales en los tres motores):
  · Números: coma flotante de doble precisión, como ODK.
  · Aritmética con un vacío da vacío; «vacío cuenta como 0» se escribe
    numero(x, 0), que es lo que hacen los formularios de Social en ODK.
  · Dividir entre 0 da vacío.
  · `=` y `!=`: vacío equivale a texto vacío; si los dos lados son números
    (o textos que son números) se comparan como números; si no, como texto.
  · `<`, `>`…: con un vacío dan falso.
  · Verdadero: true, número distinto de 0, texto no vacío, lista no vacía.
"""
import math
import re
from datetime import date

MAX_PROFUNDIDAD = 40
MAX_NODOS = 2000
MAX_PATRON = 200

OPERADORES = ('+', '-', '*', '/', 'mod', '=', '!=', '>', '>=', '<', '<=', 'y', 'o', 'no')
FUNCIONES = ('si', 'vacio', 'lleno', 'numero', 'entero', 'redondear', 'incluye', 'cuantos',
             'suma', 'promedio', 'contar', 'minimo', 'maximo', 'concatenar', 'longitud',
             'patron', 'cedula_valida', 'hoy', 'dias_entre', 'edad', 'primero_lleno')
# Cuántos argumentos admite cada función: (mínimo, máximo o None).
_ARIDAD = {
    'si': (3, 3), 'vacio': (1, 1), 'lleno': (1, 1), 'numero': (1, 2), 'entero': (1, 1),
    'redondear': (1, 2), 'incluye': (2, 2), 'cuantos': (1, 1), 'suma': (1, None),
    'promedio': (1, None), 'contar': (1, None), 'minimo': (1, None), 'maximo': (1, None),
    'concatenar': (1, None), 'longitud': (1, 1), 'patron': (2, 2), 'cedula_valida': (1, 1),
    'hoy': (0, 0), 'dias_entre': (2, 2), 'edad': (1, 1), 'primero_lleno': (1, None),
}
_NUMERO = re.compile(r'^\s*-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$')


class ReglaInvalida(ValueError):
    """El árbol no cumple el formato; el mensaje es apto para mostrar en el editor."""


# ---------------------------------------------------------------- validación

def validar(nodo):
    """Comprueba la forma del árbol (no lo evalúa). Lanza ReglaInvalida."""
    cuenta = [0]

    def ver(n, prof):
        cuenta[0] += 1
        if cuenta[0] > MAX_NODOS:
            raise ReglaInvalida('La regla es demasiado grande.')
        if prof > MAX_PROFUNDIDAD:
            raise ReglaInvalida('La regla tiene demasiados niveles.')
        if not isinstance(n, dict) or len(n) not in (1, 2):
            raise ReglaInvalida('Parte de la regla no se entiende.')
        if 'num' in n:
            if isinstance(n['num'], bool) or not isinstance(n['num'], (int, float)) or not math.isfinite(n['num']):
                raise ReglaInvalida('Número no válido.')
        elif 'txt' in n:
            if not isinstance(n['txt'], str) or len(n['txt']) > 1000:
                raise ReglaInvalida('Texto no válido.')
        elif 'bool' in n:
            if not isinstance(n['bool'], bool):
                raise ReglaInvalida('Valor sí/no no válido.')
        elif 'nulo' in n:
            pass
        elif 'ref' in n:
            if not isinstance(n['ref'], str) or not n['ref'] or len(n['ref']) > 80:
                raise ReglaInvalida('Referencia a una pregunta no válida.')
        elif 'op' in n:
            op, args = n['op'], n.get('args')
            if op not in OPERADORES or not isinstance(args, list):
                raise ReglaInvalida(f'Operación desconocida: {op}.')
            if op == 'no' and len(args) != 1:
                raise ReglaInvalida('«no» lleva una sola condición.')
            if op != 'no' and len(args) < 2:
                raise ReglaInvalida(f'«{op}» necesita al menos dos partes.')
            for a in args:
                ver(a, prof + 1)
        elif 'fn' in n:
            fn, args = n['fn'], n.get('args', [])
            if fn not in FUNCIONES or not isinstance(args, list):
                raise ReglaInvalida(f'Función desconocida: {fn}.')
            minimo, maximo = _ARIDAD[fn]
            if len(args) < minimo or (maximo is not None and len(args) > maximo):
                raise ReglaInvalida(f'«{fn}» con un número de partes no válido.')
            if fn == 'patron':
                p = args[1]
                if not (isinstance(p, dict) and isinstance(p.get('txt'), str) and len(p['txt']) <= MAX_PATRON):
                    raise ReglaInvalida('El patrón debe ser un texto fijo y corto.')
                try:
                    re.compile(p['txt'])
                except re.error:
                    raise ReglaInvalida('El patrón no es válido.')
            for a in args:
                ver(a, prof + 1)
        else:
            raise ReglaInvalida('Parte de la regla no se entiende.')

    ver(nodo, 0)
    return nodo


def referencias(nodo):
    """Ids de las preguntas que usa la regla (para el orden de cálculo y avisos)."""
    vistas = []

    def rec(n):
        if not isinstance(n, dict):
            return
        r = n.get('ref')
        if r and r != '.' and r not in vistas:
            vistas.append(r)
        for a in n.get('args') or ():
            rec(a)

    rec(nodo)
    return vistas


# ---------------------------------------------------------------- valores

def _vacio(v):
    return v is None or v == '' or (isinstance(v, list) and not v)


def a_numero(v):
    """Número o None. Acepta números, textos numéricos y sí/no (1/0)."""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str) and _NUMERO.match(v):
        return float(v)
    return None


def a_texto(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    if isinstance(v, list):
        return ' '.join(a_texto(x) for x in v)
    return str(v)


def verdadero(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0 and not (isinstance(v, float) and math.isnan(v))
    if isinstance(v, (str, list)):
        return len(v) > 0
    return False


def _lista(v):
    """Respuesta de selección múltiple: lista, o texto separado por espacios (como ODK)."""
    if isinstance(v, list):
        return [a_texto(x) for x in v]
    if _vacio(v):
        return []
    return a_texto(v).split()


def _fecha(v):
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(a_texto(v)[:10])
    except ValueError:
        return None


def _comparar(op, a, b):
    if op in ('=', '!='):
        na, nb = a_numero(a), a_numero(b)
        if na is not None and nb is not None:
            igual = na == nb
        elif isinstance(a, list) or isinstance(b, list):
            igual = _lista(a) == _lista(b)
        else:
            igual = a_texto(a) == a_texto(b)
        return igual if op == '=' else not igual
    if _vacio(a) or _vacio(b):
        return False
    na, nb = a_numero(a), a_numero(b)
    if na is not None and nb is not None:
        x, y = na, nb
    else:
        x, y = a_texto(a), a_texto(b)
    return {'>': x > y, '>=': x >= y, '<': x < y, '<=': x <= y}[op]


def _aritmetica(op, args):
    nums = [a_numero(a) for a in args]
    if any(n is None for n in nums):
        return None
    total = nums[0]
    for n in nums[1:]:
        if op == '+':
            total += n
        elif op == '-':
            total -= n
        elif op == '*':
            total *= n
        elif op == '/':
            if n == 0:
                return None
            total /= n
        elif op == 'mod':
            if n == 0:
                return None
            total = math.fmod(total, n)
    return total


def cedula_valida(v):
    """Cédula ecuatoriana: 10 dígitos, provincia 01-24 o 30, tercer dígito < 6 y dígito verificador."""
    t = a_texto(v).strip()
    if not re.fullmatch(r'\d{10}', t):
        return False
    prov = int(t[:2])
    if not (1 <= prov <= 24 or prov == 30) or int(t[2]) >= 6:
        return False
    suma = 0
    for i, c in enumerate(t[:9]):
        d = int(c) * (2 if i % 2 == 0 else 1)
        suma += d - 9 if d > 9 else d
    return (10 - suma % 10) % 10 == int(t[9])


def _redondear(x, dec):
    # Mitad hacia arriba (como ODK y JavaScript), no «al par» de Python.
    f = 10 ** dec
    return math.floor(x * f + 0.5) / f


# ---------------------------------------------------------------- evaluación

def evaluar(nodo, valores, actual=None, hoy=None):
    """Valor de la regla con las respuestas `valores` ({id: valor}).

    `actual` es el valor de la pregunta que se valida ({"ref": "."}).
    `hoy` permite fijar la fecha en las pruebas.
    """
    hoy = hoy or date.today()

    def ev(n):
        if 'num' in n:
            return float(n['num'])
        if 'txt' in n:
            return n['txt']
        if 'bool' in n:
            return n['bool']
        if 'nulo' in n:
            return None
        if 'ref' in n:
            v = actual if n['ref'] == '.' else valores.get(n['ref'])
            return None if _vacio(v) else v
        if 'op' in n:
            op, args = n['op'], n['args']
            if op == 'y':
                return all(verdadero(ev(a)) for a in args)
            if op == 'o':
                return any(verdadero(ev(a)) for a in args)
            if op == 'no':
                return not verdadero(ev(args[0]))
            vals = [ev(a) for a in args]
            if op in ('=', '!=', '>', '>=', '<', '<='):
                # a < b < c se lee como (a < b) y (b < c).
                return all(_comparar(op, vals[i], vals[i + 1]) for i in range(len(vals) - 1))
            return _aritmetica(op, vals)
        return _funcion(n['fn'], n.get('args', []))

    def _funcion(fn, args):
        if fn == 'si':
            return ev(args[1]) if verdadero(ev(args[0])) else ev(args[2])
        if fn == 'hoy':
            return hoy.isoformat()
        vals = [ev(a) for a in args]
        if fn == 'vacio':
            return _vacio(vals[0])
        if fn == 'lleno':
            return not _vacio(vals[0])
        if fn == 'numero':
            n = a_numero(vals[0])
            if n is None and len(vals) > 1:
                return a_numero(vals[1])
            return n
        if fn == 'entero':
            n = a_numero(vals[0])
            return None if n is None else float(math.trunc(n))
        if fn == 'redondear':
            n = a_numero(vals[0])
            d = a_numero(vals[1]) if len(vals) > 1 else 0.0
            return None if n is None or d is None else _redondear(n, int(d))
        if fn == 'incluye':
            return a_texto(vals[1]) in _lista(vals[0])
        if fn == 'cuantos':
            return float(len(_lista(vals[0])))
        if fn in ('suma', 'promedio', 'contar', 'minimo', 'maximo'):
            planos = []
            for v in vals:
                planos.extend(v if isinstance(v, list) else [v])
            nums = [a_numero(v) for v in planos if not _vacio(v)]
            nums = [x for x in nums if x is not None]
            if fn == 'contar':
                return float(len([v for v in planos if not _vacio(v)]))
            if fn == 'suma':
                return float(sum(nums))
            if not nums:
                return None
            if fn == 'promedio':
                return sum(nums) / len(nums)
            return min(nums) if fn == 'minimo' else max(nums)
        if fn == 'concatenar':
            return ''.join(a_texto(v) for v in vals)
        if fn == 'longitud':
            return float(len(a_texto(vals[0])))
        if fn == 'patron':
            return re.search(args[1]['txt'], a_texto(vals[0])) is not None
        if fn == 'cedula_valida':
            return cedula_valida(vals[0])
        if fn == 'dias_entre':
            a, b = _fecha(vals[0]), _fecha(vals[1])
            return None if a is None or b is None else float((b - a).days)
        if fn == 'edad':
            f = _fecha(vals[0])
            if f is None:
                return None
            anos = hoy.year - f.year - ((hoy.month, hoy.day) < (f.month, f.day))
            return float(anos)
        if fn == 'primero_lleno':
            return next((v for v in vals if not _vacio(v)), None)
        raise ReglaInvalida(f'Función desconocida: {fn}.')

    return ev(nodo)


def cumple(nodo, valores, actual=None, hoy=None):
    """Para «Mostrar si», «Obligatoria si» y validaciones. Una regla vacía (None) se cumple."""
    if nodo is None:
        return True
    return verdadero(evaluar(nodo, valores, actual, hoy))
