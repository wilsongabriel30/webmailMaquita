/* ============================================================
   Raíces Maquita - Editor PDF: DESHACER y REHACER (Ctrl+Z · Ctrl+Y)

   «necesito que me habilites a presionar ctrl z y que se me deshaga el cambio
   e igual para rehacer un cambio» — el usuario, 27-jul-2026.

   Guarda una foto del documento ANTES de cada cambio que lo modifica de verdad
   (tablas, páginas, texto, imágenes, firmas…) y permite volver atrás paso a
   paso, o rehacer lo deshecho.

   Se guarda el documento entero, no "el cambio": es lo único fiable cuando
   cada operación la hace el servidor y devuelve un PDF nuevo. Como eso ocupa,
   se limita el número de pasos y se descartan los más viejos — con aviso, para
   que nadie crea que puede volver hasta el principio de la sesión.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    // Se puede deshacer hasta el PRIMER cambio y rehacer hasta el último: no hay
    // límite de pasos (pedido del usuario el 30-jul-2026).
    //
    // Cada paso es una copia del documento entero, así que tenerlos todos en memoria
    // llenaría el navegador: antes se guardaban solo los 25 últimos y los viejos se
    // tiraban. Ahora los que no caben en memoria se bajan al disco del navegador
    // (historial_almacen.js) y se recuperan cuando hacen falta; no se tira ninguno.
    const MEMORIA_MAXIMA = 60 * 1024 * 1024;    // lo que se conserva a mano, en memoria
    // Tope de seguridad: si un documento enorme se edita cientos de veces, en algún
    // momento hay que parar. Es diez veces más de lo que se guardaba antes.
    const PESO_MAXIMO = 1800 * 1024 * 1024;

    let api = null;
    // Cada paso es de una de estas dos clases:
    //   {tipo:'doc',  bytes, etiqueta}                  -> una foto del documento entero
    //   {tipo:'anot', pagina, copia, pesoAprox, etiqueta} -> las anotaciones de UNA página
    // Están en la misma pila a propósito: así Ctrl+Z deshace en el orden en que se
    // hicieron las cosas, sin que el usuario tenga que adivinar qué se deshace antes.
    const atras = [];
    const adelante = [];
    let aplicando = false;  // para no registrar el propio deshacer como cambio

    function peso(pila) {
        // Los pasos de anotaciones no tienen bytes; se guarda su tamaño aproximado al
        // registrarlos, porque una imagen o una firma pegada pesa de verdad.
        return pila.reduce((suma, paso) =>
            suma + (paso.bytes ? paso.bytes.length : (paso.pesoAprox || 0)), 0);
    }

    /** Lo que ocupa AHORA MISMO en memoria (lo que ya está en disco no cuenta). */
    function pesoEnMemoria() {
        const dePila = p => p.reduce((s, paso) => s + (paso.bytes ? paso.bytes.length : 0), 0);
        return dePila(atras) + dePila(adelante);
    }

    const almacen = () => window.PDFHistorialAlmacen;

    /** Baja al disco del navegador los pasos más viejos hasta que la memoria vuelva a
     *  estar por debajo del límite. No se pierde ninguno: solo cambian de sitio. */
    let bajando = false;
    async function liberarMemoria() {
        if (bajando || !almacen() || !almacen().disponible()) return;
        bajando = true;
        try {
            // Del más viejo al más nuevo: los recientes se quieren a mano, porque son
            // los que el usuario va a deshacer primero.
            const candidatos = atras.concat(adelante).filter(p => p.bytes && p.tipo === 'doc');
            for (const paso of candidatos) {
                if (pesoEnMemoria() <= MEMORIA_MAXIMA) break;
                try {
                    const id = await almacen().guardar(paso.bytes);
                    paso.id = id;
                    paso.pesoAprox = paso.bytes.length;
                    paso.bytes = null;      // se suelta la memoria SOLO cuando ya está a salvo
                } catch (e) {
                    break;                  // el disco no acepta más: se deja en memoria
                }
            }
        } finally {
            bajando = false;
        }
    }

    /** Los bytes de un paso, estén en memoria o en el disco del navegador. */
    async function bytesDe(paso) {
        if (paso.bytes) return paso.bytes;
        if (paso.id != null && almacen()) return await almacen().leer(paso.id);
        return null;
    }

    function recortar() {
        // Ya no se descarta por número de pasos: se puede volver hasta el primer cambio.
        // Solo se tira si se llega al tope de seguridad, y entonces se avisa.
        let descartados = 0;
        while (atras.length > 1 && peso(atras) + peso(adelante) > PESO_MAXIMO) {
            const fuera = atras.shift();
            if (fuera && fuera.id != null && almacen()) almacen().borrar(fuera.id);
            descartados++;
        }
        return descartados;
    }

    // ── registro ─────────────────────────────────────────────────────────
    // Se llama ANTES de cambiar el documento, con lo que hay ahora mismo.
    function registrar(bytes, etiqueta) {
        if (aplicando || !bytes || !bytes.length) return;
        atras.push({tipo: 'doc', bytes: bytes.slice(0), etiqueta: etiqueta || 'el último cambio'});
        adelante.length = 0;        // una acción nueva corta la rama de rehacer
        const descartados = recortar();
        liberarMemoria();       // en segundo plano: no hace esperar al usuario
        if (descartados && api) {
            api.toast('El historial llegó a su tope: los cambios más antiguos ya no se '
                      + 'pueden deshacer.', 'warn');
        }
        pintarBotones();
    }

    /** Guarda cómo estaban las anotaciones de una página ANTES de tocarlas.
     *  Lo usa la goma: si no, borrar una firma no tendría marcha atrás. */
    function registrarAnotaciones(pagina, anotaciones, etiqueta) {
        if (aplicando) return;
        // Se copia de verdad (no la referencia): si no, al borrar se modificaría
        // también la copia guardada y el deshacer no serviría de nada.
        const texto = JSON.stringify(anotaciones || []);
        atras.push({
            tipo: 'anot',
            pagina: pagina,
            copia: JSON.parse(texto),
            pesoAprox: texto.length,
            etiqueta: etiqueta || 'el último borrado',
        });
        adelante.length = 0;
        const descartados = recortar();
        liberarMemoria();       // en segundo plano: no hace esperar al usuario
        if (descartados && api) {
            api.toast('El historial llegó a su tope: los cambios más antiguos ya no se '
                      + 'pueden deshacer.', 'warn');
        }
        pintarBotones();
    }

    /** Foto de las anotaciones de una página tal como están AHORA. */
    function fotoAnotaciones(pagina, etiqueta) {
        const texto = JSON.stringify((api.getAnotaciones && api.getAnotaciones(pagina)) || []);
        return {tipo: 'anot', pagina: pagina, copia: JSON.parse(texto),
                pesoAprox: texto.length, etiqueta: etiqueta};
    }

    async function deshacer() {
        if (!atras.length) {
            api.toast('No hay nada que deshacer.', 'warn');
            return;
        }
        const paso = atras.pop();
        if (paso.tipo === 'anot') {
            adelante.push(fotoAnotaciones(paso.pagina, paso.etiqueta));
            aplicarAnotaciones(paso, 'Se deshizo ' + paso.etiqueta + '.');
            return;
        }
        const actual = api.getPdfBytes();
        if (actual && actual.length) {
            adelante.push({tipo: 'doc', bytes: actual.slice(0), etiqueta: paso.etiqueta});
        }
        const bytes = await bytesDe(paso);
        if (!bytes) {
            api.toast('No se pudo recuperar ese paso del historial.', 'error');
            return;
        }
        await aplicar(bytes, 'Se deshizo ' + paso.etiqueta + '.');
    }

    async function rehacer() {
        if (!adelante.length) {
            api.toast('No hay nada que rehacer.', 'warn');
            return;
        }
        const paso = adelante.pop();
        if (paso.tipo === 'anot') {
            atras.push(fotoAnotaciones(paso.pagina, paso.etiqueta));
            aplicarAnotaciones(paso, 'Se rehízo ' + paso.etiqueta + '.');
            return;
        }
        const actual = api.getPdfBytes();
        if (actual && actual.length) {
            atras.push({tipo: 'doc', bytes: actual.slice(0), etiqueta: paso.etiqueta});
        }
        const bytes = await bytesDe(paso);
        if (!bytes) {
            api.toast('No se pudo recuperar ese paso del historial.', 'error');
            return;
        }
        await aplicar(bytes, 'Se rehízo ' + paso.etiqueta + '.');
    }

    /** Devolver las anotaciones de una página a como estaban. No toca el documento,
     *  así que no hace falta el velo de carga ni volver a abrir el PDF. */
    function aplicarAnotaciones(paso, mensaje) {
        aplicando = true;
        try {
            api.reemplazarAnotaciones(paso.pagina, paso.copia);
            api.toast(mensaje, 'ok');
        } catch (e) {
            api.toast('No se pudo: ' + e.message, 'error');
        } finally {
            aplicando = false;
            pintarBotones();
        }
    }

    async function aplicar(bytes, mensaje) {
        aplicando = true;
        api.showLoading(true, 'Un momento…');
        const pagina = api.getPagina();
        try {
            await api.reemplazarPdf(bytes.slice(0));
            // Volver donde estaba el usuario, no al principio del documento
            if (api.irAPagina && pagina > 1) api.irAPagina(pagina);
            api.toast(mensaje, 'ok');
        } catch (e) {
            api.toast('No se pudo: ' + e.message, 'error');
        } finally {
            api.showLoading(false);
            aplicando = false;
            pintarBotones();
            // Si había controles de tabla puestos, se vuelven a reconocer
            if (window.PDFTablasColumnas) {
                setTimeout(() => window.PDFTablasColumnas.refrescarTrasCambio(), 500);
            }
        }
    }

    function limpiar() {
        // Documento nuevo: lo guardado ya no vale para nada, ni en memoria ni en disco.
        if (almacen()) almacen().vaciar();
        atras.length = 0;
        adelante.length = 0;
        pintarBotones();
    }

    // ── botones de la barra ──────────────────────────────────────────────
    function pintarBotones() {
        const deshacerBtn = document.getElementById('btnDeshacer');
        const rehacerBtn = document.getElementById('btnRehacer');
        if (deshacerBtn) {
            deshacerBtn.disabled = !atras.length;
            deshacerBtn.title = atras.length
                ? 'Deshacer ' + atras[atras.length - 1].etiqueta + ' (Ctrl+Z)'
                : 'Deshacer (Ctrl+Z) — no hay nada que deshacer';
        }
        if (rehacerBtn) {
            rehacerBtn.disabled = !adelante.length;
            rehacerBtn.title = adelante.length
                ? 'Rehacer ' + adelante[adelante.length - 1].etiqueta + ' (Ctrl+Y)'
                : 'Rehacer (Ctrl+Y) — no hay nada que rehacer';
        }
    }

    function iniciar(puente) {
        // Se limpia lo que quedara de sesiones anteriores en el disco del navegador.
        if (almacen()) almacen().iniciar();
        api = puente;
        document.getElementById('btnDeshacer')?.addEventListener('click', deshacer);
        document.getElementById('btnRehacer')?.addEventListener('click', rehacer);

        document.addEventListener('keydown', function (e) {
            if (!(e.ctrlKey || e.metaKey)) return;
            const tecla = (e.key || '').toLowerCase();
            // Dentro de un campo de texto mandan el deshacer del propio campo
            const donde = document.activeElement;
            if (donde && (donde.tagName === 'INPUT' || donde.tagName === 'TEXTAREA' ||
                          donde.isContentEditable)) return;
            if (tecla === 'z' && !e.shiftKey) { e.preventDefault(); deshacer(); }
            else if (tecla === 'y' || (tecla === 'z' && e.shiftKey)) { e.preventDefault(); rehacer(); }
        });
        pintarBotones();
    }

    window.PDFHistorial = {
        iniciar: iniciar,
        registrar: registrar,
        registrarAnotaciones: registrarAnotaciones,
        deshacer: deshacer,
        rehacer: rehacer,
        limpiar: limpiar,
        hayPasos: () => atras.length,
        // Para las pruebas: cuánto se guarda y cuánto queda en memoria.
        detalle: () => ({ atras: atras.length, adelante: adelante.length,
                          enMemoria: pesoEnMemoria(),
                          enDisco: atras.concat(adelante).filter(p => p.id != null).length })
    };
})();
