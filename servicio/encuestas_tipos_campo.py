"""Formularios del Almacén — tipos de pregunta para el trabajo de campo (Fase 1, paso 2, 10/11/2026).

  numero   Un número, entero o con decimales, con mínimo y máximo opcionales.
  cedula   Cédula ecuatoriana con dígito verificador (o pasaporte, si se permite).
  nota     Solo texto para leer: no se responde.
  calculo  Un valor que se calcula solo con las respuestas (reglas.calculo).
           Lo que mande el navegador no cuenta: el servidor lo vuelve a calcular.
  gps      Ubicación del teléfono: «lat lon altitud precisión», el mismo formato
           que el geopoint de ODK, para que lo importado y lo nuevo se lean igual.

`completar()` deja la configuración de cada tipo acotada en la definición y
`valor_limpio()` normaliza lo respondido. Ni el modelo ni la página pública
tienen que saber nada más de estos tipos.
"""
import re

import encuestas_reglas as reglas

TIPOS = ('numero', 'cedula', 'nota', 'calculo', 'gps', 'lista', 'repeticion', 'recorrido')
# «Lista desde archivo» necesita al dueño y lo ya respondido: la limpia
# `api_encuestas_publico` con la evaluación de reglas a mano.
CON_CONTEXTO = ('lista',)
SIN_RESPUESTA = ('nota',)          # no se responden
DECIMALES_MAX = 6
NUMERO_TOPE = 1e15
GPS_PRECISION_DEFECTO = 30        # metros
GPS_PRECISION_MAX = 5000
_PASAPORTE = re.compile(r'^[A-Za-z0-9]{5,20}$')


def _plano(texto):
    return re.sub(r'<[^>]+>', '', texto or '').strip()[:80]


def _entero(valor, defecto, minimo, maximo):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return defecto
    return min(max(n, minimo), maximo)


def _numero_o_nada(valor):
    n = a_numero(valor)
    return n if n is not None and abs(n) <= NUMERO_TOPE else None


def a_numero(valor):
    """Número de lo escrito; acepta la coma decimal («3,5»)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, str):
        valor = valor.strip().replace(' ', '')
        if valor.count(',') == 1 and '.' not in valor:
            valor = valor.replace(',', '.')
    return reglas.a_numero(valor)


def completar(pregunta, bruto):
    tipo = pregunta['tipo']
    if tipo == 'lista':
        import encuestas_listas
        return encuestas_listas.completar(pregunta, bruto)
    if tipo == 'repeticion':
        import encuestas_repeticion
        return encuestas_repeticion.completar(pregunta, bruto)
    if tipo == 'recorrido':                # video con recorrido (app): encuestas_tipo_recorrido.py
        import encuestas_tipo_recorrido
        return encuestas_tipo_recorrido.completar(pregunta, bruto)
    if tipo == 'numero':
        pregunta['numero_decimales'] = _entero(bruto.get('numero_decimales'), 0, 0, DECIMALES_MAX)
        minimo, maximo = _numero_o_nada(bruto.get('numero_min')), _numero_o_nada(bruto.get('numero_max'))
        if minimo is not None and maximo is not None and minimo > maximo:
            minimo, maximo = maximo, minimo
        pregunta['numero_min'], pregunta['numero_max'] = minimo, maximo
    elif tipo == 'cedula':
        pregunta['cedula_pasaporte'] = bool(bruto.get('cedula_pasaporte'))
    elif tipo == 'calculo':
        pregunta['calculo_decimales'] = _entero(bruto.get('calculo_decimales'), 2, 0, DECIMALES_MAX)
        pregunta['obligatoria'] = False
        # «Ocultar al responder» (10/11/2026): un cálculo intermedio que no hace falta
        # enseñar, como los `calculate` de ODK. Se sigue calculando y guardando.
        pregunta['calculo_oculto'] = bool(bruto.get('calculo_oculto'))
    elif tipo == 'nota':
        pregunta['obligatoria'] = False
    elif tipo == 'gps':
        pregunta['gps_precision_max'] = _entero(bruto.get('gps_precision_max'), GPS_PRECISION_DEFECTO,
                                                1, GPS_PRECISION_MAX)
    return pregunta


def _como_numero(n, decimales):
    n = reglas._redondear(n, decimales)
    return int(n) if decimales == 0 or float(n).is_integer() else n


def valor_limpio(pregunta, bruto):
    """(valor, error). None = sin responder."""
    tipo, titulo = pregunta['tipo'], _plano(pregunta.get('titulo'))
    if tipo == 'repeticion':
        import encuestas_repeticion
        return encuestas_repeticion.valor_limpio(pregunta, bruto)
    if tipo == 'recorrido':
        import encuestas_tipo_recorrido
        return encuestas_tipo_recorrido.valor_limpio(pregunta, bruto, titulo)
    if tipo in SIN_RESPUESTA or tipo == 'calculo':
        return None, None                 # el cálculo lo pone el servidor
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return None, None

    if tipo == 'numero':
        n = a_numero(bruto) if isinstance(bruto, (str, int, float)) else None
        if n is None or abs(n) > NUMERO_TOPE:
            return None, f'«{titulo}» debe ser un número.'
        dec = pregunta.get('numero_decimales') or 0
        if dec == 0 and not float(n).is_integer():
            return None, f'«{titulo}» debe ser un número entero.'
        if pregunta.get('numero_min') is not None and n < pregunta['numero_min']:
            return None, f'«{titulo}» no puede ser menor que {reglas.a_texto(pregunta["numero_min"])}.'
        if pregunta.get('numero_max') is not None and n > pregunta['numero_max']:
            return None, f'«{titulo}» no puede ser mayor que {reglas.a_texto(pregunta["numero_max"])}.'
        return _como_numero(n, dec), None

    if tipo == 'cedula':
        texto = re.sub(r'[\s\-.]', '', str(bruto))
        if reglas.cedula_valida(texto):
            return texto, None
        if pregunta.get('cedula_pasaporte') and _PASAPORTE.match(texto) and not texto.isdigit():
            return texto.upper(), None
        return None, (f'«{titulo}»: la cédula no es válida. Revisa los 10 dígitos.'
                      + (' Si es pasaporte, escríbelo con sus letras.' if pregunta.get('cedula_pasaporte') else ''))

    if tipo == 'gps':
        return _gps(pregunta, bruto, titulo)
    return None, None


def _gps(pregunta, bruto, titulo):
    if isinstance(bruto, dict):
        partes = [bruto.get('lat'), bruto.get('lon'), bruto.get('alt', 0), bruto.get('precision', 0)]
    else:
        partes = str(bruto).split()
    numeros = [reglas.a_numero(p) for p in partes[:4]]
    if len(numeros) < 2 or numeros[0] is None or numeros[1] is None:
        return None, f'«{titulo}»: la ubicación no es válida. Vuelve a tomarla.'
    numeros += [0] * (4 - len(numeros))
    lat, lon, alt, prec = [n if n is not None else 0 for n in numeros]
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None, f'«{titulo}»: la ubicación no es válida. Vuelve a tomarla.'
    tope = pregunta.get('gps_precision_max') or GPS_PRECISION_DEFECTO
    if prec and prec > tope:
        return None, (f'«{titulo}»: la ubicación es poco precisa (±{round(prec)} m; se pide ±{tope} m). '
                      'Sal a un lugar abierto, espera unos segundos y vuelve a tomarla.')
    return ' '.join(reglas.a_texto(round(v, d)) for v, d in ((lat, 7), (lon, 7), (alt, 1), (prec, 1))), None


def valor_calculado(pregunta, valor):
    """El resultado de un cálculo, listo para guardar (número redondeado o texto)."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, bool):
        return 'sí' if valor else 'no'
    if isinstance(valor, (int, float)):
        return _como_numero(valor, pregunta.get('calculo_decimales', 2))
    return str(valor)[:2000]


def texto(pregunta, valor):
    """Lo respondido en una línea (hoja de cálculo, correo, tabla)."""
    if pregunta.get('tipo') == 'repeticion':
        import encuestas_repeticion
        return encuestas_repeticion.texto(pregunta, valor)
    if pregunta.get('tipo') == 'recorrido':
        import encuestas_tipo_recorrido
        return encuestas_tipo_recorrido.texto(valor)
    if isinstance(valor, list):
        return ', '.join(str(v) for v in valor)
    return '' if valor is None else str(valor)
