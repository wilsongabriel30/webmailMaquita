"""Formularios del Almacén — reglas de cada pregunta en la definición (Fase 1, 10/11/2026).

Cada pregunta puede llevar:
  · `nombre`: la variable con la que la nombran las reglas (como el `name` de
    XLSForm: «edad», «p01», «total_hogar»). Se genera sola si falta y no cambia
    al reordenar ni al renombrar el título, para que las reglas no se rompan.
  · `reglas` (opcional; solo se guarda si hay alguna):
      mostrar_si      → la pregunta aparece solo si se cumple
      obligatoria_si  → es obligatoria solo si se cumple
      validar         → {"regla": árbol, "mensaje": texto}; «.» es lo respondido
      calculo         → valor que se calcula a partir de otras respuestas

Los árboles son los de `encuestas_reglas` (cerrados: no se ejecuta código).
`coherencia()` se llama con TODOS los elementos ya limpios: da nombre a quien
no lo tiene, quita repetidos, y rechaza referencias a preguntas que no existen y
cálculos en círculo, con un mensaje que la persona entiende.
"""
import re

import encuestas_reglas as reglas

_NOMBRE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
CLAVES_ARBOL = ('mostrar_si', 'obligatoria_si', 'calculo')
MENSAJE_MAX = 300
TEXTO_MAX = 2000


class ReglasInvalidas(ValueError):
    pass


def _nombre(valor):
    if not isinstance(valor, str):
        return None
    v = valor.strip()
    return v if _NOMBRE.match(v) else None


def _arbol(valor, titulo, que, texto=None):
    """Árbol validado. Si llega `texto` (p. ej. «${hijos} * 2», sintaxis de XLSForm),
    manda el texto: se traduce aquí y el árbol que viniera se descarta."""
    if isinstance(texto, str) and texto.strip():
        import encuestas_reglas_odk as odk
        try:
            valor = odk.traducir(texto.strip()[:TEXTO_MAX])
        except odk.NoTraducible as e:
            raise ReglasInvalidas(f'«{titulo}» ({que}): {e} Revisa la fórmula «{texto.strip()[:80]}».')
    if valor in (None, '', {}):
        return None
    try:
        reglas.validar(valor)
    except reglas.ReglaInvalida as e:
        raise ReglasInvalidas(f'«{titulo}» ({que}): {e}')
    return valor


def completar(pregunta, bruto):
    """Añade `nombre` y `reglas` a una pregunta ya limpia (se llama desde el modelo)."""
    pregunta['nombre'] = _nombre(bruto.get('nombre'))
    crudo = bruto.get('reglas')
    if not isinstance(crudo, dict):
        return pregunta
    titulo = re.sub(r'<[^>]+>', '', pregunta.get('titulo') or '')[:60]
    limpio = {}
    for clave, que in (('mostrar_si', 'mostrar si'), ('obligatoria_si', 'obligatoria si'),
                       ('calculo', 'cálculo')):
        texto = crudo.get(clave + '_texto')
        arbol = _arbol(crudo.get(clave), titulo, que, texto)
        if arbol is not None:
            limpio[clave] = arbol
            if isinstance(texto, str) and texto.strip():
                limpio[clave + '_texto'] = texto.strip()[:TEXTO_MAX]
    val = crudo.get('validar')
    if isinstance(val, dict):
        texto = val.get('texto')
        arbol = _arbol(val.get('regla'), titulo, 'validación', texto)
        if arbol is not None:
            mensaje = val.get('mensaje') if isinstance(val.get('mensaje'), str) else ''
            limpio['validar'] = {'regla': arbol,
                                 'mensaje': mensaje.strip()[:MENSAJE_MAX] or 'La respuesta no es válida.'}
            if isinstance(texto, str) and texto.strip():
                limpio['validar']['texto'] = texto.strip()[:TEXTO_MAX]
    if limpio:
        pregunta['reglas'] = limpio
    return pregunta


def _arboles(pregunta):
    r = pregunta.get('reglas') or {}
    for clave in CLAVES_ARBOL:
        if clave in r:
            yield clave, r[clave]
    if 'validar' in r:
        yield 'validar', r['validar']['regla']


def coherencia(elementos):
    """Nombres únicos y referencias válidas en todo el formulario. Modifica en sitio."""
    preguntas = [e for e in elementos if e.get('clase') == 'pregunta']
    # Las subpreguntas de una «Repetición» también se nombran: en las reglas,
    # su nombre es la columna entera (sum(${edad})).
    nombrables = []
    for p in preguntas:
        nombrables.append(p)
        nombrables.extend(p.get('campos') or [])
    usados = set()
    for p in nombrables:                     # primero se respetan los nombres puestos
        n = p.get('nombre')
        if n and n.lower() not in usados:
            usados.add(n.lower())
        else:
            p['nombre'] = None
    siguiente = 1
    for p in nombrables:                     # luego se numera a quien no tiene
        if not p.get('nombre'):
            while f'p{siguiente}' in usados:
                siguiente += 1
            p['nombre'] = f'p{siguiente}'
            usados.add(p['nombre'])

    por_nombre = {p['nombre']: p for p in preguntas}
    conocidos = {p['nombre'] for p in nombrables}
    for p in preguntas:
        for ref in [f.get('pregunta') for f in p.get('lista_filtros') or []]:
            if ref not in conocidos:
                raise ReglasInvalidas(
                    f'La lista «{_titulo(p)}» se filtra por «{ref}», que no es ninguna pregunta del formulario.')
        for clave, arbol in _arboles(p):
            for ref in reglas.referencias(arbol):
                if ref not in conocidos:
                    raise ReglasInvalidas(
                        f'La regla de «{_titulo(p)}» usa «{ref}», que no es ninguna pregunta del formulario.')
    _sin_circulos(preguntas, por_nombre)
    return elementos


def _titulo(p):
    return re.sub(r'<[^>]+>', '', p.get('titulo') or '')[:60]


def _sin_circulos(preguntas, por_nombre):
    """Un cálculo no puede depender, directa o indirectamente, de sí mismo."""
    deps = {p['nombre']: [r for r in reglas.referencias((p.get('reglas') or {}).get('calculo'))
                          if r in por_nombre and (por_nombre[r].get('reglas') or {}).get('calculo') is not None]
            for p in preguntas if (p.get('reglas') or {}).get('calculo') is not None}
    estado = {}

    def visitar(n, camino):
        estado[n] = 1
        for d in deps.get(n, ()):
            if estado.get(d) == 1:
                ciclo = camino[camino.index(d):] + [d] if d in camino else [n, d]
                raise ReglasInvalidas('Hay cálculos en círculo: ' + ' → '.join(ciclo) + '.')
            if not estado.get(d):
                visitar(d, camino + [d])
        estado[n] = 2

    for n in deps:
        if not estado.get(n):
            visitar(n, [n])


def orden_calculo(definicion):
    """Nombres con cálculo en un orden en que cada uno se calcula después de lo que usa."""
    preguntas = [e for e in definicion.get('elementos') or [] if e.get('clase') == 'pregunta']
    calc = {p['nombre']: p['reglas']['calculo'] for p in preguntas
            if p.get('nombre') and (p.get('reglas') or {}).get('calculo') is not None}
    hecho, salida = set(), []

    def poner(n):
        if n in hecho:
            return
        hecho.add(n)
        for d in reglas.referencias(calc[n]):
            if d in calc:
                poner(d)
        salida.append(n)

    for n in calc:
        poner(n)
    return salida
