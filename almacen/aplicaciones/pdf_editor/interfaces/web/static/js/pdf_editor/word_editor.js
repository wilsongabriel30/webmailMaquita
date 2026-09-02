/* ============================================================
   Raíces Maquita - Editor PDF: EDICIÓN TIPO WORD ("Digitalizar y OCR")

   Antes esta herramienta encendía la edición palabra por palabra con doble
   clic (y en escaneos descargaba un .txt). El usuario pidió otra cosa: que el
   documento se abra como un Word de verdad, donde se pueda escribir con
   soltura y manejar tablas — agregar y quitar columnas — sin perder el
   formato ni el tipo de letra.

   Aquí se hace justo eso: el PDF se manda al servidor, vuelve convertido en
   .docx y se abre incrustado en el OnlyOffice de Maquita. Al terminar, el
   documento vuelve a PDF y se recarga en el editor.

   Sobre la ESPERA (27-jul-2026, el usuario reportó que tardaba):
     - el api.js del editor de documentos se va cargando SOLO, en cuanto se
       abre el editor PDF, para que al pulsar la herramienta ya esté listo;
     - la ventana se abre en el acto y la espera se ve DENTRO, contando lo que
       está pasando en cada momento, en vez de dejar la pantalla congelada.

   El trabajo pesado (OCR si es un escaneo, PDF→Word, Word→PDF) está en
   modulos/pdf_editor/interfaces/api/pdf_word_api.py.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    const $ = id => document.getElementById(id);

    let api = null;         // puente con el núcleo del editor
    let editor = null;      // instancia de DocsAPI.DocEditor
    let clave = null;       // documento abierto en el servidor
    let cerrando = false;
    let promesaScript = null;   // carga del api.js (una sola vez por página)
    let cronometro = null;

    // ── carga del api.js del Document Server ─────────────────────────────
    // Se dispara al abrir el editor PDF, sin que el usuario pida nada: son
    // varios cientos de KB desde otra VM y no tiene sentido empezar a
    // buscarlos cuando ya está esperando.
    function cargarScript(url) {
        if (window.DocsAPI) return Promise.resolve();
        if (promesaScript) return promesaScript;
        promesaScript = new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = url;
            s.onload = () => resolve();
            s.onerror = () => { promesaScript = null; reject(new Error('No se pudo cargar el editor de documentos')); };
            document.head.appendChild(s);
        });
        return promesaScript;
    }

    function precargar() {
        fetch('/api/pdf/word/estado?rapido=1', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (d && d.exito && d.configurado && d.servidor) {
                    cargarScript(d.servidor + '/web-apps/apps/api/documents/api.js')
                        .catch(() => { /* si falla, se reintenta al pulsar */ });
                }
            })
            .catch(() => { /* sin conexión: se reintenta al pulsar */ });
    }

    // ── ventana ──────────────────────────────────────────────────────────
    function mostrarVentana(titulo) {
        $('modalWord').classList.remove('hidden');
        $('tituloWord').textContent = titulo || 'Documento';
        document.body.style.overflow = 'hidden';
    }

    function mostrarAviso(texto) {
        const cartel = $('avisoWord');
        if (!cartel) return;
        cartel.textContent = texto || '';
        cartel.style.display = texto ? 'block' : 'none';
    }

    function ocultarVentana() {
        $('modalWord').classList.add('hidden');
        document.body.style.overflow = '';
        mostrarAviso('');
        const contenedor = $('contenedorWord');
        if (contenedor) contenedor.innerHTML = '<div id="editorWord"></div>';
        try { if (editor) editor.destroyEditor(); } catch (e) { /* ya cerrado */ }
        editor = null;
    }

    // Espera visible: dice QUÉ se está haciendo y cuánto lleva, que es lo que
    // separa "está trabajando" de "se colgó".
    function ocupado(si, mensaje) {
        const capa = $('cargandoWord');
        if (!capa) return;
        capa.classList.toggle('hidden', !si);
        const texto = $('textoCargandoWord');
        if (texto && mensaje) texto.dataset.base = mensaje;
        clearInterval(cronometro);
        if (si) {
            const desde = Date.now();
            const pintar = () => {
                if (!texto) return;
                const s = Math.round((Date.now() - desde) / 1000);
                texto.textContent = (texto.dataset.base || 'Un momento…') +
                                    (s >= 3 ? '  (' + s + ' s)' : '');
            };
            pintar();
            cronometro = setInterval(pintar, 1000);
        }
        ['btnWordAPdf', 'btnWordDocx', 'btnWordCerrar'].forEach(id => {
            const b = $(id);
            if (b) b.disabled = !!si;
        });
    }

    function paso(mensaje) {
        const texto = $('textoCargandoWord');
        if (texto) texto.dataset.base = mensaje;
    }

    // ── abrir: PDF → Word ────────────────────────────────────────────────
    async function abrir(puente) {
        api = puente;
        if (!api || !api.getPdfBlob()) {
            api && api.toast('Primero abre un documento PDF.', 'warn');
            return;
        }

        // La ventana se abre YA: la espera se ve dentro, no en una pantalla
        // congelada detrás de la que no se sabe si pasa algo.
        mostrarVentana(api.getNombre().replace(/\.pdf$/i, ''));
        ocupado(true, 'Preparando el documento para editarlo como Word…');
        try {
            const datos = new FormData();
            datos.append('archivo', api.getPdfBlob(), api.getNombre() || 'documento.pdf');
            datos.append('idioma', $('selectIdioma')?.value || 'spa');

            const resp = await fetch('/api/pdf/word/abrir', {
                method: 'POST', body: datos, credentials: 'same-origin'
            });
            const json = await resp.json();
            if (!json.exito) throw new Error(json.mensaje || 'No se pudo convertir el documento');

            clave = json.clave;
            paso('Abriendo el editor…');
            await cargarScript(json.api_js_url);

            $('tituloWord').textContent = json.titulo || 'Documento';
            if (json.ocr) {
                mostrarAviso('Este documento era un escaneo: su texto se reconoció con OCR ' +
                             'para que puedas editarlo. Conviene repasarlo — el OCR puede ' +
                             'confundir alguna palabra, y los sellos y firmas manuscritas ' +
                             'no se conservan.');
            }

            const config = JSON.parse(JSON.stringify(json.config));
            config.events = {
                // El editor ya está en pantalla: se retira la espera
                onDocumentReady: () => ocupado(false),
                onAppReady: () => paso('Cargando el documento…'),
                onError: e => {
                    ocupado(false);
                    api.toast('El editor de documentos avisó de un error: ' +
                              (e && e.data ? e.data : ''), 'error');
                },
                onRequestClose: () => cerrar(false),
            };
            editor = new window.DocsAPI.DocEditor('editorWord', config);

            // Red de seguridad: si onDocumentReady no llegara (versión del
            // servidor, red rara), no dejar la espera puesta para siempre.
            setTimeout(() => ocupado(false), 90000);
        } catch (e) {
            ocupado(false);
            ocultarVentana();
            api.toast('No se pudo abrir el documento como Word: ' + e.message, 'error');
        }
    }

    // ── terminar: Word → PDF y de vuelta al editor ───────────────────────
    async function volverAPdf() {
        if (!clave) return;
        ocupado(true, 'Guardando los cambios y volviendo a PDF…');
        try {
            const datos = new FormData();
            datos.append('clave', clave);
            const resp = await fetch('/api/pdf/word/finalizar', {
                method: 'POST', body: datos, credentials: 'same-origin'
            });
            if (!resp.ok) {
                let mensaje = 'El servidor respondió ' + resp.status;
                try { mensaje = (await resp.json()).mensaje || mensaje; } catch (e) { /* no era JSON */ }
                throw new Error(mensaje);
            }
            const bytes = new Uint8Array(await resp.arrayBuffer());
            ocupado(false);
            ocultarVentana();
            await api.reemplazarPdf(bytes);
            api.toast('Listo: los cambios del Word ya están en el PDF.', 'ok');
            clave = null;
        } catch (e) {
            api.toast('No se pudo volver a PDF: ' + e.message, 'error');
        } finally {
            ocupado(false);
        }
    }

    async function descargarDocx() {
        if (!clave) return;
        ocupado(true, 'Preparando el documento de Word…');
        try {
            window.location.href = '/api/pdf/word/descargar-docx?clave=' +
                                   encodeURIComponent(clave);
            api.toast('Descargando el documento de Word…', 'ok');
        } finally {
            setTimeout(() => ocupado(false), 1500);
        }
    }

    // Cerrar sin aplicar. Lo escrito NO se pierde: sigue guardado en el
    // servidor, pero el PDF del editor se queda como estaba.
    function cerrar(preguntar) {
        if (cerrando) return;
        if (preguntar !== false && clave) {
            const seguir = window.confirm(
                'Vas a cerrar el Word sin llevar los cambios al PDF.\n\n' +
                '¿Cerrar de todas formas?');
            if (!seguir) return;
        }
        cerrando = true;
        ocupado(false);
        ocultarVentana();
        clave = null;
        cerrando = false;
    }

    document.addEventListener('DOMContentLoaded', function () {
        $('btnWordAPdf')?.addEventListener('click', volverAPdf);
        $('btnWordDocx')?.addEventListener('click', descargarDocx);
        $('btnWordCerrar')?.addEventListener('click', () => cerrar(true));
        // Precarga en segundo plano, sin estorbar a la carga de la página. Solo
        // si la herramienta está puesta: desde el 17-08-2026 el botón «Editar
        // como Word» no está en el menú, y traerse varios cientos de KB del
        // Document Server en cada visita para nada sería tirar el tiempo del
        // usuario. Si el botón vuelve, esto vuelve solo.
        if ($('toolWordAvanzado')) setTimeout(precargar, 2500);
    });

    window.PDFWordEditor = { abrir: abrir };
})();
