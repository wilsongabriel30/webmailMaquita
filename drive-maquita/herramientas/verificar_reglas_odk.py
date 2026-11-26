"""Verifica el motor de reglas contra envíos REALES de ODK (Fase 1, 10/11/2026).

Para cada formulario: traduce sus cálculos, condiciones y validaciones, y con las
respuestas de cada envío comprueba que
  · cada cálculo dé lo mismo que guardó ODK (al centavo),
  · toda pregunta con respuesta tenga su condición «mostrar si» cumplida,
  · toda respuesta cumpla su validación.
Además deja los cálculos en un JSON para que el motor de JavaScript los repita.

Uso (VM 101, como sistemas):
  venv/bin/python /home/sistemas/almacen-maquita/herramientas/verificar_reglas_odk.py 41 42 ...
Lee la conexión de solo lectura de ODK de /home/sistemas/Maquita/.env (DB_*). No escribe en ODK.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import psycopg2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', 'servicio'))
import encuestas_reglas as reglas            # noqa: E402
import encuestas_reglas_odk as odk           # noqa: E402

SALIDA_JS = '/tmp/verificar-reglas-odk-calculos.json'


def _entorno():
    d = {}
    for linea in open('/home/sistemas/Maquita/.env', encoding='utf-8'):
        m = re.match(r'^(DB_[A-Z]+)=(.*)$', linea.strip())
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"\'')
    return d


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _binds(xml_form):
    """[(nombre, ruta, calculate, relevant, constraint)] del XForm."""
    raiz = ET.fromstring(xml_form)
    salida = []
    for el in raiz.iter():
        if _local(el.tag) != 'bind':
            continue
        ruta = el.get('nodeset') or ''
        salida.append((ruta.rstrip('/').rsplit('/', 1)[-1], ruta,
                       el.get('calculate'), el.get('relevant'), el.get('constraint')))
    return salida


def _valores(xml_envio):
    """{nombre: texto} de las hojas del envío; los grupos guardan si tienen algo dentro."""
    raiz = ET.fromstring(xml_envio)
    valores, con_algo = {}, set()

    def rec(el, ancestros):
        hijos = list(el)
        nombre = _local(el.tag)
        if hijos:
            for h in hijos:
                rec(h, ancestros + [nombre])
            return
        texto = (el.text or '').strip()
        valores[nombre] = texto
        if texto:
            con_algo.update(ancestros)

    rec(raiz, [])
    return valores, con_algo


def _iguales(odk_valor, propio):
    if (odk_valor or '') == '' and (propio is None or propio == ''):
        return True
    a, b = reglas.a_numero(odk_valor), reglas.a_numero(propio)
    if a is not None and b is not None:
        return abs(a - b) < 0.005
    return (odk_valor or '') == reglas.a_texto(propio)


def verificar(cur, form_id, calculos_js):
    cur.execute('SELECT fd.xml FROM forms f JOIN form_defs fd ON fd.id = f."currentDefId" WHERE f.id = %s', (form_id,))
    fila = cur.fetchone()
    if not fila:
        print(f'form {form_id}: no existe')
        return {}
    binds = _binds(fila[0])
    traducidos, no_traducidos = [], []
    for nombre, ruta, calc, rel, con in binds:
        t = {'nombre': nombre}
        for clave, expr in (('calc', calc), ('rel', rel), ('con', con)):
            if expr:
                try:
                    t[clave] = odk.traducir(expr)
                except odk.NoTraducible as e:
                    no_traducidos.append((nombre, clave, str(e), expr[:80]))
        if len(t) > 1:
            traducidos.append(t)

    cur.execute('''SELECT sd.xml FROM submissions s JOIN submission_defs sd ON sd."submissionId" = s.id AND sd.current
                   WHERE s."formId" = %s AND s."deletedAt" IS NULL AND NOT s.draft''', (form_id,))
    envios = [r[0] for r in cur.fetchall()]
    r = {'envios': len(envios), 'calc_total': 0, 'calc_ok': 0, 'calc_exactos': 0, 'rel_total': 0, 'rel_ok': 0,
         'con_total': 0, 'con_ok': 0, 'no_traducidos': len(no_traducidos)}
    ejemplos = []
    for xml_envio in envios:
        valores, con_algo = _valores(xml_envio)
        for t in traducidos:
            n = t['nombre']
            v = valores.get(n, '')
            if 'calc' in t and n in valores:
                propio = reglas.evaluar(t['calc'], valores)
                r['calc_total'] += 1
                if _iguales(v, propio):
                    r['calc_ok'] += 1
                    if reglas.a_texto(propio) == v or (v == '' and propio is None):
                        r['calc_exactos'] += 1
                elif len(ejemplos) < 8:
                    ejemplos.append(('cálculo', n, v, propio))
                if len(calculos_js) < 200000:
                    calculos_js.append({'regla': t['calc'], 'valores': valores, 'py': propio})
            tiene = bool(v) or n in con_algo
            if 'rel' in t and tiene:
                r['rel_total'] += 1
                if reglas.cumple(t['rel'], valores):
                    r['rel_ok'] += 1
                elif len(ejemplos) < 8:
                    ejemplos.append(('mostrar si', n, v, None))
            if 'con' in t and v:
                r['con_total'] += 1
                if reglas.cumple(t['con'], valores, actual=v):
                    r['con_ok'] += 1
                elif len(ejemplos) < 8:
                    ejemplos.append(('validación', n, v, None))
    print(f"form {form_id}: {r['envios']} envíos | cálculos {r['calc_ok']}/{r['calc_total']} "
          f"(idénticos {r['calc_exactos']}) | mostrar-si {r['rel_ok']}/{r['rel_total']} | "
          f"validaciones {r['con_ok']}/{r['con_total']} | sin traducir {r['no_traducidos']}")
    for e in ejemplos:
        print('   diferencia:', e)
    for nt in no_traducidos[:5]:
        print('   sin traducir:', nt)
    return r


def main():
    e = _entorno()
    con = psycopg2.connect(host=e['DB_HOST'], port=e.get('DB_PORT', 5432), dbname=e['DB_NAME'],
                           user=e['DB_USER'], password=e['DB_PASSWORD'], connect_timeout=10)
    con.set_session(readonly=True)
    calculos_js = []
    total = {}
    with con, con.cursor() as cur:
        for f in sys.argv[1:]:
            for k, v in verificar(cur, int(f), calculos_js).items():
                total[k] = total.get(k, 0) + v
    print('TOTAL', total)
    with open(SALIDA_JS, 'w', encoding='utf-8') as fh:
        json.dump(calculos_js, fh, ensure_ascii=False)
    print(f'{len(calculos_js)} cálculos guardados para el motor JS en {SALIDA_JS}')


if __name__ == '__main__':
    main()
