/* =============================================================================
   T-49 · CIFRAR Y DESCIFRAR LO QUE SE GUARDA EN EL EQUIPO
   -----------------------------------------------------------------------------
   QUE HACE: convierte cualquier dato en un paquete cifrado listo para guardar, y
   lo devuelve tal cual estaba al leerlo. Ademas calcula las «huellas» con las que
   se puede buscar sin descifrar nada.
   POR QUE:  lo que se guarda en el disco no puede quedar legible para quien copie
   los archivos del equipo. Aqui solo esta el CIFRADO; donde vive la llave es otro
   asunto y vive en cache-llave.js, que es la pieza que de verdad decide si esto
   protege algo.
   DONDE SE LLAMA: lo usa cache-almacen.js. Nadie mas deberia cifrar por su cuenta.
   ============================================================================= */
(function (global) {
    'use strict';

    var VERSION = 1;          // por si algun dia cambia el formato y hay que migrar
    var TAM_IV = 12;          // AES-GCM pide 12 bytes
    var codificador = new TextEncoder();
    var decodificador = new TextDecoder();

    var llaveIndice = null;   // la de las huellas: NUNCA la misma que la de cifrar

    /* Dos usos distintos, dos llaves distintas. Usar la misma para cifrar y para
       firmar huellas es un error clasico: filtra informacion de una a la otra. */
    async function obtenerLlaveIndice() {
        if (llaveIndice) return llaveIndice;
        var base = await global.MaquitaLlave.obtener();
        // la llave de cifrado no es exportable, asi que la del indice se deriva de algo
        // que si podemos manejar: una firma estable hecha CON ella.
        var semilla = await crypto.subtle.encrypt(
            {name: 'AES-GCM', iv: new Uint8Array(TAM_IV)},
            base, codificador.encode('indice-busqueda-v1'));
        var material = await crypto.subtle.importKey(
            'raw', new Uint8Array(semilla).slice(0, 32), {name: 'HMAC', hash: 'SHA-256'},
            false, ['sign']);
        llaveIndice = material;
        return llaveIndice;
    }

    /* --- cifrar --- */
    async function cifrar(valor) {
        var llave = await global.MaquitaLlave.obtener();
        var iv = crypto.getRandomValues(new Uint8Array(TAM_IV));   // NUNCA se repite
        var claro = codificador.encode(JSON.stringify(valor));
        var cifrado = await crypto.subtle.encrypt({name: 'AES-GCM', iv: iv}, llave, claro);
        return {v: VERSION, iv: iv, ct: new Uint8Array(cifrado)};
    }

    async function descifrar(paquete) {
        if (!paquete || !paquete.ct) return null;
        var llave = await global.MaquitaLlave.obtener();
        try {
            var claro = await crypto.subtle.decrypt(
                {name: 'AES-GCM', iv: new Uint8Array(paquete.iv)}, llave,
                new Uint8Array(paquete.ct));
            return JSON.parse(decodificador.decode(claro));
        } catch (e) {
            // Si no se puede descifrar, lo honesto es tratarlo como si no estuviera:
            // pasa cuando la llave cambio (otro usuario, otro equipo, sesion nueva).
            // Nunca se devuelve algo a medias.
            return null;
        }
    }

    /* Un lote entero en una sola pasada: WebCrypto es asincrono y hacerlo de uno en
       uno son cientos de idas y vueltas que si se notan al abrir el chat. */
    async function cifrarLote(lista) {
        return cifrar(lista);
    }

    /* --- huellas para buscar sin descifrar --- */
    function normalizar(texto) {
        return String(texto || '')
            .toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '')   // sin tildes
            .replace(/[^\w\s]/g, ' ')
            .split(/\s+/)
            .filter(function (p) { return p.length >= 3; });
    }

    async function huella(termino) {
        var llave = await obtenerLlaveIndice();
        var firma = await crypto.subtle.sign('HMAC', llave, codificador.encode(termino));
        // 12 bytes bastan para no chocar y ocupan la mitad que la firma entera
        return btoa(String.fromCharCode.apply(null, new Uint8Array(firma).slice(0, 12)));
    }

    /* Las huellas de un texto, para poder encontrarlo despues por palabra exacta.
       Que quede claro: NO permite buscar por trozos («factur» no encuentra «facturas»);
       eso es el precio de que el contenido este cifrado. */
    async function huellas(texto) {
        var palabras = normalizar(texto);
        var unicas = Object.keys(palabras.reduce(function (a, p) { a[p] = 1; return a; }, {}));
        var salida = [];
        for (var i = 0; i < unicas.length && i < 200; i++) {
            salida.push(await huella(unicas[i]));
        }
        return salida;
    }

    function olvidar() {
        llaveIndice = null;
    }

    global.MaquitaCifrado = {
        cifrar: cifrar,
        descifrar: descifrar,
        cifrarLote: cifrarLote,
        huella: huella,
        huellas: huellas,
        normalizar: normalizar,
        olvidar: olvidar,
        VERSION: VERSION,
    };
})(window);
