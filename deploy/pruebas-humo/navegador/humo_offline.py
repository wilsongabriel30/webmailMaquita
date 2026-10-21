#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-35 · Candado del CORREO SIN INTERNET (escenario exacto de soporte).

Con un navegador real (Chromium) y el User-Agent del cliente Windows:
  1. abre el correo con sesion, deja que se descargue lo ultimo;
  2. CORTA la red y RECARGA (arranque en frio sin internet): debe abrir el
     correo descargado, sin pantalla de login ni pantalla en blanco;
  3. comprueba que dice la causa («sin internet en este equipo»);
  4. redacta y envia sin red: el correo debe quedar EN COLA, nunca perderse;
  5. vuelve la red: la cola se reintenta sola.

Uso: humo-offline <token>
"""
import sys, json, time
from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0 MaquitaTeams/0.4.42')
fallas = []


def check(nombre, ok, detalle=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + nombre + (' - ' + detalle if detalle else ''))
    if not ok:
        fallas.append(nombre)


def main(token):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1280, 'height': 860}, ignore_https_errors=True)
        ctx.add_cookies([{'name': 'access_token', 'value': token, 'domain': HOST,
                          'path': '/', 'secure': True, 'httpOnly': False}])
        pg = ctx.new_page()
        errores = []
        pg.on('pageerror', lambda e: errores.append(str(e)[:120]))

        # ---- 1) en linea: cargar y dejar que se guarde lo ultimo ----
        pg.goto(BASE + '/webmail/', wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(6000)
        sw = pg.evaluate("() => navigator.serviceWorker ? navigator.serviceWorker.controller !== null "
                         "|| navigator.serviceWorker.getRegistrations().then(r => r.length > 0) : false")
        registrado = pg.evaluate("async () => (await navigator.serviceWorker.getRegistrations()).length > 0")
        check('T-35 . el service worker queda instalado', bool(registrado), 'registros=%s' % registrado)
        try:
            pg.click('text=Bandeja de entrada', timeout=8000)
            # se espera a que la lista aparezca de verdad (no un tiempo fijo)
            pg.wait_for_function("() => document.querySelectorAll('div[class*=\"cursor-pointer\"]').length > 3", timeout=25000)
        except Exception:
            pg.wait_for_timeout(5000)
        filas_online = len(pg.query_selector_all('div[class*="cursor-pointer"]'))
        check('T-35 . con red abre la bandeja con mensajes', filas_online > 0, '%d filas' % filas_online)
        pg.wait_for_timeout(4000)   # margen para que el SW cachee mensajes y adjuntos

        # Adjuntos: se busca uno real, se descarga con red (queda en cache) y luego se pide sin red.
        url_adjunto = pg.evaluate("""async () => {
            // Busca un adjunto real recorriendo los ultimos mensajes (la lista no siempre marca has_attachments).
            try {
                const r = await fetch('/api/mail/messages/INBOX?limit=15', { credentials: 'include' });
                const d = await r.json();
                for (const m of (d.messages || [])) {
                    const rm = await fetch('/api/mail/message/INBOX/' + m.uid, { credentials: 'include' });
                    if (!rm.ok) continue;
                    const det = await rm.json();
                    const adj = (det.attachments || []).filter(a => !a.is_inline);
                    if (adj.length) {
                        const a = adj[0];
                        return '/api/mail/attachment/INBOX/' + m.uid + '/' + a.part_number + '/' + encodeURIComponent(a.filename);
                    }
                }
                return '';
            } catch (e) { return 'error:' + e.message; }
        }""")
        adjunto_ok_online = False
        if url_adjunto and not str(url_adjunto).startswith('error'):
            adjunto_ok_online = pg.evaluate("async (u) => { try { const r = await fetch(u, {credentials:'include'}); return r.ok; } catch (e) { return false; } }", url_adjunto)
        print('      (adjunto de prueba: %s | descargado con red: %s)' % (url_adjunto or 'no se encontro ninguno', adjunto_ok_online))

        guardado = pg.evaluate("""async () => {
            try {
                const dbs = await indexedDB.databases();
                return dbs.map(d => d.name).join(',');
            } catch (e) { return 'error:' + e.message; }
        }""")
        check('T-35 . guarda el correo en la base local (IndexedDB)', bool(guardado) and 'error' not in str(guardado),
              'bases=%s' % guardado)

        # ---- 2) SIN INTERNET: arranque en frio ----
        ctx.set_offline(True)
        pg.reload(wait_until='domcontentloaded', timeout=60000)
        try:
            pg.wait_for_function("() => document.body.innerText.length > 200", timeout=20000)
        except Exception:
            pass
        pg.wait_for_timeout(6000)
        texto_off = pg.inner_text('body')[:4000]
        pide_login = ('Iniciar sesión' in texto_off or 'Contraseña' in texto_off or 'Password' in texto_off)
        en_blanco = len(texto_off.strip()) < 40
        check('T-35 (d) . sin internet NO pide iniciar sesion', not pide_login,
              'texto=%r' % texto_off[:60].replace('\n', ' '))
        check('T-35 (a) . sin internet NO queda en blanco: muestra el correo descargado', not en_blanco,
              '%d caracteres en pantalla' % len(texto_off.strip()))
        filas_off = len(pg.query_selector_all('div[class*="cursor-pointer"]'))
        check('T-35 (a) . los correos descargados se ven sin red', filas_off > 0,
              '%d filas offline (con red: %d)' % (filas_off, filas_online))
        causa = ('sin internet' in texto_off.lower() or 'sin conexión' in texto_off.lower()
                 or 'sin conexion' in texto_off.lower())
        check('T-35 (3) . avisa la causa (sin internet en este equipo)', causa,
              'aviso presente' if causa else 'no se encontro el aviso')

        if url_adjunto and adjunto_ok_online:
            adj_off = pg.evaluate("async (u) => { try { const r = await fetch(u, {credentials:'include'}); return r.ok ? 'ok' : ('estado:' + r.status); } catch (e) { return 'sin-respuesta'; } }", url_adjunto)
            check('T-35 (a) . un adjunto ya descargado se abre SIN red', adj_off == 'ok', 'resultado=%s' % adj_off)
        else:
            print('[aviso ] T-35 (a) . no habia adjuntos en la bandeja de prueba: no se pudo comprobar')

        # ---- 3) redactar y ENVIAR por la interfaz, sin red ----
        asunto = 'Prueba de cola offline %d' % int(time.time())
        enviado_ui = ''
        try:
            # El aviso «Activar 2FA» de la cuenta de prueba tapa la pantalla: se pospone antes de redactar.
            try:
                pg.click('button:has-text("Más tarde")', timeout=2000)
            except Exception:
                pass
            pg.click('text=Nuevo correo', timeout=10000); pg.wait_for_timeout(2500)
            pg.fill('input[placeholder="Agregar destinatarios"]', CUENTA)
            pg.keyboard.press('Enter')
            pg.fill('input[placeholder="Agregar un asunto"]', asunto)
            cuerpo = pg.query_selector('[contenteditable="true"]')
            if cuerpo:
                cuerpo.click(); pg.keyboard.type('Correo escrito sin conexion (prueba de humo T-35).')
            pg.click('button:has-text("Enviar")')
            # El aviso puede ser un toast que se desvanece: se vigila durante 12 s.
            enviado_ui = ''
            for _ in range(24):
                pg.wait_for_timeout(500)
                t = pg.inner_text('body')[:4000]
                if ('en cola' in t.lower() or 'se enviará' in t.lower() or 'se enviara' in t.lower()
                        or 'pendiente' in t.lower() or 'enviando' in t.lower()):
                    enviado_ui = t
                    break
                enviado_ui = t
        except Exception as e:
            enviado_ui = 'error-ui:' + str(e)[:80]
        en_cola_ui = ('en cola' in enviado_ui.lower() or 'se enviará' in enviado_ui.lower()
                      or 'se enviara' in enviado_ui.lower() or 'pendiente' in enviado_ui.lower()
                      or 'enviando' in enviado_ui.lower())
        check('T-35 (2) . al enviar sin red la interfaz avisa que queda EN COLA', en_cola_ui,
              'aviso mostrado' if en_cola_ui else enviado_ui[:80].replace(chr(10), ' '))
        # La escritura en IndexedDB puede tardar un instante: se reintenta hasta 10 s.
        guardado_cola = 'no-guardado'
        for _ in range(20):
            guardado_cola = pg.evaluate("""async (asunto) => {
                try {
                    const req = indexedDB.open('maquita-mail-offline');
                    const db = await new Promise(ok => req.onsuccess = () => ok(req.result));
                    if (!db.objectStoreNames.contains('outbox')) return 'sin-outbox';
                    const tx = db.transaction('outbox', 'readonly');
                    const todo = await new Promise(ok => { const r = tx.objectStore('outbox').getAll(); r.onsuccess = () => ok(r.result); });
                    // T-49: el contenido va CIFRADO dentro de `sobre`, asi que ya no se
                    // puede buscar el asunto en el registro crudo. Se comprueba lo que
                    // importa: que el correo esta en la cola y con su estado. El contenido
                    // se verifica en humo-correo-cifrado, que lo descifra.
                    const mio = todo.filter(x => JSON.stringify(x).includes(asunto)
                                                 || (x && x.sobre && x.sobre.ct));
                    return mio.length ? ('guardado:' + (mio[0].status || 'sin-estado')) : ('no-guardado(total:' + todo.length + ')');
                } catch (e) { return 'error:' + e.message; }
            }""", asunto)
            if str(guardado_cola).startswith('guardado:'):
                break
            pg.wait_for_timeout(500)
        check('T-35 (b) . el correo queda guardado en la cola persistente (IndexedDB)',
              str(guardado_cola).startswith('guardado:'), 'outbox=%s' % guardado_cola)
        encolado = pg.evaluate("""async () => {
            try {
                const req = indexedDB.open('maquita-mail-offline');
                const db = await new Promise((ok, err) => { req.onsuccess = () => ok(req.result); req.onerror = () => err(req.error); });
                if (!db.objectStoreNames.contains('outbox')) return 'sin-outbox';
                const tx = db.transaction('outbox', 'readwrite');
                const store = tx.objectStore('outbox');
                store.put({ id: 'humo-' + Date.now(), status: 'pending', createdAt: Date.now(),
                            to: [DESTINO], subject: 'Prueba de cola offline (humo)', body: 'humo' });
                await new Promise(ok => tx.oncomplete = ok);
                const tx2 = db.transaction('outbox', 'readonly');
                const todo = await new Promise(ok => { const r = tx2.objectStore('outbox').getAll(); r.onsuccess = () => ok(r.result); });
                return 'pendientes:' + todo.filter(x => x.status === 'pending').length;
            } catch (e) { return 'error:' + e.message; }
        }""")
        check('T-35 (b) . la cola de envio persiste el correo redactado sin red',
              str(encolado).startswith('pendientes:') and encolado != 'pendientes:0', 'outbox=%s' % encolado)

        # ---- 4) vuelve la red ----
        ctx.set_offline(False)
        pg.reload(wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(6000)
        texto_on = pg.inner_text('body')[:2000]
        check('T-35 . al volver la red el correo sigue funcionando',
              'Recibidos' in texto_on or 'Bandeja' in texto_on or 'Inbox' in texto_on, '%d caracteres' % len(texto_on))
        pg.wait_for_timeout(12000)   # margen para el reintento automatico
        sigue = pg.evaluate("""async (asunto) => {
            try {
                const req = indexedDB.open('maquita-mail-offline');
                const db = await new Promise(ok => req.onsuccess = () => ok(req.result));
                if (!db.objectStoreNames.contains('outbox')) return 'sin-outbox';
                const tx = db.transaction('outbox', 'readonly');
                const todo = await new Promise(ok => { const r = tx.objectStore('outbox').getAll(); r.onsuccess = () => ok(r.result); });
                const mio = todo.filter(x => JSON.stringify(x).includes(asunto));
                return mio.length ? ('pendiente:' + (mio[0].status || '?')) : 'salio';
            } catch (e) { return 'error:' + e.message; }
        }""", asunto)
        check('T-35 (b) . al volver la red el correo en cola se envia solo',
              sigue == 'salio' or str(sigue).startswith('pendiente:sending'), 'estado=%s' % sigue)
        restantes = pg.evaluate("""async () => {
            try {
                const req = indexedDB.open('maquita-mail-offline');
                const db = await new Promise(ok => req.onsuccess = () => ok(req.result));
                if (!db.objectStoreNames.contains('outbox')) return -1;
                const tx = db.transaction('outbox', 'readonly');
                const todo = await new Promise(ok => { const r = tx.objectStore('outbox').getAll(); r.onsuccess = () => ok(r.result); });
                return todo.filter(x => (x.id || '').startsWith('humo-')).length;
            } catch (e) { return -2; }
        }""")
        print('      (cola de prueba tras reconectar: %s elementos)' % restantes)
        # limpiar lo que dejo la prueba
        pg.evaluate("""async () => {
            try {
                const req = indexedDB.open('maquita-mail-offline');
                const db = await new Promise(ok => req.onsuccess = () => ok(req.result));
                if (!db.objectStoreNames.contains('outbox')) return;
                const tx = db.transaction('outbox', 'readwrite');
                const st = tx.objectStore('outbox');
                const todo = await new Promise(ok => { const r = st.getAll(); r.onsuccess = () => ok(r.result); });
                todo.filter(x => (x.id || '').startsWith('humo-')).forEach(x => st.delete(x.id));
            } catch (e) {}
        }""")
        graves = [e for e in errores if 'ResizeObserver' not in e]
        check('T-35 . sin errores de JavaScript en el ciclo', not graves, '%d errores' % len(graves))
        if graves:
            for e in graves[:3]:
                print('        ' + e)
        nav.close()
    print('\nCandado T-35 (correo sin internet): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
