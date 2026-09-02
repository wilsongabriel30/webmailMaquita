/* ============================================================
   Raíces Maquita — Editor PDF · texto pdf
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.texto_pdf = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, FUENTES_TEXTO, _apiParrafo, _cssFuente, _getPdfBlob, loadPDF, mostrarToast, renderAllPages, showLoading, state, updateNavButtons } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const _paginaTieneTexto = (...a) => E._paginaTieneTexto(...a);   // parte tablas_ocr
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    const renderSinglePage = (...a) => E.renderSinglePage(...a);   // parte render_vista
    // ==================== EDITAR EL TEXTO DEL PDF (DOBLE CLIC) ====================
    // Doble clic sobre una línea de texto del documento y se edita ahí mismo,
    // conservando letra, tamaño y color. Como el texto original está "pintado"
    // dentro de la página, no se puede borrar de verdad: lo que se hace es TAPAR
    // esa línea con un rectángulo del color del fondo y escribir encima el texto
    // nuevo. Por eso se detectan del canvas los dos colores (fondo y letra): así
    // el parche también funciona sobre fondos de color, no solo sobre blanco.
    //
    // Limitaciones conocidas (documentadas en el manual):
    //   - si detrás hay una foto o un degradado, el rectángulo se nota;
    //   - la tipografía nueva es la estándar más parecida (Helvetica/Times/Courier).

    // ¿Dos fragmentos comparten tipografía? Se compara la fuente REAL del PDF; si no
    // se conoce, se cae en lo que diga el CSS de la capa de texto.
    function _mismoEstilo(a, b) {
        const fa = a.dataset.fuentePdf, fb = b.dataset.fuentePdf;
        const ta = Math.round(parseFloat(a.dataset.tamPt) || 0);
        const tb = Math.round(parseFloat(b.dataset.tamPt) || 0);
        if (fa && fb) return fa === fb && ta === tb;
        const ea = getComputedStyle(a), eb = getComputedStyle(b);
        return ea.fontFamily === eb.fontFamily && ea.fontSize === eb.fontSize;
    }

    // Fragmentos que se van a editar juntos: los de la MISMA línea visual y, dentro
    // de ella, solo el bloque contiguo que comparte tipografía con el pulsado.
    //
    // Lo segundo es imprescindible: un renglón como "**AUTORA:** Ulloa Guillén…" son
    // dos fragmentos con fuentes distintas, y editarlo entero con un único estilo
    // cambiaba la letra de la parte que el usuario no había tocado.
    // - línea de un solo estilo -> se edita el renglón completo;
    // - línea con mezcla        -> solo el trozo del estilo pulsado.
    function _spansDeLaLinea(span) {
        const capa = span.parentElement;
        if (!capa) return { spans: [span], mixta: false };
        const r = span.getBoundingClientRect();
        const centro = r.top + r.height / 2;
        const linea = [...capa.querySelectorAll('span')].filter(s => {
            if (!s.textContent) return false;
            const b = s.getBoundingClientRect();
            if (!b.height || !b.width) return false;
            // misma línea = el centro vertical del pulsado cae dentro del otro
            return centro >= b.top && centro <= b.bottom;
        });
        linea.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
        if (!linea.length) return { spans: [span], mixta: false };

        const i = linea.indexOf(span);
        if (i < 0) return { spans: [span], mixta: false };
        let ini = i, fin = i;
        while (ini > 0 && _mismoEstilo(linea[ini - 1], span)) ini--;
        while (fin < linea.length - 1 && _mismoEstilo(linea[fin + 1], span)) fin++;
        const bloque = linea.slice(ini, fin + 1);
        // se recortan los espacios sueltos de los extremos: no aportan y agrandan el parche
        while (bloque.length > 1 && !bloque[0].textContent.trim()) bloque.shift();
        while (bloque.length > 1 && !bloque[bloque.length - 1].textContent.trim()) bloque.pop();
        return { spans: bloque, mixta: bloque.length < linea.length };
    }

    // Color de la letra (el píxel más oscuro) y del fondo (el más repetido) dentro
    // del recuadro, leídos del canvas ya renderizado de la página.
    function _coloresDelArea(canvas, x, y, w, h) {
        const fondoPorDefecto = '#ffffff', letraPorDefecto = '#000000';
        try {
            const ix = Math.max(0, Math.round(x)), iy = Math.max(0, Math.round(y));
            const iw = Math.min(canvas.width - ix, Math.round(w));
            const ih = Math.min(canvas.height - iy, Math.round(h));
            if (iw <= 0 || ih <= 0) return { fondo: fondoPorDefecto, letra: letraPorDefecto };
            const datos = canvas.getContext('2d', { willReadFrequently: true })
                                .getImageData(ix, iy, iw, ih).data;
            // 1) fondo = color más repetido del recuadro
            const cuenta = {}; const muestra = {};
            let fondoLuz = 255, fondoHex = fondoPorDefecto, maxFondo = 0;
            for (let i = 0; i < datos.length; i += 4) {
                const r = datos[i], g = datos[i + 1], b = datos[i + 2];
                const clave = (r >> 3) + ',' + (g >> 3) + ',' + (b >> 3);
                cuenta[clave] = (cuenta[clave] || 0) + 1;
                if (!muestra[clave]) muestra[clave] = [r, g, b];
                if (cuenta[clave] > maxFondo) {
                    maxFondo = cuenta[clave];
                    fondoHex = _rgbAHex(r, g, b);
                    fondoLuz = 0.299 * r + 0.587 * g + 0.114 * b;
                }
            }
            // 2) letra = el tono MÁS FRECUENTE entre los píxeles claramente más oscuros
            //    que el fondo. Coger el píxel más oscuro a secas daba un color falso:
            //    los bordes suavizados (antialias) siempre traen algún píxel casi negro.
            let mejor = 0, letraHex = null;
            for (const clave in cuenta) {
                const [r, g, b] = muestra[clave];
                const luz = 0.299 * r + 0.587 * g + 0.114 * b;
                if (fondoLuz - luz < 60) continue;          // no es tinta, es fondo
                if (cuenta[clave] > mejor) { mejor = cuenta[clave]; letraHex = _rgbAHex(r, g, b); }
            }
            return { fondo: fondoHex || fondoPorDefecto, letra: letraHex || letraPorDefecto };
        } catch (e) {
            // canvas "manchado" u otra restricción: se asume papel blanco con tinta negra
            return { fondo: fondoPorDefecto, letra: letraPorDefecto };
        }
    }

    function _rgbAHex(r, g, b) {
        return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
    }

    // Familia estándar equivalente a la que usa el PDF
    function _familiaEstandar(fontFamily) {
        const f = (fontFamily || '').toLowerCase();
        if (f.includes('mono') || f.includes('courier')) return 'courier';
        if (f.includes('serif') && !f.includes('sans')) return 'times';
        if (f.includes('times') || f.includes('georgia') || f.includes('roman')) return 'times';
        return 'helvetica';
    }

    // Estilo real a partir del NOMBRE de la fuente incrustada en el PDF
    // (p. ej. "BAAAAA+LiberationSerif-Italic", "ABCDEE+TimesNewRoman,Bold").
    // Es la única vía fiable: el CSS de la capa de texto no distingue negrita ni cursiva.
    function _estiloDesdeNombrePdf(nombre) {
        if (!nombre) return null;
        const n = nombre.toLowerCase();
        let fuente = 'helvetica';
        if (/mono|courier|consol/.test(n)) fuente = 'courier';
        else if (/times|serif|roman|georgia|garamond|cambria|book|minion|palatino/.test(n) && !/sans/.test(n)) fuente = 'times';
        return {
            fuente,
            negrita: /bold|black|heavy|semib|demi/.test(n),
            cursiva: /italic|oblique/.test(n)
        };
    }

    // Los estilos del editor van con prioridad "important": la hoja general de Raíces
    // define reglas propias para los <input> (color, fuente, tamaño) que si no
    // pisaban el aspecto de la caja y el texto salía con OTRA letra y OTRO color.
    function _aplicarEstiloForzado(el, props) {
        for (const [k, v] of Object.entries(props)) el.style.setProperty(k, v, 'important');
    }

    let _edicionAbierta = null;   // { caja, ann, pag } mientras se está editando
    // La edición de texto NO está siempre activa: se enciende al pulsar la herramienta
    // "Digitalizar y OCR". Mientras esté apagada, el doble clic sobre el documento se
    // comporta como siempre (seleccionar una palabra) y no abre nada.
    let _modoEdicionTexto = false;
    // Otras partes (elegir herramienta, y las anotaciones al pintarse) necesitan saber
    // si el modo de edición de texto está activo. Un `let` no se comparte entre
    // archivos: se publica por esta funcioncita, que siempre lee el valor de ahora.
    E.enModoEdicion = () => _modoEdicionTexto;
    let _btnSeleccion = null;        // botón "Cambiar este texto" de la selección múltiple

    function _activarModoEdicionTexto(activo) {
        _modoEdicionTexto = activo;
        document.body.classList.toggle('modo-editar-texto', activo);
        const aviso = $('avisoModoEdicion');
        if (aviso) aviso.classList.toggle('hidden', !activo);
        if (!activo) _ocultarBotonSeleccion();
        if (!activo && _edicionAbierta) _cerrarEdicionTexto(true);
    }
    let _avisoMixtaDado = false;  // el aviso de "línea con estilos mezclados" se da una vez

    function _cerrarEdicionTexto(guardar) {
        if (!_edicionAbierta) return;
        // Las reediciones (_reabrirEdicion) traen su propio cierre: actualizan la
        // anotación existente en vez de crear una nueva
        if (_edicionAbierta.propia) { const f = _edicionAbierta.propia; _edicionAbierta = null; f(guardar); return; }
        const { caja, datos, pag } = _edicionAbierta;
        const nuevo = caja.value;
        _edicionAbierta = null;
        // El cierre puede llegar dos veces (Enter y, acto seguido, blur) y la capa
        // de anotaciones se vacía entera al re-renderizar: quitar la caja sin dar por
        // hecho que sigue colgando de su padre
        if (caja.isConnected) caja.remove();
        if (!guardar || nuevo === datos.textoOriginal) return;
        if (!nuevo.trim()) {
            // texto vaciado: se tapa la línea y no se escribe nada (equivale a borrarla)
            mostrarToast('Línea borrada del documento.', 'success');
        }
        if (!state.annotations[pag]) state.annotations[pag] = [];
        state.annotations[pag].push({
            type: 'edicion',
            x: datos.x, y: datos.y, width: datos.width, height: datos.height,
            text: nuevo,
            size: datos.size,
            fuente: datos.fuente,
            negrita: datos.negrita,
            cursiva: datos.cursiva,
            color: datos.color,
            fondo: datos.fondo
        });
        state.hayCambios = true;
        renderAnnotations(pag);
        _programarAplicarEdiciones();
    }

    function _abrirEdicionTexto(span, pagina, cx, cy, seleccion) {
        if (_edicionAbierta) _cerrarEdicionTexto(true);
        _ocultarBotonSeleccion();
        const wrapper = document.getElementById('pageWrapper_' + pagina);
        const canvas = wrapper ? wrapper.querySelector('canvas') : null;
        const capaAnot = wrapper ? wrapper.querySelector('.annotation-layer') : null;
        if (!wrapper || !capaAnot) return;

        // Lo que se edita es la PALABRA sobre la que se hizo doble clic: el navegador
        // ya la deja seleccionada, así que su recuadro es exacto. Cambiar la línea
        // entera obligaba a reescribirla y con ello se perdía el reparto original.
        // ---- Qué se va a editar: LA PALABRA del doble clic ----
        // El navegador ya la marca, pero su API es inconsistente (Chrome devuelve el
        // texto de la palabra y a la vez isCollapsed=true), así que no basta con
        // fiarse de la selección: se localiza el nodo de texto y se expande desde el
        // punto pulsado hasta los espacios que lo rodean. Es determinista.
        // Si viene de la selección con el ratón (varias palabras), ya está resuelto:
        // el recuadro y el texto son los del trozo que el usuario marcó.
        let palabra = seleccion ? { rect: seleccion.rect, texto: seleccion.texto } : null;
        const sel = palabra ? null : window.getSelection();
        let nodoTexto = null, desde = 0, hasta = 0;
        if (sel && sel.rangeCount) {
            const rg = sel.getRangeAt(0);
            if (rg.startContainer && rg.startContainer.nodeType === 3 && span.contains(rg.startContainer)) {
                nodoTexto = rg.startContainer; desde = rg.startOffset; hasta = rg.endOffset;
            }
        }
        if (!palabra && !nodoTexto && span.firstChild && span.firstChild.nodeType === 3) {
            // sin selección utilizable: se estima el carácter por la posición del clic
            nodoTexto = span.firstChild;
            const b = span.getBoundingClientRect();
            const frac = b.width ? Math.min(1, Math.max(0, ((cx || b.left) - b.left) / b.width)) : 0;
            desde = hasta = Math.round(frac * (nodoTexto.textContent || '').length);
        }
        if (nodoTexto) {
            const txt = nodoTexto.textContent || '';
            let a = Math.min(desde, txt.length), b2 = Math.min(Math.max(hasta, desde), txt.length);
            while (a > 0 && !/\s/.test(txt[a - 1])) a--;
            while (b2 < txt.length && !/\s/.test(txt[b2])) b2++;
            // pdf.js parte el texto donde el PDF cambia el espaciado: los importes de
            // un PDF de Word llegan como "2" ".2" "00" y el doble clic solo cogía un
            // pedazo (el usuario "no podía editar los valores"). Se reconstruye la
            // palabra tal como se ve, cruzando los trozos pegados. Ver edicion_palabra.js
            const completa = window.PDFEdicionPalabra
                ? window.PDFEdicionPalabra.expandir(nodoTexto, a, b2) : null;
            if (completa) palabra = completa;
            if (!palabra && b2 > a && txt.slice(a, b2).trim()) {
                const r = document.createRange();
                r.setStart(nodoTexto, a); r.setEnd(nodoTexto, b2);
                const rect = r.getBoundingClientRect();
                if (rect.width > 2) palabra = { rect, texto: txt.slice(a, b2) };
            }
        }
        const { spans, mixta } = _spansDeLaLinea(span);
        if (mixta && !palabra && !_avisoMixtaDado) {
            _avisoMixtaDado = true;
            mostrarToast('Esta línea mezcla estilos: se edita solo el trozo que tiene la misma letra, para no cambiar el resto.', 'info');
        }
        const rw = wrapper.getBoundingClientRect();
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        spans.forEach(s => {
            const b = s.getBoundingClientRect();
            x0 = Math.min(x0, b.left); y0 = Math.min(y0, b.top);
            x1 = Math.max(x1, b.right); y1 = Math.max(y1, b.bottom);
        });
        let texto = spans.map(s => s.textContent).join('');
        if (palabra && palabra.rect.width > 2) {
            // recuadro y contenido de la palabra, no de todo el renglón
            x0 = palabra.rect.left; y0 = palabra.rect.top;
            x1 = palabra.rect.right; y1 = palabra.rect.bottom;
            texto = palabra.texto;
        }
        if (!texto.trim()) return;

        const est = getComputedStyle(span);
        // Tamaño: el real del PDF (en puntos) si pdf.js lo dio; si no, el del CSS
        const tamPt = parseFloat(span.dataset.tamPt) || (parseFloat(est.fontSize) || 12) / state.zoom;
        const tamPx = tamPt * state.zoom;
        // Estilo: preferimos el nombre de la fuente incrustada; la heurística CSS es el respaldo
        const estilo = _estiloDesdeNombrePdf(span.dataset.fuentePdf) || {
            fuente: _familiaEstandar(est.fontFamily),
            negrita: parseInt(est.fontWeight) >= 600,
            cursiva: est.fontStyle === 'italic'
        };
        // Margen mínimo: el recuadro NO debe rozar los renglones vecinos. Con
        // márgenes generosos, la redacción del servidor se comía palabras de las
        // líneas de arriba y abajo (el "se cambia totalmente la vista del PDF").
        const margen = Math.max(1, tamPx * 0.06);
        const izq = x0 - rw.left, arr = y0 - rw.top - margen / 2;
        const ancho = (x1 - x0) + margen, alto = (y1 - y0) + margen;

        // Nota: aquí no se leen los colores de la página renderizada; se asume papel
        // blanco con tinta negra. Es el mismo resultado que daba antes (la variable
        // `canvas` de la que se leía nunca llegaba a tener valor).
        const colores = { fondo: '#ffffff', letra: '#000000' };

        const datos = {
            textoOriginal: texto,
            x: izq / state.zoom, y: arr / state.zoom,
            width: ancho / state.zoom, height: alto / state.zoom,
            size: tamPt,
            // línea base del texto original: es lo que mantiene el renglón en su sitio
            baseY: (y1 - rw.top) / state.zoom,
            fuente: estilo.fuente,
            negrita: estilo.negrita,
            cursiva: estilo.cursiva,
            color: colores.letra,
            fondo: colores.fondo
        };

        // Caja de edición sobre la propia línea, con su misma letra y tamaño
        const caja = document.createElement('input');
        caja.type = 'text';
        // Sin esto Chrome ofrece contraseñas y direcciones guardadas encima del PDF
        caja.autocomplete = 'off';
        caja.setAttribute('autocorrect', 'off');
        caja.setAttribute('autocapitalize', 'off');
        caja.setAttribute('spellcheck', 'false');
        caja.name = 'edicion-pdf-' + Math.random().toString(36).slice(2);
        caja.value = texto;
        caja.className = 'edicion-texto-pdf';
        _aplicarEstiloForzado(caja, {
            left: izq + 'px',
            top: arr + 'px',
            width: Math.max(60, ancho) + 'px',
            height: alto + 'px',
            'font-size': tamPx + 'px',
            'font-family': (FUENTES_TEXTO[datos.fuente] || FUENTES_TEXTO.helvetica).css,
            'font-weight': datos.negrita ? '700' : '400',
            'font-style': datos.cursiva ? 'italic' : 'normal',
            color: datos.color,
            background: datos.fondo
        });
        capaAnot.classList.add('active');
        capaAnot.appendChild(caja);
        caja.focus();
        caja.setSelectionRange(0, caja.value.length);

        _edicionAbierta = { caja, datos, pag: pagina };

        caja.addEventListener('keydown', e => {
            e.stopPropagation();
            if (e.key === 'Enter')  { e.preventDefault(); _cerrarEdicionTexto(true); }
            if (e.key === 'Escape') { e.preventDefault(); _cerrarEdicionTexto(false); }
        });
        caja.addEventListener('blur', () => _cerrarEdicionTexto(true));
        caja.addEventListener('dblclick', e => e.stopPropagation());
    }

    // ---- Aplicar las ediciones en el servidor, con la fuente ORIGINAL del PDF ----
    // El navegador solo puede escribir con las 14 fuentes estándar; por eso el texto
    // reescrito "cambiaba de letra". PyMuPDF (servidor) sí puede: borra de verdad el
    // texto viejo y escribe el nuevo con la MISMA fuente incrustada del documento.
    // Al volver, el visor recarga el PDF ya corregido: lo que se ve en pantalla es
    // exactamente lo que se va a descargar.
    let _tempoAplicar = null;

    function _programarAplicarEdiciones() {
        clearTimeout(_tempoAplicar);
        // Espera por si el usuario encadena varias correcciones seguidas. Eran 400 ms,
        // pero desde que el modo se apaga solo al aplicar (v1.9.36) ya no se encadenan:
        // es tiempo muerto que el usuario ve como lentitud. 150 ms basta para agrupar
        // un doble envío accidental.
        _tempoAplicar = setTimeout(_aplicarEdicionesEnServidor, 150);
    }

    // Mete el PDF ya corregido en el visor SIN mover la vista: mismo zoom, mismas
    // columnas, mismo scroll y misma página; solo se vuelve a pintar la página tocada.
    //
    // Antes se llamaba a loadPDF(), que reconstruye el documento entero: en una tesis
    // de 130 páginas eso significaba rehacer 130 contenedores, volver a la página 1 y
    // saltar con scrollIntoView al principio del renglón editado. Ese era el salto del
    // que se quejaba el usuario. Cambiar texto no altera el número ni el tamaño de las
    // páginas, así que los contenedores que ya están en pantalla siguen siendo válidos.
    async function _recargarPdfEnSitio(arrayBuffer, paginas) {
        const viewer = $('viewerScroll');
        const sTop  = viewer ? viewer.scrollTop  : 0;
        const sLeft = viewer ? viewer.scrollLeft : 0;
        const pagAntes   = state.currentPage;
        const totalAntes = state.totalPages;

        state.pdfBytes = new Uint8Array(arrayBuffer.slice(0));
        state.pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer.slice(0) }).promise;
        state.totalPages = state.pdfDoc.numPages;

        if (state.totalPages !== totalAntes) {
            // No debería ocurrir editando texto; si ocurre, se reconstruye todo
            await renderAllPages();
            document.getElementById('pageWrapper_' + Math.min(pagAntes, state.totalPages))
                ?.scrollIntoView({ block: 'start' });
            return;
        }

        for (const p of paginas) {
            if (!document.getElementById('pageWrapper_' + p)) continue;
            state.renderedPages[p] = false;
            await renderSinglePage(p);
        }
        // Las demás páginas conservan su canvas: su contenido no ha cambiado (la edición
        // solo toca una página), y repintarlas es justo lo que producía el parpadeo.
        if (viewer) { viewer.scrollTop = sTop; viewer.scrollLeft = sLeft; }
        state.currentPage = pagAntes;
        $('currentPage').textContent = pagAntes;
        updateNavButtons();
    }

    async function _aplicarEdicionesEnServidor() {
        if (!state.pdfDoc || _edicionAbierta) return;
        const ediciones = [];
        for (const [pag, lista] of Object.entries(state.annotations || {})) {
            (lista || []).forEach(a => {
                if (a.type !== 'edicion' || a.aplicada) return;
                ediciones.push({
                    pagina: parseInt(pag), x: a.x, y: a.y,
                    ancho: a.width, alto: a.height, texto: a.text || '', tam: a.size
                });
            });
        }
        if (!ediciones.length) return;

        showLoading(true);
        try {
            const formData = new FormData();
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
            formData.append('ediciones', JSON.stringify(ediciones));
            const resp = await fetch('/api/pdf/operacion/reemplazar-texto',
                                     { method: 'POST', body: formData, credentials: 'same-origin' });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.mensaje || 'Error ' + resp.status);
            }
            // El servidor informa con qué letra pudo escribir cada fragmento
            const detalle = (resp.headers.get('X-Fuentes-Usadas') || '').split(',').filter(Boolean);
            const buf = await resp.arrayBuffer();
            // las ediciones ya viven DENTRO del PDF: fuera los parches de pantalla
            const tocadas = new Set(ediciones.map(e => e.pagina));
            for (const [pag, lista] of Object.entries(state.annotations || {})) {
                if (!lista) continue;
                for (let i = lista.length - 1; i >= 0; i--) {
                    if (lista[i].type === 'edicion') { lista.splice(i, 1); tocadas.add(parseInt(pag)); }
                }
            }
            await _recargarPdfEnSitio(buf, [...tocadas]);
            state.hayCambios = true;
            const conOriginal = detalle.filter(d => d.startsWith('original:')).length;
            const equivalentes = detalle.filter(d => d.startsWith('equivalente:'));
            // El renglón se recoloca solo si el resultado puede quedar igual de bien: si
            // no cabía o el resto del renglón no se podía reescribir con su misma letra,
            // se deja como estaba y el texto nuevo puede pisar la palabra siguiente. Vale
            // más decirlo que dejar que el usuario lo descubra mirando.
            const sinCorrer = detalle.some(d => d.includes('no cabe re-fluido'));
            const aviso = sinCorrer
                ? ' Ojo: el texto nuevo no cabía en el renglón, así que puede quedar pegado a la palabra siguiente.'
                : '';
            const tipo = sinCorrer ? 'warn' : 'success';
            if (equivalentes.length) {
                // Pasa cuando el PDF trae la fuente recortada (solo los caracteres que ya
                // usaba). Se escribe con la equivalente instalada, prácticamente idéntica.
                // el detalle viene como "equivalente:Nombre (doc: FuenteOriginal)"
                const nombre = (equivalentes[0].slice('equivalente:'.length).split('(doc:')[0] || '').trim();
                mostrarToast('Cambio aplicado con ' + nombre + ', la letra equivalente a la del documento ' +
                             '(el PDF no traía la suya completa).' + aviso, tipo);
            } else if (conOriginal) {
                mostrarToast('Cambio aplicado con la letra original del documento.' + aviso, tipo);
            } else {
                mostrarToast('Cambio aplicado.' + aviso, tipo);
            }
            // La edición SIGUE ENCENDIDA: el usuario cambia varias palabras seguidas y
            // tener que volver a pulsar "Digitalizar y OCR" después de cada una era una
            // molestia. Se apaga cuando él lo diga: con Esc o eligiendo otra herramienta.
            // (Lo que nunca hace es encenderse sola: para eso sigue haciendo falta la
            // herramienta, que es lo que se pidió en la v1.9.36.)
        } catch (e) {
            // Si el servidor no puede, se conserva el parche dibujado en el editor:
            // el cambio no se pierde, solo sale con la fuente estándar más parecida.
            mostrarToast('El cambio se ve en pantalla, pero no se pudo aplicar con la letra original: ' + e.message, 'warn');
        } finally {
            showLoading(false);
        }
    }

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && _modoEdicionTexto && !_edicionAbierta) {
            _activarModoEdicionTexto(false);
            mostrarToast('Edición de texto desactivada.', 'info');
        }
    });

    // Volver a editar una línea ya cambiada: se reutiliza la misma caja, sobre el
    // parche existente, y al confirmar se actualiza esa anotación en vez de crear otra.
    function _reabrirEdicion(ann, pagina, el) {
        if (_edicionAbierta) _cerrarEdicionTexto(true);
        const wrapper = document.getElementById('pageWrapper_' + pagina);
        const capaAnot = wrapper ? wrapper.querySelector('.annotation-layer') : null;
        if (!capaAnot) return;

        const caja = document.createElement('input');
        caja.type = 'text';
        caja.autocomplete = 'off';
        caja.setAttribute('spellcheck', 'false');
        caja.name = 'edicion-pdf-' + Math.random().toString(36).slice(2);
        caja.value = ann.text || '';
        caja.className = 'edicion-texto-pdf';
        _aplicarEstiloForzado(caja, {
            left: (ann.x * state.zoom) + 'px',
            top: (ann.y * state.zoom) + 'px',
            width: Math.max(60, ann.width * state.zoom) + 'px',
            height: (ann.height * state.zoom) + 'px',
            'font-size': (ann.size * state.zoom) + 'px',
            'font-family': _cssFuente(ann),
            'font-weight': ann.negrita ? '700' : '400',
            'font-style': ann.cursiva ? 'italic' : 'normal',
            color: ann.color,
            background: ann.fondo || '#ffffff'
        });
        capaAnot.classList.add('active');
        capaAnot.appendChild(caja);
        caja.focus();
        caja.setSelectionRange(0, caja.value.length);

        let cerrado = false;
        const cerrar = guardar => {
            if (cerrado) return;      // Enter y blur pueden llegar los dos
            cerrado = true;
            const valor = caja.value;
            if (caja.isConnected) caja.remove();
            _edicionAbierta = null;
            if (guardar && valor !== ann.text) {
                ann.text = valor;
                state.hayCambios = true;
                renderAnnotations(pagina);
                _programarAplicarEdiciones();
            }
        };
        _edicionAbierta = { caja, datos: { textoOriginal: ann.text }, pag: pagina, propia: cerrar };
        caja.addEventListener('keydown', e => {
            e.stopPropagation();
            if (e.key === 'Enter')  { e.preventDefault(); cerrar(true); }
            if (e.key === 'Escape') { e.preventDefault(); cerrar(false); }
        });
        caja.addEventListener('blur', () => cerrar(true));
    }

    // Span más cercano al punto donde se hizo doble clic, dentro de la misma página.
    // Hace falta porque el usuario casi nunca acierta encima de una letra: pincha en
    // el espacio entre palabras, en la sangría o entre dos renglones, y sin esto
    // "no pasaba nada" en media página.
    function _spanCercano(wrapper, cx, cy) {
        const capa = wrapper.querySelector('.textLayer');
        if (!capa) return null;
        // Se busca por renglón: primero el más cercano en vertical y, dentro de ese
        // renglón, el fragmento más cercano en horizontal. Da igual que el clic caiga
        // en el espacio entre palabras o al final de la línea: sigue siendo esa línea.
        let mejor = null, mejorDy = Infinity, mejorDx = Infinity;
        capa.querySelectorAll('span').forEach(s => {
            if (!(s.textContent || '').trim()) return;
            const b = s.getBoundingClientRect();
            if (!b.width || !b.height) return;
            const dy = Math.max(b.top - cy, 0, cy - b.bottom);
            const dx = Math.max(b.left - cx, 0, cx - b.right);
            if (dy < mejorDy - 0.5 || (Math.abs(dy - mejorDy) <= 0.5 && dx < mejorDx)) {
                mejorDy = dy; mejorDx = dx; mejor = s;
            }
        });
        if (!mejor) return null;
        // Se acepta si el clic cayó dentro del renglón o a menos de un renglón de él;
        // en horizontal no se exige nada: apuntar a una línea es apuntar a la línea.
        const alto = mejor.getBoundingClientRect().height || 16;
        return mejorDy <= alto ? mejor : null;
    }

    // Enganche: doble clic sobre el documento
    document.addEventListener('dblclick', e => {
        // Solo si el usuario encendió la edición con la herramienta
        if (!_modoEdicionTexto) return;
        // con el lápiz, la goma o las formas activos manda la herramienta
        if (['draw', 'erase', 'shape'].includes(state.currentTool)) return;
        // sobre una anotación propia (texto, imagen, sello…) no interviene
        if (e.target.closest('.annotation') && !e.target.closest('.annotation-edicion')) return;
        const wrapper = e.target.closest('.page-wrapper');
        if (!wrapper) return;

        const span = e.target.closest('.textLayer span') || _spanCercano(wrapper, e.clientX, e.clientY);
        const pag = parseInt(wrapper.dataset.page) || state.currentPage;

        // Por PÁRRAFO, no por palabra (pedido del usuario: «igualito que si
        // fuera un word»). Si ahí no hay un párrafo reconocible, el módulo
        // devuelve false y sigue la edición palabra por palabra de siempre.
        if (window.PDFEdicionParrafo && !e.target.closest('.capa-tablas')) {
            const caja = wrapper.getBoundingClientRect();
            const px = (e.clientX - caja.left) / state.zoom;
            const py = (e.clientY - caja.top) / state.zoom;
            window.PDFEdicionParrafo.abrir(_apiParrafo, pag, px, py).then(function (tomado) {
                if (!tomado && span) { state.currentPage = pag; _abrirEdicionTexto(span, pag, e.clientX, e.clientY); }
            });
            return;
        }
        if (!span) {
            // sin texto cerca: o es un escaneo, o se pinchó en una zona vacía
            if (!_paginaTieneTexto(pag)) {
                mostrarToast('Esta página es una imagen escaneada: no tiene texto que editar. Usa "Digitalizar y OCR" para obtener su contenido.', 'warn');
            }
            return;
        }
        e.preventDefault();
        state.currentPage = pag;
        _abrirEdicionTexto(span, pag, e.clientX, e.clientY);
    });

    // ==================== CAMBIAR VARIAS PALABRAS A LA VEZ ====================
    // El doble clic cambia UNA palabra. Para cambiar una frase había que ir palabra
    // por palabra, y como cada texto nuevo se escribe donde estaba el anterior, al
    // meter una frase entera en el hueco de una sola palabra el resultado salía
    // montado sobre lo que venía detrás ("HUMANOEDES DECLADAETIERRA").
    // Ahora se marca el trozo con el ratón y se cambia entero: el texto nuevo ocupa
    // el sitio de TODO lo que se marcó, que es lo que evita el amontonamiento.
    let _avisoVariasLineasDado = false;

    function _ocultarBotonSeleccion() {
        if (_btnSeleccion) { _btnSeleccion.remove(); _btnSeleccion = null; }
    }

    function _seleccionEditable() {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
        const rg = sel.getRangeAt(0);
        const nodo = rg.commonAncestorContainer;
        const elem = nodo.nodeType === 1 ? nodo : nodo.parentElement;
        const wrapper = elem && elem.closest ? elem.closest('.page-wrapper') : null;
        if (!wrapper || !elem.closest('.textLayer')) return null;

        // Se amplía a palabras completas: el servidor sustituye palabras enteras, así
        // que lo que se ve en la caja tiene que ser exactamente lo que se va a cambiar.
        const r = rg.cloneRange();
        if (r.startContainer.nodeType === 3) {
            const t = r.startContainer.textContent || '';
            let a = r.startOffset;
            while (a > 0 && !/\s/.test(t[a - 1])) a--;
            r.setStart(r.startContainer, a);
        }
        if (r.endContainer.nodeType === 3) {
            const t = r.endContainer.textContent || '';
            let b = r.endOffset;
            while (b < t.length && !/\s/.test(t[b])) b++;
            r.setEnd(r.endContainer, b);
        }
        const texto = r.toString();
        // Una sola palabra ya se cambia con doble clic: no hace falta el botón
        if (!texto.trim() || !/\s/.test(texto.trim())) return null;

        const cajas = [...r.getClientRects()].filter(b => b.width > 0.5 && b.height > 0.5);
        if (!cajas.length) return null;
        const arriba = Math.min(...cajas.map(b => b.top));
        const altoLinea = Math.max(...cajas.map(b => b.height));
        if (cajas.some(b => Math.abs(b.top - arriba) > altoLinea * 0.5)) {
            // Selección de varios renglones: cada uno tiene su propia línea base y su
            // propio reparto, así que no se puede tratar como un solo trozo.
            if (!_avisoVariasLineasDado) {
                _avisoVariasLineasDado = true;
                mostrarToast('Seleccione texto de un mismo renglón: por ahora los cambios se aplican renglón a renglón.', 'info');
            }
            return null;
        }
        const rect = {
            left: Math.min(...cajas.map(b => b.left)), top: arriba,
            right: Math.max(...cajas.map(b => b.right)),
            bottom: Math.max(...cajas.map(b => b.bottom))
        };
        rect.width = rect.right - rect.left;
        rect.height = rect.bottom - rect.top;
        const nodoIni = r.startContainer;
        const elemIni = nodoIni.nodeType === 3 ? nodoIni.parentElement : nodoIni;
        const span = (elemIni && elemIni.closest('.textLayer span')) || wrapper.querySelector('.textLayer span');
        if (!span) return null;
        return { rect, texto, span, pag: parseInt(wrapper.dataset.page) || state.currentPage };
    }

    function _mostrarBotonSeleccion(sel) {
        _ocultarBotonSeleccion();
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn-cambiar-seleccion';
        btn.innerHTML = '<i class="bi bi-pencil-square"></i> Cambiar este texto';
        _aplicarEstiloForzado(btn, {
            position: 'fixed',
            left: Math.round(Math.max(8, Math.min(sel.rect.left, window.innerWidth - 190))) + 'px',
            top: Math.round(Math.min(sel.rect.bottom + 6, window.innerHeight - 44)) + 'px',
            'z-index': '9000',
            padding: '5px 10px',
            border: 'none',
            'border-radius': '6px',
            background: '#0d6efd',
            color: '#fff',
            'font-size': '13px',
            'font-family': 'inherit',
            cursor: 'pointer',
            'box-shadow': '0 2px 8px rgba(0,0,0,.25)'
        });
        // Se escucha al PULSAR y no al soltar: el navegador borra la selección en
        // cuanto se pulsa, y sin ella
        // no habría nada que editar
        btn.addEventListener('mousedown', ev => {
            ev.preventDefault();
            ev.stopPropagation();
            const s = _seleccionEditable() || sel;
            _ocultarBotonSeleccion();
            state.currentPage = s.pag;
            _abrirEdicionTexto(s.span, s.pag, 0, 0, { rect: s.rect, texto: s.texto });
        });
        document.body.appendChild(btn);
        _btnSeleccion = btn;
    }

    document.addEventListener('mouseup', e => {
        if (!_modoEdicionTexto || _edicionAbierta) { _ocultarBotonSeleccion(); return; }
        if (e.target.closest && e.target.closest('.btn-cambiar-seleccion')) return;
        // el navegador termina de fijar la selección justo después del mouseup
        setTimeout(() => {
            if (!_modoEdicionTexto || _edicionAbierta) return;
            const sel = _seleccionEditable();
            if (sel) _mostrarBotonSeleccion(sel);
            else _ocultarBotonSeleccion();
        }, 0);
    });

    document.addEventListener('selectionchange', () => {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed) _ocultarBotonSeleccion();
    });
    $('viewerScroll')?.addEventListener('scroll', _ocultarBotonSeleccion);

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _activarModoEdicionTexto, _aplicarEstiloForzado, _reabrirEdicion });
};
