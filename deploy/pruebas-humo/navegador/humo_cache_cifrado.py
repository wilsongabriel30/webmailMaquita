#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-49 - Candado del cache local cifrado.

El que pidio soporte: se guarda una frase conocida, se BUSCA EN LOS ARCHIVOS REALES del
disco y no debe aparecer. Se comprueba ademas que se puede volver a leer, que la busqueda
por huellas funciona, que el presupuesto de 2 GB purga lo viejo y que NUNCA borra la cola
de envios pendientes.
"""
import os
import re
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.66')
FRASE = 'ContrasenaDelDirectorFinancieroSecretoAbsoluto2026'
ASUNTO = 'AsuntoConfidencialNominaDiciembre'
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok):
    perfil = tempfile.mkdtemp(prefix='mq-cache-')
    with sync_playwright() as p:
        # perfil en disco DE VERDAD: es la unica forma de mirar despues los archivos
        ctx = p.chromium.launch_persistent_context(
            perfil, headless=True, args=['--no-sandbox'], user_agent=UA,
            viewport={'width': 1280, 'height': 860})
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(BASE + '/chat/', wait_until='load', timeout=60000)
        pg.wait_for_timeout(7000)

        listo = pg.evaluate("() => !!(window.MaquitaLlave && window.MaquitaCifrado && window.MaquitaAlmacen)")
        check('T-49 . los modulos del cache estan cargados', listo)
        if not listo:
            ctx.close()
            return 1

        modo = pg.evaluate("() => window.MaquitaLlave.protegidaPorElEquipo()")
        print('         (llave protegida por el equipo: %s -> %s)'
              % (modo, 'DPAPI, opcion C' if modo else 'respaldo del navegador, opcion A'))

        # 1) se guarda algo sensible y se vuelve a leer
        ok = pg.evaluate("""async ([frase, asunto]) => {
            await window.MaquitaAlmacen.guardar('prueba:1',
                {cuerpo: frase, asunto: asunto, de: DESTINO},
                {area: 'chat', texto: frase + ' ' + asunto});
            const v = await window.MaquitaAlmacen.leer('prueba:1');
            return !!(v && v.cuerpo === frase && v.asunto === asunto);
        }""", [FRASE, ASUNTO])
        check('T-49 . lo guardado se puede volver a leer intacto', ok)

        # 2) la busqueda por huellas encuentra por palabra exacta
        encontrado = pg.evaluate("async (f) => (await window.MaquitaAlmacen.buscar(f)).length",
                                 FRASE)
        check('T-49 . se puede buscar sin descifrar (indice de huellas)', encontrado >= 1,
              '%d resultados' % encontrado)

        # 3) el presupuesto: se llena y se purga lo viejo, pero NO los pendientes
        r = pg.evaluate("""async () => {
            await window.MaquitaAlmacen.guardar('prueba:pendiente',
                {texto: 'mensaje escrito sin conexion'},
                {area: 'chat', fijo: true, estado: 'pendiente'});
            for (let i = 0; i < 30; i++) {
                await window.MaquitaAlmacen.guardar('prueba:relleno:' + i,
                    {relleno: 'x'.repeat(2000), i: i}, {area: 'chat'});
            }
            const antes = await window.MaquitaAlmacen.espacio();
            const purga = await window.MaquitaAlmacen.hacerSitio(1000);
            const despues = await window.MaquitaAlmacen.espacio();
            const pendiente = await window.MaquitaAlmacen.leer('prueba:pendiente');
            return {antes: antes.total, despues: despues.total, borrados: purga.borrados,
                    pendienteVive: !!pendiente, tope: antes.tope};
        }""")
        check('T-49 . el tope es de 2 GB', r['tope'] == 2 * 1024 * 1024 * 1024,
              '%d bytes' % r['tope'])
        check('T-49 . al llenarse, se borra lo mas viejo', r['borrados'] > 0,
              '%d registros, de %d a %d bytes' % (r['borrados'], r['antes'], r['despues']))
        check('T-49 . la purga NUNCA toca los envios pendientes', r['pendienteVive'])

        pg.wait_for_timeout(1500)
        ctx.close()

    # 4) EL CANDADO QUE PIDIO SOPORTE: mirar los archivos del disco
    encontrados = []
    total = 0
    for raiz, _, archivos in os.walk(perfil):
        for a in archivos:
            ruta = os.path.join(raiz, a)
            try:
                if os.path.getsize(ruta) > 80 * 1024 * 1024:
                    continue
                with open(ruta, 'rb') as f:
                    datos = f.read()
                total += 1
                for aguja in (FRASE, ASUNTO):
                    if aguja.encode() in datos or aguja.encode('utf-16-le') in datos:
                        encontrados.append('%s en %s' % (aguja[:18], ruta.replace(perfil, '')))
            except (OSError, IOError):
                continue
    check('T-49 . NADA se lee en claro en los archivos del disco', not encontrados,
          '%d archivos revisados%s' % (total, ('; APARECE: ' + '; '.join(encontrados[:2]))
                                       if encontrados else ''))
    subprocess.run(['rm', '-rf', perfil])

    print('\nCandado T-49 (cache local cifrado): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
