/* ============================================================
   Raíces Maquita — Editor PDF · anotar borrador
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.anotar_borrador = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _currentPageWrapper, _getPageFromEvent, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    // ==================== BORRADOR (goma tipo Paint) ====================
    // Borra SOLO el trozo de trazo que queda bajo la goma: el trazo se parte y
    // los pedazos que sobreviven se conservan (no se elimina el trazo entero).
    // El radio va en pixeles de PANTALLA (dividido por el zoom al usarlo), así
    // la goma borra siempre lo mismo que muestra el cursor, haya el zoom que haya.
    const _goma = { activa: false, radioPantalla: 9, rafId: null, pagina: null, ultimo: null,
                    antes: null,        // foto de las anotaciones antes de esta pasada
                    borroAlgo: false }; // ¿esta pasada borró algo? (si no, no se registra)

    // Distancia de un punto al segmento AB: permite saber si la goma toca el
    // trazo sin tener que subdividirlo antes.
    function _distPuntoSegmento(px, py, ax, ay, bx, by) {
        const dx = bx - ax, dy = by - ay;
        const largo2 = dx * dx + dy * dy;
        if (largo2 === 0) return Math.hypot(px - ax, py - ay);
        let t = ((px - ax) * dx + (py - ay) * dy) / largo2;
        t = Math.max(0, Math.min(1, t));
        return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
    }

    // Subdivide un trazo en puntos cada `paso` para poder recortarlo con finura
    // (un trazo rápido puede tener dos puntos muy separados).
    function _densificarTrazo(trazo, paso) {
        if (trazo.length < 2) return trazo.slice();
        const out = [];
        for (let i = 0; i < trazo.length - 1; i++) {
            const [ax, ay] = trazo[i], [bx, by] = trazo[i + 1];
            const n = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) / paso));
            for (let k = 0; k < n; k++) out.push([ax + (bx - ax) * k / n, ay + (by - ay) * k / n]);
        }
        out.push(trazo[trazo.length - 1]);
        return out;
    }

    /** ¿La goma toca esta anotación? Es para lo que NO se puede recortar a medias
     *  (una imagen, un cuadro de texto, una firma, una forma): o se borra entera o
     *  no se toca. Función pura: se puede probar sin navegador.
     *
     *  Con las formas se mira la LÍNEA dibujada, no el rectángulo que la contiene:
     *  pasar la goma por dentro de un recuadro vacío no debe llevárselo, igual que
     *  en Paint no borras un cuadrado por pasar la goma por el hueco del medio. */
    function _gomaTocaAnotacion(ann, cx, cy, radio) {
        const x = ann.x || 0, y = ann.y || 0;
        const w = ann.width || 0, h = ann.height || 0;
        const margen = radio + (ann.grosor || 1) / 2;

        if (ann.type === 'shape') {
            const sub = ann.subtipo || 'rect';
            if (sub === 'linea' || sub === 'flecha') {
                // p1/p2 se guardan como fracciones del rectángulo (así la diagonal
                // se conserva al escalar): se pasan a puntos de la página.
                const p1 = ann.p1 || [0, 0], p2 = ann.p2 || [1, 1];
                return _distPuntoSegmento(cx, cy, x + p1[0] * w, y + p1[1] * h,
                                                  x + p2[0] * w, y + p2[1] * h) <= margen;
            }
            if (sub === 'elipse') {
                // Se lleva el punto a un círculo de radio 1: allí el borde es d = 1.
                const rx = Math.max(w / 2, 0.001), ry = Math.max(h / 2, 0.001);
                const dx = (cx - (x + rx)) / rx, dy = (cy - (y + ry)) / ry;
                const d = Math.hypot(dx, dy);
                return Math.abs(d - 1) * Math.min(rx, ry) <= margen;
            }
            // Rectángulo: se miran sus cuatro lados, no el relleno.
            const lados = [[x, y, x + w, y], [x + w, y, x + w, y + h],
                           [x + w, y + h, x, y + h], [x, y + h, x, y]];
            return lados.some(l => _distPuntoSegmento(cx, cy, l[0], l[1], l[2], l[3]) <= margen);
        }

        // Todo lo demás (imagen, cuadro de texto, firma, sello, comentario, campo) es
        // un bloque macizo: basta con que la goma entre en su recuadro.
        const cerca = (v, a, b) => Math.max(a, Math.min(v, b));
        const px = cerca(cx, x, x + Math.max(w, 1)), py = cerca(cy, y, y + Math.max(h, 1));
        return Math.hypot(cx - px, cy - py) <= radio;
    }

    /** Recorta una franja (resaltado, subrayado o tachado) por donde pasa la goma.
     *  La franja es un rectángulo, así que borrar un trozo del medio deja DOS trozos:
     *  el de la izquierda y el de la derecha. Es lo que se espera al pasar la goma por
     *  media frase resaltada: se queda resaltado lo de antes y lo de después.
     *
     *  Devuelve los trozos que sobreviven (lista vacía si la goma se lo llevó todo),
     *  o `null` si la goma no llega a tocar la franja y hay que dejarla como está.
     *  Es una función pura (solo números): así se puede probar sin navegador. */
    function _recortarBanda(ann, cx, cy, radio) {
        const MINIMO = 1;                      // un trozo más fino que esto no se ve
        const izq = ann.x, der = ann.x + ann.width;
        const arr = ann.y, aba = ann.y + ann.height;
        // ¿La goma toca la franja? Se compara el cuadrado de la goma con el rectángulo.
        if (cx + radio <= izq || cx - radio >= der) return null;
        if (cy + radio <= arr || cy - radio >= aba) return null;

        const trozos = [];
        const cortaDesde = cx - radio, cortaHasta = cx + radio;
        if (cortaDesde - izq >= MINIMO) {
            trozos.push(Object.assign({}, ann, { x: izq, width: cortaDesde - izq }));
        }
        if (der - cortaHasta >= MINIMO) {
            trozos.push(Object.assign({}, ann, { x: cortaHasta, width: der - cortaHasta }));
        }
        return trozos;
    }

    // Aplica la goma en un punto: recorta lo que cae dentro del circulo y parte
    // el trazo en los pedazos restantes. Devuelve true si borro algo.
    function _gomaEnPunto(pageNum, cx, cy, radio) {
        const lista = state.annotations[pageNum];
        if (!lista || !lista.length) return false;
        let cambio = false;
        let tocoBandas = false;
        const quedan = [];
        const BANDAS = ['highlight', 'underline', 'strikeout'];
        for (const ann of lista) {
            if (ann.type !== 'draw' && !BANDAS.includes(ann.type)) {
                // Una edición de texto NO se borra con la goma: no es un adorno, es un
                // cambio de texto que el servidor ya tiene o va a recibir. Quitarla de
                // un brochazo dejaría la pantalla y el documento diciendo cosas
                // distintas. Para deshacer un cambio de texto se vuelve a editar.
                if (ann.type === 'edicion') { quedan.push(ann); continue; }
                if (_gomaTocaAnotacion(ann, cx, cy, radio)) {
                    cambio = true;
                    tocoBandas = true;      // hay que rehacer la capa del DOM
                    continue;               // se va entera: no se puede partir una imagen
                }
                quedan.push(ann);
                continue;
            }
            if (BANDAS.includes(ann.type)) {
                // Resaltados, subrayados y tachados: se recortan por donde pasa la goma.
                const trozos = _recortarBanda(ann, cx, cy, radio);
                if (trozos === null) { quedan.push(ann); continue; }
                cambio = true;
                tocoBandas = true;
                for (const t of trozos) quedan.push(t);
                continue;
            }
            const nuevos = [];
            let tocado = false;
            for (const trazo of (ann.trazos || [])) {
                // ¿la goma toca este trazo? si no, se conserva intacto
                let cerca = false;
                if (trazo.length === 1) {
                    cerca = Math.hypot(trazo[0][0] - cx, trazo[0][1] - cy) <= radio;
                } else {
                    for (let i = 0; i < trazo.length - 1 && !cerca; i++) {
                        if (_distPuntoSegmento(cx, cy, trazo[i][0], trazo[i][1],
                                               trazo[i+1][0], trazo[i+1][1]) <= radio) cerca = true;
                    }
                }
                if (!cerca) { nuevos.push(trazo); continue; }
                tocado = true;
                const denso = _densificarTrazo(trazo, Math.max(0.5, radio / 3));
                let tramo = [];
                for (const p of denso) {
                    if (Math.hypot(p[0] - cx, p[1] - cy) <= radio) {
                        if (tramo.length > 1) nuevos.push(tramo);   // pedazo que sobrevive
                        tramo = [];
                    } else tramo.push(p);
                }
                if (tramo.length > 1) nuevos.push(tramo);
            }
            if (tocado) cambio = true;
            if (nuevos.length) { ann.trazos = nuevos; quedan.push(ann); }
            else if (!tocado) quedan.push(ann);   // intacta: se conserva
            // tocada y sin pedazos supervivientes => desaparece
        }
        if (cambio) {
            state.annotations[pageNum] = quedan;
            state.hayCambios = true;
            // Los trazos viven en el SVG y los repinta _redrawDrawAnnotations; las
            // franjas son elementos del DOM, así que hay que rehacer la capa.
            if (tocoBandas) _repintarBandas(pageNum);
        }
        return cambio;
    }

    // Rehacer la capa de anotaciones es caro, y mover la goma dispara muchísimos
    // eventos: se hace como máximo una vez por frame.
    let _rafBandas = null;
    function _repintarBandas(pageNum) {
        if (_rafBandas) return;
        _rafBandas = requestAnimationFrame(() => {
            _rafBandas = null;
            renderAnnotations(pageNum);
        });
    }

    // Aplica la goma a lo largo del recorrido del raton: interpola entre la
    // posición anterior y la actual para no dejar huecos al mover rapido.
    function _gomaDesdeEvento(e) {
        const wrapper = document.getElementById('pageWrapper_' + _goma.pagina) || _currentPageWrapper();
        if (!wrapper) return;
        const rect  = wrapper.getBoundingClientRect();
        const radio = _goma.radioPantalla / state.zoom;
        const cx = (e.clientX - rect.left) / state.zoom;
        const cy = (e.clientY - rect.top)  / state.zoom;
        const puntos = [];
        if (_goma.ultimo) {
            const [ux, uy] = _goma.ultimo;
            const n = Math.max(1, Math.ceil(Math.hypot(cx - ux, cy - uy) / (radio / 2)));
            for (let k = 1; k <= n; k++) puntos.push([ux + (cx - ux) * k / n, uy + (cy - uy) * k / n]);
        } else {
            puntos.push([cx, cy]);
        }
        _goma.ultimo = [cx, cy];
        let algo = false;
        for (const [px, py] of puntos) if (_gomaEnPunto(_goma.pagina, px, py, radio)) algo = true;
        if (algo) _goma.borroAlgo = true;
        // Repintar como máximo una vez por frame (mover la goma dispara muchos eventos)
        if (algo && !_goma.rafId) {
            _goma.rafId = requestAnimationFrame(() => {
                _redrawDrawAnnotations(_goma.pagina);
                _goma.rafId = null;
            });
        }
    }

    $('viewerScroll').addEventListener('mousedown', e => {
        if (state.currentTool !== 'erase' || !state.pdfDoc) return;
        e.preventDefault();
        _getPageFromEvent(e);
        _goma.activa = true;
        _goma.pagina = state.currentPage;
        _goma.ultimo = null;
        // Foto de cómo estaban las anotaciones ANTES de este pasada de goma. Se
        // registra en el historial al soltar, y solo si se borró algo: así Ctrl+Z
        // devuelve lo borrado y no se llena el historial de pasos vacíos.
        _goma.antes = JSON.stringify(state.annotations[_goma.pagina] || []);
        _goma.borroAlgo = false;
        _gomaDesdeEvento(e);
    });

    $('viewerScroll').addEventListener('mousemove', e => {
        if (!_goma.activa || state.currentTool !== 'erase') return;
        _gomaDesdeEvento(e);
    });

    document.addEventListener('mouseup', () => {
        if (!_goma.activa) return;
        _goma.activa = false;
        _goma.ultimo = null;
        if (_goma.rafId) { cancelAnimationFrame(_goma.rafId); _goma.rafId = null; }
        _redrawDrawAnnotations(_goma.pagina);   // repintado final garantizado
        // Una pasada de goma = un paso de Ctrl+Z. Se registra al soltar (no en cada
        // punto del recorrido), y solo si de verdad se borró algo.
        if (_goma.borroAlgo && _goma.antes !== null) {
            window.PDFHistorial?.registrarAnotaciones(
                _goma.pagina, JSON.parse(_goma.antes), 'el borrado con la goma');
        }
        _goma.antes = null;
        _goma.borroAlgo = false;
    });

    // ==================== HERRAMIENTA DIBUJO (pluma libre) ====================
    const _draw = { active: false, path: [], rafId: null, dString: '', livePath: null };

    $('viewerScroll').addEventListener('mousedown', e => {
        if (state.currentTool !== 'draw' || !state.pdfDoc) return;
        e.preventDefault();
        _getPageFromEvent(e);
        _draw.active  = true;
        _draw.path    = [];
        _draw.dString = '';
        const rect = _currentPageWrapper().getBoundingClientRect();
        const px   = (e.clientX - rect.left) / state.zoom;
        const py   = (e.clientY - rect.top)  / state.zoom;
        _draw.path.push([px, py]);
        _draw.dString = `M ${px * state.zoom} ${py * state.zoom}`;

        // Crear path SVG de vista previa
        const svg = _currentPageWrapper().querySelector('.draw-svg');
        if (!svg) return;
        const live = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        live.id = 'liveDraw';
        live.setAttribute('fill', 'none');
        live.setAttribute('stroke-linecap', 'round');
        live.setAttribute('stroke-linejoin', 'round');
        const color = $('annotColor')?.value || '#000000';
        const width = parseFloat($('drawWidthSelect')?.value || 2);
        live.setAttribute('stroke', color);
        live.setAttribute('stroke-width', width * state.zoom);
        live.setAttribute('d', _draw.dString);
        svg.appendChild(live);
        _draw.livePath = live;
    });

    $('viewerScroll').addEventListener('mousemove', e => {
        if (!_draw.active || state.currentTool !== 'draw') return;
        const rect = _currentPageWrapper().getBoundingClientRect();
        const px   = (e.clientX - rect.left) / state.zoom;
        const py   = (e.clientY - rect.top)  / state.zoom;
        _draw.path.push([px, py]);
        // Construir path incrementalmente (solo agregar nuevo segmento)
        _draw.dString += ` L ${px * state.zoom} ${py * state.zoom}`;

        // Actualizar SVG con requestAnimationFrame para no bloquear
        if (!_draw.rafId) {
            _draw.rafId = requestAnimationFrame(() => {
                if (_draw.livePath) {
                    _draw.livePath.setAttribute('d', _draw.dString);
                }
                _draw.rafId = null;
            });
        }
    });

    document.addEventListener('mouseup', function() {
        if (!_draw.active || state.currentTool !== 'draw') return;
        _draw.active = false;
        if (_draw.rafId) { cancelAnimationFrame(_draw.rafId); _draw.rafId = null; }
        const svg = _currentPageWrapper()?.querySelector('.draw-svg');
        svg?.querySelector('#liveDraw')?.remove();
        _draw.livePath = null;

        if (_draw.path.length > 1) {
            const color  = $('annotColor')?.value || '#000000';
            const grosor = parseFloat($('drawWidthSelect')?.value || 2);
            if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];
            state.hayCambios = true;
            state.annotations[state.currentPage].push({
                type: 'draw', trazos: [_draw.path.slice()],
                color, grosor,
                x: Math.min(..._draw.path.map(p => p[0])),
                y: Math.min(..._draw.path.map(p => p[1]))
            });
            _redrawDrawAnnotations(state.currentPage);
        }
        _draw.path    = [];
        _draw.dString = '';
    });

    function _redrawDrawAnnotations(pageNum) {
        // Buscar el SVG de LA PÁGINA PEDIDA (con render perezoso puede repintarse
        // una página vecina que no es la actual; usar _currentPageWrapper aquí
        // pintaba los trazos en la página equivocada)
        const wrapper = document.getElementById('pageWrapper_' + pageNum) || _currentPageWrapper();
        const svg = wrapper?.querySelector('.draw-svg');
        if (!svg) return;
        svg.querySelectorAll('.draw-path').forEach(el => el.remove());
        (state.annotations[pageNum] || [])
            .filter(a => a.type === 'draw')
            .forEach(ann => {
                for (const trazo of (ann.trazos || [])) {
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    path.className.baseVal = 'draw-path';
                    path.setAttribute('fill',             'none');
                    path.setAttribute('stroke',           ann.color || '#000000');
                    path.setAttribute('stroke-width',     (ann.grosor || 2) * state.zoom);
                    path.setAttribute('stroke-linecap',   'round');
                    path.setAttribute('stroke-linejoin',  'round');
                    const d = trazo.map((p, i) => `${i===0?'M':'L'} ${p[0]*state.zoom} ${p[1]*state.zoom}`).join(' ');
                    path.setAttribute('d', d);
                    path.style.pointerEvents = 'auto';
                    path.addEventListener('dblclick', ev => {
                        ev.stopPropagation();
                        if (confirm('¿Eliminar este trazo?')) {
                            state.annotations[pageNum] =
                                (state.annotations[pageNum] || []).filter(a => a !== ann);
                            _redrawDrawAnnotations(pageNum);
                        }
                    });
                    // El borrador NO se maneja aquí: es una goma que recorta trozos
                    // (ver "BORRADOR"), no un borrado del trazo entero al tocarlo.
                    svg.appendChild(path);
                }
            });
    }

    // ==================== CONTROLES DE ANOTACIÓN (color / tamaño) ====================
    $('annotColor')?.addEventListener('change', e => {
        state.annotationColor = e.target.value;
    });
    $('textSizeSelect')?.addEventListener('change', e => {
        state.textSize = parseInt(e.target.value);
    });
    $('drawWidthSelect')?.addEventListener('change', e => {
        state.drawWidth = parseFloat(e.target.value);
    });

    // Firma
    $('toolAgregarFirma')?.addEventListener('click', () => {
        $('modalSignature').classList.remove('hidden');
        initSignatureCanvas();
    });

    $('btnCloseSignature').addEventListener('click', () => $('modalSignature').classList.add('hidden'));

    let signatureCtx;
    function initSignatureCanvas() {
        const sigCanvas = $('signatureCanvas');
        signatureCtx = sigCanvas.getContext('2d');
        signatureCtx.fillStyle = 'white';
        signatureCtx.fillRect(0, 0, sigCanvas.width, sigCanvas.height);
        signatureCtx.strokeStyle = state.signatureColor;
        signatureCtx.lineWidth = 2;
        signatureCtx.lineCap = 'round';

        let isDrawing = false;
        sigCanvas.addEventListener('mousedown', e => {
            isDrawing = true;
            signatureCtx.beginPath();
            signatureCtx.moveTo(e.offsetX, e.offsetY);
        });
        sigCanvas.addEventListener('mousemove', e => {
            if (!isDrawing) return;
            signatureCtx.lineTo(e.offsetX, e.offsetY);
            signatureCtx.stroke();
        });
        sigCanvas.addEventListener('mouseup', () => isDrawing = false);
        sigCanvas.addEventListener('mouseleave', () => isDrawing = false);
    }

    $('btnClearSignature').addEventListener('click', () => {
        const sigCanvas = $('signatureCanvas');
        signatureCtx.fillStyle = 'white';
        signatureCtx.fillRect(0, 0, sigCanvas.width, sigCanvas.height);
    });

    $('btnApplySignature').addEventListener('click', () => {
        const sigCanvas = $('signatureCanvas');
        const data = sigCanvas.toDataURL();

        if (!state.annotations[state.currentPage]) state.annotations[state.currentPage] = [];
        state.annotations[state.currentPage].push({
            type: 'signature',
            x: 50,
            y: 50,
            data
        });
        state.hayCambios = true;

        $('modalSignature').classList.add('hidden');
        renderAnnotations(state.currentPage);
    });

    document.querySelectorAll('#modalSignature .color-option').forEach(opt => {
        opt.addEventListener('click', () => {
            document.querySelectorAll('#modalSignature .color-option').forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            state.signatureColor = opt.dataset.color;
            if (signatureCtx) signatureCtx.strokeStyle = state.signatureColor;
        });
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _redrawDrawAnnotations, _recortarBanda });
};
