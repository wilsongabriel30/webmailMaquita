/* ============================================================
   Raíces Maquita — Editor PDF · operaciones
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.operaciones = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _abrirModal, _cerrarModal, _mostrarError, _necesitaPDF, _ocultarError, _operacionBackend, mostrarToast, state } = E;
    // ==================== COMPRIMIR ====================
    $('toolComprimir')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        const kb = (state.pdfBytes.length / 1024).toFixed(1);
        $('infoTamanoComprimir').textContent = 'Tamaño actual: ' + kb + ' KB (' + (state.pdfBytes.length / 1024 / 1024).toFixed(2) + ' MB)';
        _ocultarError('errorComprimir');
        _abrirModal('modalComprimir');
    });
    $('btnCerrarComprimir')?.addEventListener('click', () => _cerrarModal('modalComprimir'));
    $('btnCancelarComprimir')?.addEventListener('click', () => _cerrarModal('modalComprimir'));
    // Tamaño en la unidad que se lee mejor: los KB en documentos pequeños, los MB en
    // los grandes.
    function _tamanoLegible(bytes) {
        return bytes >= 1024 * 1024
            ? (bytes / 1024 / 1024).toFixed(2) + ' MB'
            : (bytes / 1024).toFixed(0) + ' KB';
    }

    // Qué se le dice al usuario después de comprimir. Los tres casos, sin adornos: a
    // veces el documento ya venía comprimido y no hay nada que rascar.
    function _resumenDeCompresion(antes, despues) {
        const bajada = antes > 0 ? (1 - despues / antes) * 100 : 0;
        if (bajada >= 0.5) {
            return ['De ' + _tamanoLegible(antes) + ' a ' + _tamanoLegible(despues)
                    + ': bajó un ' + bajada.toFixed(0) + ' %. Descárgalo cuando quieras.', 'ok'];
        }
        if (bajada > -0.5) {
            return ['Este documento ya estaba comprimido: se queda en '
                    + _tamanoLegible(despues) + '.', 'warn'];
        }
        return ['Con esta calidad el documento abulta más (' + _tamanoLegible(antes)
                + ' → ' + _tamanoLegible(despues) + '). Prueba otra calidad o déjalo '
                + 'como estaba.', 'warn'];
    }

    $('btnEjecutarComprimir')?.addEventListener('click', async function() {
        const calidad = document.querySelector('input[name="calidadComprimir"]:checked')?.value || 'media';
        this.textContent = 'Comprimiendo...'; this.disabled = true;
        _ocultarError('errorComprimir');
        try {
            const antes = state.pdfBytes.length;
            const blob = await _operacionBackend('comprimir', {calidad}, 'documento_comprimido.pdf', 'errorComprimir', true);
            _cerrarModal('modalComprimir');
            const [mensaje, tipo] = _resumenDeCompresion(antes, blob ? blob.size : antes);
            mostrarToast(mensaje, tipo);
        } catch(e) { _mostrarError('errorComprimir', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-file-zip"></i> Comprimir y aplicar'; this.disabled = false; }
    });

    // ==================== PROTEGER ====================
    $('toolProteger')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        $('inputPasswordProteger').value = '';
        $('inputPasswordConfirmar').value = '';
        _ocultarError('errorProteger');
        _abrirModal('modalProteger');
    });
    $('btnRightProtect')?.addEventListener('click', () => { if (!_necesitaPDF()) { $('inputPasswordProteger').value=''; $('inputPasswordConfirmar').value=''; _ocultarError('errorProteger'); _abrirModal('modalProteger'); } });
    $('btnCerrarProteger')?.addEventListener('click', () => _cerrarModal('modalProteger'));
    $('btnCancelarProteger')?.addEventListener('click', () => _cerrarModal('modalProteger'));
    $('btnEjecutarProteger')?.addEventListener('click', async function() {
        const pw = $('inputPasswordProteger').value;
        const pw2 = $('inputPasswordConfirmar').value;
        if (!pw) { _mostrarError('errorProteger', 'Introduce una contraseña'); return; }
        if (pw !== pw2) { _mostrarError('errorProteger', 'Las contraseñas no coinciden'); return; }
        this.textContent = 'Protegiendo...'; this.disabled = true;
        _ocultarError('errorProteger');
        try {
            await _operacionBackend('proteger', {
                password: pw,
                impresion: String($('permImpresion').checked),
                copia: String($('permCopia').checked)
            }, 'documento_protegido.pdf');
            _cerrarModal('modalProteger');
            mostrarToast('PDF protegido descargado. El documento abierto queda sin contraseña para que sigas editando.', 'ok');
        } catch(e) { _mostrarError('errorProteger', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-shield-lock"></i> Proteger y descargar'; this.disabled = false; }
    });

    // ==================== MARCA DE AGUA ====================
    $('sliderTamanoMA')?.addEventListener('input', function() { $('lblTamanoMA').textContent = this.value; });
    $('sliderOpacidadMA')?.addEventListener('input', function() { $('lblOpacidadMA').textContent = this.value; });
    $('toolMarca')?.addEventListener('click', () => {
        if (_necesitaPDF()) return; _ocultarError('errorMarcaAgua'); _abrirModal('modalMarcaAgua');
    });
    $('btnCerrarMarcaAgua')?.addEventListener('click', () => _cerrarModal('modalMarcaAgua'));
    $('btnCancelarMarcaAgua')?.addEventListener('click', () => _cerrarModal('modalMarcaAgua'));
    $('btnEjecutarMarcaAgua')?.addEventListener('click', async function() {
        const texto = $('inputTextoMarcaAgua').value.trim();
        if (!texto) { _mostrarError('errorMarcaAgua', 'Escribe el texto de la marca de agua'); return; }
        this.textContent = 'Aplicando...'; this.disabled = true;
        _ocultarError('errorMarcaAgua');
        try {
            await _operacionBackend('marca-agua', {
                texto,
                opacidad: ($('sliderOpacidadMA').value / 100).toFixed(2),
                tamano: $('sliderTamanoMA').value,
                rotacion: $('selectRotacionMA').value
            }, 'documento_marcado.pdf', 'errorMarcaAgua', true);
            _cerrarModal('modalMarcaAgua');
            mostrarToast('Marca de agua aplicada al documento. Descárgalo cuando quieras.', 'ok');
        } catch(e) { _mostrarError('errorMarcaAgua', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-droplet"></i> Aplicar al documento'; this.disabled = false; }
    });

    // ==================== ENCABEZADO Y PIE ====================
    // Tres sitios arriba y tres abajo, como en Word. Antes era una sola línea a
    // cada lado y el pie venía con «Página {pagina} de {total}» ya escrito, que
    // repetía lo que hace «Numerar páginas»: quien numeraba y luego ponía un
    // encabezado se encontraba el número dos veces (aviso del usuario).
    const _CAMPOS_ENCPIE = ['inputEncIzquierda', 'inputEncCentro', 'inputEncDerecha',
                            'inputPieIzquierda', 'inputPieCentro', 'inputPieDerecha'];

    // El último sitio donde estuvo el cursor: es donde se mete el comodín que se
    // pulse. Sin esto habría que adivinar en cuál de los seis lo quiere.
    let _campoEncPieActivo = null;
    _CAMPOS_ENCPIE.forEach(id => {
        $(id)?.addEventListener('focus', () => { _campoEncPieActivo = id; });
    });

    function _ponerComodin(texto) {
        const campo = $(_campoEncPieActivo) || $('inputPieDerecha');
        if (!campo) return;
        const desde = campo.selectionStart ?? campo.value.length;
        const hasta = campo.selectionEnd ?? campo.value.length;
        campo.value = campo.value.slice(0, desde) + texto + campo.value.slice(hasta);
        campo.focus();
        campo.setSelectionRange(desde + texto.length, desde + texto.length);
    }
    document.querySelectorAll('#modalEncabezado .btn-comodin').forEach(boton => {
        boton.addEventListener('click', () => _ponerComodin(boton.dataset.comodin || ''));
    });

    $('toolEncabezado')?.addEventListener('click', () => {
        if (_necesitaPDF()) return; _ocultarError('errorEncabezado'); _abrirModal('modalEncabezado');
    });
    $('btnCerrarEncabezado')?.addEventListener('click', () => _cerrarModal('modalEncabezado'));
    $('btnCancelarEncabezado')?.addEventListener('click', () => _cerrarModal('modalEncabezado'));
    $('btnEjecutarEncabezado')?.addEventListener('click', async function() {
        const valor = id => ($(id)?.value || '').trim();
        const campos = {
            encabezado_izquierda: valor('inputEncIzquierda'),
            encabezado_centro:    valor('inputEncCentro'),
            encabezado_derecha:   valor('inputEncDerecha'),
            pie_izquierda:        valor('inputPieIzquierda'),
            pie_centro:           valor('inputPieCentro'),
            pie_derecha:          valor('inputPieDerecha')
        };
        if (!Object.values(campos).some(t => t)) {
            _mostrarError('errorEncabezado', 'Escribe al menos un texto en el encabezado o en el pie');
            return;
        }
        campos.tamano = $('selectTamanoEnc').value;
        campos.margen = $('selectMargenEnc')?.value || 'normal';
        const aplicar = $('chkEncabezadoAplicar') ? $('chkEncabezadoAplicar').checked : true;
        this.textContent = 'Aplicando...'; this.disabled = true;
        _ocultarError('errorEncabezado');
        try {
            await _operacionBackend('encabezado-pie', campos,
                                    'documento_encabezado.pdf', 'errorEncabezado', aplicar);
            _cerrarModal('modalEncabezado');
            mostrarToast(aplicar
                ? 'Encabezado y pie aplicados al documento. Descárgalo cuando quieras.'
                : 'Encabezado y pie aplicados: se descargó una copia y el documento abierto queda como estaba.',
                'ok');
        } catch(e) { _mostrarError('errorEncabezado', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-card-heading"></i> Aplicar al documento'; this.disabled = false; }
    });

    // ==================== CENSURAR ====================
    $('toolCensurar')?.addEventListener('click', () => {
        if (_necesitaPDF()) return; $('textareaCensurar').value = ''; _ocultarError('errorCensurar'); _abrirModal('modalCensurar');
    });
    document.getElementById('toolCensurarEdit')?.addEventListener('click', () => { if (!_necesitaPDF()) { $('textareaCensurar').value = ''; _ocultarError('errorCensurar'); _abrirModal('modalCensurar'); } });
    $('btnCerrarCensurar')?.addEventListener('click', () => _cerrarModal('modalCensurar'));
    $('btnCancelarCensurar')?.addEventListener('click', () => _cerrarModal('modalCensurar'));
    $('btnEjecutarCensurar')?.addEventListener('click', async function() {
        const terminos = $('textareaCensurar').value.trim();
        if (!terminos) { _mostrarError('errorCensurar', 'Escribe al menos un término a censurar'); return; }
        if (!confirm('⚠ Esta acción es permanente e irreversible. ¿Continuar?')) return;
        this.textContent = 'Censurando...'; this.disabled = true;
        _ocultarError('errorCensurar');
        try {
            await _operacionBackend('censurar', { terminos }, 'documento_censurado.pdf', null, true);
            _cerrarModal('modalCensurar');
            mostrarToast('Texto censurado y aplicado al documento. Descárgalo cuando quieras.', 'ok');
        } catch(e) { _mostrarError('errorCensurar', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-eraser"></i> Censurar y aplicar'; this.disabled = false; }
    });

    // ==================== EXTRAER PÁGINAS ====================
    // Tiene su propia entrada en el panel de herramientas desde el 30-jul-2026. Antes
    // solo se llegaba con DOBLE CLIC en «Organizar páginas»: existía, funcionaba, y no
    // había manera de dar con ella.
    const _abrirExtraer = () => {
        if (_necesitaPDF()) return;
        $('lblTotalPaginasExtraer').textContent = state.totalPages;
        _ocultarError('errorExtraer');
        _abrirModal('modalExtraer');
    };
    $('toolExtraer')?.addEventListener('click', _abrirExtraer);
    $('toolOrganizar')?.addEventListener('dblclick', _abrirExtraer);   // como antes
    $('btnCerrarExtraer')?.addEventListener('click', () => _cerrarModal('modalExtraer'));
    $('btnCancelarExtraer')?.addEventListener('click', () => _cerrarModal('modalExtraer'));
    $('btnEjecutarExtraer')?.addEventListener('click', async function() {
        const paginasStr = $('inputPaginasExtraer').value.trim();
        if (!paginasStr) { _mostrarError('errorExtraer', 'Introduce las páginas a extraer'); return; }
        this.textContent = 'Extrayendo...'; this.disabled = true;
        _ocultarError('errorExtraer');
        try {
            await _operacionBackend('extraer', { paginas: paginasStr }, 'extracto.pdf');
            _cerrarModal('modalExtraer');
            mostrarToast('Páginas extraídas y descargadas', 'ok');
        } catch(e) { _mostrarError('errorExtraer', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-file-earmark-break"></i> Extraer y descargar'; this.disabled = false; }
    });

};
