# -*- coding: utf-8 -*-
"""Prueba del complemento «respuestas en vivo» con el motor REAL del editor.

El complemento escribe dentro del libro abierto con la API del editor. Aquí se
toma su MISMO código (las funciones marcadas en `code.js`) y se ejecuta en el
Document Server (servicio docbuilder) sobre un libro de prueba; después se
comprueba el `.xlsx` que resulta. Casos:

  · tabla VACÍA (sin respuestas): las respuestas entran bajo los encabezados,
    sin duplicarlos ni pisarse (fallo del 29/09/2026);
  · tabla con respuestas: las nuevas se añaden al final;
  · «Verdadero», «6 / 10» y un teléfono con cero inicial quedan como TEXTO.

Trabaja en su propia carpeta de pruebas y borra lo suyo al terminar.

Uso:  python prueba_vivo_complemento.py <usuario> [--dejar] [--codigo <code.js>]

Autoría: Equipo de Tecnología Maquita — 2026-09-29
"""
import io
import json
import os
import re
import secrets
import sys
import time
import uuid
import zipfile
from datetime import datetime

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_libro as libro
import encuestas_hoja_recalculo as recalculo
import encuestas_hoja_xml as xml_mod
import nucleo_archivos as nucleo

CODIGO = ('/home/sistemas/Maquita/interfaces/web/estaticos/onlyoffice-plugins/'
          'respuestas-filas/code.js')
CARPETA = '/PRUEBAS FLUJO'
NOMBRE = 'Prueba vivo %s' % datetime.now().strftime('%H%M%S')
fallos = []


def comprobar(paso, condicion, detalle=''):
    print('  %-62s %s' % (paso, 'BIEN' if condicion else 'MAL  <-- %s' % (detalle,)))
    if not condicion:
        fallos.append(paso)


def funcion(codigo, marca):
    """El texto de la función del complemento entre /*MARCA*/ y /*FIN-MARCA*/."""
    hallado = re.search(r'/\*%s\*/(.*?)/\*FIN-%s\*/' % (marca, marca), codigo, re.S)
    if not hallado:
        raise SystemExit('code.js no tiene la marca %s' % marca)
    # Sin comentarios: el guion del docbuilder es delicado con lo que no es código.
    texto = re.sub(r'^\s*//.*$', '', hallado.group(1), flags=re.M)
    return re.sub(r'\s+//[^\n\'"]*$', '', texto, flags=re.M)


def en_el_editor(usuario, ruta, guion):
    """Ejecuta `guion` sobre el libro (usuario, ruta) y devuelve el .xlsx."""
    import requests
    from config_almacen import URL_PUBLICA
    from api_onlyoffice import firmar_jwt, url_interna_ds, _reescribir_url_interna
    token = firmar_jwt({'u': int(usuario), 'r': ruta, 'uso': 'descarga',
                        'exp': int(time.time()) + 300})
    url_libro = '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA, token)
    nombre = secrets.token_hex(16) + '.docbuilder'
    archivo = os.path.join(recalculo.CARPETA_SCRIPTS, nombre)
    os.makedirs(recalculo.CARPETA_SCRIPTS, exist_ok=True)
    try:
        with open(archivo, 'w', encoding='utf-8') as salida:
            salida.write('builder.OpenFile("%s");\n%s\n'
                         'builder.SaveFile("xlsx", "salida.xlsx");\nbuilder.CloseFile();\n'
                         % (url_libro, guion))
        os.chmod(archivo, 0o644)
        cuerpo = {'async': False, 'key': 'prueba' + secrets.token_hex(8),
                  'url': '%s%s/%s' % (URL_PUBLICA, recalculo.URL_SCRIPTS, nombre)}
        cuerpo['token'] = firmar_jwt(dict(cuerpo))
        respuesta = requests.post(
            url_interna_ds().rstrip('/') + '/docbuilder', json=cuerpo, timeout=(3, 120),
            headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
        datos = respuesta.json() or {}
        urls = list((datos.get('urls') or {}).values())
        if not urls:
            raise RuntimeError('el docbuilder respondió %s' % datos)
        libro_nuevo = requests.get(_reescribir_url_interna(urls[0]), timeout=(3, 60))
        libro_nuevo.raise_for_status()
        return libro_nuevo.content
    finally:
        try:
            os.remove(archivo)
        except OSError:
            pass


def escribir_en_vivo(usuario, ruta, hoja, filas, codigo):
    """Lo que hace el complemento: leer la tabla y añadir las filas."""
    guion = ('Asc.scope = {hoja: %s};\n'
             'var estado = (%s)();\n'
             'Asc.scope.filas = %s; Asc.scope.columnas = []; Asc.scope.renombres = [];\n'
             'Asc.scope.cabeceras = estado.cabeceras; Asc.scope.ultima = estado.ultima;\n'
             'Asc.scope.ancho = estado.encabezados.length;\n'
             '(%s)();\n'
             % (json.dumps(hoja), funcion(codigo, 'LEER'),
                json.dumps(filas, ensure_ascii=False), funcion(codigo, 'ESCRIBIR')))
    contenido = en_el_editor(usuario, ruta, guion)
    carpeta, _, nombre = ruta.rpartition('/')
    nucleo.subir(usuario, carpeta or '/', nombre, io.BytesIO(contenido))
    return contenido


def tipos_de_fila(contenido, numero):
    """{columna: tipo de celda} de una fila de la hoja de la tabla (t="s", "b"…)."""
    z = zipfile.ZipFile(io.BytesIO(contenido))
    parte_hoja, _ = xml_mod._buscar_tabla(z)
    xml = z.read(parte_hoja).decode('utf-8')
    fila = re.search(r'<row [^>]*\br="%d"[^>]*>(.*?)</row>' % numero, xml, re.S)
    salida = {}
    for celda in re.finditer(r'<c r="([A-Z]+)%d"([^>]*)' % numero, fila.group(1) if fila else ''):
        tipo = re.search(r'\bt="(\w+)"', celda.group(2))
        salida[celda.group(1)] = tipo.group(1) if tipo else 'n'
    return salida


def principal(usuario, dejar, ruta_codigo):
    codigo = open(ruta_codigo, encoding='utf-8').read()
    ruta_forma = '%s/%s.forma' % (CARPETA, NOMBRE)
    ruta_hoja = '%s/%s (respuestas).xlsx' % (CARPETA, NOMBRE)
    try:
        nucleo.crear_carpeta(usuario, '/', CARPETA.strip('/'))
    except Exception:
        pass
    preguntas = [{'clase': 'pregunta', 'id': str(uuid.uuid4()), 'tipo': 'texto_corto',
                  'titulo': t, 'obligatoria': False, 'opciones': []}
                 for t in ('Nombre', '¿Es correcto?', 'Teléfono', 'Nota')]
    definicion = {'id': str(uuid.uuid4()), 'titulo': NOMBRE, 'elementos': preguntas}
    nucleo.subir(usuario, CARPETA, NOMBRE + '.forma',
                 io.BytesIO(json.dumps(definicion, ensure_ascii=False).encode('utf-8')))
    ebd.registrar(definicion['id'], usuario, ruta_forma, NOMBRE)
    hoja_mod.vincular(definicion['id'], ruta_hoja)
    contenido, _ = libro.preparar(ebd.obtener(definicion['id']), definicion, usuario, ruta_hoja)
    nucleo.subir(usuario, CARPETA, NOMBRE + ' (respuestas).xlsx', contenido)
    from encuestas_vivo import _hoja_de_la_tabla
    hoja = _hoja_de_la_tabla(usuario, ruta_hoja)
    antes, filas = xml_mod.leer_tabla(open(nucleo.ruta_fisica(usuario, ruta_hoja), 'rb').read())
    print('\n1) Hoja sin respuestas (pestaña «%s»): %s' % (hoja, antes))
    comprobar('la hoja nace con la tabla vacía', not [f for f in filas if any(f)], filas)

    def fila(momento, nombre, correcto, telefono, nota):
        return [momento, 'Sin identificar', nombre, correcto, telefono, nota]

    # ── tabla vacía: tres respuestas, de una en una y luego dos juntas ─────
    resultado = escribir_en_vivo(usuario, ruta_hoja, hoja, [
        fila('29/09/2026 09:06:06', 'Ana', 'Verdadero', '0999999999', '6 / 10')], codigo)
    resultado = escribir_en_vivo(usuario, ruta_hoja, hoja, [
        fila('29/09/2026 09:07:10', 'Luis', 'Falso', '0988888888', '10 / 10'),
        fila('29/09/2026 09:08:15', 'Rosa', 'Verdadero', '022345678', '4 / 10')], codigo)
    enc, filas = xml_mod.leer_tabla(resultado)
    filas = [f for f in filas if any(v not in (None, '') for v in f)]
    columna = {t: i for i, t in enumerate(enc)}
    comprobar('los encabezados siguen en su sitio', enc == antes, enc)
    comprobar('entran las tres respuestas, sin pisarse', len(filas) == 3,
              '%d filas' % len(filas))
    nombres = [f[columna['Nombre']] for f in filas] if 'Nombre' in columna else []
    comprobar('en el orden en que llegaron', nombres == ['Ana', 'Luis', 'Rosa'], nombres)
    z = zipfile.ZipFile(io.BytesIO(resultado))
    _, parte_tabla = xml_mod._buscar_tabla(z)
    ref = re.search(r'\bref="([^"]+)"', z.read(parte_tabla).decode('utf-8')).group(1)
    c1, f1, c2, f2 = xml_mod._rango(ref)
    comprobar('la tabla empieza donde empezaba y abarca las tres', f2 - f1 == 3, ref)
    hoja_xml = z.read(xml_mod._buscar_tabla(z)[0]).decode('utf-8')
    copias = len(re.findall(r'<row ', hoja_xml))
    comprobar('los encabezados no se duplican', nombres.count('Nombre') == 0
              and 'Nombre' not in [f[columna.get('Nombre', 0)] for f in filas], copias)
    if filas and len(filas) == 3:
        comprobar('«Verdadero» queda como texto',
                  [f[columna['¿Es correcto?']] for f in filas] == ['Verdadero', 'Falso', 'Verdadero'],
                  [f[columna['¿Es correcto?']] for f in filas])
        comprobar('la nota «6 / 10» queda como texto, no como fecha',
                  [f[columna['Nota']] for f in filas] == ['6 / 10', '10 / 10', '4 / 10'],
                  [f[columna['Nota']] for f in filas])
        comprobar('el teléfono conserva el cero inicial',
                  [f[columna['Teléfono']] for f in filas]
                  == ['0999999999', '0988888888', '022345678'],
                  [f[columna['Teléfono']] for f in filas])
        tipos = tipos_de_fila(resultado, f1 + 1)
        comprobar('la fecha de envío queda como fecha (número)',
                  tipos.get(xml_mod._col_letras(c1)) == 'n', tipos)

    # ── tabla con respuestas: una más, al final ──────────────────────────
    resultado = escribir_en_vivo(usuario, ruta_hoja, hoja, [
        fila('29/09/2026 09:09:32', 'Pedro', 'Falso', '0977777777', '8 / 10')], codigo)
    enc, filas = xml_mod.leer_tabla(resultado)
    filas = [f for f in filas if any(v not in (None, '') for v in f)]
    columna = {t: i for i, t in enumerate(enc)}
    nombres = [f[columna['Nombre']] for f in filas] if 'Nombre' in columna else []
    comprobar('con respuestas ya escritas, la nueva va al final',
              nombres == ['Ana', 'Luis', 'Rosa', 'Pedro'], nombres)

    print('\nRESULTADO: %s' % ('el complemento escribe bien' if not fallos
                               else '%d comprobaciones fallan: %s' % (len(fallos), fallos)))
    if not dejar:
        for ruta in (ruta_forma, ruta_hoja):
            try:
                nucleo.enviar_a_papelera(usuario, ruta)
            except Exception as excepcion:
                print('  (no se pudo limpiar %s: %s)' % (ruta, excepcion))
        ebd.bd.ejecutar('DELETE FROM encuestas WHERE id = %s', (definicion['id'],))
        ebd.bd.ejecutar('DELETE FROM encuesta_hoja_estado WHERE encuesta_id = %s',
                        (definicion['id'],))
        print('  pruebas retiradas')
    return 1 if fallos else 0


if __name__ == '__main__':
    argumentos = sys.argv[1:]
    ruta_codigo = CODIGO
    if '--codigo' in argumentos:
        ruta_codigo = argumentos[argumentos.index('--codigo') + 1]
    sys.exit(principal(int(argumentos[0]), '--dejar' in argumentos, ruta_codigo))
