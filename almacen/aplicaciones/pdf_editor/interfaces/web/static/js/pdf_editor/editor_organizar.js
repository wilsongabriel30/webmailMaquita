/* ============================================================
   Raíces Maquita — Editor PDF · organizar
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.organizar = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _abrirModal, _cambiarDocumento, _cerrarModal, _mostrarError, _necesitaPDF, _ocultarError, mostrarToast, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const renderPage = (...a) => E.renderPage(...a);   // parte render_vista
    // ==================== ORGANIZAR PÁGINAS ====================

    let ordenPaginas = [];

    async function abrirModalOrganizar() {
        if (_necesitaPDF()) return;
        const grid = $('gridOrganizar');
        grid.innerHTML = '<p style="font-size:12px;color:#6d6d6d;grid-column:1/-1;">Cargando miniaturas...</p>';
        ordenPaginas = Array.from({length: state.totalPages}, (_, i) => i);
        _idxSelOrganizar = -1; // documento/orden nuevo: no hay ficha seleccionada
        // invalidar caché de miniaturas si el documento cambió
        if (_cacheMinisRef !== state.pdfBytes) { _cacheMinisOrganizar = {}; _cacheMinisRef = state.pdfBytes; }
        _abrirModal('modalOrganizar');
        window.PDFOrganizarRango?.iniciar(_apiOrganizarRango);   // barra "eliminar por rango" (modulo aparte)

        await renderizarGridOrganizar();
    }

    function actualizarContadorSeleccionadas() {
        const checks = document.querySelectorAll('.chk-pagina:checked');
        const btn = $('btnEliminarSeleccionadas');
        const cnt = $('contadorSeleccionadas');
        if (checks.length > 0 && checks.length < ordenPaginas.length) {
            btn.style.display = '';
            cnt.textContent = checks.length;
        } else {
            btn.style.display = 'none';
        }
    }

    // Primitivas que usa organizar_rango.js (eliminar/marcar páginas por rango escrito).
    // El análisis del texto y la interfaz viven en ESE archivo; aquí solo lo imprescindible,
    // que es lo único que necesita tocar el estado privado del editor.
    const _apiOrganizarRango = {
        // Total de páginas del documento abierto (los números que ve el usuario van de 1 a este)
        getTotalOriginal: () => state.totalPages,
        // Orden actual: array de índices 0-based; el número visible de cada ficha es idx+1
        getOrden: () => ordenPaginas,
        // Marca las casillas de esas páginas (por número visible, no por posición) y devuelve cuántas
        marcarPaginas(nums) {
            const buscadas = new Set(nums);
            let n = 0, primera = null;
            document.querySelectorAll('#gridOrganizar .chk-pagina').forEach(chk => {
                const idx = parseInt(chk.dataset.idx);
                const marcar = buscadas.has(ordenPaginas[idx] + 1);
                chk.checked = marcar;
                if (marcar) { n++; if (primera === null) primera = chk; }
            });
            actualizarContadorSeleccionadas();
            primera?.closest('div[data-idx]')?.scrollIntoView({ block: 'nearest' });
            return n;
        },
        // Quita esas páginas del orden (por número visible) y re-dibuja el grid
        quitarPaginas(nums) {
            const fuera = new Set(nums);
            ordenPaginas = ordenPaginas.filter(idx => !fuera.has(idx + 1));
            _idxSelOrganizar = -1;   // los índices cambiaron: la selección ya no es fiable
            renderizarGridOrganizar();
        },
        toast: (msg, tipo) => mostrarToast(msg, tipo)
    };

    // Token de generación + caché de miniaturas: evita que dos renders del grid
    // se entrelacen (causaba páginas duplicadas y órdenes descuadrados al arrastrar
    // rápido) y hace instantáneos los re-renders tras cada movimiento.
    let _genOrganizar = 0;
    let _cacheMinisOrganizar = {};
    let _cacheMinisRef = null;

    // ==================== PANEL DE MINIATURAS (navegación) ====================
    // Icono "Miniaturas" de la barra inferior (btnThumbnails): muestra una miniatura
    // por página y al hacer clic navega a esa página. Solo navegación; para reordenar
    // o eliminar está "Organizar páginas". Comparte la caché de miniaturas con Organizar.
    let _genMinis = 0;
    async function abrirModalMiniaturas() {
        if (_necesitaPDF()) return;
        if (_cacheMinisRef !== state.pdfBytes) { _cacheMinisOrganizar = {}; _cacheMinisRef = state.pdfBytes; }
        let modal = document.getElementById('modalMiniaturas');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'modalMiniaturas';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';
            modal.innerHTML = `
                <div style="background:#fff;border-radius:12px;padding:20px;max-width:720px;width:92%;max-height:82vh;display:flex;flex-direction:column;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <h3 style="margin:0;color:#2c2c2c;font-size:17px;"><i class="bi bi-grid-3x2"></i> Miniaturas</h3>
                        <button id="btnCerrarMiniaturas" title="Cerrar" style="border:none;background:none;font-size:24px;line-height:1;cursor:pointer;color:#6d6d6d;">&times;</button>
                    </div>
                    <p style="font-size:12px;color:#6d6d6d;margin:0 0 12px;">Haz clic en una página para ir a ella.</p>
                    <div id="gridMiniaturas" style="flex:1;min-height:0;overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:12px;padding:2px;align-content:start;"></div>
                </div>`;
            document.body.appendChild(modal);
            modal.querySelector('#btnCerrarMiniaturas').addEventListener('click', () => { modal.style.display = 'none'; });
            modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
        }
        modal.style.display = 'flex';
        await _renderGridMiniaturas();
    }

    // Render de una miniatura concreta (cacheada por página). Devuelve el dataURL.
    async function _renderMiniatura(pageNum) {
        if (_cacheMinisOrganizar[pageNum]) return _cacheMinisOrganizar[pageNum];
        const page = await state.pdfDoc.getPage(pageNum);
        const vp = page.getViewport({ scale: 100 / page.getViewport({ scale: 1 }).width });
        const cv = document.createElement('canvas');
        cv.width = vp.width; cv.height = vp.height;
        await page.render({ canvasContext: cv.getContext('2d'), viewport: vp }).promise;
        const url = cv.toDataURL('image/jpeg', 0.75);
        _cacheMinisOrganizar[pageNum] = url;
        return url;
    }

    let _obsMinis = null;
    async function _renderGridMiniaturas() {
        const gen = ++_genMinis;
        const grid = document.getElementById('gridMiniaturas');
        if (!grid) return;
        if (_obsMinis) { _obsMinis.disconnect(); _obsMinis = null; }
        grid.innerHTML = '';
        // Render PEREZOSO: cada miniatura se genera solo cuando entra en el área visible
        // del panel. Con documentos de cientos de páginas el panel abre al instante y las
        // miniaturas visibles se llenan de inmediato (antes se renderizaban las N de golpe).
        _obsMinis = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const mini = entry.target;
                obs.unobserve(mini);
                const n = parseInt(mini.dataset.page);
                _renderMiniatura(n).then(url => { if (gen === _genMinis) mini.src = url; }).catch(() => {});
            });
        }, { root: grid, rootMargin: '150px' });

        let cardActual = null;
        for (let n = 1; n <= state.totalPages; n++) {
            const card = document.createElement('div');
            // Altura FIJA del card (no del img): un <img> sin src no reserva altura de forma
            // fiable y el grid colapsaba, haciendo que el observer viera TODAS las páginas como
            // visibles (renderizaba las N de golpe). Con altura fija el grid clipa y el lazy real funciona.
            card.style.cssText = 'border:2px solid ' + (n === state.currentPage ? '#1473e6' : '#e5e5e5') + ';border-radius:6px;overflow:hidden;cursor:pointer;background:white;height:160px;display:flex;flex-direction:column;';
            card.title = 'Ir a la página ' + n;
            if (n === state.currentPage) cardActual = card;
            const mini = document.createElement('img');
            mini.dataset.page = n;
            mini.style.cssText = 'width:100%;flex:1;min-height:0;display:block;object-fit:contain;background:#f0f0f0;';
            if (_cacheMinisOrganizar[n]) mini.src = _cacheMinisOrganizar[n];
            else _obsMinis.observe(mini);
            card.appendChild(mini);
            const lbl = document.createElement('div');
            lbl.style.cssText = 'text-align:center;font-size:11px;padding:4px;background:' + (n === state.currentPage ? '#e8f0fe' : '#f5f5f5') + ';border-top:1px solid #e5e5e5;color:#444;';
            lbl.textContent = 'Pág. ' + n;
            card.appendChild(lbl);
            card.addEventListener('click', () => {
                const m = document.getElementById('modalMiniaturas');
                if (m) m.style.display = 'none';
                renderPage(n);
            });
            grid.appendChild(card);
        }
        // Al abrir, centrar en la página actual (dispara el render de las miniaturas cercanas)
        if (cardActual) cardActual.scrollIntoView({ block: 'center' });
    }

    $('btnThumbnails')?.addEventListener('click', () => abrirModalMiniaturas());

    // Ficha seleccionada en el grid de Organizar (-1 = ninguna). Da soporte a
    // mover con las flechas arriba/abajo, que la ayuda del modal anuncia.
    let _idxSelOrganizar = -1;

    function _seleccionarFichaOrganizar(idx) {
        _idxSelOrganizar = idx;
        const grid = $('gridOrganizar');
        if (!grid) return;
        Array.from(grid.children).forEach(f => {
            const sel = parseInt(f.dataset.idx) === idx;
            f.style.borderColor = sel ? '#1473e6' : '#e5e5e5';
            f.style.boxShadow   = sel ? '0 0 0 2px rgba(20,115,230,.25)' : '';
        });
    }

    // Mueve la ficha seleccionada una posición en el orden (-1 arriba / +1 abajo)
    function _moverFichaOrganizar(dir) {
        const from = _idxSelOrganizar;
        const to   = from + dir;
        if (from < 0 || to < 0 || to >= ordenPaginas.length) return;
        const tmp = ordenPaginas[from];
        ordenPaginas.splice(from, 1);
        ordenPaginas.splice(to, 0, tmp);
        _idxSelOrganizar = to;
        renderizarGridOrganizar(); // crea las fichas de forma sincrona: ya se puede desplazar
        $('gridOrganizar')?.querySelector(`[data-idx="${to}"]`)?.scrollIntoView({ block: 'nearest' });
    }

    // Flechas arriba/abajo mueven la página seleccionada. Solo con el modal
    // Organizar abierto: si no, las flechas siguen navegando por el documento.
    document.addEventListener('keydown', e => {
        const modal = $('modalOrganizar');
        if (!modal || modal.classList.contains('hidden')) return;
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
        if (_idxSelOrganizar < 0) {
            mostrarToast('Selecciona primero una página (haz clic en su miniatura) para moverla con ↑ ↓', 'info');
            return;
        }
        e.preventDefault(); // evita que el grid haga scroll al mover
        _moverFichaOrganizar(e.key === 'ArrowUp' ? -1 : 1);
    });

    async function renderizarGridOrganizar() {
        const gen  = ++_genOrganizar;
        const grid = $('gridOrganizar');
        grid.innerHTML = '';
        $('btnAplicarOrganizar').disabled = false;
        $('btnEliminarSeleccionadas').style.display = 'none';
        const pendientes = [];
        // 1) Crear TODAS las fichas de forma síncrona (sin await: no puede entrelazarse)
        for (let i = 0; i < ordenPaginas.length; i++) {
            const pageNum = ordenPaginas[i] + 1;
            const div = document.createElement('div');
            div.dataset.idx = i;
            div.style.cssText = 'border:2px solid #e5e5e5;border-radius:6px;overflow:hidden;cursor:move;background:white;position:relative;';
            div.draggable = true;
            // Checkbox para selección múltiple
            const chkWrap = document.createElement('div');
            chkWrap.style.cssText = 'position:absolute;top:4px;left:4px;z-index:2;';
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.className = 'chk-pagina';
            chk.dataset.idx = i;
            chk.style.cssText = 'width:16px;height:16px;cursor:pointer;accent-color:#1473e6;';
            chk.title = 'Seleccionar para eliminar';
            chk.addEventListener('change', actualizarContadorSeleccionadas);
            chkWrap.appendChild(chk);
            div.appendChild(chkWrap);
            const mini = document.createElement('img');
            mini.draggable = false;
            mini.style.cssText = 'width:100%;display:block;min-height:60px;background:#fafafa;';
            if (_cacheMinisOrganizar[pageNum]) mini.src = _cacheMinisOrganizar[pageNum];
            else pendientes.push({ mini, pageNum });
            div.appendChild(mini);
            const lbl = document.createElement('div');
            lbl.style.cssText = 'text-align:center;font-size:11px;padding:4px;background:#f5f5f5;border-top:1px solid #e5e5e5;color:#444;';
            lbl.innerHTML = `Pág. ${pageNum} <button onclick="eliminarPaginaOrganizar(${i})" style="background:#fee2e2;border:none;border-radius:3px;padding:1px 5px;cursor:pointer;font-size:10px;color:#dc2626;margin-left:4px;" title="Eliminar">✕</button>`;
            div.appendChild(lbl);
            if (i === _idxSelOrganizar) {
                div.style.borderColor = '#1473e6';
                div.style.boxShadow   = '0 0 0 2px rgba(20,115,230,.25)';
            }
            grid.appendChild(div);
            // Clic = seleccionar la ficha (para moverla con ↑ ↓); doble clic = eliminarla.
            // Se ignoran los clics en el checkbox y en el botón ✕: ya tienen su accion.
            div.addEventListener('click', ev => {
                if (ev.target.closest('input, button')) return;
                _seleccionarFichaOrganizar(parseInt(div.dataset.idx));
            });
            div.addEventListener('dblclick', ev => {
                if (ev.target.closest('input, button')) return;
                ev.preventDefault();
                window.eliminarPaginaOrganizar(parseInt(div.dataset.idx));
            });
            // Drag & drop (índices leídos del DOM en el momento del evento)
            div.addEventListener('dragstart', e => { e.dataTransfer.setData('text', div.dataset.idx); });
            div.addEventListener('dragover', e => { e.preventDefault(); div.style.borderColor = '#1473e6'; });
            div.addEventListener('dragleave', () => { div.style.borderColor = '#e5e5e5'; });
            div.addEventListener('drop', e => {
                e.preventDefault();
                div.style.borderColor = '#e5e5e5';
                const from = parseInt(e.dataTransfer.getData('text'));
                const to = parseInt(div.dataset.idx);
                if (!isNaN(from) && !isNaN(to) && from !== to) {
                    const tmp = ordenPaginas[from];
                    ordenPaginas.splice(from, 1);
                    ordenPaginas.splice(to, 0, tmp);
                    renderizarGridOrganizar();
                }
            });
        }
        // 2) Renderizar las miniaturas que falten (cancelable si hay un render más nuevo)
        for (const { mini, pageNum } of pendientes) {
            if (gen !== _genOrganizar) return; // hubo otro render: abortar este
            try {
                const page = await state.pdfDoc.getPage(pageNum);
                const vp = page.getViewport({ scale: 100 / page.getViewport({scale:1}).width });
                const cv = document.createElement('canvas');
                cv.width = vp.width; cv.height = vp.height;
                await page.render({ canvasContext: cv.getContext('2d'), viewport: vp }).promise;
                const url = cv.toDataURL('image/jpeg', 0.75);
                _cacheMinisOrganizar[pageNum] = url;
                if (gen === _genOrganizar) mini.src = url;
            } catch(e) { /* miniatura fallida, no rompe */ }
        }
    }

    window.eliminarPaginaOrganizar = function(idx) {
        if (ordenPaginas.length <= 1) { mostrarToast('No puedes eliminar la única página', 'warn'); return; }
        if (!confirm('¿Eliminar la página ' + (ordenPaginas[idx]+1) + '?')) return;
        ordenPaginas.splice(idx, 1);
        // La selección apuntaria a otra página (o a ninguna) tras el borrado
        if (_idxSelOrganizar === idx) _idxSelOrganizar = -1;
        else if (_idxSelOrganizar > idx) _idxSelOrganizar--;
        renderizarGridOrganizar();
    };

    async function aplicarCambiosOrganizar() {
        if (!state.pdfBytes) return;
        showLoading(true);
        try {
            await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
            const { PDFDocument } = PDFLib;
            const pdfOrig = await PDFDocument.load(state.pdfBytes);
            const nuevo = await PDFDocument.create();
            for (const idx of ordenPaginas) {
                const [pg] = await nuevo.copyPages(pdfOrig, [idx]);
                nuevo.addPage(pg);
            }
            const bytes = await nuevo.save();
            await _cambiarDocumento(bytes, 'la rotación de páginas');
            state.hayCambios = true;
            _cerrarModal('modalOrganizar');
            mostrarToast('Páginas reorganizadas correctamente', 'ok');
        } catch(e) {
            _mostrarError('errorOrganizar', 'Error: ' + e.message);
        } finally { showLoading(false); }
    }

    // Eliminar múltiples páginas seleccionadas
    $('btnEliminarSeleccionadas')?.addEventListener('click', function() {
        const checks = document.querySelectorAll('.chk-pagina:checked');
        if (checks.length === 0) return;
        if (checks.length >= ordenPaginas.length) {
            mostrarToast('No puedes eliminar todas las páginas', 'warn');
            return;
        }
        const indices = Array.from(checks).map(c => parseInt(c.dataset.idx)).sort((a,b) => b - a);
        const pagNums = indices.map(i => ordenPaginas[i] + 1).sort((a,b) => a - b);
        if (!confirm('¿Eliminar ' + indices.length + ' página(s): ' + pagNums.join(', ') + '?')) return;
        // Eliminar de atrás hacia adelante para no alterar índices
        indices.forEach(i => ordenPaginas.splice(i, 1));
        _idxSelOrganizar = -1; // los indices cambiaron: la selección ya no es fiable
        renderizarGridOrganizar();
        mostrarToast(indices.length + ' página(s) marcadas para eliminar. Haz clic en "Aplicar cambios" para confirmar.', 'info');
    });

    $('btnAplicarOrganizar')?.addEventListener('click', aplicarCambiosOrganizar);
    $('btnCancelarOrganizar')?.addEventListener('click', () => _cerrarModal('modalOrganizar'));
    $('btnCerrarOrganizar')?.addEventListener('click', () => _cerrarModal('modalOrganizar'));
    $('btnExtraerDesdeOrganizar')?.addEventListener('click', () => {
        _cerrarModal('modalOrganizar');
        $('lblTotalPaginasExtraer').textContent = state.totalPages;
        _ocultarError('errorExtraer');
        _abrirModal('modalExtraer');
    });

    // ==================== ORGANIZAR (tools) ====================
    $('toolOrganizar')?.addEventListener('click', () => { if (!_necesitaPDF()) abrirModalOrganizar(); });
    $('toolOrganizarPag')?.addEventListener('click', () => { if (!_necesitaPDF()) abrirModalOrganizar(); });
    $('btnRightPages')?.addEventListener('click', () => { if (!_necesitaPDF()) abrirModalOrganizar(); });

};
