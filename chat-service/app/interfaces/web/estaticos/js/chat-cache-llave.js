/* =============================================================================
   T-49 · LA LLAVE DEL CACHÉ LOCAL (módulo que consume el canal de la app)
   -----------------------------------------------------------------------------
   QUE HACE: consigue la llave con la que se cifra todo lo que se guarda en el
   equipo. Si estamos dentro de la aplicación de Windows, se la pide a la app,
   que la protege con DPAPI (opción C). Si estamos en un navegador normal, donde
   DPAPI no existe, cae al respaldo: una llave no exportable guardada por el
   propio navegador (opción A).
   POR QUE:  el algoritmo de cifrado es lo de menos; lo que decide si esto sirve
   de algo es DÓNDE vive la llave. Por eso vive en su propio archivo, pequeño y
   legible: es la pieza que hay que poder auditar de un vistazo.
   DONDE SE LLAMA: lo cargan el chat y el correo antes que cualquier módulo que
   escriba en el caché. `await MaquitaLlave.obtener()` devuelve la CryptoKey.
   ============================================================================= */
(function (global) {
    'use strict';

    var BD = 'maquita-cache-llave';
    var ALMACEN = 'llaves';
    var ID = 'principal';
    var enMemoria = null;

    /* ---------------------------------------------------------------------
       CONTRATO CON LA APLICACIÓN DE WINDOWS (lo que la app debe exponer)
       ---------------------------------------------------------------------
       La app inyecta en la página un objeto `window.maquitaApp` con dos
       funciones que devuelven promesas:

         maquitaApp.protegerLlave(bytesBase64)   -> Promise<string>
             Recibe 32 bytes en base64 y devuelve el resultado de envolverlos
             con DPAPI (CryptProtectData, ámbito USUARIO), también en base64.

         maquitaApp.recuperarLlave(envueltaBase64) -> Promise<string>
             Deshace lo anterior (CryptUnprotectData) y devuelve los 32 bytes
             originales en base64. Si la envoltura es de otro usuario u otro
             equipo, DPAPI falla: debe rechazar la promesa, NO devolver basura.

       La app NUNCA guarda la llave desnuda; solo envuelve y desenvuelve. Lo
       envuelto lo guarda la página aquí mismo (ver `guardarEnvuelta`).
       --------------------------------------------------------------------- */
    function hayApp() {
        return !!(global.maquitaApp
                  && typeof global.maquitaApp.protegerLlave === 'function'
                  && typeof global.maquitaApp.recuperarLlave === 'function');
    }

    function abrirBD() {
        return new Promise(function (ok, mal) {
            var p = indexedDB.open(BD, 1);
            p.onupgradeneeded = function () {
                p.result.createObjectStore(ALMACEN);
            };
            p.onsuccess = function () { ok(p.result); };
            p.onerror = function () { mal(p.error); };
        });
    }

    function leer(clave) {
        return abrirBD().then(function (db) {
            return new Promise(function (ok, mal) {
                var p = db.transaction(ALMACEN, 'readonly').objectStore(ALMACEN).get(clave);
                p.onsuccess = function () { ok(p.result); };
                p.onerror = function () { mal(p.error); };
            });
        });
    }

    function escribir(clave, valor) {
        return abrirBD().then(function (db) {
            return new Promise(function (ok, mal) {
                var p = db.transaction(ALMACEN, 'readwrite').objectStore(ALMACEN).put(valor, clave);
                p.onsuccess = function () { ok(true); };
                p.onerror = function () { mal(p.error); };
            });
        });
    }

    function aBase64(buffer) {
        var b = new Uint8Array(buffer), s = '';
        for (var i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
        return btoa(s);
    }

    function deBase64(texto) {
        var s = atob(texto), b = new Uint8Array(s.length);
        for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
        return b;
    }

    /* ---- opción C: la app protege la llave con DPAPI ---- */
    async function conApp() {
        var envuelta = await leer('dpapi');
        if (envuelta) {
            try {
                var bytes = deBase64(await global.maquitaApp.recuperarLlave(envuelta));
                return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false,
                                               ['encrypt', 'decrypt']);
            } catch (e) {
                // la envoltura no sirve (otro usuario, otro equipo, perfil movido):
                // se descarta y se empieza de cero. El caché viejo queda ilegible,
                // que es exactamente lo que se busca.
                console.warn('la llave guardada no se pudo recuperar; se rehace', e);
            }
        }
        var material = crypto.getRandomValues(new Uint8Array(32));
        await escribir('dpapi', await global.maquitaApp.protegerLlave(aBase64(material)));
        var llave = await crypto.subtle.importKey('raw', material, 'AES-GCM', false,
                                                  ['encrypt', 'decrypt']);
        material.fill(0);   // no dejarla rondando en memoria más de lo necesario
        return llave;
    }

    /* ---- opción A: respaldo para navegador, sin DPAPI ---- */
    async function sinApp() {
        var guardada = await leer(ID);
        if (guardada) return guardada;
        // `extractable: false`: ni el propio JavaScript puede volver a leer su
        // material. Es más débil que DPAPI —sigue en el perfil del navegador—
        // pero cumple lo pedido: en disco no hay nada legible.
        var llave = await crypto.subtle.generateKey({name: 'AES-GCM', length: 256}, false,
                                                    ['encrypt', 'decrypt']);
        await escribir(ID, llave);
        return llave;
    }

    var pendiente = null;

    function obtener() {
        if (enMemoria) return Promise.resolve(enMemoria);
        if (pendiente) return pendiente;          // varias llamadas a la vez, una sola llave
        pendiente = (hayApp() ? conApp() : sinApp()).then(function (k) {
            enMemoria = k;
            pendiente = null;
            return k;
        }, function (e) {
            pendiente = null;
            throw e;
        });
        return pendiente;
    }

    /* Al cerrar sesión hay que borrar la llave Y el caché: sin llave, lo guardado
       ya no se puede leer, pero se borra igual para no dejar bultos. */
    async function olvidar() {
        enMemoria = null;
        var db = await abrirBD();
        db.transaction(ALMACEN, 'readwrite').objectStore(ALMACEN).clear();
    }

    global.MaquitaLlave = {
        obtener: obtener,
        olvidar: olvidar,
        protegidaPorElEquipo: hayApp,   // true = DPAPI (fuerte); false = respaldo del navegador
    };
})(window);
