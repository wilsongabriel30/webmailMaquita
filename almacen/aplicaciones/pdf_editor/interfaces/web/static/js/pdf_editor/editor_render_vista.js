/* ============================================================
   Raíces Maquita — Editor PDF · render vista
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.render_vista = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, deseleccionarTexto, mostrarToast, renderAllPages, state, updateNavButtons } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const _redrawDrawAnnotations = (...a) => E._redrawDrawAnnotations(...a);   // parte anotar_borrador
    const createAnnotationElement = (...a) => E.createAnnotationElement(...a);   // parte anotaciones_dom
    // ==================== VISTA DE VARIAS PÁGINAS POR FILA ====================
    // Igual que Word: si al alejar el zoom caben dos o más páginas a lo ancho, se
    // colocan una junto a otra en vez de dejar franjas grises a los lados.
    // Solo cambia la DISPOSICIÓN (clase CSS); no toca el zoom, ni el canvas, ni las
    // anotaciones (sus coordenadas son relativas al wrapper de su página).
    const GAP_COLUMNAS = 24;   // separación horizontal entre páginas (px)

    function _anchoDisponibleVisor() {
        const viewer = $('viewerScroll');
        if (!viewer) return 0;
        const est = getComputedStyle(viewer);
        return viewer.clientWidth - parseFloat(est.paddingLeft) - parseFloat(est.paddingRight);
    }

    // Cuántas páginas del ancho actual caben a lo ancho del visor
    function _columnasQueCaben() {
        const viewer = $('viewerScroll');
        const primera = viewer && viewer.querySelector('.page-wrapper');
        if (!primera) return 1;
        const anchoPag = primera.offsetWidth;
        if (anchoPag <= 0) return 1;
        const disponible = _anchoDisponibleVisor();
        return Math.max(1, Math.floor((disponible + GAP_COLUMNAS) / (anchoPag + GAP_COLUMNAS)));
    }

    function _aplicarDisposicionPaginas() {
        const viewer = $('viewerScroll');
        if (!viewer) return;
        const cols = state.pdfDoc ? _columnasQueCaben() : 1;
        state.columnas = cols;
        viewer.classList.toggle('multi-col', cols >= 2);
        _actualizarIndicadorZoom();
    }

    // Zoom exacto para que quepan justo N páginas por fila (botón "Ver N páginas")
    function _zoomParaColumnas(n) {
        if (!state.anchoPagina1x) return null;
        const disponible = _anchoDisponibleVisor() - GAP_COLUMNAS * (n - 1);
        if (disponible <= 0) return null;
        // -6 px de margen: deja aire para el borde/sombra y evita que por un pixel
        // de más el navegador mande la última página a la fila siguiente
        return Math.max(0.1, ((disponible / n) - 6) / state.anchoPagina1x);
    }

    async function verPaginasPorFila(n) {
        if (!state.pdfDoc) { mostrarToast('Primero abre un PDF.', 'info'); return; }
        const z = _zoomParaColumnas(n);
        if (!z) return;
        // Math.floor (no round): redondear hacia arriba agranda la página lo justo
        // para que la última no quepa y caiga a la fila siguiente.
        state.zoom = Math.min(4, Math.max(0.1, Math.floor(z * 100) / 100));
        state.renderedPages = {};
        const pagAntes = state.currentPage;
        await renderAllPages();
        document.getElementById('pageWrapper_' + pagAntes)?.scrollIntoView({ block: 'start' });
        mostrarToast(n === 1 ? 'Vista de una página' : 'Vista de ' + n + ' páginas por fila', 'success');
    }

    // Rótulo con el porcentaje de zoom y las páginas por fila (bajo los botones +/-)
    function _actualizarIndicadorZoom() {
        const el = $('zoomIndicador');
        if (!el) return;
        el.textContent = Math.round(state.zoom * 100) + '%';
        el.title = 'Zoom ' + Math.round(state.zoom * 100) + '%' +
                   (state.columnas > 1 ? ' — ' + state.columnas + ' páginas por fila' : '');
    }

    // Al cambiar el tamaño de la ventana cambian las columnas que caben
    let _resizeColsTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(_resizeColsTimer);
        _resizeColsTimer = setTimeout(() => {
            _aplicarDisposicionPaginas();
            if (state.pdfDoc) renderVisiblePages();
        }, 150);
    });

    let _scrollTimer = null;
    function _onViewerScroll() {
        if (_scrollTimer) return;
        _scrollTimer = requestAnimationFrame(() => {
            _scrollTimer = null;
            _updateCurrentPageFromScroll();
            renderVisiblePages();
        });
    }

    function _updateCurrentPageFromScroll() {
        const viewer = $('viewerScroll');
        const scrollTop = viewer.scrollTop;
        const viewerMid = scrollTop + viewer.clientHeight / 3;
        const wrappers = viewer.querySelectorAll('.page-wrapper');
        if (!wrappers.length) return;
        // Búsqueda binaria de la página en el centro del viewport (O(log n)).
        const w = wrappers[_indicePaginaEn(wrappers, viewerMid)];
        if (w) {
            const pg = parseInt(w.dataset.page);
            if (pg !== state.currentPage) {
                state.currentPage = pg;
                $('currentPage').textContent = pg;
                updateNavButtons();
            }
        }
    }

    // Búsqueda binaria: índice del primer wrapper cuyo borde inferior supera 'y'.
    // Los offsetTop son monótonos crecientes, así que evita recorrer las N páginas
    // (clave con documentos de miles de páginas: O(log n) en vez de O(n) por frame).
    function _indicePaginaEn(wrappers, y) {
        let lo = 0, hi = wrappers.length - 1, res = wrappers.length - 1;
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            const w = wrappers[mid];
            if (w.offsetTop + w.offsetHeight > y) { res = mid; hi = mid - 1; }
            else lo = mid + 1;
        }
        return res;
    }

    let _renderVisiblesLock = false, _renderVisiblesPend = false;
    async function renderVisiblePages() {
        // Candado de re-entrada: varios eventos de scroll no deben solaparse renderizando
        // y descargando a la vez (amplificaba el trabajo y el parpadeo).
        if (_renderVisiblesLock) { _renderVisiblesPend = true; return; }
        _renderVisiblesLock = true;
        try {
            const viewer = $('viewerScroll');
            const scrollTop = viewer.scrollTop;
            const viewHeight = viewer.clientHeight;
            const wrappers = viewer.querySelectorAll('.page-wrapper');
            if (!wrappers.length) return;

            // Renderizar SOLO la ventana visible (± pantallas), localizada por búsqueda
            // binaria — no se recorren las miles de páginas en cada frame.
            const yTop = scrollTop - viewHeight;
            const yBot = scrollTop + viewHeight * 2;
            for (let i = _indicePaginaEn(wrappers, yTop); i < wrappers.length; i++) {
                const w = wrappers[i];
                if (w.offsetTop > yBot) break;
                const pg = parseInt(w.dataset.page);
                if (!state.renderedPages[pg]) await renderSinglePage(pg);
            }

            // Liberar memoria: una página renderizada conserva su canvas (~8 MB). Se itera
            // SOLO el conjunto de páginas renderizadas (pequeño), no las N del documento.
            if (state.totalPages > 20) {
                for (const pgStr of Object.keys(state.renderedPages)) {
                    if (!state.renderedPages[pgStr]) continue;
                    const pg = parseInt(pgStr);
                    if (pg === state.currentPage) continue;
                    const w = document.getElementById('pageWrapper_' + pg);
                    if (!w) continue;
                    const top = w.offsetTop;
                    const bottom = top + w.offsetHeight;
                    const lejos = (bottom < scrollTop - viewHeight * 3) || (top > scrollTop + viewHeight * 4);
                    if (lejos) _descargarPagina(pg, w);
                }
            }
        } finally {
            _renderVisiblesLock = false;
            if (_renderVisiblesPend) { _renderVisiblesPend = false; renderVisiblePages(); }
        }
    }

    function _descargarPagina(pg, wrapper) {
        wrapper.querySelector('canvas')?.remove();
        wrapper.querySelector('.textLayer')?.remove();
        wrapper.querySelectorAll('.draw-path').forEach(el => el.remove());
        const annot = wrapper.querySelector('.annotation-layer');
        if (annot) annot.innerHTML = '';
        state.renderedPages[pg] = false;
    }

    async function renderSinglePage(pageNum) {
        if (!state.pdfDoc || state.renderedPages[pageNum]) return;
        state.renderedPages[pageNum] = true;

        const page = await state.pdfDoc.getPage(pageNum);
        const rotation = state.rotation[pageNum] || 0;
        const viewport = page.getViewport({ scale: state.zoom, rotation });

        const pageWrapper = document.getElementById('pageWrapper_' + pageNum);
        if (!pageWrapper) return;

        state.currentViewport = viewport;
        state.pageHeight = viewport.height / state.zoom;

        // Ajustar el wrapper al viewport (cambia con la rotación 90/270)
        pageWrapper.style.width  = viewport.width + 'px';
        pageWrapper.style.height = viewport.height + 'px';

        // Canvas
        let canvas = pageWrapper.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            pageWrapper.insertBefore(canvas, pageWrapper.firstChild);
        }
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.display = 'block';
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;

        // Capa de texto: la que deja seleccionar y copiar
        let textLayerDiv = pageWrapper.querySelector('.textLayer');
        if (textLayerDiv) textLayerDiv.remove();
        textLayerDiv = document.createElement('div');
        textLayerDiv.className = 'textLayer';
        textLayerDiv.style.width = viewport.width + 'px';
        textLayerDiv.style.height = viewport.height + 'px';
        // pdf.js 3.x posiciona los spans con calc(var(--scale-factor)*...): sin esta
        // variable la capa de texto queda desalineada y la selección no funciona
        textLayerDiv.style.setProperty('--scale-factor', viewport.scale);
        pageWrapper.appendChild(textLayerDiv);
        try {
            const textContent = await page.getTextContent();
            const textDivs = [];
            const renderTask = pdfjsLib.renderTextLayer({
                textContentSource: textContent, container: textLayerDiv, viewport, textDivs
            });
            await (renderTask.promise || renderTask);
            // Datos REALES de cada fragmento para poder editarlo conservando su estilo.
            // El CSS que pinta pdf.js no sirve para eso: pone siempre serif/sans-serif,
            // peso 400 y estilo normal (la negrita y la cursiva viven DENTRO de la fuente
            // incrustada, no en el CSS), y su font-size es la altura del glifo escalada
            // por el zoom, no el tamaño en puntos.
            // El emparejamiento va por TEXTO, no por índice: pdf.js mete en textDivs
            // también los <br> de los saltos de línea, y contar posiciones desplazaba
            // el estilo un fragmento (la negrita caía en el renglón de al lado).
            let j = 0;
            for (const it of textContent.items) {
                if (!it.str) continue;
                while (j < textDivs.length && textDivs[j] && textDivs[j].textContent !== it.str) j++;
                if (j >= textDivs.length) break;
                const div = textDivs[j++];
                if (!div) break;
                // transform = [a,b,c,d,e,f]; el tamaño en puntos sale de (c,d)
                const tam = Math.hypot(it.transform[2] || 0, it.transform[3] || 0);
                if (tam) div.dataset.tamPt = tam.toFixed(2);
                try {
                    if (it.fontName && page.commonObjs.has(it.fontName)) {
                        const f = page.commonObjs.get(it.fontName);
                        if (f && f.name) div.dataset.fuentePdf = f.name;
                    }
                } catch (e) { /* la fuente no está lista: se usa la heurística CSS */ }
            }
        } catch(e) { /* no crítico */ }

        // Dibujo vectorial: las formas se pintan en SVG, no en el lienzo, para que
        // se puedan seleccionar y mover después
        let drawSVG = pageWrapper.querySelector('.draw-svg');
        if (!drawSVG) {
            drawSVG = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            // en SVG className es de solo lectura: usar setAttribute
            drawSVG.setAttribute('class', 'draw-svg');
            pageWrapper.appendChild(drawSVG);
        }
        drawSVG.setAttribute('width', viewport.width);
        drawSVG.setAttribute('height', viewport.height);
        drawSVG.setAttribute('viewBox', '0 0 ' + viewport.width + ' ' + viewport.height);

        // Capa de anotaciones: notas, formas y textos añadidos
        let annotLayer = pageWrapper.querySelector('.annotation-layer');
        if (!annotLayer) {
            annotLayer = document.createElement('div');
            annotLayer.className = 'annotation-layer';
            annotLayer.id = 'annotationLayer_' + pageNum;
            pageWrapper.appendChild(annotLayer);
        }
        annotLayer.style.width = viewport.width + 'px';
        annotLayer.style.height = viewport.height + 'px';

        renderAnnotations(pageNum);
    }

    // Compatibilidad: renderPage ahora navega a la página y re-renderiza
    async function renderPage(pageNum) {
        if (!state.pdfDoc) return;
        state.currentPage = pageNum;
        $('currentPage').textContent = pageNum;

        // Re-renderizar esa página (forzar)
        state.renderedPages[pageNum] = false;
        await renderSinglePage(pageNum);

        // Salto INSTANTÁNEO (no 'smooth'): en documentos grandes la animación suave
        // recorría decenas de páginas en blanco y dejaba la página destino con "hueco".
        const wrapper = document.getElementById('pageWrapper_' + pageNum);
        if (wrapper) wrapper.scrollIntoView({ behavior: 'auto', block: 'start' });

        // Tras el salto, renderizar de inmediato las páginas que quedaron visibles
        // (sin esperar al evento de scroll throttled) para que no se vean en blanco.
        await renderVisiblePages();
        // El scroll pudo cambiar currentPage: reafirmar la página destino.
        state.currentPage = pageNum;
        $('currentPage').textContent = pageNum;

        updateNavButtons();
    }

    function renderAnnotations(pageNum) {
        const wrapper = document.getElementById('pageWrapper_' + pageNum);
        const layer = wrapper ? wrapper.querySelector('.annotation-layer') : $('annotationLayer');
        if (!layer) return;
        layer.innerHTML = '';

        const annotations = state.annotations[pageNum] || [];
        annotations.forEach((ann, idx) => {
            if (ann.type === 'draw') return;  // gestionado por SVG
            const el = createAnnotationElement(ann, idx);
            if (el) layer.appendChild(el);
        });
        _redrawDrawAnnotations(pageNum);
        _sincronizarSeleccionTexto();
    }

    // Esta capa se borra y se recrea entera en cada render. Si el texto o enlace
    // seleccionado se eliminó, hay que cerrar el panel de propiedades: si no,
    // se queda abierto apuntando a un elemento que ya no existe (y deja de
    // responder). Si sigue existiendo, createAnnotationElement ya lo reengancho
    // a su nodo nuevo.
    function _sincronizarSeleccionTexto() {
        const sel = E.textoSel();
        if (!sel) return;
        const lista = state.annotations[sel.pag] || [];
        if (!lista.includes(sel.ann)) deseleccionarTexto();
    }

    // Tamaño mínimo (pt) al redimensionar una imagen: por debajo se pierde el tirador

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _aplicarDisposicionPaginas, _onViewerScroll, renderAnnotations, renderPage, renderSinglePage, renderVisiblePages, verPaginasPorFila });
};
