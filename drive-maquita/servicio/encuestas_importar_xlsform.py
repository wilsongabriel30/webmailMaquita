"""Formularios del Almacén — importar un XLSForm de ODK o Kobo (Fase 1, paso 6, 10/11/2026).

Convierte el Excel de ODK/Kobo en elementos de un `.forma`, con sus reglas y
cálculos, para no reescribir a mano encuestas como la línea base IFA (656 filas)
o la ficha IPS. Lo que no tiene equivalente NO se inventa: se informa fila por
fila para que alguien lo revise en el editor.

Cómo se traduce:
  · Grupos: cada grupo con preguntas abre una SECCIÓN (página), con el título
    de sus grupos («Sección 1 · Lote 2»). El «relevant» del grupo se suma al
    «mostrar si» de cada pregunta de dentro; una página sin nada visible se
    salta al responder.
  · `begin repeat` → pregunta «Repetición» con sus columnas.
  · Tipos: text, integer, decimal, range, select_one, select_multiple, date,
    time, datetime, note, calculate, geopoint, image, audio, video, file.
    Los metadatos (start, end, today, deviceid, username…) se registran solos y
    no se importan como preguntas.
  · required / relevant / constraint (+ mensaje) / calculation, con
    `encuestas_reglas_odk` y `encuestas_xlsform_reglas`.
  · Las etiquetas con `${nombre}` muestran el valor al responder.
  · Los cálculos se importan ocultos (en ODK no se ven) y con 6 decimales,
    para no redondear a mitad de una cadena de cálculos.

Uso: `importar(contenido_xlsx, ocupados=set())` → (bruto, informe). `bruto` va
a `encuestas_modelo.limpiar`, como todo lo demás.
"""
import html
import re
import uuid

import encuestas_xlsform_leer as leer_mod
from encuestas_xlsform_reglas import Traductor

METADATOS = {'start', 'end', 'today', 'deviceid', 'subscriberid', 'simserial', 'phonenumber',
             'username', 'email', 'audit', 'start-geopoint', 'background-audio', 'imei', 'uri:deviceid'}
_GRUPO_INI = {'begin group', 'begin_group'}
_GRUPO_FIN = {'end group', 'end_group'}
_REP_INI = {'begin repeat', 'begin_repeat'}
_REP_FIN = {'end repeat', 'end_repeat'}
_NOMBRE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
_HTML = re.compile(r'</?(span|b|i|u|br|font|p|div|strong|em)\b', re.I)
_SI = {'yes', 'true', 'true()', '1', 'si', 'sí'}
_NO = {'', 'no', 'false', 'false()', '0'}
# Una apariencia escrita por error en la columna «required»: ODK la toma como «no obligatoria».
_APARIENCIAS = {'field-list', 'compact', 'minimal', 'quick', 'horizontal', 'horizontal-compact', 'likert',
                'table-list', 'label', 'list-nolabel', 'list', 'multiline', 'autocomplete'}
DESPLEGABLE_DESDE = 15          # opciones a partir de las cuales se usa desplegable
TITULO_MAX = 480
DECIMALES = 6


def _id():
    return str(uuid.uuid4())


def _rico(texto):
    """Etiqueta de ODK → texto con formato del editor (HTML saneado después por el modelo)."""
    texto = (texto or '').strip()
    if not texto:
        return ''
    if not _HTML.search(texto):
        texto = html.escape(texto, quote=False)
        texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)
        texto = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<i>\1</i>', texto)
        texto = re.sub(r'(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])', r'<i>\1</i>', texto)
    return texto.replace('\r\n', '\n').replace('\n', '<br>')


def _y(arboles):
    arboles = [a for a in arboles if a]
    if not arboles:
        return None
    if len(arboles) == 1:
        return arboles[0]
    planos = []
    for a in arboles:
        planos.extend(a['args'] if a.get('op') == 'y' else [a])
    return {'op': 'y', 'args': planos}


def _parametros(texto):
    return dict(re.findall(r'(\w+)\s*=\s*([^\s]+)', texto or ''))


def _numero(texto):
    try:
        return float(str(texto).replace(',', '.'))
    except (TypeError, ValueError):
        return None


class _Importacion:
    def __init__(self, datos, ocupados):
        self.datos = datos
        self.ocupados = set(ocupados or ())
        self.avisos = []
        self.omitidas = []
        self.elementos = []
        self.mapa = {}                # id → {odk: nombre en ODK, opciones: {código: etiqueta}}
        self.cuenta = {'preguntas': 0, 'secciones': 0, 'mostrar_si': 0, 'obligatoria_si': 0,
                       'validar': 0, 'calculo': 0}
        self.opciones = {}            # lista → [(código, etiqueta)] sin etiquetas repetidas
        for lista, pares in datos['choices'].items():
            vistas, limpias = set(), []
            for codigo, etiqueta in pares:
                etiqueta = re.sub(r'<[^>]+>', '', etiqueta).strip()[:300] or codigo
                if etiqueta in vistas:
                    etiqueta = f'{etiqueta} ({codigo})'[:300]
                vistas.add(etiqueta)
                limpias.append((codigo, etiqueta))
            self.opciones[lista] = limpias

    def aviso(self, fila, nombre, texto):
        self.avisos.append({'fila': fila, 'nombre': nombre, 'texto': texto})

    # ------------------------------------------------------------ nombres
    def _nombres(self):
        """{nombre ODK: nombre importado} de todas las filas con nombre, y las listas de cada select."""
        nombres, usados, opciones_de = {}, set(self.ocupados), {}
        for fila, d in self.datos['survey']:
            original = d.get('name', '')
            tipo = d.get('type', '').strip()
            if not original or tipo.lower() in _GRUPO_INI | _GRUPO_FIN | _REP_FIN or tipo in METADATOS:
                continue
            nuevo = original if _NOMBRE.match(original) else re.sub(r'[^A-Za-z0-9_]', '_', original)
            if not re.match(r'^[A-Za-z_]', nuevo):
                nuevo = 'p_' + nuevo
            nuevo = nuevo[:64]
            base, n = nuevo, 2
            while nuevo in usados:
                sufijo = f'_{n}'
                nuevo, n = base[:64 - len(sufijo)] + sufijo, n + 1
            if nuevo != original:
                self.aviso(fila, original, f'Se renombró a «{nuevo}» (nombre no válido o repetido).')
            usados.add(nuevo)
            nombres[original] = nuevo
            partes = tipo.split()
            if len(partes) == 2 and partes[0] in ('select_one', 'select_multiple') and partes[1] in self.opciones:
                opciones_de[nuevo] = dict(self.opciones[partes[1]])
        return nombres, opciones_de

    # ------------------------------------------------------------ reglas
    def _regla(self, fila, nombre, expresion, propio=None):
        if not expresion:
            return None
        arbol, avisos = self.trad.traducir(expresion, propio)
        for a in avisos:
            self.aviso(fila, nombre, a)
        return arbol

    def _reglas(self, fila, d, nombre, grupos, tipo):
        reglas = {}
        mostrar = _y(grupos + [self._regla(fila, nombre, d.get('relevant'), nombre)])
        if mostrar:
            reglas['mostrar_si'] = mostrar
        req = (d.get('required') or '').strip()
        if req.lower() in _APARIENCIAS:
            self.aviso(fila, nombre, f'En «required» dice «{req}» (una apariencia, no una condición): '
                                     'como en ODK, no es obligatoria.')
        elif tipo not in ('nota', 'calculo') and req.lower() not in _SI | _NO:
            arbol = self._regla(fila, nombre, req, nombre)
            if arbol:
                reglas['obligatoria_si'] = arbol
        if d.get('constraint') and tipo not in ('nota', 'calculo'):
            arbol = self._regla(fila, nombre, d['constraint'], nombre)
            if arbol:
                reglas['validar'] = {'regla': arbol,
                                     'mensaje': re.sub(r'<[^>]+>', '', d.get('constraint_message') or '')[:300]
                                     or 'La respuesta no es válida.'}
        if d.get('calculation'):
            if tipo == 'calculo':
                arbol = self._regla(fila, nombre, d['calculation'], nombre)
                if arbol:
                    reglas['calculo'] = arbol
            else:
                self.aviso(fila, nombre, 'Tiene «calculation» sin ser un cálculo (valor por omisión dinámico): '
                                         'no se importó.')
        for clave in self.cuenta:
            if clave in reglas:
                self.cuenta[clave] += 1
        return reglas

    # ------------------------------------------------------------ preguntas
    def _pregunta(self, fila, d, grupos):
        tipo_raw = re.sub(r'\s+', ' ', d.get('type', '').strip())
        partes = tipo_raw.split(' ')
        t = partes[0].lower()
        arg = partes[1] if len(partes) > 1 else ''
        original = d.get('name', '')
        nombre = self.nombres.get(original)
        apariencia = (d.get('appearance') or '').lower()
        if t in METADATOS:
            self.omitidas.append({'fila': fila, 'nombre': original, 'motivo': f'metadato «{t}»: se registra solo'})
            return None
        p = {'clase': 'pregunta', 'id': _id(), 'nombre': nombre,
             'obligatoria': (d.get('required') or '').strip().lower() in _SI}
        titulo, avisos_t = self.trad.texto(d.get('label'))
        ayuda, avisos_a = self.trad.texto(d.get('hint'))
        for a in avisos_t + avisos_a:
            self.aviso(fila, original, a)
        if t in ('select_one', 'select_multiple', 'rank'):
            if arg not in self.opciones:
                self.aviso(fila, original, f'La lista de opciones «{arg}» no está en la hoja choices.')
                return None
            etiquetas = [e for _, e in self.opciones[arg]]
            if t == 'select_one':
                largo = len(etiquetas) >= DESPLEGABLE_DESDE
                p['tipo'] = 'desplegable' if (largo or 'minimal' in apariencia or 'autocomplete' in apariencia) \
                    else 'opcion_unica'
            else:
                p['tipo'] = 'casillas'
                if t == 'rank':
                    self.aviso(fila, original, '«rank» (ordenar opciones) se importó como casillas.')
            p['opciones'] = etiquetas
            if d.get('choice_filter'):
                self.aviso(fila, original, 'Tiene «choice_filter» (opciones en cascada): se muestran todas. '
                                           'Para cascadas usa una «Lista desde archivo».')
        elif t in ('select_one_from_file', 'select_multiple_from_file'):
            p['tipo'] = 'texto_corto'
            self.aviso(fila, original, f'Elige de «{arg}»: súbelo al Drive y cambia la pregunta a «Lista desde archivo».')
        elif t == 'text':
            p['tipo'] = 'parrafo' if 'multiline' in apariencia else 'texto_corto'
        elif t in ('integer', 'decimal', 'range'):
            p['tipo'] = 'numero'
            p['numero_decimales'] = 0 if t == 'integer' else DECIMALES
            if t == 'range':
                par = _parametros(d.get('parameters'))
                p['numero_min'], p['numero_max'] = _numero(par.get('start', 0)), _numero(par.get('end', 10))
                paso = _numero(par.get('step', 1))
                p['numero_decimales'] = 0 if paso is not None and float(paso).is_integer() else DECIMALES
        elif t == 'date':
            p['tipo'] = 'fecha'
        elif t == 'datetime':
            p['tipo'], p['fecha_con_hora'] = 'fecha', True
        elif t == 'time':
            p['tipo'] = 'hora'
        elif t == 'note':
            p['tipo'] = 'nota'
            if not titulo:
                motivo = 'nota sin texto (solo imagen)' if d.get('media_image') else 'nota vacía'
                self.omitidas.append({'fila': fila, 'nombre': original, 'motivo': motivo})
                return None
        elif t == 'calculate':
            p['tipo'] = 'calculo'
            p['calculo_decimales'] = DECIMALES
            p['calculo_oculto'] = True
            titulo = titulo or original
        elif t == 'geopoint':
            p['tipo'] = 'gps'
        elif t in ('image', 'audio', 'video', 'file'):
            p['tipo'] = 'archivo'
            p['archivo_foto'] = t == 'image'
            p['archivo_tipos'] = {'image': ['imagen'], 'audio': ['audio'], 'video': ['video']}.get(t, [])
        elif t in ('barcode', 'acknowledge', 'trigger'):
            p['tipo'] = 'texto_corto' if t == 'barcode' else 'casillas'
            if t != 'barcode':
                p['opciones'] = ['Confirmo']
            self.aviso(fila, original, f'«{t}» no existe aquí: se importó como {p["tipo"].replace("_", " ")}.')
        elif t == 'hidden':
            self.omitidas.append({'fila': fila, 'nombre': original, 'motivo': 'campo oculto («hidden»)'})
            return None
        else:
            self.aviso(fila, original, f'El tipo «{tipo_raw}» no se reconoce: no se importó.')
            return None
        if d.get('media_image') and t != 'note':
            self.aviso(fila, original, 'Tiene una imagen en la etiqueta: no se importó; agrégala en el editor.')
        if d.get('default'):
            self.aviso(fila, original, f'Valor por omisión «{d["default"]}» no importado.')
        largo = _rico(titulo)
        if len(re.sub(r'<[^>]+>', '', largo)) > TITULO_MAX:
            self.aviso(fila, original, 'La etiqueta es muy larga: se recortó; el texto completo quedó en la ayuda.')
            ayuda = titulo + ('\n' + ayuda if ayuda else '')
            largo = _rico(titulo[:TITULO_MAX] + '…')
        p['titulo'] = largo or original or 'Pregunta sin título'
        p['ayuda'] = _rico(ayuda)[:2000]
        p['reglas'] = self._reglas(fila, d, original, grupos, p['tipo'])
        self.mapa[p['id']] = {'odk': original, 'tipo': p['tipo'],
                              'opciones': dict(self.opciones.get(arg, [])) if t.startswith('select') else None}
        if p['tipo'] in ('nota', 'calculo'):
            p['obligatoria'] = False
        return p

    def _campo_repeticion(self, fila, d, rep):
        """Una pregunta dentro de un begin repeat → columna de la Repetición."""
        p = self._pregunta(fila, d, [])
        if not p:
            return
        if p['tipo'] not in ('texto_corto', 'numero', 'cedula', 'opcion_unica', 'desplegable', 'casillas', 'fecha'):
            self.aviso(fila, d.get('name'), f'«{p["tipo"]}» no cabe dentro de una repetición: no se importó.')
            return
        r = p.get('reglas') or {}
        if any(k in r for k in ('mostrar_si', 'obligatoria_si', 'validar')):
            self.aviso(fila, d.get('name'), 'Las reglas por fila dentro de una repetición todavía no se importan.')
        campo = {k: p[k] for k in ('id', 'nombre', 'tipo', 'obligatoria') if k in p}
        campo['titulo'] = re.sub(r'<[^>]+>', '', p['titulo'])
        for k in ('opciones', 'numero_decimales', 'numero_min', 'numero_max'):
            if k in p:
                campo[k] = p[k]
        rep['campos'].append(campo)

    # ------------------------------------------------------------ recorrido
    def ejecutar(self):
        self.nombres, opciones_de = self._nombres()
        self.trad = Traductor(self.nombres, opciones_de)
        pila = []                     # grupos abiertos: {nombre, titulo, regla}
        seccion_de = None             # a qué tramo de grupos corresponde la última sección
        rep = None
        for fila, d in self.datos['survey']:
            tipo = re.sub(r'\s+', ' ', d.get('type', '').strip()).lower()
            if not tipo:
                continue
            if tipo in _GRUPO_INI or tipo in _REP_INI:
                regla = self._regla(fila, d.get('name'), d.get('relevant'))
                if tipo in _REP_INI:
                    if rep is not None:
                        self.aviso(fila, d.get('name'), 'Repetición dentro de otra repetición: se juntó con la de fuera.')
                    else:
                        rep = {'clase': 'pregunta', 'id': _id(), 'tipo': 'repeticion',
                               'nombre': self.nombres.get(d.get('name')),
                               'titulo': _rico(d.get('label')) or d.get('name') or 'Repetición',
                               'ayuda': _rico(d.get('hint')), 'campos': [], 'rep_min': 0,
                               'reglas': {'mostrar_si': _y([g['regla'] for g in pila] + [regla])} if
                               _y([g['regla'] for g in pila] + [regla]) else {}}
                        if d.get('repeat_count'):
                            self.aviso(fila, d.get('name'), f'«repeat_count» ({d["repeat_count"]}) no se importa: '
                                                            'pon el máximo de filas en la repetición.')
                        rep['_pila'] = len(pila)
                pila.append({'nombre': d.get('name'), 'titulo': re.sub(r'<[^>]+>', '', d.get('label') or ''),
                             'regla': regla, 'repeticion': tipo in _REP_INI})
                continue
            if tipo in _GRUPO_FIN or tipo in _REP_FIN:
                if not pila:
                    self.aviso(fila, d.get('name'), '«end» sin su «begin»: se ignoró.')
                    continue
                cerrado = pila.pop()
                if cerrado['repeticion'] and rep is not None and rep['_pila'] == len(pila):
                    rep.pop('_pila')
                    if not rep['campos']:
                        self.aviso(fila, rep['nombre'], 'Repetición sin columnas importables: no se importó.')
                    else:
                        self.elementos.append(rep)
                        self.cuenta['preguntas'] += 1
                    rep = None
                continue
            if rep is not None:
                self._campo_repeticion(fila, d, rep)
                continue
            clave = tuple(g['nombre'] for g in pila)
            if clave != seccion_de and (pila or seccion_de):
                titulos = [g['titulo'] for g in pila if g['titulo']]
                if not titulos and pila:      # grupo sin etiqueta: su nombre, legible («seccion_1» → «Seccion 1»)
                    titulos = [(pila[-1]['nombre'] or '').replace('_', ' ').strip().capitalize()]
                self.elementos.append({'clase': 'seccion', 'id': _id(),
                                       'titulo': _rico(' · '.join(t for t in titulos[-2:] if t))[:300] or 'Continuación',
                                       'descripcion': ''})
                self.cuenta['secciones'] += 1
                seccion_de = clave
            p = self._pregunta(fila, d, [g['regla'] for g in pila])
            if p:
                self.elementos.append(p)
                self.cuenta['preguntas'] += 1
        if pila:
            self.aviso(None, pila[-1]['nombre'], 'Hay grupos sin cerrar («end group»); se cerraron al final.')
        # Una sección que se quedó sin preguntas (todas omitidas) no sirve.
        limpios = []
        for i, e in enumerate(self.elementos):
            if e['clase'] == 'seccion':
                siguiente = self.elementos[i + 1] if i + 1 < len(self.elementos) else None
                if not siguiente or siguiente['clase'] == 'seccion':
                    self.cuenta['secciones'] -= 1
                    continue
            limpios.append(e)
        self.elementos = limpios


def importar(contenido, ocupados=None, detalle=False):
    """(bruto para encuestas_modelo.limpiar, informe). Con `detalle`, el informe trae
    `_mapa` (id → nombre y opciones en ODK) para comparar con los envíos de ODK."""
    datos = leer_mod.leer(contenido)
    imp = _Importacion(datos, ocupados)
    imp.ejecutar()
    ajustes = datos['settings']
    bruto = {'titulo': html.escape(ajustes.get('form_title') or 'Formulario importado', quote=False),
             'elementos': imp.elementos}
    informe = dict(imp.cuenta)
    informe.update({
        'avisos': imp.avisos[:500], 'avisos_total': len(imp.avisos),
        'omitidas': imp.omitidas[:500], 'omitidas_total': len(imp.omitidas),
        'formulario_odk': ajustes.get('form_id') or '', 'version_odk': ajustes.get('version') or '',
        'idioma': datos.get('idioma') or '',
    })
    if detalle:
        informe['_mapa'] = imp.mapa
    return bruto, informe
