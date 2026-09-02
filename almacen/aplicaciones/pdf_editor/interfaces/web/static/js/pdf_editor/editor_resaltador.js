/* ============================================================
   Raíces Maquita — Editor PDF · resaltador a mano alzada
   El resaltador funciona como un rotulador de verdad: se aprieta, se arrastra y se
   resalta SOLO la franja por la que se pasa. La franja sale siempre recta aunque la
   mano tiemble en vertical, que es justo lo que se quiere al resaltar un renglón.

   Antes había que seleccionar el texto con el ratón y se resaltaba la selección
   entera, renglón completo incluido. Eso es lo que se cambió el 2026-07-30.

   Esta es UNA PARTE del editor: se registra aquí y el núcleo la arranca pasándole
   `E`, el objeto con lo que se comparte entre partes.
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.resaltador = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo:
    const { $, _currentPageWrapper, _currentAnnotLayer, _getPageFromEvent, state } = E;

    // Funciones que viven en otras partes:
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista

    // Alto mínimo de la franja, en puntos: por debajo no se ve el resaltado.
    const ALTO_MINIMO = 6;
    // El selector de grosor da 1, 2, 4, 6 y 10 (pensado para el lápiz). Para el
    // rotulador esos números son pelos, así que se multiplican: un grosor 2 (el que
    // viene puesto) da una franja de 10 puntos, que es lo que mide un renglón normal.
    const PUNTOS_POR_GROSOR = 5;
    // Ancho mínimo para que el trazo cuente: por debajo fue un clic, no un arrastre.
    const ANCHO_MINIMO = 3;

    const _rotu = { activo: false, pagina: null, x0: 0, y: 0, alto: 0, color: '#FFE500', previa: null };

    function _altoDeLaFranja() {
        const grosor = parseFloat($('drawWidthSelect')?.value || 2);
        return Math.max(ALTO_MINIMO, grosor * PUNTOS_POR_GROSOR);
    }

    /** Convierte '#RRGGBB' en 'rgba(r,g,b,alfa)'. El resaltado tiene que dejar leer
     *  el texto de debajo, así que nunca se pinta opaco. */
    function _conAlfa(hex, alfa) {
        const h = String(hex || '#FFE500').replace('#', '');
        const r = parseInt(h.substr(0, 2), 16), g = parseInt(h.substr(2, 2), 16), b = parseInt(h.substr(4, 2), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alfa + ')';
    }

    /** Coordenadas del ratón en puntos del PDF (o null si no hay página debajo). */
    function _puntoEnLaPagina(e) {
        const envoltorio = document.getElementById('pageWrapper_' + _rotu.pagina) || _currentPageWrapper();
        if (!envoltorio) return null;
        const caja = envoltorio.getBoundingClientRect();
        return {
            x: (e.clientX - caja.left) / state.zoom,
            y: (e.clientY - caja.top) / state.zoom,
            envoltorio: envoltorio,
        };
    }

    /** Repinta la franja de vista previa mientras se arrastra. */
    function _pintarPrevia(xActual) {
        if (!_rotu.previa) return;
        const izq = Math.min(_rotu.x0, xActual);
        const ancho = Math.abs(xActual - _rotu.x0);
        _rotu.previa.style.left = (izq * state.zoom) + 'px';
        _rotu.previa.style.top = (_rotu.y * state.zoom) + 'px';
        _rotu.previa.style.width = (ancho * state.zoom) + 'px';
        _rotu.previa.style.height = (_rotu.alto * state.zoom) + 'px';
    }

    $('viewerScroll')?.addEventListener('mousedown', e => {
        if (state.currentTool !== 'highlight' || !state.pdfDoc) return;
        // Sin esto el navegador empieza a seleccionar texto y el arrastre se ve fatal.
        e.preventDefault();
        _getPageFromEvent(e);
        _rotu.pagina = state.currentPage;
        const p = _puntoEnLaPagina(e);
        if (!p) return;

        _rotu.alto = _altoDeLaFranja();
        _rotu.color = $('annotColor')?.value || '#FFE500';
        _rotu.x0 = p.x;
        // La franja se centra donde se apretó: así se resalta el renglón que se apunta.
        _rotu.y = p.y - _rotu.alto / 2;
        _rotu.activo = true;

        const capa = _currentAnnotLayer();
        if (capa) {
            const previa = document.createElement('div');
            previa.className = 'resaltado-previa';
            previa.style.position = 'absolute';
            previa.style.background = _conAlfa(_rotu.color, 0.4);
            previa.style.pointerEvents = 'none';
            capa.appendChild(previa);
            _rotu.previa = previa;
        }
        _pintarPrevia(p.x);
    });

    $('viewerScroll')?.addEventListener('mousemove', e => {
        if (!_rotu.activo || state.currentTool !== 'highlight') return;
        const p = _puntoEnLaPagina(e);
        if (p) _pintarPrevia(p.x);
    });

    document.addEventListener('mouseup', e => {
        if (!_rotu.activo) return;
        _rotu.activo = false;
        if (_rotu.previa) { _rotu.previa.remove(); _rotu.previa = null; }

        const p = _puntoEnLaPagina(e);
        if (!p) return;
        const izq = Math.min(_rotu.x0, p.x);
        const ancho = Math.abs(p.x - _rotu.x0);
        // Un clic sin arrastrar no resalta nada: sería una mancha en medio del texto.
        if (ancho < ANCHO_MINIMO) return;

        // No dejar que la franja se salga de la hoja.
        const caja = p.envoltorio.getBoundingClientRect();
        const anchoPagina = caja.width / state.zoom;
        const altoPagina = caja.height / state.zoom;
        const x = Math.max(0, izq);
        const y = Math.max(0, Math.min(_rotu.y, altoPagina - _rotu.alto));

        if (!state.annotations[_rotu.pagina]) state.annotations[_rotu.pagina] = [];
        state.annotations[_rotu.pagina].push({
            type: 'highlight',
            x: x,
            y: y,
            width: Math.min(ancho, anchoPagina - x),
            height: _rotu.alto,
            color: _rotu.color,
        });
        state.hayCambios = true;
        renderAnnotations(_rotu.pagina);
        // La herramienta se queda activa: se suele resaltar varias cosas seguidas.
    });
};
