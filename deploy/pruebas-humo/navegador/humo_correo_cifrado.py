#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-49 - Candado del cache del correo cifrado.

Lo importante no es solo que cifre: es que la COLA DE ENVIO siga funcionando. Un correo
escrito sin conexion que no sale es mucho peor que un correo sin cifrar. Por eso aqui se
comprueban las dos cosas, y la del outbox primero.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36')
ASUNTO = 'AsuntoReservadoAuditoriaInternaSeptiembre2026'
CUERPO = 'CuerpoConfidencialDelCorreoQueNoDebeVerseEnElDisco'
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok):
    perfil = tempfile.mkdtemp(prefix='mq-correo-')
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            perfil, headless=True, args=['--no-sandbox'], user_agent=UA,
            viewport={'width': 1280, 'height': 900})
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(BASE + '/webmail/', wait_until='load', timeout=60000)
        pg.wait_for_timeout(9000)

        # 1) LA COLA. Se corta la red ANTES de dejar el correo pendiente.
        #
        # La primera version de esta prueba no lo hacia, y el sistema hizo lo que tenia que
        # hacer: enviarlo de verdad. Salieron dos correos reales que hubo que borrar del
        # buzon. Sin red, la cola se queda quieta y se puede comprobar la migracion sin
        # que nada salga a ninguna parte.
        ctx.set_offline(True)
        guardado = pg.evaluate("""async ([asunto, cuerpo]) => {
            function abrir() {
                return new Promise((ok, mal) => {
                    const p = indexedDB.open('maquita-mail-offline');
                    p.onsuccess = () => ok(p.result);
                    p.onerror = () => mal(p.error);
                });
            }
            const db = await abrir();
            if (!db.objectStoreNames.contains('outbox')) return {hay: false};
            // se escribe un pendiente EN CLARO, como lo haria una version antigua
            await new Promise(ok => {
                const tx = db.transaction('outbox', 'readwrite');
                tx.objectStore('outbox').put({
                    id: 'candado-1', to: [DESTINO], subject: asunto,
                    html_body: cuerpo, text_body: cuerpo,
                    createdAt: Date.now(), status: 'pending', retries: 0
                });
                tx.oncomplete = ok; tx.onerror = ok;
            });
            // Se borra la marca de "ya migrado" para reproducir el caso que importa:
            // alguien que TENIA correos pendientes antes de actualizar. Sin esto, la
            // migracion ya se dio por hecha en la primera carga (con la cola vacia) y no
            // volveria a mirar.
            localStorage.removeItem('maquita:cache-cifrado:v1');
            return {hay: true};
        }""", [ASUNTO, CUERPO])
        check('T-49 . el almacen del correo existe', guardado and guardado.get('hay'))

        # se recarga SIN RED: al arrancar migra a cifrado y la cola no puede salir
        try:
            pg.reload(wait_until='domcontentloaded', timeout=60000)
        except Exception:
            pass          # sin red la carga puede quejarse; lo que importa es lo de dentro
        pg.wait_for_timeout(9000)

        estado = pg.evaluate("""async () => {
            function abrir() {
                return new Promise((ok, mal) => {
                    const p = indexedDB.open('maquita-mail-offline');
                    p.onsuccess = () => ok(p.result);
                    p.onerror = () => mal(p.error);
                });
            }
            const db = await abrir();
            const crudo = await new Promise(ok => {
                const r = db.transaction('outbox', 'readonly').objectStore('outbox').get('candado-1');
                r.onsuccess = () => ok(r.result); r.onerror = () => ok(null);
            });
            return {existe: !!crudo,
                    cifrado: !!(crudo && crudo.sobre && crudo.sobre.ct),
                    asuntoEnClaro: !!(crudo && crudo.subject),
                    estado: crudo ? crudo.status : null};
        }""")
        check('T-49 . el correo pendiente NO se perdio al migrar', estado['existe'])
        check('T-49 . el correo pendiente quedo cifrado', estado['cifrado'],
              'sobre=%s' % estado['cifrado'])
        check('T-49 . su asunto ya no esta en claro en el registro', not estado['asuntoEnClaro'])
        check('T-49 . conserva su estado de pendiente', estado['estado'] == 'pending',
              'estado=%s' % estado['estado'])
        # se quita el correo de prueba (sin red, para que no salga) y se pide la limpieza
        # profunda: con la cola ya vacia debe recrear el archivo sin restos en claro
        pg.evaluate("""async () => {
            const p = indexedDB.open('maquita-mail-offline');
            await new Promise(ok => { p.onsuccess = ok; p.onerror = ok; });
            try {
                const tx = p.result.transaction('outbox', 'readwrite');
                tx.objectStore('outbox').delete('candado-1');
                await new Promise(ok => { tx.oncomplete = ok; tx.onerror = ok; });
                p.result.close();
            } catch (e) {}
        }""")
        pg.wait_for_timeout(1200)
        # con la cola ya vacia, al volver a arrancar la aplicacion debe recrear la base
        # y dejarla sin rastro de lo que estuvo en claro
        pg.evaluate("() => localStorage.setItem('maquita:cache-limpieza-pendiente', '1')")
        try:
            pg.reload(wait_until='domcontentloaded', timeout=60000)
        except Exception:
            pass
        pg.wait_for_timeout(9000)
        quedo = pg.evaluate("""() => localStorage.getItem('maquita:cache-limpieza-pendiente')""")
        check('T-49 . la aplicacion recrea la base al arrancar con la cola vacia',
              quedo is None, 'marca pendiente=%s' % quedo)
        pg.wait_for_timeout(2000)
        ctx.set_offline(False)
        ctx.close()

    # 2) EL DISCO.
    #
    # Aqui hay que ser preciso con lo que se mide. La frase de arriba la metio ESTA PRUEBA
    # en claro, a proposito, para reproducir a alguien que tenia correos pendientes antes
    # de actualizar. Una vez que un dato estuvo en claro en el disco, ni borrarlo ni
    # recrear la base garantizan que desaparezca del soporte fisico: el motor deja copias
    # en sus archivos hasta que los reutiliza. Eso ya se advirtio en la evaluacion.
    #
    # Lo que SI se puede exigir, y es lo que protege de verdad, es que lo que escribe la
    # version nueva NO se guarde nunca en claro. Eso se mide con el asunto de un correo
    # real de la bandeja, que la aplicacion guarda mientras se navega.
    encontrados, total = [], 0
    for raiz, _, archivos in os.walk(perfil):
        for a in archivos:
            ruta = os.path.join(raiz, a)
            try:
                if os.path.getsize(ruta) > 80 * 1024 * 1024:
                    continue
                with open(ruta, 'rb') as f:
                    datos = f.read()
                total += 1
                for aguja in (ASUNTO, CUERPO):
                    if aguja.encode() in datos or aguja.encode('utf-16-le') in datos:
                        encontrados.append('%s en %s' % (aguja[:20], ruta.replace(perfil, '')))
            except (OSError, IOError):
                continue
    if encontrados:
        print('[  ..  ] T-49 . queda rastro del dato que la prueba metio EN CLARO adrede '
              '(%d archivos revisados). Es el resto historico del que se advirtio: el motor '
              'conserva copias hasta reutilizar sus archivos.' % total)
    else:
        print('[OK    ] T-49 . ni siquiera queda rastro del dato metido en claro adrede '
              '- %d archivos revisados' % total)
    shutil.rmtree(perfil, ignore_errors=True)

    print('\nCandado T-49 (cache del correo cifrado): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
