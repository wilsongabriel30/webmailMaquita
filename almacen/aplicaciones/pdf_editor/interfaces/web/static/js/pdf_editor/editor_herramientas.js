/* ============================================================
   Raíces Maquita — Editor PDF · herramientas
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.herramientas = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _cssFuente, _currentAnnotLayer, _currentPageWrapper, _getPageFromEvent, _panelTextoModoNuevo, deseleccionarTexto, loadPDF, mostrarToast, seleccionarTexto, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const _activarModoEdicionTexto = (...a) => E._activarModoEdicionTexto(...a);   // parte texto_pdf
    const _actualizarPanelAnotacion = (...a) => E._actualizarPanelAnotacion(...a);   // parte anotar_formas
    const abrirModalConvertirPDF = (...a) => E.abrirModalConvertirPDF(...a);   // parte convertir
    const downloadPDF = (...a) => E.downloadPDF(...a);   // parte compartir
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    const renderPage = (...a) => E.renderPage(...a);   // parte render_vista
    // ==================== HERRAMIENTAS ====================
    function setTool(tool) {
        // Elegir CUALQUIER herramienta (incluida "Seleccionar") apaga la edición de
        // texto: el usuario espera que con el cursor de selección el doble clic no
        // abra nada. Solo "Digitalizar y OCR" vuelve a encenderla.
        if (E.enModoEdicion()) {
            _activarModoEdicionTexto(false);
        }
        if (tool === null) {
            state.currentTool = null;
        } else {
            state.currentTool = (state.currentTool === tool) ? null : tool;
        }

        // Botones activos
        document.querySelectorAll('.mini-btn').forEach(b => b.classList.remove('active'));
        const btnMap = {
            select: 'btnSelect', hand: 'btnHand',
            highlight: 'btnHighlight',
            comment: 'btnComment', draw: 'btnDraw', text: 'btnAddText',
            erase: 'btnErase', shape: 'btnShapes', unhighlight: 'btnQuitarResaltado'
        };
        // Con la herramienta de texto, el panel de letra/tamaño/color sale YA, sin
        // tener que escribir algo primero para poder ajustarlo.
        _panelTextoModoNuevo(state.currentTool === 'text');
        // Y con la de comentario sale su barra de marcas y colores, arriba del documento.
        if (E.mostrarBarraComentarios) E.mostrarBarraComentarios(state.currentTool === 'comment');
        const activeTool = state.currentTool;
        if (activeTool && btnMap[activeTool]) $(btnMap[activeTool])?.classList.add('active');
        else $('btnSelect').classList.add('active');

        // Gestión de capas según herramienta (en TODAS las páginas, no solo la actual)
        const selTools     = ['highlight', 'underline', 'strikeout']; // necesitan texto seleccionable
        const clickTools   = ['comment', 'text', 'form', 'stamp', 'unhighlight']; // necesitan clic en página
        const isSelTool    = selTools.includes(activeTool);
        const isClickTool  = clickTools.includes(activeTool);
        const isDrawTool   = activeTool === 'draw';
        const isEraseTool  = activeTool === 'erase';
        const annotActiva  = !!activeTool && (activeTool === 'select' || isClickTool);

        document.querySelectorAll('.page-wrapper').forEach(pw => {
            const tl = pw.querySelector('.textLayer');
            const al = pw.querySelector('.annotation-layer');
            if (tl) tl.classList.toggle('no-select', !isSelTool);
            if (al) al.classList.toggle('active', annotActiva);
            pw.classList.toggle('cursor-draw', isDrawTool);
            pw.classList.toggle('cursor-erase', isEraseTool);
            pw.classList.toggle('cursor-unhighlight', activeTool === 'unhighlight');
        });

        // Panel de color/grosor/formas según la herramienta elegida
        _actualizarPanelAnotacion(activeTool);
        window.PDFManoDesplazar?.refrescar();   // el puntero de la mano (modulo aparte)

        if (activeTool === 'unhighlight') {
            mostrarToast('Haz clic sobre un resaltado (o subrayado/tachado) para quitarlo.', 'info');
        }

        // Aviso util: el borrador solo actua sobre trazos del lapiz
        if (isEraseTool && state.pdfDoc) {
            const hayTrazos = Object.values(state.annotations || {})
                .some(lista => (lista || []).some(a => a.type === 'draw'));
            mostrarToast(hayTrazos
                ? 'Borrador activo: arrastra la goma sobre el trazo y borra solo la parte que toques.'
                : 'Borrador activo, pero no hay trazos de lápiz que borrar. Para otras anotaciones, haz doble clic sobre ellas.',
                'info');
        }

        // Avisar si el PDF no tiene texto reconocible (escaneado) al activar
        // resaltar/subrayar/tachar: sin texto, la selección no puede funcionar
        if (isSelTool && state.pdfDoc) {
            const tlActual = _currentPageWrapper()?.querySelector('.textLayer');
            if (!tlActual || !tlActual.querySelector('span')) {
                mostrarToast('Esta página no tiene texto reconocible (posiblemente es un PDF escaneado). Usa "Digitalizar y OCR" en la pestaña Convertir para reconocer el texto antes de resaltar o subrayar.', 'error');
            }
        }
    }

    // La manito se marcaba como activa pero no desplazaba nada: no existía
    // ningún manejador de arrastre en todo el módulo. La acción está en
    // mano_desplazar.js; aquí solo se le dice qué herramienta está puesta.
    window.PDFManoDesplazar?.iniciar({ getHerramienta: () => state.currentTool });

    // Deshacer y rehacer (Ctrl+Z · Ctrl+Y). El módulo guarda las fotos; aquí
    // solo se le da acceso al documento.
    window.PDFHistorial?.iniciar({
        getPdfBytes: () => state.pdfBytes,
        getPagina: () => state.currentPage,
        irAPagina: n => { if (typeof renderPage === 'function') renderPage(parseInt(n)); },
        toast: (m, t) => mostrarToast(m, t),
        showLoading: (s, m) => showLoading(s, m),
        reemplazarPdf: async function (bytes) {
            state.pdfBytes = bytes;
            await loadPDF(bytes.buffer ? bytes.buffer.slice(0) : bytes.slice(0).buffer);
            state.hayCambios = true;
        },
        // Las anotaciones (resaltados, dibujos, imágenes, firmas) no viven en el
        // documento hasta que se descarga: viven en state.annotations. Para que Ctrl+Z
        // pueda deshacer un borrado con la goma, el historial necesita leerlas y
        // devolverlas a como estaban.
        getAnotaciones: pagina => state.annotations[pagina] || [],
        reemplazarAnotaciones: function (pagina, copia) {
            state.annotations[pagina] = copia;
            state.hayCambios = true;
            renderAnnotations(pagina);
            E._redrawDrawAnnotations(pagina);   // los trazos del lápiz van en su SVG aparte
        }
    });

    $('btnSelect').addEventListener('click', () => setTool('select'));
    $('btnHand').addEventListener('click', () => setTool('hand'));
    $('btnHighlight').addEventListener('click', () => setTool('highlight'));
    $('btnComment').addEventListener('click', () => setTool('comment'));
    $('btnDraw').addEventListener('click', () => setTool('draw'));
    $('btnErase')?.addEventListener('click', () => setTool('erase'));
    $('btnShapes')?.addEventListener('click', () => setTool('shape'));
    $('btnAddText').addEventListener('click', () => setTool('text'));

    // Clic en el visor: escribir texto o dejar un comentario en el sitio
    $('viewerScroll').addEventListener('click', e => {
        // Clic fuera de un cuadro de texto: quitar la selección (los textos detienen la propagación)
        deseleccionarTexto();
        if (!e.target.closest('.annotation-layer') && !e.target.closest('.page-wrapper')) return;
        const tool = state.currentTool;
        if (!tool || tool === 'select' || tool === 'hand') return;
        if (e.target.closest('.annotation')) return;

        _getPageFromEvent(e);
        const wrapper = _currentPageWrapper();
        const rect    = wrapper.getBoundingClientRect();
        const x = (e.clientX - rect.left) / state.zoom;
        const y = (e.clientY - rect.top)  / state.zoom;
        if (x < 0 || y < 0) return;

        if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];

        if (tool === 'form' && state.campoFormPendiente) {
            // Colocar un campo de formulario donde el usuario hizo clic.
            // El campo se vuelve interactivo (AcroForm) al descargar el PDF.
            const cfg = state.campoFormPendiente;
            const dims = cfg.subtipo === 'checkbox' ? { width: 16, height: 16 } : { width: 180, height: 24 };
            state.annotations[state.currentPage].push({
                type: 'form', subtipo: cfg.subtipo, nombre: cfg.nombre, opciones: cfg.opciones,
                x, y, width: dims.width, height: dims.height
            });
            state.hayCambios = true;
            renderAnnotations(state.currentPage);
            mostrarToast('Campo "' + cfg.nombre + '" colocado. Arrástralo si hace falta; doble clic para eliminarlo.', 'ok');
            state.campoFormPendiente = null;
            setTool(null);
            return;
        }

        if (tool === 'stamp' && state.selloPendiente) {
            // Colocar el sello elegido (✓ ✗ ● ▢ —) centrado en el punto del clic;
            // la herramienta queda activa para colocar varios seguidos
            const st = state.selloPendiente;
            const size = 22;
            const sw = st === 'linea' ? size * 3 : size;
            const sh = st === 'linea' ? size / 3 : size;
            state.annotations[state.currentPage].push({
                type: 'stamp', subtipo: st, x: x - sw / 2, y: y - sh / 2, size, color: '#111111'
            });
            state.hayCambios = true;
            renderAnnotations(state.currentPage);
            return;
        }

        if (tool === 'text') {
            // Editor de texto en línea
            const layer      = _currentAnnotLayer();
            if (!layer) return;
            // Lo que se va a escribir sale con lo elegido en el panel «Texto nuevo»
            // (letra, tamaño, color, negrita y cursiva). Antes el tamaño y el color se
            // leían de otros controles y la fuente estaba fija: había que escribir
            // primero y corregir después.
            const fontSize   = parseInt($('selTamanoTexto')?.value || $('textSizeSelect')?.value || 14);
            const color      = $('colorTextoSel')?.value || $('annotColor')?.value || '#000000';
            const fuente     = $('selFuenteTexto')?.value || 'helvetica';
            const negrita    = !!$('btnNegritaTexto')?.classList.contains('activo');
            const cursiva    = !!$('btnCursivaTexto')?.classList.contains('activo');
            const editor     = document.createElement('div');
            editor.className = 'inline-text-editor';
            editor.contentEditable = 'true';
            editor.style.left      = (x * state.zoom) + 'px';
            editor.style.top       = (y * state.zoom) + 'px';
            editor.style.fontSize  = (fontSize * state.zoom) + 'px';
            editor.style.color     = color;
            // Se escribe ya con esa letra: lo que se ve mientras se teclea es lo que queda.
            editor.style.fontFamily = _cssFuente({ fuente: fuente });
            editor.style.fontWeight = negrita ? '700' : '400';
            editor.style.fontStyle  = cursiva ? 'italic' : 'normal';
            editor.style.minWidth  = '100px';
            layer.appendChild(editor);
            editor.focus();
            let confirmado = false;
            const commit = () => {
                // Enter dispara remove() y eso dispara blur → evitar el doble commit
                if (confirmado) return;
                confirmado = true;
                const text = editor.textContent.trim();
                const anchoEditor = editor.offsetWidth;
                const altoEditor  = editor.offsetHeight;
                editor.remove();
                if (text) {
                    const annNueva = {
                        type: 'text', x, y, text,
                        size: fontSize, color,
                        fuente: fuente, negrita: negrita, cursiva: cursiva,
                        width:  (anchoEditor || 100) / state.zoom,
                        height: (altoEditor || fontSize * 1.4) / state.zoom
                    };
                    state.annotations[state.currentPage].push(annNueva);
                    state.hayCambios = true;
                    renderAnnotations(state.currentPage);
                    // Seleccionar el texto recién creado: el panel de propiedades
                    // (fuente, tamaño, negrita…) se activa de inmediato para ajustarlo
                    const capa = _currentAnnotLayer();
                    const textos = capa ? capa.querySelectorAll('.annotation-text') : [];
                    if (textos.length) seleccionarTexto(annNueva, textos[textos.length - 1]);
                }
                setTool('select');
            };
            editor.addEventListener('blur', commit);
            editor.addEventListener('keydown', e2 => {
                if (e2.key === 'Escape') { editor.remove(); setTool('select'); }
                if (e2.key === 'Enter' && !e2.shiftKey) { e2.preventDefault(); commit(); }
            });
            return;
        }

        if (tool === 'comment' && E.crearComentario) {
            // La marca, el color y la notita los pone la parte de comentarios.
            E.crearComentario(x, y);
            return;
        }
        if (tool === 'comment') {
            // Nota adhesiva con mini textarea flotante
            const layer  = _currentAnnotLayer();
            if (!layer) return;
            const noteEl = document.createElement('textarea');
            noteEl.style.cssText = `position:absolute;left:${x*state.zoom}px;top:${y*state.zoom}px;
                width:200px;height:80px;z-index:600;border:2px dashed #ffc107;border-radius:6px;
                padding:6px;font-size:12px;background:rgba(255,255,200,0.97);outline:none;
                resize:both;box-shadow:0 2px 8px rgba(0,0,0,.2);`;
            noteEl.placeholder = 'Escribe tu comentario…';
            layer.appendChild(noteEl);
            noteEl.focus();
            const commitNote = () => {
                const text = noteEl.value.trim();
                noteEl.remove();
                if (text) {
                    state.annotations[state.currentPage].push({ type: 'note', x, y, text });
                    state.hayCambios = true;
                    renderAnnotations(state.currentPage);
                }
                setTool('select');
            };
            noteEl.addEventListener('blur', commitNote);
            noteEl.addEventListener('keydown', e2 => {
                if (e2.key === 'Escape') { noteEl.remove(); setTool('select'); }
                if (e2.key === 'Enter' && e2.ctrlKey) { e2.preventDefault(); commitNote(); }
            });
            return;
        }
    });

    // Modal texto (acceso desde panel lateral Texto)
    $('btnCloseText')?.addEventListener('click', () => $('modalText').classList.add('hidden'));
    $('btnCancelText')?.addEventListener('click', () => $('modalText').classList.add('hidden'));
    $('btnApplyText')?.addEventListener('click', () => {
        const text = $('textInput').value.trim();
        if (!text) return;
        if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];
        state.annotations[state.currentPage].push({
            type: 'text', x: 50, y: 50, text,
            size: parseInt($('textSize').value), color: $('textColor').value
        });
        $('textInput').value = '';
        $('modalText').classList.add('hidden');
        setTool(null);
        renderAnnotations(state.currentPage);
    });

    // ==================== HERRAMIENTAS DEL PANEL IZQUIERDO ====================

    // Exportar PDF
    $('toolExportar')?.addEventListener('click', () => {
        if (!state.pdfBytes) {
            alert('Primero carga un documento PDF');
            return;
        }
        downloadPDF();
    });

    // Editar PDF - ir a tab Editar
    $('toolEditar')?.addEventListener('click', () => {
        document.querySelector('[data-panel="editar"]').click();
    });

    // Crear PDF - construir un PDF nuevo desde imágenes/Word/Excel/etc. y abrirlo en el editor
    // (antes solo abria el selector de PDF, es decir importaba un PDF ya existente)
    $('toolCrear')?.addEventListener('click', () => abrirModalConvertirPDF(true));

    // Combinar archivos
    $('toolCombinar')?.addEventListener('click', () => abrirModalCombinar());
    $('toolCombinarEdit')?.addEventListener('click', () => abrirModalCombinar());

    // "Ver mas": despliega/oculta las herramientas adicionales del panel "Todas".
    // Cada item reenvia el clic a la herramienta equivalente de las pestañas
    // Editar/Convertir/Firma, así reutiliza sus handlers y validaciones existentes.
    (function () {
        const link = $('linkVerMas');
        const extra = $('panelTodasExtra');
        if (!link || !extra) return;
        link.addEventListener('click', () => {
            const oculto = extra.style.display === 'none' || extra.style.display === '';
            extra.style.display = oculto ? 'block' : 'none';
            link.textContent = oculto ? 'Ver menos' : 'Ver mas';
        });
        extra.querySelectorAll('.tool-item[data-proxy]').forEach(item => {
            item.addEventListener('click', () => {
                const destino = document.getElementById(item.dataset.proxy);
                if (destino) destino.click();
            });
        });
    })();

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { setTool });
};
