/* ============================================================
   Raíces Maquita — Editor PDF · buscar exportar
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.buscar_exportar = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _abrirModal, _cambiarDocumento, _cerrarModal, _descargarBlob, _getPdfBlob, _mostrarError, _necesitaPDF, _ocultarError, _operacionBackend, mostrarToast, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const renderPage = (...a) => E.renderPage(...a);   // parte render_vista
    const setTool = (...a) => E.setTool(...a);   // parte herramientas
    // ==================== BÚSQUEDA ====================
    function abrirPanelBusqueda() {
        if (_necesitaPDF()) return;
        document.getElementById('panelBusqueda').style.right = '0';
        document.getElementById('overlaySemiTransp').style.display = 'block';
        $('inputBusquedaPanel').focus();
    }
    window.cerrarPanelBusqueda = function() {
        document.getElementById('panelBusqueda').style.right = '-360px';
        document.getElementById('overlaySemiTransp').style.display = 'none';
    };
    $('btnCerrarBusqueda')?.addEventListener('click', cerrarPanelBusqueda);

    async function ejecutarBusqueda() {
        const termino = $('inputBusquedaPanel').value.trim();
        if (!termino || !state.pdfBytes) return;
        $('infoBusqueda').textContent = 'Buscando...';
        $('resultadosBusqueda').innerHTML = '';
        try {
            const formData = new FormData();
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
            formData.append('termino', termino);
            const resp = await fetch('/api/pdf/operacion/buscar', { method: 'POST', body: formData });
            const datos = await resp.json();
            if (!datos.exito) throw new Error(datos.mensaje);
            $('infoBusqueda').textContent = datos.total + ' resultado(s) para "' + termino + '"';
            if (datos.total === 0) {
                $('resultadosBusqueda').innerHTML = '<p style="font-size:12px;color:#6d6d6d;margin-top:12px;">Sin resultados en este documento.</p>';
                return;
            }
            const agrupado = {};
            datos.resultados.forEach(r => {
                if (!agrupado[r.pagina]) agrupado[r.pagina] = 0;
                agrupado[r.pagina]++;
            });
            let html = '';
            Object.entries(agrupado).sort((a,b)=>a[0]-b[0]).forEach(([pag, cnt]) => {
                html += `<div onclick="irAPaginaBusqueda(${pag})" style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border:1px solid #e5e5e5;border-radius:6px;margin-bottom:6px;cursor:pointer;background:white;" onmouseover="this.style.background='#f0f0f0'" onmouseout="this.style.background='white'"><span style="font-size:13px;">Página ${pag}</span><span style="font-size:11px;background:#1473e6;color:white;padding:2px 8px;border-radius:10px;">${cnt}</span></div>`;
            });
            $('resultadosBusqueda').innerHTML = html;
        } catch(e) { $('infoBusqueda').textContent = 'Error: ' + e.message; }
    }

    window.irAPaginaBusqueda = function(pag) {
        if (typeof renderPage === 'function') renderPage(parseInt(pag));
        cerrarPanelBusqueda();
    };

    $('btnBuscarPanel')?.addEventListener('click', ejecutarBusqueda);
    $('inputBusquedaPanel')?.addEventListener('keypress', e => { if (e.key === 'Enter') ejecutarBusqueda(); });

    $('searchInput')?.addEventListener('focus', () => {
        if (state.pdfDoc) abrirPanelBusqueda();
    });
    $('searchInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && e.target.value.trim()) {
            if (!state.pdfDoc) { mostrarToast('Primero carga un documento PDF', 'warn'); return; }
            abrirPanelBusqueda();
            $('inputBusquedaPanel').value = e.target.value.trim();
            e.target.value = '';
            ejecutarBusqueda();
        }
    });

    // ==================== ELIMINAR PÁGINA (real con pdf-lib) ====================
    async function eliminarPaginaReal(numPagina) {
        if (!state.pdfBytes) return;
        if (state.totalPages <= 1) { mostrarToast('No puedes eliminar la única página', 'warn'); return; }
        if (!confirm('¿Eliminar la página ' + numPagina + '? Esta acción no se puede deshacer.')) return;
        showLoading(true);
        try {
            await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
            const { PDFDocument } = PDFLib;
            const doc = await PDFDocument.load(state.pdfBytes);
            doc.removePage(numPagina - 1);
            const bytes = await doc.save();
            await _cambiarDocumento(bytes, 'la eliminación de la página');
            mostrarToast('Página ' + numPagina + ' eliminada', 'ok');
        } catch(e) {
            mostrarToast('Error al eliminar: ' + e.message, 'error');
        } finally { showLoading(false); }
    }

    // Borra VARIAS páginas de una vez (números de página, 1-based). La usa la
    // ventana de "Eliminar páginas" (eliminar_paginas.js), que es la que pregunta
    // cuáles; aquí solo se hace el trabajo sobre el documento abierto.
    async function eliminarPaginasReales(nums) {
        if (!state.pdfBytes) return;
        const fuera = [...new Set(nums)].sort((a, b) => b - a);   // de atrás hacia delante
        if (!fuera.length) return;
        if (fuera.length >= state.totalPages) {
            mostrarToast('No puedes eliminar todas las páginas', 'warn');
            return;
        }
        showLoading(true);
        try {
            await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
            const { PDFDocument } = PDFLib;
            const doc = await PDFDocument.load(state.pdfBytes);
            fuera.forEach(n => doc.removePage(n - 1));
            const bytes = await doc.save();
            await _cambiarDocumento(bytes, 'la eliminación de páginas');
            state.hayCambios = true;
            mostrarToast(fuera.length === 1 ? ('Página ' + fuera[0] + ' eliminada')
                                            : (fuera.length + ' páginas eliminadas'), 'ok');
        } catch (e) {
            mostrarToast('Error al eliminar: ' + e.message, 'error');
        } finally { showLoading(false); }
    }

    // Primitivas de la ventana "Eliminar páginas" (el resto vive en eliminar_paginas.js)
    const _apiEliminarPaginas = {
        getTotal: () => state.totalPages,
        getPaginaActual: () => state.currentPage,
        abrirModal: () => _abrirModal('modalElimPag'),
        cerrarModal: () => _cerrarModal('modalElimPag'),
        eliminar: nums => eliminarPaginasReales(nums),
        eliminarPaginaActual: () => eliminarPaginaReal(state.currentPage),
        toast: (m, t) => mostrarToast(m, t)
    };

    $('toolEliminar')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        // Antes borraba la página en la que estabas sin preguntar. Ahora se elige.
        if (window.PDFEliminarPaginas) window.PDFEliminarPaginas.abrir(_apiEliminarPaginas);
        else eliminarPaginaReal(state.currentPage);
    });

    // "Agregar texto" / "Texto" del panel: NO tenía manejador, así que el usuario
    // pulsaba y no pasaba nada (de ahí "no me deja agregar otro ítem"). El único
    // sitio desde donde se podía era el botón de la barra de iconos (btnAddText).
    $('toolTexto')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        setTool('text');
        mostrarToast('Haz clic en el documento donde quieras escribir el texto.', 'ok');
    });

    // ==================== INSERTAR PÁGINA EN BLANCO ====================
    // Tiene su propia entrada en el panel «Páginas» desde el 30-jul-2026. Antes solo se
    // llegaba haciendo DOBLE CLIC en «Organizar páginas», que se llama otra cosa: la
    // función existía y funcionaba, pero no había forma de encontrarla.
    const _abrirInsertarPagina = () => { if (!_necesitaPDF()) _abrirModal('modalInsertarPag'); };
    $('toolInsertarPag')?.addEventListener('click', _abrirInsertarPagina);
    $('toolOrganizarPag')?.addEventListener('dblclick', _abrirInsertarPagina);   // como antes
    $('btnCerrarInsertarPag')?.addEventListener('click', () => _cerrarModal('modalInsertarPag'));
    $('btnCancelarInsertarPag')?.addEventListener('click', () => _cerrarModal('modalInsertarPag'));
    $('btnEjecutarInsertarPag')?.addEventListener('click', async function() {
        if (!state.pdfBytes) return;
        const pos = $('selectPosInsertarPag').value;
        const tam = $('selectTamInsertarPag').value;
        const tamaños = { letter: [612,792], a4: [595,842], legal: [612,1008] };
        const [w,h] = tamaños[tam] || [612,792];
        let insertIdx;
        if (pos === 'antes') insertIdx = state.currentPage - 1;
        else if (pos === 'despues') insertIdx = state.currentPage;
        else if (pos === 'inicio') insertIdx = 0;
        else insertIdx = state.totalPages;
        showLoading(true);
        try {
            await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
            const { PDFDocument } = PDFLib;
            const doc = await PDFDocument.load(state.pdfBytes);
            doc.insertPage(insertIdx, [w, h]);
            const bytes = await doc.save();
            await _cambiarDocumento(bytes, 'la página insertada');
            _cerrarModal('modalInsertarPag');
            mostrarToast('Página en blanco insertada', 'ok');
        } catch(e) { mostrarToast('Error: ' + e.message, 'error'); }
        finally { showLoading(false); }
    });

    // ==================== EXPORTAR COMO TEXTO ====================
    async function exportarComoTexto() {
        if (_necesitaPDF()) return;
        _ocultarError('errorExportTexto');
        _abrirModal('modalExportTexto');
    }
    // Exportaciones REALES a Office (backend: pdf2docx / pdfplumber / python-pptx)
    let _convirtiendo = false;

    function exportarOficina(endpoint, extension, etiqueta) {
        if (_necesitaPDF()) return;
        // La conversión reconstruye el documento página a página para que el archivo
        // salga EDITABLE (párrafos y tablas de verdad, no una foto de cada hoja), y eso
        // en un documento largo son decenas de segundos. Antes solo salía un aviso que
        // decía "unos segundos" y desaparecía: la pantalla se quedaba igual, el usuario
        // daba por hecho que no funcionaba y recargaba —y al recargar se corta la
        // petición a medias, que es lo que quedaba en el registro del servidor como
        // descarga fallida—. Ahora se bloquea la pantalla, se avisa de lo que puede
        // tardar y se cuentan los segundos.
        if (_convirtiendo) {
            mostrarToast('Ya se está convirtiendo el documento: espere a que termine.', 'warn');
            return;
        }
        _convirtiendo = true;
        const inicio = Date.now();
        const pintar = () => showLoading(true,
            'Convirtiendo a ' + etiqueta + '… ' + Math.round((Date.now() - inicio) / 1000) + ' s\n' +
            'En documentos largos puede pasar del minuto.\nNo cierre ni recargue la página.');
        pintar();
        const reloj = setInterval(pintar, 1000);
        const terminar = () => { clearInterval(reloj); _convirtiendo = false; showLoading(false); };
        _operacionBackend(endpoint, {}, 'documento.' + extension, null)
            .then(() => {
                terminar();
                mostrarToast(etiqueta + ' descargado (' +
                             Math.round((Date.now() - inicio) / 1000) + ' s). Búsquelo en las descargas del navegador.', 'ok');
            })
            .catch(err => {
                terminar();
                mostrarToast('Error al convertir a ' + etiqueta + ': ' + err.message, 'error');
            });
    }
    $('toolExportWord')?.addEventListener('click', () => exportarOficina('pdf-a-word', 'docx', 'Word'));
    $('toolExportPPT')?.addEventListener('click', () => exportarOficina('pdf-a-ppt', 'pptx', 'PowerPoint'));
    $('toolExportExcel')?.addEventListener('click', () => exportarOficina('pdf-a-excel', 'xlsx', 'Excel'));
    $('btnCerrarExportTexto')?.addEventListener('click', () => _cerrarModal('modalExportTexto'));
    $('btnCancelarExportTexto')?.addEventListener('click', () => _cerrarModal('modalExportTexto'));
    async function _extraerTextoCompleto() {
        const formData = new FormData();
        formData.append('archivo', _getPdfBlob(), 'documento.pdf');
        const resp = await fetch('/api/pdf/operacion/ocr', { method: 'POST', body: formData });
        const datos = await resp.json();
        if (!datos.exito) throw new Error(datos.mensaje);
        return datos.datos.texto_total || '';
    }

    // El texto extraído se descarga como Word para poder seguir editándolo
    // (pedido del usuario: preferir Word en vez de .txt)
    async function _descargarTextoComoWord(texto, nombre) {
        const r = await fetch('/api/pdf/operacion/texto-a-word', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto, nombre })
        });
        if (!r.ok) {
            const d = await r.json().catch(() => ({}));
            throw new Error(d.mensaje || 'no se pudo generar el Word');
        }
        _descargarBlob(await r.blob(), nombre + '.docx');
    }

    $('btnEjecutarExportTexto')?.addEventListener('click', async function() {
        this.textContent = 'Extrayendo...'; this.disabled = true;
        try {
            const texto = await _extraerTextoCompleto();
            await _descargarTextoComoWord(texto, 'documento');
            _cerrarModal('modalExportTexto');
            mostrarToast('Texto exportado como Word (.docx)', 'ok');
        } catch(e) { _mostrarError('errorExportTexto', 'Error: ' + e.message); }
        finally { this.innerHTML = '<i class="bi bi-file-earmark-word"></i> Descargar como Word'; this.disabled = false; }
    });

    $('btnExportTextoTxt')?.addEventListener('click', async function() {
        this.textContent = 'Extrayendo...'; this.disabled = true;
        try {
            const texto = await _extraerTextoCompleto();
            const blob = new Blob([texto], { type: 'text/plain;charset=utf-8' });
            _descargarBlob(blob, 'documento.txt');
            _cerrarModal('modalExportTexto');
            mostrarToast('Texto exportado como .txt', 'ok');
        } catch(e) { _mostrarError('errorExportTexto', 'Error: ' + e.message); }
        finally { this.textContent = 'Solo texto (.txt)'; this.disabled = false; }
    });

    // ==================== EXPORTAR IMAGEN (página actual) ====================
    $('toolExportImage')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        // El canvas es por página desde el render multipágina: tomar el de la página actual
        const cvsPag = document.querySelector('#pageWrapper_' + state.currentPage + ' canvas');
        if (!cvsPag) { mostrarToast('La página actual aún no está renderizada.', 'error'); return; }
        cvsPag.toBlob(blob => {
            _descargarBlob(blob, 'pagina_' + state.currentPage + '.png');
            mostrarToast('Imagen de la página ' + state.currentPage + ' descargada', 'ok');
        }, 'image/png');
    });

    $('btnConvertir')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        exportarComoTexto();
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _descargarTextoComoWord, exportarComoTexto });
};
