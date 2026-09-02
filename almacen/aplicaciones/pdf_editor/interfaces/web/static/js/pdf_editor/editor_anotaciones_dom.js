/* ============================================================
   Raíces Maquita — Editor PDF · anotaciones dom
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.anotaciones_dom = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, MIN_IMG_PT, SVGNS, _cssFuente, mostrarToast, seleccionarTexto, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const _aplicarEstiloForzado = (...a) => E._aplicarEstiloForzado(...a);   // parte texto_pdf
    const _pintarFormaSVG = (...a) => E._pintarFormaSVG(...a);   // parte anotar_formas
    const _reabrirEdicion = (...a) => E._reabrirEdicion(...a);   // parte texto_pdf
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    // ==================== __ANOTACIONES_DOM__ ====================
    /** Pone en la anotación una ✕ que aparece al pasar el ratón por encima y la borra
     *  de UN SOLO CLIC.
     *
     *  Por qué una ✕ y no un clic directo encima: las anotaciones se arrastran para
     *  moverlas, y al soltar el navegador dispara también un `click`. Con el borrado en
     *  el clic directo, mover una anotación la haría desaparecer. La ✕ es un solo clic
     *  y no se pisa con el arrastre.
     *
     *  No pregunta «¿seguro?»: preguntar convierte un clic en dos, que es justo lo que
     *  se quería quitar. La red está debajo — queda registrado para Ctrl+Z. */
    function _ponerBotonEliminar(el, ann) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'annot-eliminar';
        boton.title = 'Eliminar (Ctrl+Z lo devuelve)';
        boton.textContent = '✕';
        boton.style.cssText = 'position:absolute;top:-10px;right:-10px;display:none;z-index:9;' +
            'width:20px;height:20px;padding:0;line-height:18px;text-align:center;' +
            'border:1px solid #fff;border-radius:50%;background:#dc2626;color:#fff;' +
            'font-size:12px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.4);';

        // Que agarrar la ✕ no arrastre la anotación ni dispare el borrado por doble clic.
        boton.addEventListener('mousedown', ev => { ev.preventDefault(); ev.stopPropagation(); });
        boton.addEventListener('dblclick', ev => ev.stopPropagation());
        boton.addEventListener('click', ev => {
            ev.preventDefault();
            ev.stopPropagation();
            const envoltorio = el.closest('.page-wrapper');
            const pagina = envoltorio ? parseInt(envoltorio.dataset.page) : state.currentPage;
            const lista = state.annotations[pagina] || [];
            const i = lista.indexOf(ann);
            if (i < 0) return;
            // Antes de quitarla, foto para poder deshacer.
            window.PDFHistorial?.registrarAnotaciones(pagina, lista, 'eliminar la anotación');
            lista.splice(i, 1);
            state.hayCambios = true;
            renderAnnotations(pagina);
        });

        el.addEventListener('mouseenter', () => { boton.style.display = 'block'; });
        el.addEventListener('mouseleave', () => { boton.style.display = 'none'; });
        el.appendChild(boton);
    }

    function createAnnotationElement(ann, idx) {
        const el = document.createElement('div');
        el.className = 'annotation annotation-' + ann.type;
        el.style.left = (ann.x * state.zoom) + 'px';
        el.style.top = (ann.y * state.zoom) + 'px';

        switch (ann.type) {
            case 'highlight':
                el.style.width  = (ann.width  * state.zoom) + 'px';
                el.style.height = (ann.height * state.zoom) + 'px';
                if (ann.color && ann.color !== '#FFE500') {
                    // color personalizado con opacidad
                    const hex = ann.color.replace('#','');
                    const r=parseInt(hex.substr(0,2),16), g=parseInt(hex.substr(2,2),16), b=parseInt(hex.substr(4,2),16);
                    el.style.background = `rgba(${r},${g},${b},0.4)`;
                }
                break;
            case 'underline':
                el.style.width  = (ann.width  * state.zoom) + 'px';
                el.style.height = (ann.height * state.zoom) + 'px';
                el.style.borderBottomColor = ann.color || '#1473e6';
                break;
            case 'strikeout':
                el.style.width  = (ann.width  * state.zoom) + 'px';
                el.style.height = (ann.height * state.zoom) + 'px';
                el.style.color  = ann.color || '#dc2626';
                break;
            // Línea del PDF reescrita con el doble clic: se pinta el rectángulo del
            // color del fondo (tapa el texto original) y encima el texto nuevo
            case 'edicion': {
                _aplicarEstiloForzado(el, {
                    width: (ann.width  * state.zoom) + 'px',
                    height: (ann.height * state.zoom) + 'px',
                    background: ann.fondo || '#ffffff',
                    color: ann.color || '#000000',
                    'font-size': (ann.size * state.zoom) + 'px',
                    'font-family': _cssFuente(ann),
                    'font-weight': ann.negrita ? '700' : '400',
                    'font-style': ann.cursiva ? 'italic' : 'normal',
                    display: 'flex',
                    'align-items': 'center',
                    'white-space': 'pre',
                    overflow: 'hidden',
                    cursor: 'text'
                });
                el.textContent = ann.text || '';
                // Mientras el servidor no lo aplique con la fuente real del documento,
                // el parche es PROVISIONAL: se marca para que nadie lo confunda con el
                // resultado final (en pantalla lleva una fuente aproximada).
                el.classList.add('provisional');
                el.title = 'Cambio en curso — se está aplicando con la letra del documento';
                // volver a editarlo: doble clic sobre el propio parche
                el.addEventListener('dblclick', ev => {
                    ev.stopPropagation();
                    if (!E.enModoEdicion()) return;   // sin la herramienta activa, no se edita
                    _reabrirEdicion(ann, state.currentPage, el);
                });
                break;
            }
            case 'text':
                el.textContent = ann.text;
                el.style.fontSize = (ann.size * state.zoom) + 'px';
                el.style.color = ann.color;
                el.style.fontFamily = _cssFuente(ann);
                el.style.fontWeight = ann.negrita ? '700' : '400';
                el.style.fontStyle  = ann.cursiva ? 'italic' : 'normal';
                // clic = seleccionar (activa el panel de propiedades del banner izquierdo)
                el.addEventListener('click', ev => {
                    ev.stopPropagation();
                    seleccionarTexto(ann, el);
                });
                // doble clic = editar en línea
                el.addEventListener('dblclick', ev => {
                    ev.stopPropagation();
                    const editor = document.createElement('div');
                    editor.className = 'inline-text-editor';
                    editor.contentEditable = 'true';
                    editor.textContent = ann.text;
                    editor.style.left     = el.style.left;
                    editor.style.top      = el.style.top;
                    editor.style.fontSize = el.style.fontSize;
                    editor.style.color    = ann.color;
                    editor.style.fontFamily = _cssFuente(ann);
                    editor.style.fontWeight = ann.negrita ? '700' : '400';
                    editor.style.fontStyle  = ann.cursiva ? 'italic' : 'normal';
                    el.replaceWith(editor);
                    editor.focus();
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(editor);
                    sel.removeAllRanges(); sel.addRange(range);
                    const commit = () => {
                        const txt = editor.textContent.trim();
                        if (txt) { ann.text = txt; ann.size = parseInt(editor.style.fontSize) || ann.size; }
                        renderAnnotations(state.currentPage);
                    };
                    editor.addEventListener('blur', commit);
                    editor.addEventListener('keydown', e2 => {
                        if (e2.key === 'Escape') renderAnnotations(state.currentPage);
                        if (e2.key === 'Enter' && !e2.shiftKey) { e2.preventDefault(); commit(); }
                    });
                    return; // omitir handler de dblclick del padre
                });
                // Si este texto/enlace era el seleccionado, reenganchar el panel de
                // propiedades a este nodo nuevo (la capa se recrea en cada render)
                const selAct = E.textoSel();
                if (selAct && selAct.ann === ann) {
                    selAct.el = el;
                    el.classList.add('seleccionado');
                }
                break;
            case 'stamp': {
                // Sello de "Rellena y firma" (✓ ✗ ● ▢ —): vectorial, arrastrable,
                // doble clic elimina; al descargar se hornea como vectores (sin fuentes)
                const s = (ann.size || 22) * state.zoom;
                const sw = ann.subtipo === 'linea' ? s * 3 : s;
                const sh = ann.subtipo === 'linea' ? Math.max(8, s / 3) : s;
                const col = ann.color || '#111111';
                const SVGS = {
                    check:  '<polyline points="15,55 40,80 85,20" fill="none" stroke="' + col + '" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>',
                    equis:  '<line x1="20" y1="20" x2="80" y2="80" stroke="' + col + '" stroke-width="12" stroke-linecap="round"/><line x1="80" y1="20" x2="20" y2="80" stroke="' + col + '" stroke-width="12" stroke-linecap="round"/>',
                    punto:  '<circle cx="50" cy="50" r="30" fill="' + col + '"/>',
                    cuadro: '<rect x="12" y="12" width="76" height="76" fill="none" stroke="' + col + '" stroke-width="8"/>',
                    linea:  '<line x1="4" y1="50" x2="96" y2="50" stroke="' + col + '" stroke-width="14" stroke-linecap="round"/>'
                };
                el.style.width = sw + 'px';
                el.style.height = sh + 'px';
                el.innerHTML = '<svg viewBox="0 0 100 100" preserveAspectRatio="none" width="100%" height="100%" style="display:block;">' + (SVGS[ann.subtipo] || SVGS.check) + '</svg>';
                el.title = 'Sello — arrastra para mover, doble clic para eliminar';
                el.addEventListener('dblclick', ev => {
                    ev.stopPropagation();
                    const pw = el.closest('.page-wrapper');
                    const pag = pw ? parseInt(pw.dataset.page) : state.currentPage;
                    const lista = state.annotations[pag] || [];
                    const i = lista.indexOf(ann);
                    if (i >= 0) lista.splice(i, 1);
                    state.hayCambios = true;
                    renderAnnotations(pag);
                });
                break;
            }
            case 'note': {
                // La marca y el color los elige el usuario en el panel del comentario.
                // Los documentos de antes no traen esos datos: se les pone lo de siempre.
                const icono = E.iconoDeLaMarca ? E.iconoDeLaMarca(ann.marca) : 'bi-sticky-fill';
                const colorNota = ann.color || '#ffc107';
                // El tamaño y el grosor los pone el CSS (.annotation-note i); aquí solo el
                // color, que lo elige el usuario en la barra del comentario.
                el.innerHTML = '<i class="bi ' + icono + '" style="color:' + colorNota + ';"></i>';
                el.title = ann.text || 'Comentario (pulsa para leerlo o cambiarlo)';
                el.style.cursor = 'pointer';
                // Un clic abre la notita para leer o cambiar el texto. Antes salía el
                // cuadro gris del navegador, que no deja ver el documento detrás.
                el.addEventListener('click', ev => {
                    ev.stopPropagation();
                    if (!E.abrirNota) return;
                    const envoltorio = el.closest('.page-wrapper');
                    const pagina = envoltorio ? parseInt(envoltorio.dataset.page) : state.currentPage;
                    E.abrirNota(ann, el, valor => {
                        if (valor === null) return;
                        ann.text = valor;
                        renderAnnotations(pagina);
                    });
                });
                break;
            }
            case 'signature': {
                const img = document.createElement('img');
                img.src = ann.data;
                img.style.maxWidth = (150 * state.zoom) + 'px';
                img.draggable = false;
                el.appendChild(img);
                break;
            }
            case 'shape': {
                // Forma dibujada por arrastre: un SVG dentro del div de anotación,
                // así hereda el arrastre y el doble clic para eliminar.
                const w = Math.max(1, (ann.width  || 1) * state.zoom);
                const h = Math.max(1, (ann.height || 1) * state.zoom);
                el.style.width  = w + 'px';
                el.style.height = h + 'px';
                const svg = document.createElementNS(SVGNS, 'svg');
                svg.setAttribute('width', w);
                svg.setAttribute('height', h);
                svg.style.overflow = 'visible';
                svg.style.display  = 'block';
                _pintarFormaSVG(svg, ann.subtipo, w, h, ann.color || '#dc2626',
                                (ann.grosor || 2) * state.zoom,
                                ann.p1 || [0, 0], ann.p2 || [1, 1]);
                el.appendChild(svg);
                break;
            }
            case 'image': {
                // Imagen insertada por el usuario (herramienta "Imagen"): tamaño propio,
                // arrastrable y redimensionable con el tirador de la esquina.
                const img = document.createElement('img');
                img.src = ann.data;
                img.style.width = ((ann.width || 200) * state.zoom) + 'px';
                img.draggable = false;
                el.appendChild(img);
                el.title = 'Imagen — arrastra para mover, tira de la esquina para el tamaño, doble clic para eliminar';

                // Tirador de tamaño (esquina inferior derecha). Mantiene la proporcion:
                // deformar una foto nunca es lo que el usuario quiere.
                const tirador = document.createElement('div');
                tirador.className = 'img-resize';
                tirador.title = 'Arrastra para agrandar o achicar';
                tirador.style.cssText = 'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                    'background:#2563eb;border:2px solid #fff;border-radius:3px;cursor:nwse-resize;' +
                    'box-shadow:0 1px 4px rgba(0,0,0,.45);z-index:6;';
                el.appendChild(tirador);

                let redim = false, xIni = 0, wIni = 0, prop = 1;
                tirador.addEventListener('mousedown', ev => {
                    ev.preventDefault();
                    ev.stopPropagation();   // que no lo tome el arrastre de la imagen
                    redim = true;
                    xIni = ev.clientX;
                    wIni = ann.width || 200;
                    prop = (ann.width && ann.height) ? (ann.height / ann.width)
                         : (img.naturalWidth ? img.naturalHeight / img.naturalWidth : 1);
                    el.style.zIndex = '1000';
                });
                // Doble clic en el tirador NO debe borrar la imagen (el padre lo escucha)
                tirador.addEventListener('dblclick', ev => ev.stopPropagation());

                document.addEventListener('mousemove', ev => {
                    if (!redim) return;
                    // MIN_IMG_PT evita dejarla en un punto imposible de volver a agarrar
                    const w = Math.max(MIN_IMG_PT, wIni + (ev.clientX - xIni) / state.zoom);
                    ann.width  = w;
                    ann.height = w * prop;
                    img.style.width = (w * state.zoom) + 'px';
                });
                document.addEventListener('mouseup', () => {
                    if (!redim) return;
                    redim = false;
                    el.style.zIndex = '';
                    state.hayCambios = true;
                });

                // Barra de la imagen (girar / recortar). Se muestra al pasar el mouse.
                // Girar y recortar se HORNEAN en ann.data via canvas: así la descarga
                // del PDF no necesita saber nada de giros ni recortes.
                const barraImg = document.createElement('div');
                barraImg.style.cssText = 'position:absolute;top:-34px;left:0;display:none;gap:4px;' +
                    'background:#1f2937;border-radius:6px;padding:3px 5px;z-index:7;' +
                    'box-shadow:0 2px 8px rgba(0,0,0,.4);white-space:nowrap;';
                const _btnImg = (titulo, texto) => {
                    const b = document.createElement('button');
                    b.type = 'button';
                    b.title = titulo;
                    b.textContent = texto;
                    b.style.cssText = 'border:0;background:transparent;color:#fff;cursor:pointer;' +
                        'font-size:15px;line-height:1;padding:3px 6px;border-radius:4px;';
                    b.addEventListener('mouseenter', () => b.style.background = '#374151');
                    b.addEventListener('mouseleave', () => b.style.background = 'transparent');
                    // que los clics no arrastren la imagen ni disparen el borrado por doble clic
                    b.addEventListener('mousedown', ev => { ev.preventDefault(); ev.stopPropagation(); });
                    b.addEventListener('dblclick', ev => ev.stopPropagation());
                    barraImg.appendChild(b);
                    return b;
                };
                barraImg.addEventListener('mousedown', ev => ev.stopPropagation());
                el.appendChild(barraImg);
                el.addEventListener('mouseenter', () => { barraImg.style.display = 'flex'; });
                el.addEventListener('mouseleave', () => { if (!el.dataset.recortando) barraImg.style.display = 'none'; });

                // Rehace ann.data pasando la imagen por un canvas transformado
                const _hornearImg = (fn) => {
                    const im = new Image();
                    im.onload = () => {
                        const cv = document.createElement('canvas');
                        fn(cv, cv.getContext('2d'), im);
                        ann.data = cv.toDataURL('image/png');
                        state.hayCambios = true;
                        const pw = el.closest('.page-wrapper');
                        renderAnnotations(pw ? parseInt(pw.dataset.page) : state.currentPage);
                    };
                    im.onerror = () => mostrarToast('No se pudo procesar la imagen', 'error');
                    im.src = ann.data;
                };

                const _girar = (grados) => _hornearImg((cv, cx, im) => {
                    cv.width = im.naturalHeight;
                    cv.height = im.naturalWidth;
                    cx.translate(cv.width / 2, cv.height / 2);
                    cx.rotate(grados * Math.PI / 180);
                    cx.drawImage(im, -im.naturalWidth / 2, -im.naturalHeight / 2);
                    // el marco gira con la imagen: se intercambian ancho y alto
                    const w = ann.width || 200, h = ann.height || w;
                    ann.width = h; ann.height = w;
                });
                _btnImg('Girar a la izquierda', '\u21ba').addEventListener('click', ev => { ev.stopPropagation(); _girar(-90); });
                _btnImg('Girar a la derecha',  '\u21bb').addEventListener('click', ev => { ev.stopPropagation(); _girar(90); });

                // Recortar: se marca un rectángulo sobre la propia imagen y se confirma
                _btnImg('Recortar: marca con el mouse la zona que quieres conservar', '\u2702').addEventListener('click', ev => {
                    ev.stopPropagation();
                    if (el.dataset.recortando) return;
                    el.dataset.recortando = '1';
                    mostrarToast('Marca sobre la imagen la zona que quieres CONSERVAR (Esc cancela)', 'ok');
                    const velo = document.createElement('div');
                    velo.style.cssText = 'position:absolute;inset:0;cursor:crosshair;z-index:8;background:rgba(0,0,0,.25);';
                    const marco = document.createElement('div');
                    marco.style.cssText = 'position:absolute;display:none;border:2px dashed #fff;' +
                        'box-shadow:0 0 0 9999px rgba(0,0,0,.35);pointer-events:none;';
                    velo.appendChild(marco);
                    el.appendChild(velo);
                    let rx0 = 0, ry0 = 0, marcando = false, rect = null;
                    const _finRecorte = () => {
                        delete el.dataset.recortando;
                        velo.remove();
                        document.removeEventListener('keydown', alEsc, true);
                    };
                    const alEsc = (e) => {
                        if (e.key === 'Escape') { e.stopPropagation(); _finRecorte(); mostrarToast('Recorte cancelado', 'ok'); }
                    };
                    document.addEventListener('keydown', alEsc, true);
                    velo.addEventListener('mousedown', e => {
                        e.preventDefault(); e.stopPropagation();
                        const r = velo.getBoundingClientRect();
                        rx0 = e.clientX - r.left; ry0 = e.clientY - r.top;
                        marcando = true;
                        marco.style.display = 'block';
                    });
                    velo.addEventListener('mousemove', e => {
                        if (!marcando) return;
                        const r = velo.getBoundingClientRect();
                        const x = Math.min(Math.max(e.clientX - r.left, 0), r.width);
                        const y = Math.min(Math.max(e.clientY - r.top, 0), r.height);
                        rect = { x: Math.min(rx0, x), y: Math.min(ry0, y),
                                 w: Math.abs(x - rx0), h: Math.abs(y - ry0) };
                        marco.style.left = rect.x + 'px'; marco.style.top = rect.y + 'px';
                        marco.style.width = rect.w + 'px'; marco.style.height = rect.h + 'px';
                    });
                    velo.addEventListener('mouseup', e => {
                        e.stopPropagation();
                        if (!marcando) return;
                        marcando = false;
                        const r = velo.getBoundingClientRect();
                        if (!rect || rect.w < 8 || rect.h < 8) { _finRecorte(); mostrarToast('Zona muy pequenia: recorte cancelado', 'error'); return; }
                        if (!confirm('\u00bfRecortar la imagen y conservar solo la zona marcada?')) { _finRecorte(); return; }
                        const fx = rect.x / r.width, fy = rect.y / r.height;
                        const fw = rect.w / r.width, fh = rect.h / r.height;
                        _finRecorte();
                        _hornearImg((cv, cx, im) => {
                            const sx = fx * im.naturalWidth, sy = fy * im.naturalHeight;
                            const sw = Math.max(1, fw * im.naturalWidth), sh = Math.max(1, fh * im.naturalHeight);
                            cv.width = Math.round(sw); cv.height = Math.round(sh);
                            cx.drawImage(im, sx, sy, sw, sh, 0, 0, cv.width, cv.height);
                            // el marco en el papel se reduce en la misma proporcion y la
                            // esquina recortada se queda donde estaba la zona marcada
                            const w0 = ann.width || 200, h0 = ann.height || w0;
                            ann.x = (ann.x || 0) + fx * w0;
                            ann.y = (ann.y || 0) + fy * h0;
                            ann.width = Math.max(MIN_IMG_PT, w0 * fw);
                            ann.height = Math.max(MIN_IMG_PT, h0 * fh);
                        });
                    });
                });
                el.title = 'Imagen \u2014 arrastra para mover, esquina para el tama\u00f1o, pasa el mouse para girar o recortar, doble clic para eliminar';
                break;
            }
            case 'form': {
                // Campo de formulario: caja punteada azul con el nombre; se hornea como AcroForm al descargar
                el.style.width  = (ann.width * state.zoom) + 'px';
                el.style.height = (ann.height * state.zoom) + 'px';
                el.style.border = '2px dashed #1473e6';
                el.style.background = 'rgba(20,115,230,0.08)';
                el.style.borderRadius = '3px';
                el.style.display = 'flex';
                el.style.alignItems = 'center';
                el.style.fontSize = (10 * state.zoom) + 'px';
                el.style.color = '#1473e6';
                el.style.padding = '0 4px';
                el.style.overflow = 'hidden';
                el.style.whiteSpace = 'nowrap';
                const icono = ann.subtipo === 'checkbox' ? 'bi-check-square'
                            : (ann.subtipo === 'lista' ? 'bi-menu-button-wide' : 'bi-input-cursor-text');
                el.innerHTML = '<i class="bi ' + icono + '" style="margin-right:3px;"></i>' +
                               (ann.subtipo === 'checkbox' ? '' : ann.nombre);
                el.title = 'Campo ' + ann.subtipo + ' "' + ann.nombre + '" — doble clic para eliminar';
                el.addEventListener('dblclick', ev => {
                    ev.stopPropagation();
                    if (!confirm('¿Eliminar el campo "' + ann.nombre + '"?')) return;
                    // La página real se toma del DOM (la anotación puede no estar en la página actual)
                    const pw = el.closest('.page-wrapper');
                    const pag = pw ? parseInt(pw.dataset.page) : state.currentPage;
                    const lista = state.annotations[pag] || [];
                    const i = lista.indexOf(ann);
                    if (i >= 0) lista.splice(i, 1);
                    state.hayCambios = true;
                    renderAnnotations(pag);
                });
                break;
            }
        }

        // Modo "quitar resaltado": un clic sobre el resaltado (o subrayado/tachado)
        // lo elimina. Solo actua sobre esos tres tipos: el resto se ignora.
        el.addEventListener('click', e => {
            if (state.currentTool !== 'unhighlight') return;
            if (!['highlight', 'underline', 'strikeout'].includes(ann.type)) return;
            e.preventDefault();
            e.stopPropagation();
            const pag   = state.currentPage;
            const lista = state.annotations[pag] || [];
            const i = lista.indexOf(ann);
            if (i >= 0) {
                lista.splice(i, 1);
                state.hayCambios = true;
                renderAnnotations(pag);
            }
        });

        // Drag
        let isDragging = false, startX, startY;
        el.addEventListener('mousedown', e => {
            if (state.currentTool === 'unhighlight') return;  // en ese modo se borra, no se arrastra
            e.preventDefault();
            e.stopPropagation();
            isDragging = true;
            startX = e.clientX - el.offsetLeft;
            startY = e.clientY - el.offsetTop;
            el.style.zIndex = '1000';
        });

        document.addEventListener('mousemove', e => {
            if (!isDragging) return;
            el.style.left = (e.clientX - startX) + 'px';
            el.style.top = (e.clientY - startY) + 'px';
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                el.style.zIndex = '';
                ann.x = el.offsetLeft / state.zoom;
                ann.y = el.offsetTop / state.zoom;
            }
        });

        // Doble clic encima: también borra. Se conserva porque mucha gente ya lo tiene
        // aprendido; la forma recomendada es la ✕ de abajo, que es de un solo clic.
        //
        // OJO con a QUIÉN se le pone. Hay tipos que ya usan el doble clic para lo suyo
        // (un cuadro de texto lo usa para editarse, un sello y un campo para borrarse a
        // su manera) y los dos escuchadores cuelgan del MISMO elemento: `stopPropagation`
        // no evita que se ejecuten los dos, para eso haría falta `stopImmediatePropagation`.
        // Resultado hasta hoy: al hacer doble clic en un texto para editarlo, se abría el
        // editor Y saltaba la pregunta de eliminar. Se corrige dejando fuera esos tipos.
        const TIENEN_SU_DOBLE_CLIC = ['text', 'edicion', 'stamp', 'form'];
        if (!TIENEN_SU_DOBLE_CLIC.includes(ann.type)) el.addEventListener('dblclick', e => {
            e.stopPropagation();
            const envoltorio = el.closest('.page-wrapper');
            const pagina = envoltorio ? parseInt(envoltorio.dataset.page) : state.currentPage;
            const lista = state.annotations[pagina] || [];
            const i = lista.indexOf(ann);
            if (i < 0) return;
            window.PDFHistorial?.registrarAnotaciones(pagina, lista, 'eliminar la anotación');
            lista.splice(i, 1);
            state.hayCambios = true;
            renderAnnotations(pagina);
        });

        // La ✕ de un solo clic, en TODAS las anotaciones. El resaltado y compañía no la
        // llevan: son franjas pegadas al texto, se quitan pasando la goma por encima.
        if (!['highlight', 'underline', 'strikeout', 'draw', 'edicion'].includes(ann.type)) {
            _ponerBotonEliminar(el, ann);
        }

        return el;
    }

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { createAnnotationElement });
};
