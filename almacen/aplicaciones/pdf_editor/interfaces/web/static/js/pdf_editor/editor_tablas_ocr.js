/* ============================================================
   Raíces Maquita — Editor PDF · tablas ocr
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.tablas_ocr = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _cambiarDocumento, _cerrarModal, _descargarBlob, _getPdfBlob, _mostrarError, _necesitaPDF, _ocultarError, mostrarToast, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const _activarModoEdicionTexto = (...a) => E._activarModoEdicionTexto(...a);   // parte texto_pdf
    const _descargarTextoComoWord = (...a) => E._descargarTextoComoWord(...a);   // parte buscar_exportar
    const renderPage = (...a) => E.renderPage(...a);   // parte render_vista
    // ==================== COLUMNAS DE LAS TABLAS ====================
    // "Digitalizar y OCR" reconoce las tablas de la página y deja agregar o
    // quitar columnas EN EL PROPIO PDF, sin convertirlo en nada
    // («ahí mismo me permitas hacer esos cambios»). Todo lo demás está en
    // tablas_columnas.js; aquí solo lo que toca estado privado del editor.
    const _apiTablas = {
        getPdfBlob: () => (state.pdfBytes ? _getPdfBlob() : null),
        // Los bytes tal cual: es lo que necesita el envío por sesión para saber
        // cuánto mide nuestra copia y para pegarle el trozo que devuelve el
        // servidor. Con un Blob habría que volver a leerlo entero cada vez.
        getPdfBytes: () => state.pdfBytes,
        getPagina: () => state.currentPage,
        getZoom: () => state.zoom,
        // Al recargar el documento el visor vuelve al principio: hay que
        // devolver al usuario a la página de SU tabla.
        irAPagina: n => { if (typeof renderPage === 'function') renderPage(parseInt(n)); },
        getTotalPaginas: () => state.totalPages,
        // Al apagar la herramienta se apaga TODO: tablas y doble clic
        apagarTexto: () => _activarModoEdicionTexto(false),
        hayTexto: () => _paginaTieneTexto(state.currentPage),
        toast: (m, t) => mostrarToast(m, t),
        showLoading: (s, m) => showLoading(s, m),
        reemplazarPdf: async function (bytes, etiqueta) {
            await _cambiarDocumento(bytes, etiqueta || 'el cambio en la tabla');
        }
    };

    // Puente del módulo de edición por párrafo (edicion_parrafo.js)

    function abrirEdicionTablas() {
        if (_necesitaPDF()) return;
        const pagina = state.currentPage;

        // Si la página es un ESCANEO no hay texto que editar: es una foto. Antes se
        // encendían los controles de tabla y no pasaba nada más — se pulsaba
        // «Digitalizar y OCR» sobre un escaneado y el editor se quedaba mudo. Ahora se
        // ofrece digitalizarlo, que es justo lo que el botón promete. (30-jul-2026.)
        if (!_paginaTieneTexto(pagina)) {
            digitalizarEscaneo();
            return;
        }

        // La edición de texto con doble clic NO se pierde por editar tablas: se
        // enciende igual que siempre. Dentro de una tabla manda el campo de la
        // celda; fuera, el doble clic de toda la vida.
        _activarModoEdicionTexto(true);
        _resaltarTextoEditable(pagina);

        if (window.PDFTablasColumnas) window.PDFTablasColumnas.activar(_apiTablas);
        else mostrarToast('La edición de tablas no está disponible en este momento.', 'error');
    }

    /** Convierte el escaneo en un documento con texto de verdad y lo deja abierto en
     *  el editor, listo para corregirlo. Reconocer el texto tarda —unos segundos por
     *  página—, así que se avisa y se cuentan los segundos, como en las conversiones. */
    let _digitalizando = false;
    async function digitalizarEscaneo() {
        if (_digitalizando) {
            mostrarToast('Ya se está digitalizando: espera a que termine.', 'warn');
            return;
        }
        const idioma = $('selectIdioma')?.value || 'spa';
        if (!confirm('Esta página es un escaneo: no tiene texto, es una imagen.\n\n'
                     + '¿Se reconoce el texto ahora? El documento pasará a tener texto de '
                     + 'verdad y podrás editarlo, buscar y copiar.')) {
            return;
        }
        _digitalizando = true;
        const inicio = Date.now();
        const pintar = () => showLoading(true,
            'Reconociendo el texto… ' + Math.round((Date.now() - inicio) / 1000) + ' s\n'
            + 'Va por páginas; en documentos largos puede pasar del minuto.\n'
            + 'No cierres ni recargues la página.');
        pintar();
        const reloj = setInterval(pintar, 1000);
        const terminar = () => { clearInterval(reloj); _digitalizando = false; showLoading(false); };
        try {
            const formData = new FormData();
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
            formData.append('idioma', idioma);
            const resp = await fetch('/api/pdf/operacion/digitalizar',
                                     { method: 'POST', body: formData, credentials: 'same-origin' });
            if (!resp.ok) {
                const d = await resp.json().catch(() => ({}));
                throw new Error(d.mensaje || 'no se pudo digitalizar');
            }
            const bytes = new Uint8Array(await (await resp.blob()).arrayBuffer());
            terminar();
            await _cambiarDocumento(bytes, 'la digitalización del escaneo');
            mostrarToast('Documento digitalizado en ' + Math.round((Date.now() - inicio) / 1000)
                         + ' s. Ya puedes editar el texto con doble clic.', 'ok');
            // Y se deja la edición de TEXTO encendida, que es a lo que venía el usuario.
            // Las columnas de tabla ya NO se encienden aquí: un escaneo recién
            // digitalizado es texto suelto, sin una sola raya, y el editor lo pintaba
            // como si fuera una tabla —«se me daña y queda en forma de tabla»,
            // 31-jul-2026—. Si el documento trae tablas de verdad, siguen estando a un
            // clic en «Digitalizar y OCR».
            _activarModoEdicionTexto(true);
            _resaltarTextoEditable(state.currentPage);
        } catch (e) {
            terminar();
            _mostrarErrorDigitalizar(e.message);
        }
    }

    function _mostrarErrorDigitalizar(mensaje) {
        mostrarToast('No se pudo digitalizar: ' + mensaje, 'error');
    }

    // ==================== EDICIÓN TIPO WORD ====================
    // "Digitalizar y OCR" ya no enciende la edición palabra por palabra: abre
    // el documento como un Word de verdad (tablas, columnas, formato y tipo de
    // letra) en el OnlyOffice de Maquita. Todo lo demás vive en word_editor.js;
    // aquí solo lo que exige tocar el estado privado del editor.
    const _apiWordEditor = {
        getPdfBlob: () => (state.pdfBytes ? _getPdfBlob() : null),
        // Los bytes tal cual: es lo que necesita el envío por sesión para saber
        // cuánto mide nuestra copia y para pegarle el trozo que devuelve el
        // servidor. Con un Blob habría que volver a leerlo entero cada vez.
        getPdfBytes: () => state.pdfBytes,
        getNombre: () => state.nombreOriginal || 'documento.pdf',
        toast: (m, t) => mostrarToast(m, t),
        showLoading: (s, m) => showLoading(s, m),
        reemplazarPdf: async function (bytes) {
            await _cambiarDocumento(bytes, 'la edición en Word');
        }
    };

    function abrirEdicionWord() {
        if (_necesitaPDF()) return;
        if (window.PDFWordEditor) window.PDFWordEditor.abrir(_apiWordEditor);
        else mostrarToast('La edición tipo Word no está disponible en este momento.', 'error');
    }

    // ==================== OCR / DIGITALIZAR ====================
    // Desde el 21-jul-2026 esta herramienta YA NO abre el recuadro con el texto
    // extraído (pedido del usuario). Ahora:
    //   - página con texto de verdad  -> se le indica que edite con doble clic;
    //   - página escaneada (una imagen) -> se reconoce el texto y se descarga en .txt,
    //     porque ahí no hay texto en el documento que se pueda editar en su sitio.
    function _paginaTieneTexto(pagina) {
        const capa = document.getElementById('pageWrapper_' + pagina)?.querySelector('.textLayer');
        if (!capa) return false;
        return [...capa.querySelectorAll('span')].some(s => (s.textContent || '').trim().length > 1);
    }

    async function abrirModalOCR() {
        if (_necesitaPDF()) return;
        const pagina = state.currentPage;

        if (_paginaTieneTexto(pagina)) {
            // Se ENCIENDE la edición: a partir de aquí el doble clic abre la palabra.
            // Sin pulsar la herramienta, el doble clic no hace nada (pedido del usuario).
            _activarModoEdicionTexto(true);
            mostrarToast('Edición de texto activada: haz doble clic sobre la palabra que quieras cambiar. Pulsa Esc para salir.', 'success');
            _resaltarTextoEditable(pagina);
            return;
        }

        mostrarToast('Página escaneada: reconociendo el texto…', 'info');
        try {
            const formData = new FormData();
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
            formData.append('pagina', pagina);
            formData.append('idioma', document.getElementById('selectIdioma')?.value || 'spa');
            const resp = await fetch('/api/pdf/operacion/ocr', { method: 'POST', body: formData, credentials: 'same-origin' });
            const datos = await resp.json();
            if (!datos.exito) throw new Error(datos.mensaje || 'No se pudo reconocer el texto');
            const texto = (datos.datos && datos.datos.texto_total || '').trim();
            if (!texto) { mostrarToast('No se reconoció texto en esta página.', 'warn'); return; }
            const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain;charset=utf-8' }));
            const a = document.createElement('a');
            a.href = url; a.download = 'texto_pagina_' + pagina + '.txt';
            a.click();
            URL.revokeObjectURL(url);
            mostrarToast('Texto reconocido y descargado (' + texto.length + ' caracteres). Es un escaneo: no se puede editar dentro del PDF.', 'success');
        } catch (e) {
            mostrarToast('No se pudo reconocer el texto: ' + e.message, 'error');
        }
    }

    // Parpadeo suave sobre la capa de texto: enseña dónde se puede hacer doble clic
    function _resaltarTextoEditable(pagina) {
        const capa = document.getElementById('pageWrapper_' + pagina)?.querySelector('.textLayer');
        if (!capa) return;
        capa.classList.add('texto-editable-aviso');
        setTimeout(() => capa.classList.remove('texto-editable-aviso'), 1800);
    }
    $('toolDigitalizar')?.addEventListener('click', () => abrirEdicionTablas());
    // «Extraer texto (OCR)»: abre la ventana que ya existía y que NO abría nadie — la
    // función estaba escrita y el botón no existía, así que era imposible llegar.
    $('toolExtraerTexto')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        const selector = $('selectPaginaOCR');
        if (selector) {
            selector.innerHTML = '<option value="">Todas las páginas</option>';
            for (let p = 1; p <= state.totalPages; p++) {
                const o = document.createElement('option');
                o.value = String(p);
                o.textContent = 'Página ' + p;
                if (p === state.currentPage) o.selected = true;
                selector.appendChild(o);
            }
        }
        $('resultadoOCR') && ($('resultadoOCR').style.display = 'none');
        _ocultarError('errorOCR');
        E._abrirModal('modalOCR');
    });
    // La edición en Word sigue estando, para el documento que se resista
    $('toolWordAvanzado')?.addEventListener('click', () => abrirEdicionWord());
    $('btnCerrarOCR')?.addEventListener('click', () => _cerrarModal('modalOCR'));
    $('btnCerrarOCRFooter')?.addEventListener('click', () => _cerrarModal('modalOCR'));
    $('btnEjecutarOCR')?.addEventListener('click', async function() {
        const pagina = $('selectPaginaOCR').value;
        this.textContent = 'Extrayendo...'; this.disabled = true;
        _ocultarError('errorOCR');
        const idioma = document.getElementById('selectIdioma')?.value || 'spa';
        try {
            const formData = new FormData();
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
            if (pagina) formData.append('pagina', pagina);
            formData.append('idioma', idioma);
            const resp = await fetch('/api/pdf/operacion/ocr', { method: 'POST', body: formData, credentials: 'same-origin' });
            const datos = await resp.json();
            if (!datos.exito) throw new Error(datos.mensaje);
            const texto = datos.datos.texto_total || '(Sin texto detectado)';
            $('textareaOCR').value = texto;
            const ocrUsado = datos.datos.ocr_utilizado ? ' (OCR Tesseract aplicado)' : ' (texto incrustado)';
            $('infoOCR').textContent = datos.datos.total_paginas + ' página(s) · ' + texto.length + ' caracteres' + ocrUsado;
            $('resultadoOCR').style.display = 'block';
        } catch(errServidor) {
            // Antes, si el servidor no podía, se reintentaba el OCR en el propio navegador
            // con Tesseract.js. Se quitó a propósito: esa librería y los datos del idioma
            // (más de 8 MB) se descargaban de servidores ajenos, y aquí no dependemos de
            // terceros. El OCR lo hace el servidor, que tiene tesseract instalado con
            // español e inglés; si falla, se dice claramente en vez de disimularlo.
            _mostrarError('errorOCR', 'No se pudo extraer el texto: ' + errServidor.message);
        }
        finally { this.innerHTML = '<i class="bi bi-type"></i> Extraer texto'; this.disabled = false; }
    });
    $('btnCopiarOCR')?.addEventListener('click', () => {
        navigator.clipboard.writeText($('textareaOCR').value).then(() => mostrarToast('Texto copiado al portapapeles', 'ok'));
    });
    $('btnDescargarTextoOCR')?.addEventListener('click', async function() {
        try {
            await _descargarTextoComoWord($('textareaOCR').value, 'texto_extraido');
            mostrarToast('Texto descargado como Word (.docx)', 'ok');
        } catch (e) {
            // si el Word falla, al menos entregar el .txt
            const blob = new Blob([$('textareaOCR').value], { type: 'text/plain;charset=utf-8' });
            _descargarBlob(blob, 'texto_extraido.txt');
        }
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _paginaTieneTexto, abrirEdicionTablas });
};
