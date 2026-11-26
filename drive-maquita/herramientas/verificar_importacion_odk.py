"""Verifica el IMPORTADOR de XLSForm contra envíos REALES de ODK (Fase 1, paso 6, 10/11/2026).

Para cada formulario de ODK: toma su Excel original (el que se subió a ODK
Central), lo importa con `encuestas_importar_xlsform`, y pasa cada envío real
por el formulario importado, tal como llegaría desde el enlace web:
  · cada cálculo tiene que dar lo mismo que guardó ODK (al centavo);
  · toda pregunta con respuesta en ODK tiene que estar visible;
  · el envío completo tiene que pasar `_respuestas_limpias` (obligatorias,
    validaciones, tipos), es decir, el servidor lo aceptaría.

Uso (VM 101, como sistemas):
  cd /home/sistemas/Maquita
  venv/bin/python /home/sistemas/almacen-maquita/herramientas/verificar_importacion_odk.py 41 42 80 ...
Solo lee de ODK (conexión de solo lectura DB_* de /home/sistemas/Maquita/.env). No escribe nada.
"""
import collections
import copy
import os
import re
import sys
import xml.etree.ElementTree as ET

import psycopg2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('SERVICIO_ALMACEN') or os.path.join(AQUI, '..', 'servicio'))
import encuestas_reglas as reglas                       # noqa: E402
import encuestas_importar_xlsform as imp                # noqa: E402
import encuestas_modelo as modelo                       # noqa: E402
import encuestas_reglas_respuestas as reglas_resp       # noqa: E402


def _entorno():
    d = {}
    for linea in open('/home/sistemas/Maquita/.env', encoding='utf-8'):
        m = re.match(r'^(DB_[A-Z]+)=(.*)$', linea.strip())
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"\'')
    return d


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _hojas(xml_envio):
    """[(nombre, texto)] de las hojas del envío, en orden (un nombre puede repetirse en grupos distintos)."""
    salida = []

    def rec(el):
        hijos = list(el)
        if hijos:
            for h in hijos:
                if _local(h.tag) != 'meta':
                    rec(h)
        else:
            salida.append((_local(el.tag), (el.text or '').strip()))

    rec(ET.fromstring(xml_envio))
    return salida


def _iguales(odk_valor, propio):
    if (odk_valor or '') == '' and (propio is None or propio == ''):
        return True
    a, b = reglas.a_numero(odk_valor), reglas.a_numero(propio)
    if a is not None and b is not None:
        return abs(a - b) < 0.005
    return (odk_valor or '') == reglas.a_texto(propio)


def verificar(cur, form_id, limpiar_envio):
    cur.execute('SELECT b.content FROM forms f JOIN form_defs fd ON fd.id = f."currentDefId" '
                'JOIN blobs b ON b.id = fd."xlsBlobId" WHERE f.id = %s', (form_id,))
    fila = cur.fetchone()
    if not fila:
        print(f'form {form_id}: sin Excel en ODK')
        return {}
    bruto, informe = imp.importar(bytes(fila[0]), detalle=True)
    mapa = informe.pop('_mapa')
    definicion = modelo.limpiar(bruto)
    preguntas = modelo.preguntas(definicion)
    por_nombre = collections.defaultdict(list)          # nombre ODK → [pregunta] en orden
    for p in preguntas:
        if p['id'] in mapa:
            por_nombre[mapa[p['id']]['odk']].append(p)

    cur.execute('''SELECT sd.xml FROM submissions s JOIN submission_defs sd ON sd."submissionId" = s.id AND sd.current
                   WHERE s."formId" = %s AND s."deletedAt" IS NULL AND NOT s.draft''', (form_id,))
    envios = [r[0] for r in cur.fetchall()]
    r = collections.Counter(envios=len(envios))
    ejemplos = []
    for xml_envio in envios:
        enviado, odk_calc, contestadas = {}, {}, []
        vistos = collections.Counter()
        for nombre, texto in _hojas(xml_envio):
            lista = por_nombre.get(nombre)
            if not lista:
                continue
            k = vistos[nombre]
            vistos[nombre] += 1
            if k >= len(lista):
                continue
            p = lista[k]
            m = mapa[p['id']]
            if p['tipo'] == 'calculo':
                odk_calc[p['id']] = texto
                continue
            if p['tipo'] == 'nota' or texto == '':
                continue
            if m['opciones'] is not None:
                if p['tipo'] == 'casillas':
                    valor = [m['opciones'].get(c, c) for c in texto.split()]
                else:
                    valor = m['opciones'].get(texto, texto)
            else:
                valor = texto
            enviado[p['id']] = valor
            contestadas.append(p)
        ev = reglas_resp.Evaluacion(definicion, enviado)
        for p in preguntas:
            if p['tipo'] != 'calculo' or p['id'] not in odk_calc:
                continue
            r['calc_total'] += 1
            propio = ev.calculado(p) if ev.visible(p) else None
            if _iguales(odk_calc[p['id']], propio):
                r['calc_ok'] += 1
            elif len(ejemplos) < 8:
                ejemplos.append(('cálculo', mapa[p['id']]['odk'], odk_calc[p['id']], propio))
        for p in contestadas:
            r['vis_total'] += 1
            if ev.visible(p):
                r['vis_ok'] += 1
            elif len(ejemplos) < 8:
                ejemplos.append(('oculta con respuesta', mapa[p['id']]['odk'], enviado[p['id']], None))
        # Una pregunta que no aparece en el envío no existía en la versión con que se
        # respondió (se agregó después): no se le exige, como no se le exigió en ODK.
        presentes = set(vistos)
        definicion_envio = definicion
        faltan = [p['id'] for p in preguntas if p['obligatoria'] and ev.visible(p)
                  and mapa.get(p['id'], {}).get('odk') not in presentes]
        if faltan:
            definicion_envio = copy.deepcopy(definicion)
            for p in modelo.preguntas(definicion_envio):
                if p['id'] in faltan:
                    p['obligatoria'] = False
            r['versiones_antiguas'] += 1
        _limpias, error = limpiar_envio(definicion_envio, enviado)
        r['aceptados'] += 0 if error else 1
        if error and len(ejemplos) < 8:
            ejemplos.append(('rechazado', error, None, None))
    print(f"form {form_id}: {r['envios']} envíos | preguntas {informe['preguntas']}, secciones {informe['secciones']}, "
          f"avisos {informe['avisos_total']} | cálculos {r['calc_ok']}/{r['calc_total']} | "
          f"visibles {r['vis_ok']}/{r['vis_total']} | envíos aceptados {r['aceptados']}/{r['envios']} "
          f"(de versiones anteriores: {r['versiones_antiguas']})")
    for e in ejemplos:
        print('   diferencia:', e)
    return r


def main():
    os.chdir(os.environ.get('SERVICIO_ALMACEN') or os.path.join(AQUI, '..', 'servicio'))
    from flask import Flask
    from api_encuestas_publico import _respuestas_limpias
    Flask('verificar').app_context().push()      # _respuestas_limpias responde con jsonify

    def limpiar_envio(definicion, enviado):
        limpias, error = _respuestas_limpias(definicion, enviado)
        if error:
            error = error[0].get_json().get('error') if isinstance(error, tuple) else str(error)
        return limpias, error
    e = _entorno()
    con = psycopg2.connect(host=e['DB_HOST'], port=e.get('DB_PORT', 5432), dbname=e['DB_NAME'],
                           user=e['DB_USER'], password=e['DB_PASSWORD'], connect_timeout=10)
    con.set_session(readonly=True)
    total = collections.Counter()
    with con, con.cursor() as cur:
        for f in sys.argv[1:]:
            total.update(verificar(cur, int(f), limpiar_envio))
    print('TOTAL', dict(total))


if __name__ == '__main__':
    main()
