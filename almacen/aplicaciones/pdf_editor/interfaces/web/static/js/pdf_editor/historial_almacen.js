/* ============================================================
   Raíces Maquita — Editor PDF: DÓNDE SE GUARDAN LOS PASOS VIEJOS

   Deshacer guarda una copia del documento entero por cada cambio. Con documentos
   grandes eso llena la memoria del navegador enseguida, y por eso antes solo se
   guardaban los 25 últimos cambios: a partir de ahí, los viejos se tiraban y ya no
   se podía volver atrás.

   Desde el 30-jul-2026 no se tira ninguno: los pasos que ya no caben en memoria se
   guardan en el disco del navegador (IndexedDB), que aguanta muchísimo más, y se
   recuperan cuando hacen falta. Así se puede deshacer hasta el primer cambio.

   Lo guardado es de la sesión: al abrir el editor se limpia lo que quedara de
   sesiones anteriores, para no ir llenando el disco de nadie.
   ============================================================ */
(function () {
    'use strict';

    const NOMBRE_BD = 'faro-editor-pdf-historial';
    const ALMACEN = 'pasos';

    let bd = null;
    let disponible = true;

    function abrir() {
        return new Promise((resolver, rechazar) => {
            if (bd) return resolver(bd);
            if (!window.indexedDB) { disponible = false; return rechazar(new Error('sin IndexedDB')); }
            const peticion = window.indexedDB.open(NOMBRE_BD, 1);
            peticion.onupgradeneeded = () => {
                const base = peticion.result;
                if (!base.objectStoreNames.contains(ALMACEN)) {
                    base.createObjectStore(ALMACEN, { autoIncrement: true });
                }
            };
            peticion.onsuccess = () => { bd = peticion.result; resolver(bd); };
            peticion.onerror = () => { disponible = false; rechazar(peticion.error); };
        });
    }

    function conAlmacen(modo, hacer) {
        return abrir().then(base => new Promise((resolver, rechazar) => {
            const transaccion = base.transaction(ALMACEN, modo);
            const almacen = transaccion.objectStore(ALMACEN);
            let resultado;
            try {
                resultado = hacer(almacen);
            } catch (e) {
                return rechazar(e);
            }
            transaccion.oncomplete = () => resolver(resultado && resultado.result !== undefined
                                                   ? resultado.result : resultado);
            transaccion.onerror = () => rechazar(transaccion.error);
            transaccion.onabort = () => rechazar(transaccion.error);
        }));
    }

    window.PDFHistorialAlmacen = {
        /** ¿Se puede usar el disco del navegador? Si no, el historial sigue
         *  funcionando solo en memoria (con menos pasos). */
        disponible: () => disponible,

        /** Se llama al arrancar el editor: abre la base y tira lo de sesiones
         *  anteriores, que ya no le sirve a nadie. */
        iniciar: function () {
            return conAlmacen('readwrite', a => a.clear()).catch(() => { disponible = false; });
        },

        /** Guarda una copia y devuelve su número, para poder pedirla luego. */
        guardar: function (bytes) {
            // Se guarda una copia propia: los bytes de fuera pueden cambiar después.
            return conAlmacen('readwrite', a => a.add(bytes.slice(0)));
        },

        /** Devuelve la copia guardada, o null si ya no está. */
        leer: function (id) {
            return conAlmacen('readonly', a => a.get(id))
                .then(v => (v ? new Uint8Array(v) : null))
                .catch(() => null);
        },

        borrar: function (id) {
            return conAlmacen('readwrite', a => a.delete(id)).catch(() => {});
        },

        vaciar: function () {
            return conAlmacen('readwrite', a => a.clear()).catch(() => {});
        },
    };
})();
