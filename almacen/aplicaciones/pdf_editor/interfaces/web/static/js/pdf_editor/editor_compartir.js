/* ============================================================
   Raíces Maquita — Editor PDF · compartir
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.compartir = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, FUENTES_TEXTO, _abrirModal, _cerrarModal, _descargarBlob, _necesitaPDF, mostrarToast, showLoading, state } = E;
    // ==================== COMPARTIR ====================
    // ==================== COMPARTIR ====================
    $('btnShare')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        $('resultadoCompartir').style.display = 'none';
        _abrirModal('modalCompartir');
    });
    $('btnCerrarCompartir')?.addEventListener('click', () => _cerrarModal('modalCompartir'));

    async function _blobHorneado() {
        return new Blob([await _hornearPDF()], { type: 'application/pdf' });
    }
    function _nombreCompartir() {
        const n = ($('inputNombreCompartir')?.value || '').trim() || 'documento.pdf';
        return n.toLowerCase().endsWith('.pdf') ? n : n + '.pdf';
    }

    // Sube el PDF (con anotaciones) a la Nube del usuario y crea un enlace público
    $('btnCompartirNube')?.addEventListener('click', async function() {
        this.disabled = true;
        const res = $('resultadoCompartir');
        try {
            showLoading(true);
            const nombre = _nombreCompartir();
            const fd = new FormData();
            fd.append('archivo', await _blobHorneado(), nombre);
            fd.append('carpeta', '/');
            const rs = await fetch('/api/nextcloud/archivos', { method: 'POST', body: fd, credentials: 'same-origin' });
            const ds = await rs.json().catch(() => ({}));
            if (!rs.ok || !ds.success) throw new Error(ds.message || ds.error || 'no se pudo subir a la Nube');
            const rc = await fetch('/api/nextcloud/compartir', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ruta: '/' + nombre, tipo: 3, permisos: 1 })
            });
            const dc = await rc.json().catch(() => ({}));
            const url = (dc.compartido && (dc.compartido.url_publica || dc.compartido.url)) || '';
            if (!rc.ok || !dc.success || !url) throw new Error(dc.message || dc.error || 'no se pudo crear el enlace');
            let copiado = false;
            try { await navigator.clipboard.writeText(url); copiado = true; } catch (e) { /* sin permiso */ }
            res.style.background = '#f0fdf4';
            res.innerHTML = '✓ Guardado en tu Nube' + (copiado ? ' y enlace copiado al portapapeles' : '') + ':<br>';
            const a = document.createElement('a');
            a.href = url; a.target = '_blank'; a.textContent = url;
            a.style.wordBreak = 'break-all';
            res.appendChild(a);
            res.style.display = 'block';
        } catch (e) {
            res.style.background = '#fff5f5';
            res.textContent = 'No se pudo compartir: ' + e.message;
            res.style.display = 'block';
        } finally { showLoading(false); this.disabled = false; }
    });

    // Web Share API (móvil / navegadores compatibles); si no hay, descarga
    $('btnCompartirApps')?.addEventListener('click', async function() {
        try {
            showLoading(true);
            const file = new File([await _blobHorneado()], _nombreCompartir(), { type: 'application/pdf' });
            showLoading(false);
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
                await navigator.share({ files: [file], title: _nombreCompartir() });
            } else {
                _descargarBlob(file, _nombreCompartir());
                mostrarToast('Tu navegador no permite compartir directo: se descargó el archivo para que lo adjuntes.', 'warn');
            }
        } catch (e) {
            showLoading(false);
            if (e.name !== 'AbortError') mostrarToast('No se pudo compartir: ' + e.message, 'warn');
        }
    });

    $('btnCompartirDescargar')?.addEventListener('click', () => {
        _cerrarModal('modalCompartir');
        downloadPDF();
    });

    // ==================== DESCARGA PDF (con anotaciones horneadas) ====================

    function _hexToRgb(hex) {
        const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '#000000');
        return r ? { r: parseInt(r[1],16)/255, g: parseInt(r[2],16)/255, b: parseInt(r[3],16)/255 }
                 : { r: 0, g: 0, b: 0 };
    }
    function _dataURLToBytes(dataURL) {
        const b64   = dataURL.split(',')[1];
        const bin   = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return bytes;
    }

    // Genera el PDF final (rotaciones + anotaciones horneadas) y lo devuelve como
    // bytes. Lo usan "Descargar" y "Compartir" para que ambos incluyan los cambios.
    async function _hornearPDF() {
            await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
            const { PDFDocument, rgb, StandardFonts } = PDFLib;
            // updateMetadata:false evita error Chrome con PDFs que tienen metadata XMP
            const pdfDoc = await PDFDocument.load(state.pdfBytes, { updateMetadata: false });
            const font   = await pdfDoc.embedFont(StandardFonts.Helvetica);
            const pages  = pdfDoc.getPages();

            // 1. Rotaciones
            for (let i = 0; i < pages.length; i++) {
                const rot = state.rotation[i + 1] || 0;
                if (rot) pages[i].setRotation({ type: 'degrees', angle: rot });
            }

            // 2. Anotaciones horneadas con pdf-lib
            const _nombresCampos = new Set();  // pdf-lib no admite campos AcroForm con nombre repetido
            const _cacheFuentes = {};          // fuentes estándar ya incrustadas (una vez por variante)
            for (const [pageStr, anns] of Object.entries(state.annotations)) {
                const pageIdx = parseInt(pageStr) - 1;
                if (pageIdx < 0 || pageIdx >= pages.length) continue;
                const page             = pages[pageIdx];
                const { width, height } = page.getSize();

                for (const ann of anns) {
                    // ann.x / ann.y están en coordenadas canvas-1x (= puntos PDF desde arriba)
                    const ax = ann.x || 0;
                    const ay = ann.y || 0;
                    const aw = ann.width  || 100;
                    const ah = ann.height || 20;
                    // pdf-lib: y desde abajo
                    const pdfY = height - ay - ah;

                    try {
                        switch (ann.type) {
                            case 'highlight': {
                                const c = _hexToRgb(ann.color || '#FFE500');
                                page.drawRectangle({ x: ax, y: pdfY, width: aw, height: ah,
                                    color: rgb(c.r, c.g, c.b), opacity: 0.35 });
                                break;
                            }
                            case 'underline': {
                                const c = _hexToRgb(ann.color || '#1473e6');
                                page.drawLine({
                                    start: { x: ax,      y: pdfY },
                                    end:   { x: ax + aw, y: pdfY },
                                    thickness: 1.5, color: rgb(c.r, c.g, c.b)
                                });
                                break;
                            }
                            case 'strikeout': {
                                const c  = _hexToRgb(ann.color || '#dc2626');
                                const midY = pdfY + ah / 2;
                                page.drawLine({
                                    start: { x: ax,      y: midY },
                                    end:   { x: ax + aw, y: midY },
                                    thickness: 1.5, color: rgb(c.r, c.g, c.b)
                                });
                                break;
                            }
                            // Línea reescrita: primero el rectángulo que tapa el texto
                            // original (color del fondo detectado) y luego el texto nuevo
                            case 'edicion': {
                                const cf = _hexToRgb(ann.fondo || '#ffffff');
                                page.drawRectangle({
                                    x: ax, y: pdfY, width: aw, height: ah,
                                    color: rgb(cf.r, cf.g, cf.b)
                                });
                                if (!(ann.text || '').trim()) break;   // línea borrada a propósito
                                const ct  = _hexToRgb(ann.color || '#000000');
                                const fam = FUENTES_TEXTO[ann.fuente || 'helvetica'] || FUENTES_TEXTO.helvetica;
                                const variante = fam.pdf[(ann.negrita ? 1 : 0) + (ann.cursiva ? 2 : 0)];
                                if (!_cacheFuentes[variante]) {
                                    _cacheFuentes[variante] = await pdfDoc.embedFont(StandardFonts[variante]);
                                }
                                const fuente = _cacheFuentes[variante];
                                // Si el texto nuevo es más largo que el hueco, se encoge
                                // hasta que quepa (nunca por debajo del 60 % del original)
                                // El tamaño se respeta tal cual: encogerlo para que
                                // cupiera era justo lo que cambiaba el aspecto del texto
                                const size = ann.size || 12;
                                // Se apoya en la línea base ORIGINAL cuando se guardó
                                // (ann.baseY = borde inferior del texto que se tapó): así el
                                // renglón nuevo queda a la misma altura que los de al lado.
                                const base = ann.baseY
                                    ? height - ann.baseY + size * 0.21
                                    : pdfY + (ah - size) / 2 + size * 0.16;
                                page.drawText(ann.text, {
                                    x: ax, y: base, size, font: fuente,
                                    color: rgb(ct.r, ct.g, ct.b)
                                });
                                break;
                            }
                            case 'text': {
                                const c    = _hexToRgb(ann.color || '#000000');
                                const size = ann.size || 12;
                                // Fuente estándar según familia + negrita/cursiva de la anotación
                                const fam = FUENTES_TEXTO[ann.fuente || 'helvetica'] || FUENTES_TEXTO.helvetica;
                                const variante = fam.pdf[(ann.negrita ? 1 : 0) + (ann.cursiva ? 2 : 0)];
                                if (!_cacheFuentes[variante]) {
                                    _cacheFuentes[variante] = await pdfDoc.embedFont(StandardFonts[variante]);
                                }
                                page.drawText(ann.text || '', {
                                    x: ax, y: height - ay - size,
                                    size, font: _cacheFuentes[variante], color: rgb(c.r, c.g, c.b)
                                });
                                break;
                            }
                            case 'note': {
                                // La marca se dibuja con vectores, con su forma y su color:
                                // lo que se descarga es lo que se ve. Antes cualquier
                                // comentario salía como un cuadrado naranja.
                                const cn = _hexToRgb(ann.color || '#f59e0b');
                                const colorNota = rgb(cn.r, cn.g, cn.b);
                                const dibujada = E.hornearMarca && E.hornearMarca(page, ann, {
                                    x: ax, y: pdfY, tamano: 20, colorRgb: colorNota, fuente: font,
                                });
                                if (!dibujada) {
                                    // Marca desconocida (documento de una versión futura):
                                    // al menos que se vea que ahí hay un comentario.
                                    page.drawRectangle({ x: ax, y: pdfY, width: 20, height: 20,
                                        color: colorNota, opacity: 0.85 });
                                }
                                break;
                            }
                            case 'stamp': {
                                // Sellos ✓ ✗ ● ▢ — como vectores (mismas proporciones que el
                                // SVG del editor, viewBox 0-100 mapeado al tamaño del sello)
                                const c   = _hexToRgb(ann.color || '#111111');
                                const col = rgb(c.r, c.g, c.b);
                                const s   = ann.size || 22;
                                const sw  = ann.subtipo === 'linea' ? s * 3 : s;
                                const sh  = ann.subtipo === 'linea' ? Math.max(8, s / 3) : s;
                                const X = u => ax + (u / 100) * sw;
                                const Y = v => height - ay - (v / 100) * sh;
                                const g = 0.12 * s;
                                switch (ann.subtipo) {
                                    case 'equis':
                                        page.drawLine({ start: {x: X(20), y: Y(20)}, end: {x: X(80), y: Y(80)}, thickness: g, color: col });
                                        page.drawLine({ start: {x: X(80), y: Y(20)}, end: {x: X(20), y: Y(80)}, thickness: g, color: col });
                                        break;
                                    case 'punto':
                                        page.drawEllipse({ x: X(50), y: Y(50), xScale: 0.3 * sw, yScale: 0.3 * sh, color: col });
                                        break;
                                    case 'cuadro':
                                        page.drawRectangle({ x: X(12), y: Y(88), width: 0.76 * sw, height: 0.76 * sh,
                                            borderColor: col, borderWidth: 0.08 * s });
                                        break;
                                    case 'linea':
                                        page.drawLine({ start: {x: X(4), y: Y(50)}, end: {x: X(96), y: Y(50)}, thickness: 0.14 * sh, color: col });
                                        break;
                                    default:  // check
                                        page.drawLine({ start: {x: X(15), y: Y(55)}, end: {x: X(40), y: Y(80)}, thickness: g, color: col });
                                        page.drawLine({ start: {x: X(40), y: Y(80)}, end: {x: X(85), y: Y(20)}, thickness: g, color: col });
                                }
                                break;
                            }
                            case 'shape': {
                                // Formas: vectores nativos de pdf-lib (sin fuentes ni imágenes)
                                const c  = _hexToRgb(ann.color || '#dc2626');
                                const gr = ann.grosor || 2;
                                const ax2 = ann.x, ay2 = ann.y;
                                const aw2 = ann.width || 1, ah2 = ann.height || 1;
                                if (ann.subtipo === 'rect') {
                                    page.drawRectangle({
                                        x: ax2, y: height - ay2 - ah2,
                                        width: aw2, height: ah2,
                                        borderColor: rgb(c.r, c.g, c.b),
                                        borderWidth: gr
                                    });
                                } else if (ann.subtipo === 'elipse') {
                                    page.drawEllipse({
                                        x: ax2 + aw2 / 2, y: height - (ay2 + ah2 / 2),
                                        xScale: Math.max(1, aw2 / 2), yScale: Math.max(1, ah2 / 2),
                                        borderColor: rgb(c.r, c.g, c.b),
                                        borderWidth: gr
                                    });
                                } else {
                                    // línea / flecha: p1 y p2 son fracciones del rectángulo
                                    const p1 = ann.p1 || [0, 0], p2 = ann.p2 || [1, 1];
                                    const x1 = ax2 + p1[0] * aw2, y1 = ay2 + p1[1] * ah2;
                                    const x2 = ax2 + p2[0] * aw2, y2 = ay2 + p2[1] * ah2;
                                    page.drawLine({
                                        start: { x: x1, y: height - y1 },
                                        end:   { x: x2, y: height - y2 },
                                        thickness: gr,
                                        color: rgb(c.r, c.g, c.b)
                                    });
                                    if (ann.subtipo === 'flecha') {
                                        // Punta: dos líneas cortas desde el extremo final
                                        const ang  = Math.atan2(-(y2 - y1), x2 - x1); // eje Y del PDF va al reves
                                        const lado = Math.max(8, gr * 3.5);
                                        [ang + Math.PI * 0.82, ang - Math.PI * 0.82].forEach(a => {
                                            page.drawLine({
                                                start: { x: x2, y: height - y2 },
                                                end:   { x: x2 + lado * Math.cos(a),
                                                         y: height - y2 + lado * Math.sin(a) },
                                                thickness: gr,
                                                color: rgb(c.r, c.g, c.b)
                                            });
                                        });
                                    }
                                }
                                break;
                            }
                            case 'draw': {
                                const c = _hexToRgb(ann.color || '#000000');
                                for (const trazo of (ann.trazos || [])) {
                                    for (let i = 1; i < trazo.length; i++) {
                                        page.drawLine({
                                            start: { x: trazo[i-1][0], y: height - trazo[i-1][1] },
                                            end:   { x: trazo[i][0],   y: height - trazo[i][1]   },
                                            thickness: ann.grosor || 2,
                                            color: rgb(c.r, c.g, c.b)
                                        });
                                    }
                                }
                                break;
                            }
                            case 'signature': {
                                if (ann.data) {
                                    const bytes = _dataURLToBytes(ann.data);
                                    const img   = ann.data.includes('data:image/png')
                                        ? await pdfDoc.embedPng(bytes)
                                        : await pdfDoc.embedJpg(bytes);
                                    page.drawImage(img, {
                                        x: ax, y: pdfY,
                                        width: Math.min(aw || 150, 200),
                                        height: Math.min(ah || 60, 100)
                                    });
                                }
                                break;
                            }
                            case 'image': {
                                // Imagen insertada: se incrusta con su tamaño real (sin los topes de la firma)
                                if (ann.data) {
                                    const bytes = _dataURLToBytes(ann.data);
                                    const img   = ann.data.includes('data:image/png')
                                        ? await pdfDoc.embedPng(bytes)
                                        : await pdfDoc.embedJpg(bytes);
                                    const iw = aw || 200;
                                    const ih = ann.height || (img.height * iw / img.width);
                                    page.drawImage(img, { x: ax, y: height - ay - ih, width: iw, height: ih });
                                }
                                break;
                            }
                            case 'form': {
                                // Campo interactivo REAL (AcroForm) con la API de formularios de pdf-lib
                                const form = pdfDoc.getForm();
                                let nombreFinal = ann.nombre || 'campo';
                                let n = 1;
                                while (_nombresCampos.has(nombreFinal)) { n++; nombreFinal = (ann.nombre || 'campo') + '_' + n; }
                                _nombresCampos.add(nombreFinal);
                                const caja = { x: ax, y: pdfY, width: aw, height: ah,
                                               borderColor: rgb(0.45, 0.55, 0.75), borderWidth: 1 };
                                if (ann.subtipo === 'checkbox') {
                                    form.createCheckBox(nombreFinal).addToPage(page, caja);
                                } else if (ann.subtipo === 'lista') {
                                    const lista = form.createDropdown(nombreFinal);
                                    lista.addOptions((ann.opciones || '').split(',').map(s => s.trim()).filter(Boolean));
                                    lista.addToPage(page, caja);
                                } else {
                                    form.createTextField(nombreFinal).addToPage(page, caja);
                                }
                                break;
                            }
                        }
                    } catch (annErr) {
                        console.warn('Anotación omitida:', annErr.message);
                    }
                }
            }

            return await pdfDoc.save();
    }

    async function downloadPDF() {
        if (!state.pdfBytes) return;
        showLoading(true);
        try {
            const modifiedPdf = await _hornearPDF();
            const blob = new Blob([modifiedPdf], { type: 'application/pdf' });
            _descargarBlob(blob, 'documento_editado.pdf');
            state.hayCambios = false; // ya tiene una copia con sus cambios
            mostrarToast('PDF descargado con todas las anotaciones', 'ok');
        } catch (e) {
            console.error('Error descargando PDF:', e);
            mostrarToast('Error al descargar: ' + e.message, 'error');
        } finally { showLoading(false); }
    }

    // ==================== INSERTAR PÁGINA (acceso desde panel Páginas) ====================
    $('btnInsertPage')?.addEventListener('click', () => {
        if (!_necesitaPDF()) _abrirModal('modalInsertarPag');
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _hornearPDF, downloadPDF });
};
