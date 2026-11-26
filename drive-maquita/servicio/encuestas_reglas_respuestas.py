"""Formularios del Almacén — las reglas de cada pregunta aplicadas a un envío (Fase 1, paso 2, 10/11/2026).

El navegador oculta preguntas y calcula en vivo, pero quien responde puede
mandar lo que quiera: aquí se decide de verdad, con lo que llegó.

  · mostrar_si falso    → la pregunta no cuenta: su respuesta se descarta y no
                          se exige (como el `relevant` de ODK).
  · obligatoria_si      → se exige solo cuando se cumple.
  · validar             → si hay respuesta y no cumple, se rechaza con su mensaje.
  · calculo             → se calcula aquí; lo que mande el navegador no cuenta.

Las reglas citan las preguntas por su `nombre` (ver encuestas_modelo_reglas.py).
"""
import encuestas_modelo as modelo
import encuestas_modelo_reglas as modelo_reglas
import encuestas_reglas as reglas
import encuestas_tipos_campo as tipos_campo


def _reglas(p):
    return p.get('reglas') or {}


def _crudo(p, valor):
    """Lo enviado, como lo leen las reglas: los números escritos con coma valen."""
    if p.get('tipo') == 'numero' and valor not in (None, ''):
        n = tipos_campo.a_numero(valor) if isinstance(valor, (str, int, float)) else None
        return n if n is not None else valor
    return valor


class Evaluacion:
    def __init__(self, definicion, enviado, hoy=None):
        self.hoy = hoy
        self.preguntas = modelo.preguntas(definicion)
        self.orden = modelo_reglas.orden_calculo(definicion)
        self.por_nombre = {p['nombre']: p for p in self.preguntas if p.get('nombre')}
        self.valores = {p['nombre']: _crudo(p, enviado.get(p['id'])) for p in self.preguntas
                        if p.get('nombre') and p.get('tipo') not in ('calculo', 'repeticion')}
        for p in self.preguntas:            # filas y columnas de cada repetición
            if p.get('tipo') == 'repeticion':
                import encuestas_repeticion
                self.valores.update(encuestas_repeticion.valores_para_reglas(p, enviado.get(p['id'])))
        self.ocultas = set()
        self._calcular()
        # Lo que queda oculto se vacía, en orden, y se recalcula: una pregunta
        # que no se ve no puede seguir mandando en otras reglas ni en cálculos.
        for p in self.preguntas:
            regla = _reglas(p).get('mostrar_si')
            if regla is not None and not self._cumple(regla):
                self.ocultas.add(p['id'])
                if p.get('nombre'):
                    self.valores[p['nombre']] = None
                for c in p.get('campos') or []:
                    if c.get('nombre'):
                        self.valores[c['nombre']] = []
        self._calcular()

    def _cumple(self, regla, actual=None):
        try:
            return reglas.cumple(regla, self.valores, actual=actual, hoy=self.hoy)
        except reglas.ReglaInvalida:
            return False

    def _calcular(self):
        for n in self.orden:
            p = self.por_nombre[n]
            if p['id'] in self.ocultas:
                self.valores[n] = None
                continue
            try:
                bruto = reglas.evaluar(_reglas(p)['calculo'], self.valores, hoy=self.hoy)
            except reglas.ReglaInvalida:
                bruto = None
            self.valores[n] = tipos_campo.valor_calculado(p, bruto)

    def visible(self, p):
        return p['id'] not in self.ocultas

    def obligatoria(self, p):
        if p.get('obligatoria'):
            return True
        regla = _reglas(p).get('obligatoria_si')
        return regla is not None and self._cumple(regla)

    def calculado(self, p):
        return self.valores.get(p.get('nombre')) if p.get('nombre') else None

    def problema(self, p, valor):
        """Mensaje si la respuesta no cumple su regla de validación; '' si está bien."""
        val = _reglas(p).get('validar')
        if not val or valor is None:
            return ''
        return '' if self._cumple(val['regla'], actual=valor) else val['mensaje']

    def padres(self, p):
        """{nombre: valor} de las preguntas que filtran una «Lista desde archivo»."""
        return {f['pregunta']: self.valores.get(f['pregunta']) for f in p.get('lista_filtros') or []}
