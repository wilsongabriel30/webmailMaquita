/* ============================================================
   Raíces Maquita — Editor PDF · anotar formas
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.anotar_formas = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, SVGNS, _currentPageWrapper, _getPageFromEvent, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    const setTool = (...a) => E.setTool(...a);   // parte herramientas
    // ==================== SELECCIÓN DE TEXTO → ANOTACIÓN ====================
    // Cuando el usuario selecciona texto con subrayado/tachado activo.
    // El RESALTADOR ya no está aquí: desde el 2026-07-30 se usa arrastrando, como un
    // rotulador, y su código vive en editor_resaltador.js. Antes se resaltaba la
    // selección entera y salían renglones completos que nadie había pedido.
    document.addEventListener('mouseup', function() {
        const tool = state.currentTool;
        if (!['underline', 'strikeout'].includes(tool)) return;
        if (!state.pdfDoc) return;

        const selection = window.getSelection();
        if (!selection || selection.isCollapsed || !selection.rangeCount) return;

        // Detectar la página desde la propia selección (no asumir la "página actual")
        const anchorEl = selection.anchorNode.nodeType === Node.ELEMENT_NODE
            ? selection.anchorNode : selection.anchorNode.parentElement;
        const pageWrapper = anchorEl ? anchorEl.closest('.page-wrapper') : null;
        const textLayer   = pageWrapper ? pageWrapper.querySelector('.textLayer') : null;
        if (!pageWrapper || !textLayer || !textLayer.contains(selection.anchorNode)) return;
        const pg = parseInt(pageWrapper.dataset.page);
        if (pg && pg !== state.currentPage) {
            state.currentPage = pg;
            $('currentPage').textContent = pg;
        }

        const range      = selection.getRangeAt(0);
        const clientRects = Array.from(range.getClientRects()).filter(r => r.width > 2 && r.height > 2);
        if (!clientRects.length) return;

        const wrapperRect = pageWrapper.getBoundingClientRect();
        if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];

        const defaultColors = { highlight: '#FFE500', underline: '#1473e6', strikeout: '#dc2626' };
        const color = $('annotColor')?.value || defaultColors[tool];

        for (const cr of clientRects) {
            state.annotations[state.currentPage].push({
                type:   tool,
                x:      (cr.left - wrapperRect.left) / state.zoom,
                y:      (cr.top  - wrapperRect.top)  / state.zoom,
                width:  cr.width  / state.zoom,
                height: cr.height / state.zoom,
                color
            });
        }
        selection.removeAllRanges();
        state.hayCambios = true;
        renderAnnotations(state.currentPage);
        // mantener herramienta activa para anotar consecutivamente
    });

    // ==================== PANEL DE LA HERRAMIENTA (color / grosor / formas) ====================
    // El color vive en el input oculto #annotColor, que es de donde ya leian el
    // lapiz y el resaltador: al cambiarlo aquí, todo lo demas funciona igual.
    const GAMA_SOLIDA  = ['#000000', '#dc2626', '#1473e6', '#16a34a', '#f59e0b', '#7c3aed', '#6d6d6d'];
    const GAMA_RESALTE = ['#FFE500', '#a3e635', '#67e8f9', '#f9a8d4', '#fdba74', '#c4b5fd'];
    // Color recordado por herramienta: cambiar de lapiz a resaltar no debe
    // pintar el resaltado del color del lapiz
    const _colorHerr = {
        draw:      '#000000',
        highlight: '#FFE500',
        underline: '#1473e6',
        strikeout: '#dc2626',
        shape:     '#dc2626'
    };
    const _TITULOS_HERR = {
        draw: 'Lápiz', highlight: 'Resaltador', underline: 'Subrayado',
        strikeout: 'Tachado', shape: 'Formas'
    };
    const _HERR_CON_PANEL = ['draw', 'highlight', 'underline', 'strikeout', 'shape'];
    // El comentario NO está aquí: sus opciones salen en su propia barra, arriba del
    // documento (editor_comentarios.js), como pidió el usuario.

    function _pintarGama(herramienta) {
        const cont = $('gamaColores');
        if (!cont) return;
        const gama = herramienta === 'highlight' ? GAMA_RESALTE : GAMA_SOLIDA;
        const actual = _colorHerr[herramienta];
        cont.innerHTML = '';
        gama.forEach(col => {
            const b = document.createElement('button');
            b.type = 'button';
            b.style.background = col;
            b.title = 'Usar este color';
            if (col.toLowerCase() === (actual || '').toLowerCase()) b.classList.add('sel');
            b.addEventListener('click', () => _fijarColorHerr(herramienta, col));
            cont.appendChild(b);
        });
    }

    function _fijarColorHerr(herramienta, color) {
        _colorHerr[herramienta] = color;
        const inp = $('annotColor');
        if (inp) inp.value = color;
        const libre = $('colorLibreAnot');
        if (libre) libre.value = color;
        _pintarGama(herramienta);
    }

    // Muestra u oculta el panel según la herramienta activa
    function _actualizarPanelAnotacion(herramienta) {
        const panel = $('panelAnotacion');
        if (!panel) return;
        const visible = _HERR_CON_PANEL.includes(herramienta);
        panel.classList.toggle('hidden', !visible);
        if (!visible) return;

        $('tituloPanelAnot').textContent = _TITULOS_HERR[herramienta] || 'Color';
        // El grosor aplica al lapiz, a las formas y —desde que el resaltador se usa
        // arrastrando— al alto de la franja del rotulador.
        const usaGrosor = (herramienta === 'draw' || herramienta === 'shape' || herramienta === 'highlight');
        $('filaGrosorAnot').style.display  = usaGrosor ? '' : 'none';
        // Para el rotulador el numero no es un grosor de linea, es el alto de la franja:
        // se le cambia el rotulo para que se entienda.
        const rotuloGrosor = $('filaGrosorAnot')?.querySelector('label');
        if (rotuloGrosor) rotuloGrosor.textContent = (herramienta === 'highlight') ? 'Alto de la franja' : 'Grosor';
        $('filaFormas').style.display      = herramienta === 'shape' ? '' : 'none';
        $('filaQuitarResaltado').style.display = herramienta === 'highlight' ? '' : 'none';
        $('ayudaPanelAnot').textContent = herramienta === 'shape'
            ? 'Elige una forma y arrástrala sobre la página.'
            : (herramienta === 'highlight'
                ? 'Arrastra sobre el texto, como un rotulador: se resalta solo por donde pases.'
                : 'El color se aplica a lo próximo que dibujes.');
        // Sincronizar el input oculto con el color recordado de ESTA herramienta
        const inp = $('annotColor');
        if (inp) inp.value = _colorHerr[herramienta];
        const libre = $('colorLibreAnot');
        if (libre) libre.value = _colorHerr[herramienta];
        _pintarGama(herramienta);
    }

    $('colorLibreAnot')?.addEventListener('input', e => {
        const herr = state.currentTool;
        if (_HERR_CON_PANEL.includes(herr)) _fijarColorHerr(herr, e.target.value);
    });

    // Quitar resaltado: activa un modo en el que un clic sobre un resaltado lo elimina
    $('btnQuitarResaltado')?.addEventListener('click', () => setTool('unhighlight'));

    // ==================== FORMAS (rectángulo, elipse, flecha, línea) ====================
    // Se dibujan arrastrando sobre la página, como se marca un area en la
    // herramienta de Recortes de Windows. Quedan como anotación arrastrable.
    const _forma = { activa: false, subtipo: 'rect', pagina: null, x0: 0, y0: 0, previa: null };

    const _BTN_FORMA = {
        rect:   'btnFormaRect',   elipse: 'btnFormaElipse',
        flecha: 'btnFormaFlecha', linea:  'btnFormaLinea'
    };

    function _elegirForma(subtipo) {
        _forma.subtipo = subtipo;
        Object.entries(_BTN_FORMA).forEach(([st, id]) =>
            $(id)?.classList.toggle('active', st === subtipo));
        if (state.currentTool !== 'shape') setTool('shape');
    }
    Object.entries(_BTN_FORMA).forEach(([st, id]) =>
        $(id)?.addEventListener('click', () => _elegirForma(st)));

    // Dibuja la forma dentro de un <svg> que ocupa todo el elemento (w x h en
    // pixeles de pantalla). Se usa tanto para la vista previa como para el render.
    function _pintarFormaSVG(svg, subtipo, w, h, color, grosorPx, p1, p2) {
        svg.innerHTML = '';
        const g = Math.max(1, grosorPx);
        const m = g / 2;   // margen para que el trazo no se corte en el borde
        let el;
        if (subtipo === 'elipse') {
            el = document.createElementNS(SVGNS, 'ellipse');
            el.setAttribute('cx', w / 2); el.setAttribute('cy', h / 2);
            el.setAttribute('rx', Math.max(1, w / 2 - m));
            el.setAttribute('ry', Math.max(1, h / 2 - m));
            el.setAttribute('fill', 'none');
            el.setAttribute('stroke', color); el.setAttribute('stroke-width', g);
            svg.appendChild(el);
        } else if (subtipo === 'rect') {
            el = document.createElementNS(SVGNS, 'rect');
            el.setAttribute('x', m); el.setAttribute('y', m);
            el.setAttribute('width',  Math.max(1, w - g));
            el.setAttribute('height', Math.max(1, h - g));
            el.setAttribute('fill', 'none');
            el.setAttribute('stroke', color); el.setAttribute('stroke-width', g);
            svg.appendChild(el);
        } else {
            // línea y flecha: p1/p2 son fracciones del rectángulo (conservan la diagonal)
            const x1 = p1[0] * w, y1 = p1[1] * h, x2 = p2[0] * w, y2 = p2[1] * h;
            el = document.createElementNS(SVGNS, 'line');
            el.setAttribute('x1', x1); el.setAttribute('y1', y1);
            el.setAttribute('x2', x2); el.setAttribute('y2', y2);
            el.setAttribute('stroke', color); el.setAttribute('stroke-width', g);
            el.setAttribute('stroke-linecap', 'round');
            svg.appendChild(el);
            if (subtipo === 'flecha') {
                const ang  = Math.atan2(y2 - y1, x2 - x1);
                const lado = Math.max(8, g * 3.5);
                const a1 = ang + Math.PI * 0.82, a2 = ang - Math.PI * 0.82;
                const tri = document.createElementNS(SVGNS, 'polygon');
                tri.setAttribute('points',
                    `${x2},${y2} ${x2 + lado*Math.cos(a1)},${y2 + lado*Math.sin(a1)} ` +
                    `${x2 + lado*Math.cos(a2)},${y2 + lado*Math.sin(a2)}`);
                tri.setAttribute('fill', color);
                svg.appendChild(tri);
            }
        }
    }

    $('viewerScroll').addEventListener('mousedown', e => {
        if (state.currentTool !== 'shape' || !state.pdfDoc) return;
        e.preventDefault();
        _getPageFromEvent(e);
        const wrapper = _currentPageWrapper();
        const svgCapa = wrapper?.querySelector('.draw-svg');
        if (!svgCapa) return;
        const rect = wrapper.getBoundingClientRect();
        _forma.activa = true;
        _forma.pagina = state.currentPage;
        _forma.x0 = (e.clientX - rect.left) / state.zoom;
        _forma.y0 = (e.clientY - rect.top)  / state.zoom;
        // Vista previa: un <g> dentro de la capa SVG de la página
        const g = document.createElementNS(SVGNS, 'g');
        g.id = 'formaPrevia';
        svgCapa.appendChild(g);
        _forma.previa = g;
    });

    $('viewerScroll').addEventListener('mousemove', e => {
        if (!_forma.activa || state.currentTool !== 'shape' || !_forma.previa) return;
        const wrapper = document.getElementById('pageWrapper_' + _forma.pagina) || _currentPageWrapper();
        const rect = wrapper.getBoundingClientRect();
        const x1 = (e.clientX - rect.left) / state.zoom;
        const y1 = (e.clientY - rect.top)  / state.zoom;
        const x = Math.min(_forma.x0, x1), y = Math.min(_forma.y0, y1);
        const w = Math.abs(x1 - _forma.x0), h = Math.abs(y1 - _forma.y0);
        const color  = $('annotColor')?.value || '#dc2626';
        const grosor = parseFloat($('drawWidthSelect')?.value || 2);
        // p1/p2 en fracciones: así la diagonal se conserva al escalar
        const p1 = [(_forma.x0 - x) / (w || 1), (_forma.y0 - y) / (h || 1)];
        const p2 = [(x1 - x) / (w || 1), (y1 - y) / (h || 1)];
        _forma.previa.innerHTML = '';
        const sub = document.createElementNS(SVGNS, 'svg');
        sub.setAttribute('x', x * state.zoom); sub.setAttribute('y', y * state.zoom);
        sub.setAttribute('width',  Math.max(1, w * state.zoom));
        sub.setAttribute('height', Math.max(1, h * state.zoom));
        sub.style.overflow = 'visible';
        _pintarFormaSVG(sub, _forma.subtipo, w * state.zoom, h * state.zoom,
                        color, grosor * state.zoom, p1, p2);
        _forma.previa.appendChild(sub);
        _forma._ultimo = { x, y, w, h, p1, p2, color, grosor };
    });

    document.addEventListener('mouseup', () => {
        if (!_forma.activa) return;
        _forma.activa = false;
        _forma.previa?.remove();
        _forma.previa = null;
        const u = _forma._ultimo;
        _forma._ultimo = null;
        // Descartar clics sueltos o formas minusculas
        if (!u || (u.w < 3 && u.h < 3)) return;
        const pag = _forma.pagina;
        if (!state.annotations[pag]) state.annotations[pag] = [];
        state.annotations[pag].push({
            type: 'shape', subtipo: _forma.subtipo,
            x: u.x, y: u.y, width: u.w, height: u.h,
            p1: u.p1, p2: u.p2, color: u.color, grosor: u.grosor
        });
        state.hayCambios = true;
        renderAnnotations(pag);
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _actualizarPanelAnotacion, _pintarFormaSVG });
};
