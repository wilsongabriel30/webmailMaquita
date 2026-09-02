/* ============================================================
   Raíces Maquita — Editor PDF · imagen recorte
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.imagen_recorte = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _currentPageWrapper, _getPageFromEvent, _necesitaPDF, loadPDF, mostrarToast, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const abrirModalFormulario = (...a) => E.abrirModalFormulario(...a);   // parte convertir
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    const renderPage = (...a) => E.renderPage(...a);   // parte render_vista
    // ==================== INSERTAR IMAGEN ====================
    // El botón "Imagen" existía en el HTML sin ningún handler: se agrega un selector
    // propio que inserta la imagen como anotación arrastrable (se incrusta al descargar)
    const MAX_IMG_MB = 20;
    const inputImagenAnot = document.createElement('input');
    inputImagenAnot.type = 'file';
    // SIN filtro accept — DEFINITIVO, NO volver a ponerlo. Historial completo:
    // se puso image/* (colgaba), lista de extensiones (colgaba), se quito (funciono),
    // se restauro a pedido del usuario tras aplicar el arreglo de OneDrive en su PC
    // (Anexo A del manual) y AUN ASI la ventana "Abrir" de Windows quedó "No responde"
    // (17-jul tarde). En su equipo hay además unidades de red, que el dialogo también
    // evalua al filtrar. Conclusion probada en ambos sentidos: CON filtro se cuelga,
    // SIN filtro funciona. El "solo imágenes" lo garantiza _insertarImagen, que valida
    // el tipo y rechaza con aviso cualquier archivo que no sea imagen.
    inputImagenAnot.removeAttribute('accept');
    inputImagenAnot.style.display = 'none';
    document.body.appendChild(inputImagenAnot);
    $('toolImagen')?.addEventListener('click', async () => {
        if (_necesitaPDF()) return;
        // Ventana moderna de Chrome (showOpenFilePicker): permite "solo imágenes" y es
        // una implementacion DISTINTA de la clasica, que en el equipo del usuario se
        // cuelga ("No responde") en cuanto se le pide filtrar. Si el navegador no la
        // tiene o falla, se cae a la clasica SIN filtro (la única que ahi no se cuelga).
        if (window.showOpenFilePicker) {
            try {
                const [h] = await window.showOpenFilePicker({
                    types: [{
                        description: 'Im\u00e1genes',
                        accept: { 'image/*': ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'] }
                    }],
                    excludeAcceptAllOption: false,
                    multiple: false
                });
                _insertarImagen(await h.getFile(), null);
                return;
            } catch (err) {
                if (err && err.name === 'AbortError') return;   // el usuario cancelo
                // cualquier otro fallo: seguir con el input clasico
            }
        }
        inputImagenAnot.value = '';
        inputImagenAnot.click();
    });

    // pdf-lib solo incrusta PNG y JPG: cualquier otro formato que el navegador
    // sepa dibujar (WEBP, GIF, BMP) se pasa a PNG por canvas. Si no, el PDF
    // descargado reventaria al hornear la imagen.
    function _aPngSiHaceFalta(dataURL, imgEl) {
        if (dataURL.startsWith('data:image/png') || dataURL.startsWith('data:image/jpeg')) return dataURL;
        const cv = document.createElement('canvas');
        cv.width = imgEl.naturalWidth; cv.height = imgEl.naturalHeight;
        cv.getContext('2d').drawImage(imgEl, 0, 0);
        return cv.toDataURL('image/png');
    }

    // Una sola vía de inserción para las tres formas de traer una imagen: el icono
    // de la barra, arrastrarla al documento y pegarla (Ctrl+V). Las dos últimas
    // existen porque el diálogo "Abrir" de Windows se cuelga con OneDrive y deja
    // al usuario sin poder insertar nada.
    // pos = {página, x, y} donde se soltó (la imagen se centra ahí); null = por defecto.
    // Extensiones que damos por imagen cuando el navegador no sabe el tipo (f.type
    // vacio): pasa con .heic en Windows. Así el HEIC llega abajo y recibe SU aviso
    // (convertir a JPG) en vez de un "esto no es una imagen" que despistaria.
    const _EXT_IMAGEN = /\.(jpe?g|jfif|png|webp|gif|bmp|heic|heif|avif|tiff?|svg|ico)$/i;

    function _insertarImagen(f, pos) {
        if (!f) return;
        // El selector ya no filtra (ver arriba: filtrar cuelga el dialogo de Windows),
        // así que aquí puede llegar cualquier cosa y hay que decirlo con claridad.
        if ((f.type || '').indexOf('image/') !== 0 && !_EXT_IMAGEN.test(f.name || '')) {
            const esPdf = f.type === 'application/pdf' || /\.pdf$/i.test(f.name || '');
            mostrarToast(esPdf
                ? 'Eso es un PDF, no una imagen. Para abrir otro PDF usa Ctrl+O.'
                : 'Eso no es una imagen. Elige un archivo JPG o PNG.', 'warn');
            return;
        }
        if (f.size > MAX_IMG_MB * 1024 * 1024) {
            mostrarToast('La imagen pesa ' + (f.size / 1024 / 1024).toFixed(1) + ' MB y supera el máximo de ' +
                         MAX_IMG_MB + ' MB. Redúcela e inténtalo de nuevo.', 'warn');
            return;
        }
        showLoading(true);
        // Si algo falla hay que quitar SIEMPRE el indicador y avisar: antes no
        // había ningún onerror y una imagen ilegible dejaba al editor "cargando"
        // para siempre, en silencio.
        const fallo = motivo => {
            showLoading(false);
            mostrarToast(motivo, 'error');
        };
        const rd = new FileReader();
        rd.onerror = () => fallo('No se pudo leer el archivo de imagen. Inténtalo de nuevo.');
        rd.onload = e => {
            const data = e.target.result;
            const imgTmp = new Image();
            imgTmp.onerror = () => fallo(
                'No se pudo abrir esta imagen: el navegador no reconoce el formato ' +
                '(las fotos HEIC de iPhone y los archivos dañados dan este error). ' +
                'Conviértela a JPG o PNG e inténtalo de nuevo.');
            imgTmp.onload = () => {
                try {
                    if (!imgTmp.naturalWidth || !imgTmp.naturalHeight) {
                        fallo('La imagen está vacía o dañada. Prueba con otro archivo.');
                        return;
                    }
                    const dataFinal = _aPngSiHaceFalta(data, imgTmp);
                    // Máx. 300 pt de ancho conservando proporción (el usuario la arrastra donde quiera)
                    const w = Math.min(imgTmp.naturalWidth, 300);
                    const h = imgTmp.naturalHeight * (w / imgTmp.naturalWidth);
                    const pagina = (pos && pos.pagina) || state.currentPage;
                    // Soltada o pegada: cae centrada en el punto elegido, sin salirse de la hoja
                    const x = pos ? Math.max(0, pos.x - w / 2) : 80;
                    const y = pos ? Math.max(0, pos.y - h / 2) : 100;
                    if (!state.annotations[pagina]) state.annotations[pagina] = [];
                    state.annotations[pagina].push({
                        type: 'image', x: x, y: y, width: w, height: h, data: dataFinal
                    });
                    state.hayCambios = true;
                    renderAnnotations(pagina);
                    showLoading(false);
                    mostrarToast('Imagen insertada. Arrástrala a la posición deseada.', 'ok');
                } catch (err) {
                    fallo('No se pudo insertar la imagen: ' + (err && err.message ? err.message : err));
                }
            };
            imgTmp.src = data;
        };
        rd.readAsDataURL(f);
    }

    inputImagenAnot.addEventListener('change', function() {
        _insertarImagen(this.files && this.files[0], null);
    });

    // ---- Arrastrar la imagen sobre el documento ----
    // Sin preventDefault, Chrome abre el archivo soltado en la pestaña y se pierde
    // TODO el trabajo sin aviso: por eso se intercepta aunque no sea una imagen.
    function _traeArchivos(e) {
        return !!(e.dataTransfer && Array.from(e.dataTransfer.types || []).indexOf('Files') !== -1);
    }
    $('viewerScroll')?.addEventListener('dragover', e => {
        if (!state.pdfDoc || !_traeArchivos(e)) return;   // sin PDF manda el drop de viewerVacio
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    });
    $('viewerScroll')?.addEventListener('drop', e => {
        if (!state.pdfDoc || !_traeArchivos(e)) return;
        e.preventDefault();
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (!f) return;
        if (f.type === 'application/pdf' || /\.pdf$/i.test(f.name || '')) {
            mostrarToast('Aquí solo se sueltan imágenes. Para abrir otro PDF usa Ctrl+O.', 'warn');
            return;
        }
        if ((f.type || '').indexOf('image/') !== 0) {
            mostrarToast('Eso no es una imagen. Suelta un archivo JPG o PNG.', 'warn');
            return;
        }
        const pg = _getPageFromEvent(e);
        const wrapper = document.getElementById('pageWrapper_' + pg) || _currentPageWrapper();
        let pos = null;
        if (wrapper) {
            const r = wrapper.getBoundingClientRect();
            pos = { pagina: pg, x: (e.clientX - r.left) / state.zoom, y: (e.clientY - r.top) / state.zoom };
        }
        _insertarImagen(f, pos);
    });

    // ---- Pegar la imagen con Ctrl+V (incluye los recortes de Win+Shift+S) ----
    document.addEventListener('paste', e => {
        if (!state.pdfDoc) return;
        // Si se está escribiendo, el pegado es del texto: no robárselo
        const act = document.activeElement;
        if (act && (act.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(act.tagName))) return;
        const items = (e.clipboardData && e.clipboardData.items) || [];
        for (let i = 0; i < items.length; i++) {
            if ((items[i].type || '').indexOf('image/') === 0) {
                const f = items[i].getAsFile();
                if (f) { e.preventDefault(); _insertarImagen(f, null); return; }
            }
        }
    });

    $('toolAgregarIniciales')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        const iniciales = prompt('Escribe tus iniciales (máx. 3 caracteres):');
        if (!iniciales || iniciales.trim().length === 0) return;
        const texto = iniciales.trim().toUpperCase().substring(0, 3);
        if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];
        state.annotations[state.currentPage].push({
            type: 'text', x: 80, y: 80, text: texto, size: 20, color: '#1473e6'
        });
        renderAnnotations(state.currentPage);
        mostrarToast('Iniciales "' + texto + '" agregadas. Arrástralas a la posición deseada.', 'ok');
    });

    // ==================== ENLACE (anotación) ====================
    // Iconos de la mini-barra vertical: reenvian a la herramienta del panel Editar
    // para reutilizar su handler y sus validaciones (no duplicar lógica aquí).
    $('btnAddImage')?.addEventListener('click', () => $('toolImagen')?.click());
    $('btnAddLink')?.addEventListener('click', () => $('toolEnlace')?.click());

    $('toolEnlace')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        const url = prompt('URL del enlace (ej: https://maquita.com.ec):');
        if (!url) return;
        if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];
        state.annotations[state.currentPage].push({
            type: 'text', x: 60, y: 120,
            text: '🔗 ' + (url.length > 40 ? url.substring(0, 37) + '...' : url),
            size: 10, color: '#1473e6', url
        });
        state.hayCambios = true;
        renderAnnotations(state.currentPage);
        mostrarToast('Enlace agregado como anotación. Arrastra para posicionar.', 'ok');
    });

    // ==================== ROTAR (panel Editar) ====================
    $('toolRotar')?.addEventListener('click', async () => {
        if (_necesitaPDF()) return;
        state.hayCambios = true;
        state.rotation[state.currentPage] = ((state.rotation[state.currentPage] || 0) + 90) % 360;
        await renderPage(state.currentPage);
        mostrarToast('Página ' + state.currentPage + ' rotada a ' + state.rotation[state.currentPage] + '°. Vuelve a pulsar para seguir girando (o usa ↺/↻ de la barra derecha).', 'ok');
    });

    // ==================== RECORTAR (recorte libre por selección) ====================
    $('toolRecortar')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        iniciarRecorte();
    });

    function iniciarRecorte() {
        const wrapper = _currentPageWrapper();
        if (!wrapper) return;
        if (document.getElementById('capaRecorte')) return; // ya hay un recorte en curso
        mostrarToast('Arrastra sobre la página para marcar el área a CONSERVAR (Esc cancela)', 'ok');
        const capa = document.createElement('div');
        capa.id = 'capaRecorte';
        capa.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;z-index:60;cursor:crosshair;background:rgba(20,115,230,0.06);';
        wrapper.appendChild(capa);
        let sel = null, x0 = 0, y0 = 0;
        const coords = e => {
            const r = wrapper.getBoundingClientRect();
            return { x: e.clientX - r.left, y: e.clientY - r.top };
        };
        const cancelar = () => { capa.remove(); document.removeEventListener('keydown', alEscape); };
        const alEscape = ev => { if (ev.key === 'Escape') { cancelar(); mostrarToast('Recorte cancelado', 'warn'); } };
        document.addEventListener('keydown', alEscape);

        capa.addEventListener('mousedown', e => {
            e.preventDefault(); e.stopPropagation();
            const p = coords(e); x0 = p.x; y0 = p.y;
            sel = document.createElement('div');
            sel.style.cssText = 'position:absolute;border:2px dashed #1473e6;background:rgba(20,115,230,0.18);pointer-events:none;';
            capa.appendChild(sel);
        });
        capa.addEventListener('mousemove', e => {
            if (!sel) return;
            const p = coords(e);
            sel.style.left   = Math.min(x0, p.x) + 'px';
            sel.style.top    = Math.min(y0, p.y) + 'px';
            sel.style.width  = Math.abs(p.x - x0) + 'px';
            sel.style.height = Math.abs(p.y - y0) + 'px';
        });
        capa.addEventListener('mouseup', async e => {
            if (!sel) return;
            const p  = coords(e);
            const x1 = Math.min(x0, p.x), y1 = Math.min(y0, p.y);
            const x2 = Math.max(x0, p.x), y2 = Math.max(y0, p.y);
            cancelar();
            if (x2 - x1 < 20 || y2 - y1 < 20) {
                mostrarToast('Área demasiado pequeña; recorte cancelado.', 'warn');
                return;
            }
            if (!confirm('¿Recortar la página ' + state.currentPage + ' al área seleccionada?')) return;
            await aplicarRecorte(x1, y1, x2, y2);
        });
    }

    async function aplicarRecorte(x1, y1, x2, y2) {
        try {
            showLoading(true);
            const pagAntes = state.currentPage;
            // Convertir coordenadas de pantalla a coordenadas PDF (respeta zoom y rotación)
            const pageJs   = await state.pdfDoc.getPage(pagAntes);
            const rot      = state.rotation[pagAntes] || 0;
            const viewport = pageJs.getViewport({ scale: state.zoom, rotation: rot });
            const [px1, py1] = viewport.convertToPdfPoint(x1, y1);
            const [px2, py2] = viewport.convertToPdfPoint(x2, y2);
            const cx = Math.min(px1, px2), cy = Math.min(py1, py2);
            const cw = Math.abs(px2 - px1), ch = Math.abs(py2 - py1);
            await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
            const { PDFDocument } = PDFLib;
            const doc    = await PDFDocument.load(state.pdfBytes);
            const pagina = doc.getPage(pagAntes - 1);
            pagina.setCropBox(cx, cy, cw, ch);
            const bytes = await doc.save();
            await loadPDF(bytes.buffer);
            // volver a la página recortada (loadPDF regresa a la 1)
            if (pagAntes <= state.totalPages) {
                state.currentPage = pagAntes;
                $('currentPage').textContent = pagAntes;
                document.getElementById('pageWrapper_' + pagAntes)?.scrollIntoView();
            }
            state.hayCambios = true;
            mostrarToast('Página ' + pagAntes + ' recortada. Descarga el PDF para conservar el cambio.', 'ok');
        } catch (e) {
            console.error('Error al recortar:', e);
            mostrarToast('Error al recortar: ' + e.message, 'error');
        } finally {
            showLoading(false);
        }
    }

    // ==================== PREPARAR FORMULARIO ====================
    $('toolFormulario')?.addEventListener('click', () => abrirModalFormulario());

};
