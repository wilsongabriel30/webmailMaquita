#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-49 punto 3 - Que el chat se pinte SIN esperar al servidor, con red lenta.

Se compara lo mismo dos veces con la MISMA red frenada: un equipo que nunca ha entrado
(sin nada guardado) y otro que ya entró (con su cache). La diferencia entre ambos es,
exactamente, lo que aporta el cache.

La espera se hace sin bloquear el hilo -con la interfaz asincrona de Playwright- porque
dormir dentro del manejador frena tambien la carga de la propia pagina y falsea la medida:
la primera version de esta prueba daba 6,2 s por ese motivo.
"""
import asyncio
import shutil
import sys
import tempfile
import time

from playwright.async_api import async_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.66')
RETRASO = 2.5      # lo que tarda el servidor en contestar, simulado
LIMITE = 1000      # lo pedido: la pantalla, en menos de un segundo
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


async def frenar(pg):
    async def lento(ruta):
        await asyncio.sleep(RETRASO)      # no bloquea: el resto de la pagina sigue
        await ruta.continue_()
    await pg.route('**/api/chat/conversations**', lento)


async def abrir_y_medir(ctx, frenada):
    pg = await ctx.new_page()
    if frenada:
        await frenar(pg)
    inicio = time.time()
    await pg.goto(BASE + '/chat/', wait_until='domcontentloaded', timeout=60000)
    try:
        await pg.wait_for_selector('.conversation-item', timeout=20000)
        tardanza = (time.time() - inicio) * 1000
    except Exception:
        tardanza = -1
    return pg, tardanza


async def principal(tok, conv=48):
    limpio = tempfile.mkdtemp(prefix='mq-limpio-')
    usado = tempfile.mkdtemp(prefix='mq-usado-')
    galleta = [{'name': 'access_token', 'value': tok,
                'domain': HOST, 'path': '/'}]
    async with async_playwright() as p:
        # --- equipo que ya entró antes: se le llena el cache ---
        ctx2 = await p.chromium.launch_persistent_context(
            usado, headless=True, args=['--no-sandbox'], user_agent=UA,
            viewport={'width': 1280, 'height': 860})
        await ctx2.add_cookies(galleta)
        pg = ctx2.pages[0] if ctx2.pages else await ctx2.new_page()
        await pg.goto(BASE + '/chat/', wait_until='load', timeout=60000)
        await pg.wait_for_timeout(6000)
        await pg.evaluate("(id) => window.openConversation && window.openConversation(id, 'direct')", conv)
        await pg.wait_for_timeout(4000)
        guardado = await pg.evaluate("async () => (await window.MaquitaCacheChat.leerLista() || []).length")
        check('T-49 . la primera visita deja guardada la lista', guardado > 0,
              '%d conversaciones' % guardado)
        await pg.close()

        # --- equipo que nunca entró: no tiene nada guardado ---
        ctx1 = await p.chromium.launch_persistent_context(
            limpio, headless=True, args=['--no-sandbox'], user_agent=UA,
            viewport={'width': 1280, 'height': 860})
        await ctx1.add_cookies(galleta)
        _, sin_cache = await abrir_y_medir(ctx1, True)
        await ctx1.close()

        # --- el que ya tiene su cache, con la MISMA red lenta ---
        pg2, con_cache = await abrir_y_medir(ctx2, True)
        uso = await pg2.evaluate("() => window.MaquitaPintadoLocal.seUso()")
        await ctx2.close()

    shutil.rmtree(limpio, ignore_errors=True)
    shutil.rmtree(usado, ignore_errors=True)

    check('T-49 . sin nada guardado hay que esperar al servidor', sin_cache > RETRASO * 1000 * 0.8,
          '%.0f ms' % sin_cache)
    check('T-49 . con lo guardado, la pantalla aparece en menos de 1 s',
          0 < con_cache < LIMITE, '%.0f ms' % con_cache)
    check('T-49 . y es mucho mas rapido que esperar al servidor',
          0 < con_cache < sin_cache / 2,
          'con cache %.0f ms frente a %.0f ms sin el' % (con_cache, sin_cache))
    check('T-49 . consta que se pinto desde el equipo', 'lista' in (uso or {}), '%s' % uso)

    print('\n   Con red lenta (%.1f s de espera del servidor):' % RETRASO)
    print('     equipo nuevo, sin nada guardado ... %6.0f ms' % sin_cache)
    print('     equipo con su cache ............... %6.0f ms' % con_cache)
    if sin_cache > 0 and con_cache > 0:
        print('     mejora ............................ %6.1f veces mas rapido'
              % (sin_cache / con_cache))
    print('\nCandado T-49 punto 3 (se nota el instantaneo): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(principal(sys.argv[1])))
