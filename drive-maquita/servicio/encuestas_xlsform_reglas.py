"""Formularios del Almacén — fórmulas de un XLSForm adaptadas al formulario importado (Fase 1, paso 6, 10/11/2026).

`encuestas_reglas_odk.traducir` convierte la fórmula XPath en un árbol. Aquí se
ajusta ese árbol al formulario que sale de la importación:

  · Nombres: si un nombre de ODK no vale como nombre de variable (guiones,
    puntos, más de 64 letras) se renombró al importar; las referencias siguen
    al nombre nuevo.
  · Opciones: ODK compara con el NOMBRE de la opción (`${sexo} = 'mujer'`),
    pero en nuestros formularios la respuesta es la ETIQUETA («Mujer»). Las
    comparaciones con una pregunta de opciones, y `selected()`, pasan a la
    etiqueta.
  · Lo que cite algo que no existe (un metadato como `${today}` o una pregunta
    que no se importó) no se inventa: se informa y la regla queda fuera.
  · Usar una pregunta de opciones como NÚMERO (sumar el código de la opción)
    no tiene equivalente, porque la respuesta es la etiqueta: se avisa.
"""
import re

import encuestas_reglas_odk as odk

_ARITMETICA = ('+', '-', '*', '/', 'mod', '<', '<=', '>', '>=')
_FN_NUMERICAS = ('numero', 'suma', 'promedio', 'minimo', 'maximo', 'entero', 'redondear')
_INTERPOLACION = re.compile(r'\$\{([^}\s]+)\}')


class Traductor:
    def __init__(self, nombres, opciones_de):
        """nombres: {nombre en ODK: nombre importado}.
        opciones_de: {nombre importado: {código de opción: etiqueta}} de las preguntas de opciones."""
        self.nombres = nombres
        self.opciones_de = opciones_de

    def traducir(self, expresion, propio=None):
        """(árbol o None, [avisos]). `propio` es el nombre de la pregunta para «.»."""
        try:
            arbol = odk.traducir(expresion)
        except odk.NoTraducible as e:
            return None, [f'No se pudo traducir «{_corto(expresion)}»: {e}']
        if arbol is None:
            return None, []
        avisos = []
        try:
            arbol = self._ajustar(arbol, propio, avisos)
        except _Ausente as e:
            return None, [f'«{_corto(expresion)}» cita «{e}», que no existe en el formulario importado '
                          '(¿un metadato o una pregunta que no se importó?).']
        return arbol, avisos

    def _nombre(self, ref):
        if ref == '.':
            return '.'
        if ref in self.nombres:
            return self.nombres[ref]
        raise _Ausente(ref)

    def _opciones(self, nodo, propio):
        if isinstance(nodo, dict) and 'ref' in nodo:
            nombre = propio if nodo['ref'] == '.' else nodo['ref']
            return nombre, self.opciones_de.get(nombre)
        return None, None

    def _a_etiqueta(self, literal, opciones, nombre, avisos):
        if not isinstance(literal, dict) or not ({'txt', 'num'} & set(literal)):
            return literal
        codigo = literal.get('txt') if 'txt' in literal else _num_texto(literal['num'])
        if codigo == '':
            return literal
        if codigo in opciones:
            return {'txt': opciones[codigo]}
        avisos.append(f'«{nombre}» no tiene la opción «{codigo}»; la comparación se dejó igual.')
        return literal

    def _ajustar(self, nodo, propio, avisos):
        if 'ref' in nodo:
            return {'ref': self._nombre(nodo['ref'])}
        if 'args' not in nodo:
            return nodo
        args = [self._ajustar(a, propio, avisos) for a in nodo['args']]
        clave = nodo.get('op') or nodo.get('fn')
        if clave in ('=', '!=') and len(args) == 2:
            for i in (0, 1):
                nombre, opciones = self._opciones(args[i], propio)
                if opciones:
                    args[1 - i] = self._a_etiqueta(args[1 - i], opciones, nombre, avisos)
                    break
        elif clave == 'incluye' and len(args) == 2:
            nombre, opciones = self._opciones(args[0], propio)
            if opciones:
                args[1] = self._a_etiqueta(args[1], opciones, nombre, avisos)
        if clave in _ARITMETICA or clave in _FN_NUMERICAS:
            for a in args:
                nombre, opciones = self._opciones(a, propio)
                if opciones:
                    avisos.append(f'Usa «{nombre}» (una pregunta de opciones) como número: en ODK eso suma '
                                  'el código de la opción y aquí la respuesta es la etiqueta. Revísalo a mano.')
        salida = dict(nodo)
        salida['args'] = args
        return salida

    def texto(self, texto):
        """Las `${nombre}` de una etiqueta, con los nombres importados. ([avisos])"""
        avisos = []

        def cambiar(m):
            original = m.group(1)
            if original in self.nombres:
                return '${' + self.nombres[original] + '}'
            avisos.append(f'El texto muestra «${{{original}}}», que no existe en el formulario importado.')
            return m.group(0)

        return _INTERPOLACION.sub(cambiar, texto or ''), avisos


class _Ausente(Exception):
    pass


def _num_texto(n):
    return str(int(n)) if isinstance(n, float) and n.is_integer() else str(n)


def _corto(texto, maximo=80):
    texto = re.sub(r'\s+', ' ', str(texto or '')).strip()
    return texto if len(texto) <= maximo else texto[:maximo] + '…'
