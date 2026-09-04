/* =============================================================================
   T-49 · EL ALMACEN LOCAL (lo que se guarda en el equipo)
   -----------------------------------------------------------------------------
   QUE HACE: guarda y devuelve datos ya cifrados, lleva la cuenta del espacio
   ocupado y borra lo mas viejo cuando se acerca al tope de 2 GB.
   POR QUE:  para que abrir el chat sea instantaneo hace falta tener las cosas en
   el equipo; y si estan en el equipo, tienen que estar cifradas y no pueden
   crecer sin limite.
   QUE QUEDA EN CLARO Y POR QUE: el identificador, la fecha, el tamano, el estado
   y un seudonimo del grupo. Son los datos MINIMOS para poder ordenar y para
   borrar lo viejo sin tener que descifrar dos gigas cada vez. El contenido -lo
   que dice el mensaje, quien lo manda, los adjuntos- va siempre cifrado.
   DONDE SE LLAMA: cache-chat.js y el caché del correo. Nadie escribe en
   IndexedDB por su cuenta.
   ============================================================================= */
(function (global) {
    'use strict';

    var BD = 'maquita-cache';
    var VERSION_BD = 1;
    var ALMACEN = 'datos';
    var INDICE = 'huellas';

    var TOPE = 2 * 1024 * 1024 * 1024;      // 2 GB, lo acordado con soporte
    var UMBRAL = 0.9;                        // al 90 % se empieza a hacer sitio
    var REPARTO = {correo: 0.50, chat: 0.35, otros: 0.15};   // 1 GB / 700 MB / resto

    function abrir() {
        return new Promise(function (ok, mal) {
            var p = indexedDB.open(BD, VERSION_BD);
            p.onupgradeneeded = function () {
                var db = p.result;
                if (!db.objectStoreNames.contains(ALMACEN)) {
                    var s = db.createObjectStore(ALMACEN, {keyPath: 'id'});
                    s.createIndex('grupo', 'grupo');
                    s.createIndex('usado', 'usado');       // para la purga por antiguedad
                    s.createIndex('area', 'area');
                    s.createIndex('fijo', 'fijo');         // lo que NUNCA se purga
                }
                if (!db.objectStoreNames.contains(INDICE)) {
                    var i = db.createObjectStore(INDICE, {autoIncrement: true});
                    i.createIndex('huella', 'huella');
                    i.createIndex('ref', 'ref');
                }
            };
            p.onsuccess = function () { ok(p.result); };
            p.onerror = function () { mal(p.error); };
        });
    }

    function pedir(peticion) {
        return new Promise(function (ok, mal) {
            peticion.onsuccess = function () { ok(peticion.result); };
            peticion.onerror = function () { mal(peticion.error); };
        });
    }

    /* Guarda un dato. `area` dice a que parte del presupuesto pertenece (correo, chat,
       otros) y `fijo` marca lo que no se puede borrar nunca: la cola de envio pendiente.
       Un mensaje escrito sin conexion no se pierde porque falte espacio. */
    async function guardar(id, valor, opciones) {
        opciones = opciones || {};
        var paquete = await global.MaquitaCifrado.cifrar(valor);
        var registro = {
            id: String(id),
            v: paquete.v,
            iv: paquete.iv,
            ct: paquete.ct,
            // --- lo unico en claro, y solo lo imprescindible ---
            grupo: opciones.grupo ? await global.MaquitaCifrado.huella(String(opciones.grupo)) : '',
            area: opciones.area || 'otros',
            fecha: opciones.fecha || Date.now(),
            usado: Date.now(),
            bytes: paquete.ct.byteLength + 64,
            fijo: opciones.fijo ? 1 : 0,
            estado: opciones.estado || '',
        };
        var db = await abrir();
        await pedir(db.transaction(ALMACEN, 'readwrite').objectStore(ALMACEN).put(registro));
        if (opciones.texto) await indexar(id, opciones.texto);
        hacerSitioSiHaceFalta();      // sin esperar: no debe frenar al que guarda
        return true;
    }

    async function leer(id) {
        var db = await abrir();
        var r = await pedir(db.transaction(ALMACEN, 'readonly').objectStore(ALMACEN).get(String(id)));
        if (!r) return null;
        // se anota que se uso, que es lo que decide quien sobrevive a la purga
        r.usado = Date.now();
        try {
            db.transaction(ALMACEN, 'readwrite').objectStore(ALMACEN).put(r);
        } catch (e) { /* si falla, solo se pierde la marca de uso */ }
        return global.MaquitaCifrado.descifrar(r);
    }

    async function borrar(id) {
        var db = await abrir();
        await pedir(db.transaction(ALMACEN, 'readwrite').objectStore(ALMACEN).delete(String(id)));
    }

    /* --- indice de busqueda: huellas, nunca el texto --- */
    async function indexar(ref, texto) {
        var hs = await global.MaquitaCifrado.huellas(texto);
        if (!hs.length) return;
        var db = await abrir();
        var tx = db.transaction(INDICE, 'readwrite');
        var s = tx.objectStore(INDICE);
        hs.forEach(function (h) { s.put({huella: h, ref: String(ref)}); });
    }

    async function buscar(termino) {
        var h = await global.MaquitaCifrado.huella(
            global.MaquitaCifrado.normalizar(termino)[0] || '');
        var db = await abrir();
        var filas = await pedir(db.transaction(INDICE, 'readonly')
            .objectStore(INDICE).index('huella').getAll(h));
        var vistos = {};
        return filas.map(function (f) { return f.ref; })
            .filter(function (r) { if (vistos[r]) return false; vistos[r] = 1; return true; });
    }

    /* --- el presupuesto --- */
    async function espacio() {
        var db = await abrir();
        var todos = await pedir(db.transaction(ALMACEN, 'readonly').objectStore(ALMACEN).getAll());
        var por = {correo: 0, chat: 0, otros: 0};
        var total = 0, pendientes = 0;
        todos.forEach(function (r) {
            total += r.bytes || 0;
            por[r.area] = (por[r.area] || 0) + (r.bytes || 0);
            if (r.fijo) pendientes += r.bytes || 0;
        });
        return {total: total, tope: TOPE, porcentaje: total / TOPE,
                areas: por, pendientes: pendientes, registros: todos.length};
    }

    /* Borra lo mas viejo y menos usado hasta bajar del 75 %. NUNCA toca lo marcado como
       fijo (la cola de envio): si alguien escribio sin conexion, su mensaje sale, ocupe
       lo que ocupe. Si solo con lo fijo se pasara del tope, se avisa en vez de borrarlo. */
    async function hacerSitio(objetivo) {
        var e = await espacio();
        if (e.total <= (objetivo || TOPE * 0.75)) return {liberado: 0, borrados: 0};
        var db = await abrir();
        var todos = await pedir(db.transaction(ALMACEN, 'readonly').objectStore(ALMACEN).getAll());
        var candidatos = todos.filter(function (r) { return !r.fijo; })
            .sort(function (a, b) { return (a.usado || 0) - (b.usado || 0); });
        var tx = db.transaction(ALMACEN, 'readwrite');
        var s = tx.objectStore(ALMACEN);
        var liberado = 0, borrados = 0, meta = e.total - (objetivo || TOPE * 0.75);
        for (var i = 0; i < candidatos.length && liberado < meta; i++) {
            s.delete(candidatos[i].id);
            liberado += candidatos[i].bytes || 0;
            borrados++;
        }
        if (liberado < meta) {
            console.warn('T-49: no se pudo liberar todo lo necesario sin tocar los envios '
                         + 'pendientes; se dejan intactos a proposito');
        }
        return {liberado: liberado, borrados: borrados};
    }

    var comprobando = false;
    async function hacerSitioSiHaceFalta() {
        if (comprobando) return;
        comprobando = true;
        try {
            var e = await espacio();
            if (e.porcentaje >= UMBRAL) await hacerSitio();
        } catch (err) {
            /* el caché es un lujo: si falla, la aplicación sigue funcionando sin él */
        } finally {
            comprobando = false;
        }
    }

    /* Al cerrar sesión: fuera todo. Sin llave ya no sería legible, pero se borra igual. */
    async function vaciar() {
        var db = await abrir();
        var tx = db.transaction([ALMACEN, INDICE], 'readwrite');
        tx.objectStore(ALMACEN).clear();
        tx.objectStore(INDICE).clear();
        global.MaquitaCifrado.olvidar();
    }

    global.MaquitaAlmacen = {
        guardar: guardar, leer: leer, borrar: borrar,
        buscar: buscar, espacio: espacio, hacerSitio: hacerSitio, vaciar: vaciar,
        TOPE: TOPE, REPARTO: REPARTO,
    };
})(window);
