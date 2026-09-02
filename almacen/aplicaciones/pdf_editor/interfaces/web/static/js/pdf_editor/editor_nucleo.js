/* ============================================================
   Raíces Maquita - Editor PDF: nucleo del editor (carga, render, herramientas, paneles)
   Extraido del template pdf_editor/index.html para modularizar el frontend.
   La configuracion que antes inyectaba Jinja llega en window.PDF_EDITOR_CFG
   (definido inline en el template antes de cargar este archivo).
   IMPORTANTE: nginx sirve /static con cache de 1 anio; cualquier
   cambio aqui exige subir la version ?v= en el template.
   ============================================================ */
// Worker de pdf.js auto-hospedado (la URL exacta llega del template via CFG)
pdfjsLib.GlobalWorkerOptions.workerSrc = (window.PDF_EDITOR_CFG || {}).workerSrc || '/static/vendor/pdfjs-3.11.174/pdf.worker.min.js';

document.addEventListener('DOMContentLoaded', function() {
    // Verificar documento pendiente
    const pendingPDF = sessionStorage.getItem('pendingPDF');
    // Modo con el que el servidor abrió el editor ('nuevo' o edición de documento)
    const modoEditor = (window.PDF_EDITOR_CFG || {}).modo || 'nuevo';

    // Estado global
    const state = {
        pdfDoc: null,
        pdfBytes: null,
        currentPage: 1,
        totalPages: 0,
        zoom: 1.0,
        // Vista de varias páginas por fila (como Word): al alejar el zoom las páginas
        // se acomodan en columnas. 'columnas' es cuántas caben AHORA (calculado),
        // 'anchoPagina1x' es el ancho de la página 1 a escala 1 (base del cálculo).
        columnas: 1,
        anchoPagina1x: 0,
        rotation: {},
        currentTool: null,
        annotations: {},
        hayCambios: false,
        signatureData: null,
        signatureColor: '#000000'
    };

    // DOM shortcuts
    const $ = id => document.getElementById(id);

    // ==================== REPARTO EN PARTES ====================
    // El editor está repartido en varios archivos (la lista PARTES, al final de este
    // archivo). Antes era uno solo de más de 6.000 líneas: no se podía revisar, y dos
    // personas no podían tocarlo a la vez sin pisarse.
    //
    // `E` es lo ÚNICO que comparten: el estado del documento, las ayudas comunes y
    // las funciones que unas partes necesitan de otras. Abajo se rellena y se arranca
    // cada parte pasándoselo.
    const E = {};

    // Estas funciones se han ido a otro archivo, pero aquí se siguen llamando por su
    // nombre: el delegador busca la de verdad en `E` en el momento de la llamada, no
    // ahora (ahora todavía no está registrada).
    const _aplicarDisposicionPaginas = (...a) => E._aplicarDisposicionPaginas(...a);   // parte render_vista
    const _hornearPDF = (...a) => E._hornearPDF(...a);   // parte compartir
    const _onViewerScroll = (...a) => E._onViewerScroll(...a);   // parte render_vista
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    const renderPage = (...a) => E.renderPage(...a);   // parte render_vista
    const renderSinglePage = (...a) => E.renderSinglePage(...a);   // parte render_vista
    const renderVisiblePages = (...a) => E.renderVisiblePages(...a);   // parte render_vista
    const setTool = (...a) => E.setTool(...a);   // parte herramientas
    const verPaginasPorFila = (...a) => E.verPaginasPorFila(...a);   // parte render_vista

    // ==================== FUENTES DE TEXTO ====================
    // Fuentes estándar de PDF (no requieren incrustar archivos): cada familia mapea
    // su equivalente CSS para el editor y sus 4 variantes pdf-lib [normal, negrita, cursiva, negrita+cursiva]
    const FUENTES_TEXTO = {
        helvetica: { css: 'Helvetica, Arial, sans-serif',        pdf: ['Helvetica', 'HelveticaBold', 'HelveticaOblique', 'HelveticaBoldOblique'] },
        times:     { css: '"Times New Roman", Times, serif',     pdf: ['TimesRoman', 'TimesRomanBold', 'TimesRomanItalic', 'TimesRomanBoldItalic'] },
        courier:   { css: '"Courier New", Courier, monospace',   pdf: ['Courier', 'CourierBold', 'CourierOblique', 'CourierBoldOblique'] }
    };
    function _cssFuente(ann) {
        return (FUENTES_TEXTO[ann.fuente || 'helvetica'] || FUENTES_TEXTO.helvetica).css;
    }

    // Cuadro de texto seleccionado: { ann, el, pag } — controla el panel de propiedades
    let textoSeleccionado = null;
    // El cuadro de texto seleccionado se lee desde otras partes, y un `let` no se
    // puede compartir entre archivos: se reparte con estas dos funcioncitas.
    E.textoSel = () => textoSeleccionado;
    E.fijarTextoSel = v => { textoSeleccionado = v; };
    // Devuelve el contenedor (pageWrapper) de la página que se está viendo
    function _currentPageWrapper() {
        return document.getElementById('pageWrapper_' + state.currentPage);
    }
    // Devuelve la capa de anotaciones de la página que se está viendo
    function _currentAnnotLayer() {
        const w = _currentPageWrapper();
        return w ? w.querySelector('.annotation-layer') : null;
    }

    // Averigua en qué página se hizo clic
    function _getPageFromEvent(e) {
        const wrapper = e.target.closest('.page-wrapper');
        if (wrapper && wrapper.dataset.page) {
            const pg = parseInt(wrapper.dataset.page);
            state.currentPage = pg;
            $('currentPage').textContent = pg;
            return pg;
        }
        return state.currentPage;
    }
    const fileInput = $('fileInput');

    // ==================== COMPARTIDO ENTRE VARIAS PARTES ====================
    // Estas tres cosas las usan partes distintas del editor, así que viven aquí,
    // en el núcleo, y se reparten por `E`. Antes estaban cada una en su sitio,
    // cuando todo el editor era un solo archivo y se veía todo entre sí.

    // Tamaño mínimo (en puntos) de una imagen insertada: por debajo no se ve.
    const MIN_IMG_PT = 24;

    // Espacio de nombres de SVG: hace falta para crear formas con createElementNS.
    const SVGNS  = 'http://www.w3.org/2000/svg';

    // Puente para el editor de párrafos (vive en su propio archivo): le da acceso
    // controlado a lo que necesita del documento sin dejarle tocar el estado.
    const _apiParrafo = {
        getPdfBlob: () => (state.pdfBytes ? _getPdfBlob() : null),
        // Los bytes tal cual: es lo que necesita el envío por sesión para saber
        // cuánto mide nuestra copia y para pegarle el trozo que devuelve el
        // servidor. Con un Blob habría que volver a leerlo entero cada vez.
        getPdfBytes: () => state.pdfBytes,
        getZoom: () => state.zoom,
        irAPagina: n => { if (typeof renderPage === 'function') renderPage(parseInt(n)); },
        toast: (m, t) => mostrarToast(m, t),
        showLoading: (s, m) => showLoading(s, m),
        reemplazarPdf: async function (bytes, etiqueta) {
            await _cambiarDocumento(bytes, etiqueta || 'el cambio del párrafo');
        }
    };

    // ==================== CARGA DE PDF ====================
    async function loadPDF(data) {
        showLoading(true);
        try {
            let arrayBuffer;
            if (typeof data === 'string' && data.startsWith('data:')) {
                // Base64
                const base64 = data.split(',')[1];
                const binary = atob(base64);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                arrayBuffer = bytes.buffer;
            } else {
                arrayBuffer = data;
            }

            const esDocumentoNuevo = !state.pdfDoc;   // recargas (numerar, organizar...) conservan el zoom del usuario
            state.pdfBytes = new Uint8Array(arrayBuffer.slice(0));
            state.pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer.slice(0) }).promise;
            state.totalPages = state.pdfDoc.numPages;
            state.currentPage = 1;
            state.rotation = {};
            state.annotations = {};
            state.renderedPages = {};

            $('totalPages').textContent = state.totalPages;
            state.hayCambios = false;

            // El documento se deja en el servidor: a partir de aquí, cada cambio
            // manda solo su identificador en vez del PDF entero (de 6 MB por clic
            // a unos 150 kB). Va aparte, sin hacer esperar a la carga.
            //
            // OJO con la condición: cuando el PDF que se está cargando VIENE del
            // servidor —es el resultado de una edición—, el de allí ya está al
            // día y volver a subirlo entero deshacía todo el ahorro. Se subía 3 MB
            // después de cada clic, justo lo que se quería evitar, y además se
            // dejaba el archivo anterior abandonado en memoria.
            // (Auditoría del 29-jul-2026.)
            if (window.PDFSesion && !state.esDelServidor) {
                window.PDFSesion.cerrar();          // suelta el anterior de verdad
                window.PDFSesion.abrir(state.pdfBytes);
            }
            state.esDelServidor = false;

            // Zoom inicial "ajustar al ancho": la página aprovecha el área real del
            // visor en lugar del 100% fijo (que deja mucho gris en pantallas grandes)
            try {
                const p1 = await state.pdfDoc.getPage(1);
                const ancho1x = p1.getViewport({ scale: 1 }).width;
                // Se guarda siempre (aunque no sea documento nuevo): es la base para
                // calcular el zoom exacto de "ver N páginas por fila".
                state.anchoPagina1x = ancho1x;
                const disponible = $('viewerScroll').clientWidth - 48;
                if (esDocumentoNuevo && disponible > 200 && ancho1x > 0) {
                    state.zoom = Math.min(1.75, Math.max(0.5, Math.round(disponible / ancho1x * 100) / 100));
                }
            } catch (e) { /* se conserva el zoom por defecto */ }
            await renderAllPages();
        } catch (error) {
            console.error('Error cargando PDF:', error);
            alert('Error al cargar el PDF');
        } finally {
            showLoading(false);
        }
    }

    // Hook global: abrir un PDF generado por otro módulo (p.ej. Combinar) en este editor
    window.abrirPDFEnEditor = function(arrayBuffer, nombre) {
        if (state.pdfDoc && state.hayCambios &&
            !confirm('Tienes cambios sin guardar en el documento actual.\n¿Descartarlos y abrir "' + (nombre || 'el PDF combinado') + '"?')) {
            return false;
        }
        loadPDF(arrayBuffer);
        mostrarToast((nombre || 'PDF') + ' cargado en el editor.', 'success');
        return true;
    };

    // Hook gemelo del anterior: QUÉ documento hay abierto ahora mismo, para que
    // otro módulo pueda partir de él. Lo usa Combinar, para poder juntar el
    // documento que se está editando con otros sin obligar a subirlo otra vez
    // (pedido del usuario, 17-08-2026). Se entrega lo que hay AHORA, con los
    // cambios hechos, no el archivo tal como se abrió.
    window.documentoAbiertoEnEditor = function () {
        if (!state.pdfBytes) return null;
        return {
            blob: _getPdfBlob(),
            nombre: state.nombreOriginal || 'documento.pdf',
            paginas: state.totalPages || 0
        };
    };

    // Cargar PDF pendiente si existe

    // Acción elegida en una tarjeta del HOME ("Utilizar ahora"): al terminar de
    // cargar el documento se activa la herramienta que esa tarjeta promete
    function _ejecutarAccionPendiente() {
        let acc = null;
        try {
            acc = sessionStorage.getItem('pendingAccion');
            sessionStorage.removeItem('pendingAccion');
        } catch (e) { return; }
        if (!acc) return;
        const irPanel = p => document.querySelector('.top-tab[data-panel="' + p + '"]')?.click();
        setTimeout(() => {
            switch (acc) {
                case 'comentarios':
                    setTool('comment');
                    mostrarToast('Comentarios activado: haz clic sobre la página para dejar una nota.', 'ok');
                    break;
                case 'firma':
                    irPanel('firma');
                    mostrarToast('Elige cómo firmar: dibuja tu firma, usa los sellos ✓ ✗ o tu certificado digital.', 'ok');
                    break;
                case 'editar':
                    irPanel('editar');
                    setTool('text');
                    mostrarToast('Edición activada: haz clic sobre la página para agregar texto.', 'ok');
                    break;
                case 'convertir':
                    irPanel('convertir');
                    mostrarToast('Elige el formato al que quieres convertir el documento.', 'ok');
                    break;
                case 'compartir':
                    $('btnShare')?.click();
                    break;
                case 'sello':
                    irPanel('editar');
                    $('toolMarca')?.click();
                    mostrarToast('Usa la marca de agua para estampar CONFIDENCIAL, APROBADO, BORRADOR, etc.', 'ok');
                    break;
                case 'certificado':
                    irPanel('firma');
                    $('toolFirmaDigitalP12')?.click();
                    break;
                case 'medir':
                    irPanel('editar');
                    mostrarToast('La medición de objetos estará disponible próximamente; mientras tanto puedes usar Dibujar.', 'warn');
                    break;
            }
        }, 350);
    }

    if (pendingPDF) {
        try {
            const pdfData = JSON.parse(pendingPDF);
            loadPDF(pdfData.data).then(_ejecutarAccionPendiente);
            sessionStorage.removeItem('pendingPDF');
        } catch (e) {
            console.error('Error parsing pending PDF:', e);
        }
    } else if (sessionStorage.getItem('pendingPDFGrande') === '1') {
        // PDF grande transferido desde el HOME via IndexedDB
        sessionStorage.removeItem('pendingPDFGrande');
        (function() {
            const avisar = () => mostrarToast('No se pudo recuperar el PDF. Ábrelo con el botón "Abrir archivo" (Ctrl+O).', 'error');
            const rq = indexedDB.open('faroPdfEditor', 1);
            rq.onupgradeneeded = () => { rq.result.createObjectStore('pending'); };
            rq.onsuccess = () => {
                try {
                    const tx = rq.result.transaction('pending', 'readwrite');
                    const st = tx.objectStore('pending');
                    const g  = st.get('pendingPDF');
                    g.onsuccess = () => {
                        const blob = g.result;
                        st.delete('pendingPDF');
                        if (blob && blob.arrayBuffer) blob.arrayBuffer().then(buf => loadPDF(buf)).then(_ejecutarAccionPendiente);
                        else avisar();
                    };
                    g.onerror = avisar;
                } catch (e) { avisar(); }
            };
            rq.onerror = avisar;
        })();
    }

    // El usuario eligió un archivo en el diálogo de abrir
    const MAX_PDF_MB = 2048;
    // Validación compartida entre el selector de archivos y el arrastre al visor vacío
    async function abrirArchivoPDF(file) {
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            mostrarToast('Solo se admiten archivos PDF.', 'error');
        } else if (file.size > MAX_PDF_MB * 1024 * 1024) {
            mostrarToast('El PDF pesa ' + (file.size / 1024 / 1024).toFixed(1) + ' MB y supera el máximo admitido (' + MAX_PDF_MB + ' MB). Comprímelo primero e inténtalo de nuevo.', 'error');
        } else {
            state.nombreOriginal = file.name;   // se conserva para nombrar la descarga
            const buffer = await file.arrayBuffer();
            loadPDF(buffer);
        }
    }

    fileInput.addEventListener('change', async e => {
        if (e.target.files.length) {
            const file = e.target.files[0];
            e.target.value = '';
            abrirArchivoPDF(file);
        }
    });

    // ==================== VISOR VACÍO (sin documento) ====================
    // En vez del espacio gris, invita a subir un PDF: clic abre el selector
    // y también acepta arrastrar el archivo encima.
    // ==================== SELECCIÓN DE CUADROS DE TEXTO ====================
    // El panel de propiedades (banner izquierdo) solo se activa con un texto seleccionado

    function seleccionarTexto(ann, el) {
        document.querySelectorAll('.annotation-text.seleccionado').forEach(x => x.classList.remove('seleccionado'));
        const pw = el.closest('.page-wrapper');
        textoSeleccionado = { ann: ann, el: el, pag: pw ? parseInt(pw.dataset.page) : state.currentPage };
        el.classList.add('seleccionado');
        // reflejar las propiedades actuales del texto en el panel
        $('selFuenteTexto').value = ann.fuente || 'helvetica';
        $('selTamanoTexto').value = String(ann.size || 14);
        $('colorTextoSel').value = ann.color || '#000000';
        $('btnNegritaTexto').classList.toggle('activo', !!ann.negrita);
        $('btnCursivaTexto').classList.toggle('activo', !!ann.cursiva);
        $('panelTexto').classList.remove('hidden');
        _panelTextoModoNuevo(false);   // hay un cuadro elegido: el panel edita ESE
    }

    function deseleccionarTexto() {
        if (!textoSeleccionado) return;
        textoSeleccionado = null;
        document.querySelectorAll('.annotation-text.seleccionado').forEach(x => x.classList.remove('seleccionado'));
        // Con la herramienta de texto puesta el panel NO se va: sirve para elegir con
        // qué letra y color se va a escribir lo siguiente.
        if (state.currentTool === 'text') _panelTextoModoNuevo(true);
        else $('panelTexto')?.classList.add('hidden');
    }

    /** El panel «Propiedades del texto» sirve para dos cosas:
     *   - con un cuadro seleccionado, cambia ESE cuadro (lo de siempre);
     *   - con la herramienta de texto puesta y nada seleccionado, elige la letra, el
     *     tamaño y el color con los que se va a escribir el PRÓXIMO texto.
     *
     * Lo segundo es del 30-jul-2026, a petición del usuario: antes había que escribir
     * el texto primero para poder cambiarle el color o la fuente, lo que obligaba a
     * escribir, seleccionar y corregir cada vez. */
    function _panelTextoModoNuevo(activo) {
        const panel = $('panelTexto');
        if (!panel) return;
        if (activo) panel.classList.remove('hidden');
        else if (!textoSeleccionado) panel.classList.add('hidden');

        const titulo = panel.querySelector('.panel-texto-titulo');
        const ayuda  = panel.querySelector('.panel-texto-ayuda');
        const borrar = $('btnEliminarTextoSel');
        // Todavía no hay ningún cuadro que borrar: el botón sobra y confunde.
        if (borrar) borrar.style.display = activo ? 'none' : '';
        if (titulo) titulo.innerHTML = activo
            ? '<i class="bi bi-fonts"></i> Texto nuevo'
            : '<i class="bi bi-fonts"></i> Propiedades del texto';
        if (ayuda) ayuda.textContent = activo
            ? 'Elige la letra, el tamaño y el color: se aplican al texto que escribas ahora.'
            : 'Los cambios se aplican al cuadro de texto seleccionado.';
    }

    // Aplica cambios de estilo al texto seleccionado SIN re-renderizar la capa
    // (se muta el mismo nodo, así la selección no se pierde)
    function _aplicarEstiloTexto(cambios) {
        if (!textoSeleccionado) return;
        const ann = textoSeleccionado.ann;
        const el  = textoSeleccionado.el;
        Object.assign(ann, cambios);
        state.hayCambios = true;
        el.style.fontFamily = _cssFuente(ann);
        el.style.fontWeight = ann.negrita ? '700' : '400';
        el.style.fontStyle  = ann.cursiva ? 'italic' : 'normal';
        el.style.fontSize   = ((ann.size || 14) * state.zoom) + 'px';
        el.style.color      = ann.color || '#000000';
    }

    $('selFuenteTexto')?.addEventListener('change', function() { _aplicarEstiloTexto({ fuente: this.value }); });
    $('selTamanoTexto')?.addEventListener('change', function() { _aplicarEstiloTexto({ size: parseInt(this.value) || 14 }); });
    $('colorTextoSel')?.addEventListener('input', function() { _aplicarEstiloTexto({ color: this.value }); });
    $('btnNegritaTexto')?.addEventListener('click', function() {
        // Sin nada seleccionado el botón sigue sirviendo: queda marcado y el texto que
        // se escriba a continuación sale en negrita.
        if (!textoSeleccionado) { this.classList.toggle('activo'); return; }
        _aplicarEstiloTexto({ negrita: !textoSeleccionado.ann.negrita });
        this.classList.toggle('activo', !!textoSeleccionado.ann.negrita);
    });
    $('btnCursivaTexto')?.addEventListener('click', function() {
        if (!textoSeleccionado) { this.classList.toggle('activo'); return; }
        _aplicarEstiloTexto({ cursiva: !textoSeleccionado.ann.cursiva });
        this.classList.toggle('activo', !!textoSeleccionado.ann.cursiva);
    });
    $('btnEliminarTextoSel')?.addEventListener('click', () => {
        if (!textoSeleccionado) return;
        const ann = textoSeleccionado.ann;
        const pag = textoSeleccionado.pag;
        deseleccionarTexto();
        const lista = state.annotations[pag] || [];
        const i = lista.indexOf(ann);
        if (i >= 0) lista.splice(i, 1);
        state.hayCambios = true;
        renderAnnotations(pag);
    });
    // Escape o clic fuera de un texto = deseleccionar (el panel se oculta)
    document.addEventListener('keydown', e => { if (e.key === 'Escape') deseleccionarTexto(); });

    $('viewerVacio')?.addEventListener('click', () => fileInput.click());
    $('viewerVacio')?.addEventListener('dragover', e => {
        e.preventDefault();
        e.currentTarget.classList.add('arrastrando');
    });
    $('viewerVacio')?.addEventListener('dragleave', e => {
        e.currentTarget.classList.remove('arrastrando');
    });
    $('viewerVacio')?.addEventListener('drop', e => {
        e.preventDefault();
        e.currentTarget.classList.remove('arrastrando');
        abrirArchivoPDF(e.dataTransfer.files && e.dataTransfer.files[0]);
    });

    // ==================== RENDERIZADO ====================
    // Crear estructura de todas las páginas en el viewer
    async function renderAllPages() {
        const viewer = $('viewerScroll');
        // Desactivar el "scroll anchoring" del navegador: al renderizar una página su altura
        // real corrige la estimada, y el anclaje ajustaba scrollTop -> disparaba scroll ->
        // renderizaba/descargaba más -> cambiaba alturas -> re-anclaba... = bucle infinito
        // (vista temblando al navegar por miniaturas en documentos grandes).
        viewer.style.overflowAnchor = 'none';
        // Se vacía conservando el aviso de "visor vacío" (el mismo nodo mantiene sus
        // escuchadores de eventos);
        // se oculta cuando hay documento y reaparece si el visor vuelve a quedar sin PDF
        const vacio = document.getElementById('viewerVacio');
        viewer.innerHTML = '';
        if (vacio) {
            vacio.classList.toggle('hidden', !!state.pdfDoc);
            viewer.appendChild(vacio);
        }
        state.renderedPages = {};

        // Documentos grandes: NO pedir getPage() de cada página solo para medirla
        // (200+ awaits secuenciales congelan la apertura). Se estima con el tamaño
        // de la página 1 y renderSinglePage corrige la medida real al renderizar.
        const modoRapido = state.totalPages > 50;
        let vpBase = null;
        if (modoRapido) {
            const p1 = await state.pdfDoc.getPage(1);
            vpBase = p1.getViewport({ scale: state.zoom });
        }

        for (let i = 1; i <= state.totalPages; i++) {
            const rotation = state.rotation[i] || 0;
            let ancho, alto;
            if (modoRapido) {
                ancho = (rotation % 180 === 0) ? vpBase.width  : vpBase.height;
                alto  = (rotation % 180 === 0) ? vpBase.height : vpBase.width;
            } else {
                const page = await state.pdfDoc.getPage(i);
                const viewport = page.getViewport({ scale: state.zoom, rotation });
                ancho = viewport.width;
                alto  = viewport.height;
            }

            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.id = 'pageWrapper_' + i;
            wrapper.dataset.page = i;
            wrapper.style.width = ancho + 'px';
            wrapper.style.height = alto + 'px';
            // CRÍTICO en documentos grandes: el visor es flex-column; sin flex-shrink:0 las
            // páginas SIN canvas (no renderizadas aún) se encogían a altura 0 -> el scrollHeight
            // quedaba mal (p.ej. 1200 págs ocupaban ~10), decenas de páginas caían en el viewport
            // a la vez EN BLANCO y el scroll/posiciones eran un caos. Con flex-shrink:0 cada
            // página respeta su altura estimada/real aunque no tenga canvas.
            wrapper.style.flexShrink = '0';
            wrapper.style.position = 'relative';
            // margin manejado por CSS gap
            wrapper.style.background = 'white';
            wrapper.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';

            // Número de página
            const pageLabel = document.createElement('div');
            pageLabel.style.cssText = 'position:absolute;bottom:-20px;left:50%;transform:translateX(-50%);font-size:11px;color:#888;white-space:nowrap;';
            pageLabel.textContent = 'Página ' + i + ' de ' + state.totalPages;
            wrapper.appendChild(pageLabel);

            viewer.appendChild(wrapper);
        }

        // Acomodar en 1 o varias columnas ANTES de renderizar: así el cálculo de
        // páginas visibles trabaja ya con las posiciones definitivas.
        _aplicarDisposicionPaginas();

        // Renderizar todas las páginas visibles
        await renderVisiblePages();

        // Detectar scroll para actualizar página actual y renderizar lazy
        viewer.addEventListener('scroll', _onViewerScroll);
        updateNavButtons();
    }

    // ==================== NAVEGACION ====================
    function updateNavButtons() {
        $('btnPrevPage').disabled = state.currentPage <= 1;
        $('btnNextPage').disabled = state.currentPage >= state.totalPages;
    }

    $('btnPrevPage').addEventListener('click', () => {
        if (state.currentPage > 1) renderPage(state.currentPage - 1);
    });

    $('btnNextPage').addEventListener('click', () => {
        if (state.currentPage < state.totalPages) renderPage(state.currentPage + 1);
    });

    // ==================== ZOOM ====================
    $('btnRightZoomIn').addEventListener('click', () => {
        state.zoom = Math.min(4, state.zoom + 0.25);
        if (state.pdfDoc) { state.renderedPages = {}; renderAllPages(); }
    });

    // Mínimo 0.1 (antes 0.25): hace falta bajar más para que quepan 4 páginas por
    // fila en pantallas normales, que es justo lo que pide la vista de varias páginas.
    $('btnRightZoomOut').addEventListener('click', () => {
        state.zoom = Math.max(0.1, state.zoom - (state.zoom <= 0.5 ? 0.1 : 0.25));
        if (state.pdfDoc) { state.renderedPages = {}; renderAllPages(); }
    });

    // Elegir cuántas páginas ver por fila: 1 -> 2 -> 3 -> 4 -> 1 ...
    $('btnVistaColumnas')?.addEventListener('click', () => {
        const siguiente = (state.columnas % 4) + 1;
        verPaginasPorFila(siguiente);
    });

    // Lo que la vista le ofrece a quien la maneja desde fuera: el zoom con el
    // pellizco del touchpad (`zoom_pellizco.js`) y el desplazamiento con las
    // flechas del teclado (`teclas_desplazar.js`). Es a propósito lo mínimo:
    // leer el zoom, ponerlo, y saber cuál es el visor y cuántas páginas hay.
    window.PDFVista = {
        hayDocumento: () => !!state.pdfDoc,
        visor: () => $('viewerScroll'),
        zoom: () => state.zoom,
        totalPaginas: () => state.totalPages,
        paginaActual: () => state.currentPage,
        irAPagina: numero => renderPage(numero),
        /** Pone el zoom (entre 0,1 y 4) y redibuja. Devuelve el que quedó. */
        ponerZoom: async function (valor) {
            if (!state.pdfDoc) return state.zoom;
            const nuevo = Math.min(4, Math.max(0.1, Math.round(valor * 100) / 100));
            if (nuevo === state.zoom) return state.zoom;
            state.zoom = nuevo;
            state.renderedPages = {};
            await renderAllPages();
            return state.zoom;
        }
    };

    // ==================== ROTACION ====================
    async function rotarPaginaActual(delta) {
        if (!state.pdfDoc) return;
        state.hayCambios = true;
        state.rotation[state.currentPage] = ((state.rotation[state.currentPage] || 0) + delta + 360) % 360;
        await renderPage(state.currentPage);
    }
    $('btnRotate').addEventListener('click', () => rotarPaginaActual(90));

    // ==================== PESTAÑAS DEL PANEL ====================
    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function switchPanel(panelName) {
        // Ocultar todos los paneles
        document.querySelectorAll('.panel-content').forEach(p => {
            p.classList.add('hidden');
            p.style.display = 'none';
        });

        // Mostrar el panel seleccionado
        const panelId = 'panel' + capitalize(panelName);
        const panelEl = document.getElementById(panelId);

        if (panelEl) {
            panelEl.classList.remove('hidden');
            panelEl.style.display = 'block';
            console.log('Panel mostrado:', panelId);
        } else {
            console.error('Panel no encontrado:', panelId);
        }
    }

    document.querySelectorAll('.top-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();

            // Marcar cuál es la pestaña activa
            document.querySelectorAll('.top-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const panelName = tab.dataset.panel;
            console.log('Tab clickeado:', panelName);

            // Actualizar título del panel
            $('leftPanelTitle').textContent = tab.textContent.trim();

            // Cambiar panel
            switchPanel(panelName);

            // Mostrar panel izquierdo si estaba colapsado
            $('leftPanel').classList.remove('collapsed');
        });
    });

    $('btnClosePanel').addEventListener('click', () => {
        $('leftPanel').classList.add('collapsed');
    });

    // ==================== HELPERS ====================
    // OJO: `base.html` (la plantilla común de todo Raíces) trae otro elemento con el
    // MISMO id, `<div class="overlay" id="loadingOverlay" style="display:none">`, y va
    // antes en la página. `getElementById` devolvía ese, así que el indicador de carga
    // del editor NUNCA se veía: se le ponía y quitaba una clase a un div invisible del
    // armazón, mientras el del editor seguía oculto. De ahí la sensación de que las
    // conversiones largas "no hacían nada". Se busca por clase, dentro del editor.
    function _overlayDeCarga() {
        return document.querySelector('.pdf-editor-app .loading-overlay') ||
               document.querySelector('.loading-overlay') || $('loadingOverlay');
    }

    function showLoading(show, mensaje) {
        const overlay = _overlayDeCarga();
        if (!overlay) return;
        overlay.classList.toggle('hidden', !show);
        // Con un mensaje propio se dice QUÉ se está haciendo y cuánto lleva: en las
        // conversiones largas era lo único que faltaba para que el usuario no creyera
        // que el editor se había quedado colgado.
        const texto = overlay.querySelector('p');
        if (texto) {
            texto.style.whiteSpace = 'pre-line';
            texto.textContent = (show && mensaje) ? mensaje : 'Cargando...';
        }
    }

    // Aviso al recargar/cerrar: los cambios se perderían. El navegador
    // bloquea la salida hasta que el usuario confirme en el diálogo nativo.
    window.addEventListener('beforeunload', e => {
        if (state.hayCambios) {
            e.preventDefault();
            e.returnValue = 'Tienes cambios sin descargar. Si recargas o cierras la página se descartarán.';
            return e.returnValue;
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
        // Ctrl+O: abre el selector del editor. Va ANTES del guard de campos de
        // texto y con preventDefault porque el navegador tiene su propio Ctrl+O,
        // que abriria el PDF en su visor nativo en vez de cargarlo aquí.
        if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'o') {
            e.preventDefault();
            // Por la misma puerta que el botón «Nuevo», para que el atajo también
            // avise si hay cambios sin descargar (31-jul-2026).
            if (E._abrirOtroPDF) E._abrirOtroPDF(); else fileInput.click();
            return;
        }

        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
            $('btnPrevPage').click();
        } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
            $('btnNextPage').click();
        } else if (e.ctrlKey && e.key === '+') {
            e.preventDefault();
            $('btnRightZoomIn').click();
        } else if (e.ctrlKey && e.key === '-') {
            e.preventDefault();
            $('btnRightZoomOut').click();
        }
    });

    // ==================== HELPERS COMUNES ====================

    function _necesitaPDF(msg) {
        if (!state.pdfDoc || !state.pdfBytes) {
            mostrarToast(msg || 'Primero carga un documento PDF', 'warn');
            return true;
        }
        return false;
    }

    function mostrarToast(msg, tipo) {
        let toast = document.getElementById('_pdfToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = '_pdfToast';
            toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:10px 20px;border-radius:8px;font-size:13px;z-index:99999;color:white;max-width:380px;text-align:center;transition:opacity 0.3s;';
            document.body.appendChild(toast);
        }
        toast.style.background = tipo === 'warn' ? '#d97706' : tipo === 'error' ? '#dc2626' : '#1473e6';
        toast.textContent = msg;
        toast.style.opacity = '1';
        clearTimeout(toast._t);
        toast._t = setTimeout(() => { toast.style.opacity = '0'; }, 3500);
    }

    function _getPdfBlob() {
        return new Blob([state.pdfBytes], { type: 'application/pdf' });
    }

    function _descargarBlob(blob, nombre) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = nombre;
        document.body.appendChild(a); a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    function _mostrarError(elId, msg) {
        const el = document.getElementById(elId);
        if (el) { el.textContent = msg; el.style.display = 'block'; }
    }
    function _ocultarError(elId) {
        const el = document.getElementById(elId);
        if (el) el.style.display = 'none';
    }

    async function _operacionBackend(endpoint, params, nombreDescarga, elError, aplicarAlDoc) {
        if (_necesitaPDF()) return;
        const formData = new FormData();
        // Si el usuario tiene anotaciones, se hornean primero: la operación debe
        // conservarlas (antes se enviaba el PDF original y se perdían)
        const hayAnotaciones = Object.values(state.annotations || {}).some(l => l && l.length);
        if (hayAnotaciones) {
            const horneado = await _hornearPDF();
            formData.append('archivo', new Blob([horneado], { type: 'application/pdf' }), 'documento.pdf');
        } else {
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
        }
        for (const [k, v] of Object.entries(params)) formData.append(k, v);
        const resp = await fetch('/api/pdf/operacion/' + endpoint, { method: 'POST', body: formData });
        if (!resp.ok) {
            const datos = await resp.json().catch(() => ({}));
            throw new Error(datos.mensaje || 'Error ' + resp.status);
        }
        // El servidor puede mandar un aviso (por ejemplo: la conversión a Word se hizo
        // de forma sencilla porque el documento no admitió la buena). Se dice en
        // pantalla: si no, el usuario abre el archivo y no entiende por qué cambió.
        const aviso = resp.headers.get('X-Aviso-Conversion');
        if (aviso) {
            try { mostrarToast(decodeURIComponent(aviso), 'warn'); }
            catch (e) { mostrarToast(aviso, 'warn'); }
        }
        const blob = await resp.blob();
        if (aplicarAlDoc) {
            // El resultado SE APLICA al documento abierto (pedido del usuario);
            // no se descarga nada automáticamente — el usuario descarga cuando quiera
            const buf = await blob.arrayBuffer();
            await loadPDF(buf);
            state.hayCambios = true;
        } else {
            _descargarBlob(blob, nombreDescarga);
        }
        return blob;
    }

    function _abrirModal(id) { document.getElementById(id).classList.remove('hidden'); }
    function _cerrarModal(id) { document.getElementById(id).classList.add('hidden'); }

    // Cerrar modal con clic en overlay (para todos los nuevos modales)
    ['modalComprimir','modalProteger','modalMarcaAgua','modalEncabezado','modalCensurar',
     'modalExtraer','modalOCR','modalOrganizar','modalExportTexto','modalFirmaDigital','modalInsertarPag',
     'modalNumerar','modalDividir','modalFormulario','modalComparar','modalCompartir','modalAsistenteIA']
    .forEach(id => {
        document.getElementById(id)?.addEventListener('click', function(e) {
            if (e.target === this) _cerrarModal(id);
        });
    });

    // ==================== DESHACER / REHACER ====================
    // Todo cambio del documento pasa por aquí: así el historial se entera de
    // TODOS, y no hay que acordarse de avisarle en cada sitio nuevo.
    // (Pedido del usuario, 27-jul-2026: Ctrl+Z y Ctrl+Y.)
    async function _cambiarDocumento(bytes, etiqueta) {
        try {
            window.PDFHistorial?.registrar(state.pdfBytes, etiqueta);
        } catch (e) { /* el historial nunca puede impedir un cambio */ }
        // Este documento ACABA de llegar del servidor, así que el de allí ya es
        // este mismo: no hay que volver a subirlo. Sin esta marca se resubía el
        // PDF entero después de cada clic (auditoría del 29-jul-2026).
        state.esDelServidor = true;
        state.pdfBytes = bytes;
        await loadPDF(bytes.buffer ? bytes.buffer.slice(0) : bytes.slice(0).buffer);
        state.hayCambios = true;
    }

    // ==================== ARRANQUE DE LAS PARTES ====================
    // Aquí ya está declarado todo lo del núcleo, así que se rellena `E` y se arranca
    // cada parte. El orden es el mismo que tenían cuando el editor era un solo archivo.
    Object.assign(E, {
        $, FUENTES_TEXTO, MIN_IMG_PT, SVGNS, _abrirModal,
        _apiParrafo, _cambiarDocumento, _cerrarModal, _cssFuente, _currentAnnotLayer,
        _currentPageWrapper, _descargarBlob, _getPageFromEvent, _getPdfBlob, _mostrarError,
        _necesitaPDF, _ocultarError, _operacionBackend, _panelTextoModoNuevo,
        deseleccionarTexto, fileInput,
        loadPDF, mostrarToast, renderAllPages, seleccionarTexto, showLoading,
        state, updateNavButtons,
    });

    const PARTES = [
        'render_vista',
        'anotaciones_dom',
        'texto_pdf',
        'ventana',
        'herramientas',
        'anotar_formas',
        'resaltador',
        'anotar_borrador',
        'comentarios',
        'organizar',
        'operaciones',
        'tablas_ocr',
        'ocr_area',
        'nuevo_documento',
        'buscar_exportar',
        'asistente',
        'firma_p12',
        'imagen_recorte',
        'compartir',
        'convertir',
        // El documento es un archivo del Drive: se abre desde su ruta y se
        // guarda sobre ella. Solo hace algo si la pagina se abrio con ?ruta=.
        // Va DESPUES de 'compartir': usa su _hornearPDF para aplanar las
        // anotaciones antes de guardar.
        'drive',
    ];

    for (const nombre of PARTES) {
        const parte = (window.PDFEditorPartes || {})[nombre];
        if (typeof parte !== 'function') {
            // Suele ser que el navegador se quedó con un index.html viejo y no pidió el
            // archivo de esa parte. Se avisa y se sigue: mejor perder una herramienta
            // que dejar el editor entero sin arrancar.
            console.error('Editor PDF: falta la parte "' + nombre + '"');
            continue;
        }
        try {
            parte(E);
        } catch (err) {
            console.error('Editor PDF: la parte "' + nombre + '" falló al arrancar', err);
        }
    }

    // Si la página se abrió con un documento guardado (/editor/<id>), cargarlo del servidor
    if ((window.PDF_EDITOR_CFG || {}).documentoId) {
        fetch('/api/pdf/documentos/' + window.PDF_EDITOR_CFG.documentoId + '/descargar')
            .then(r => r.arrayBuffer())
            .then(data => loadPDF(data))
            .catch(err => console.error('Error cargando documento:', err));
    }
});
