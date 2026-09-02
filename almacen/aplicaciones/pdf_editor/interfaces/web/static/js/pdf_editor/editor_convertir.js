/* ============================================================
   Raíces Maquita — Editor PDF · convertir
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.convertir = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _abrirModal, _cerrarModal, _descargarBlob, _getPdfBlob, _necesitaPDF, _ocultarError, _operacionBackend, fileInput, mostrarToast, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const abrirEdicionTablas = (...a) => E.abrirEdicionTablas(...a);   // parte tablas_ocr
    const downloadPDF = (...a) => E.downloadPDF(...a);   // parte compartir
    const exportarComoTexto = (...a) => E.exportarComoTexto(...a);   // parte buscar_exportar
    const setTool = (...a) => E.setTool(...a);   // parte herramientas
    // ==================== HERRAMIENTAS EN OTRAS PESTAÑAS (aliases) ====================
    // Comprimir en pestaña Convertir y Firmar
    $('toolComprimirConv')?.addEventListener('click', () => { if (!_necesitaPDF()) { _ocultarError('errorComprimir'); _abrirModal('modalComprimir'); } });
    $('toolComprimirFirma')?.addEventListener('click', () => { if (!_necesitaPDF()) { _ocultarError('errorComprimir'); _abrirModal('modalComprimir'); } });
    // OCR en pestaña Convertir y Firmar
    $('toolOCRConv')?.addEventListener('click', () => abrirEdicionTablas());
    $('toolOCRFirma')?.addEventListener('click', () => abrirEdicionTablas());
    // Exportar a RTF: se hace igual que exportar el texto
    $('toolExportRTF')?.addEventListener('click', () => exportarComoTexto());
    // Convertir a PDF — modal para convertir imágenes a PDF (client-side con pdf-lib)
    function abrirModalConvertirPDF(modoCrear) {
        // Crear modal si no existe
        let modal = document.getElementById('modalConvertirPDF');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'modalConvertirPDF';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';
            modal.innerHTML = `
                <div style="background:#fff;border-radius:12px;padding:30px;max-width:500px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
                    <h3 style="margin:0 0 8px;color:#2c2c2c;font-size:18px;"><i class="bi bi-file-earmark-plus"></i> Convertir a PDF</h3>
                    <p style="color:#6d6d6d;font-size:13px;margin:0 0 16px;">Selecciona documentos de Office (Word, Excel, PowerPoint), imágenes o archivos de texto para convertirlos a PDF.</p>
                    <div id="dropConvertir" style="border:2px dashed #1473e6;border-radius:8px;padding:40px 20px;text-align:center;cursor:pointer;background:#f8fbff;transition:background 0.2s;">
                        <i class="bi bi-cloud-upload" style="font-size:36px;color:#1473e6;"></i>
                        <p style="margin:8px 0 0;color:#1473e6;font-weight:500;">Arrastra archivos aquí o haz clic para seleccionar</p>
                        <p style="margin:4px 0 0;color:#999;font-size:12px;">Formatos: DOC(X), XLS(X), PPT(X), ODT/ODS/ODP, RTF, HTML, CSV, JPG, PNG, GIF, BMP, WEBP, TXT</p>
                        <input type="file" id="inputConvertirFiles" multiple accept="image/*,.txt,.doc,.docx,.odt,.rtf,.html,.htm,.xls,.xlsx,.ods,.csv,.ppt,.pptx,.odp" style="display:none;">
                    </div>
                    <div id="listaConvertirFiles" style="margin-top:12px;max-height:150px;overflow-y:auto;"></div>
                    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
                        <button id="btnCerrarConvertir" style="padding:8px 20px;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;font-size:14px;">Cancelar</button>
                        <button id="btnEjecutarConvertir" style="padding:8px 20px;border:none;border-radius:6px;background:#1473e6;color:#fff;cursor:pointer;font-size:14px;font-weight:500;" disabled>Convertir a PDF</button>
                    </div>
                </div>`;
            document.body.appendChild(modal);

            const dropZone  = modal.querySelector('#dropConvertir');
            const fileInput = modal.querySelector('#inputConvertirFiles');
            const listaDiv  = modal.querySelector('#listaConvertirFiles');
            const btnConv   = modal.querySelector('#btnEjecutarConvertir');
            let archivos    = [];

            dropZone.addEventListener('click', () => fileInput.click());
            dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.style.background = '#e8f0fe'; });
            dropZone.addEventListener('dragleave', () => { dropZone.style.background = '#f8fbff'; });
            dropZone.addEventListener('drop', e => {
                e.preventDefault();
                dropZone.style.background = '#f8fbff';
                agregarArchivos(e.dataTransfer.files);
            });
            fileInput.addEventListener('change', () => agregarArchivos(fileInput.files));

            // Extensiones de oficina que convierte el backend (Gotenberg/LibreOffice)
            const EXT_OFICINA = ['.doc', '.docx', '.odt', '.rtf', '.html', '.htm', '.xls', '.xlsx', '.ods', '.csv', '.ppt', '.pptx', '.odp'];
            const _esOficina = nombre => EXT_OFICINA.some(ext => nombre.toLowerCase().endsWith(ext));

            function agregarArchivos(files) {
                const rechazados = [];
                for (const f of files) {
                    if (f.type.startsWith('image/') || f.type === 'text/plain' || f.name.toLowerCase().endsWith('.txt') || _esOficina(f.name)) {
                        archivos.push(f);
                    } else {
                        rechazados.push(f.name);
                    }
                }
                if (rechazados.length > 0) {
                    mostrarToast('Archivos no soportados (Office, imagenes o TXT): ' + rechazados.join(', '), 'error');
                }
                renderLista();
            }
            function renderLista() {
                listaDiv.innerHTML = archivos.map((f, i) =>
                    '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 8px;border-bottom:1px solid #eee;">' +
                    '<span style="font-size:13px;"><i class="bi bi-file-image"></i> ' + f.name + ' (' + (f.size/1024).toFixed(0) + ' KB)</span>' +
                    '<button data-idx="' + i + '" style="border:none;background:none;color:#fa0f00;cursor:pointer;font-size:16px;">×</button></div>'
                ).join('');
                listaDiv.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
                    archivos.splice(parseInt(b.dataset.idx), 1);
                    renderLista();
                }));
                btnConv.disabled = archivos.length === 0;
            }

            modal.querySelector('#btnCerrarConvertir').addEventListener('click', () => {
                modal.style.display = 'none';
                archivos = [];
                listaDiv.innerHTML = '';
                btnConv.disabled = true;
            });
            modal.addEventListener('click', e => {
                if (e.target === modal) { modal.style.display = 'none'; archivos = []; listaDiv.innerHTML = ''; btnConv.disabled = true; }
            });

            btnConv.addEventListener('click', async () => {
                if (archivos.length === 0) return;
                btnConv.disabled   = true;
                btnConv.textContent = 'Convirtiendo...';
                try {
                    await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
                    const { PDFDocument } = PDFLib;
                    const pdfDoc = await PDFDocument.create();

                    for (const archivo of archivos) {
                        if (_esOficina(archivo.name)) {
                            // Word/Excel/PowerPoint/ODF/RTF/HTML/CSV: convierte el backend (Gotenberg)
                            const fd = new FormData();
                            fd.append('archivo', archivo, archivo.name);
                            const r = await fetch('/api/pdf/operacion/convertir-oficina', { method: 'POST', body: fd, credentials: 'same-origin' });
                            if (!r.ok) {
                                const d = await r.json().catch(() => ({}));
                                throw new Error(archivo.name + ': ' + (d.mensaje || 'error ' + r.status));
                            }
                            const pdfOficina = await PDFDocument.load(await r.arrayBuffer());
                            const paginas = await pdfDoc.copyPages(pdfOficina, pdfOficina.getPageIndices());
                            paginas.forEach(p => pdfDoc.addPage(p));
                        } else if (archivo.type.startsWith('image/')) {
                            const bytes = await archivo.arrayBuffer();
                            let img;
                            const ext = archivo.name.toLowerCase();
                            if (ext.endsWith('.png')) {
                                img = await pdfDoc.embedPng(bytes);
                            } else if (ext.endsWith('.jpg') || ext.endsWith('.jpeg')) {
                                img = await pdfDoc.embedJpg(bytes);
                            } else {
                                // Para GIF, BMP, WEBP: convertir a PNG via canvas
                                const blob   = new Blob([bytes], { type: archivo.type });
                                const bmpUrl = URL.createObjectURL(blob);
                                const imgEl  = new Image();
                                await new Promise((res, rej) => { imgEl.onload = res; imgEl.onerror = rej; imgEl.src = bmpUrl; });
                                const cvs = document.createElement('canvas');
                                cvs.width = imgEl.naturalWidth; cvs.height = imgEl.naturalHeight;
                                cvs.getContext('2d').drawImage(imgEl, 0, 0);
                                URL.revokeObjectURL(bmpUrl);
                                const pngBlob = await new Promise(r => cvs.toBlob(r, 'image/png'));
                                const pngBuf  = await pngBlob.arrayBuffer();
                                img = await pdfDoc.embedPng(pngBuf);
                            }
                            const page = pdfDoc.addPage([img.width, img.height]);
                            page.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
                        } else if (archivo.type === 'text/plain' || archivo.name.endsWith('.txt')) {
                            const texto = await archivo.text();
                            let page    = pdfDoc.addPage([595, 842]); // A4
                            const font  = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
                            const lines = texto.split('\n');
                            let y = 800;
                            for (const line of lines) {
                                if (y < 40) { page = pdfDoc.addPage([595, 842]); y = 800; }
                                page.drawText(line.substring(0, 100), { x: 40, y, size: 11, font });
                                y -= 16;
                            }
                        }
                    }

                    const pdfBytes = await pdfDoc.save();
                    if (modal.dataset.modo === 'crear') {
                        // "Crear un PDF": abre el PDF generado en el editor para seguir trabajando
                        const ok = window.abrirPDFEnEditor(pdfBytes.buffer, 'documento_nuevo.pdf');
                        if (!ok) return;   // el usuario canceló descartar cambios: deja el modal abierto
                    } else {
                        const blob = new Blob([pdfBytes], { type: 'application/pdf' });
                        const url  = URL.createObjectURL(blob);
                        const a    = document.createElement('a');
                        a.href = url; a.download = 'convertido.pdf'; a.click();
                        URL.revokeObjectURL(url);
                        mostrarToast('PDF generado y descargado exitosamente', 'success');
                    }
                    modal.style.display = 'none';
                    archivos = [];
                    listaDiv.innerHTML = '';
                } catch (err) {
                    console.error('Error al convertir:', err);
                    mostrarToast('Error al convertir: ' + err.message, 'error');
                } finally {
                    btnConv.disabled    = false;
                    btnConv.textContent = modal.dataset.modo === 'crear' ? 'Crear PDF' : 'Convertir a PDF';
                }
            });
        }
        // Ajusta el modo en cada apertura (el modal se construye una sola vez):
        // 'crear' -> el resultado se abre en el editor; 'convertir' -> se descarga.
        modal.dataset.modo = modoCrear ? 'crear' : 'convertir';
        const _h3  = modal.querySelector('h3');
        const _btn = modal.querySelector('#btnEjecutarConvertir');
        const _p   = modal.querySelector('h3 + p');
        if (_h3) _h3.innerHTML = '<i class="bi bi-file-earmark-plus"></i> ' + (modoCrear ? 'Crear un PDF' : 'Convertir a PDF');
        if (_p)  _p.textContent = modoCrear
            ? 'Selecciona una o varias imágenes, documentos de Office (Word, Excel, PowerPoint) o archivos de texto para crear un PDF nuevo y editarlo aquí.'
            : 'Selecciona documentos de Office (Word, Excel, PowerPoint), imágenes o archivos de texto para convertirlos a PDF.';
        if (_btn && _btn.textContent !== 'Convirtiendo...') _btn.textContent = modoCrear ? 'Crear PDF' : 'Convertir a PDF';
        modal.style.display = 'flex';
    }

    $('toolConvertirAPDF')?.addEventListener('click', () => abrirModalConvertirPDF());
    $('toolConvertirFirma')?.addEventListener('click', () => abrirModalConvertirPDF());
    // ==================== CAMPOS DE FORMULARIO INTERACTIVOS ====================
    // Flujo: modal define tipo/nombre → clic en la página coloca la caja punteada →
    // al descargar, downloadPDF crea el campo AcroForm real con pdf-lib.
    let _contadorCampos = 0;
    function abrirModalFormulario() {
        if (_necesitaPDF()) return;
        $('inputNombreCampo').value = '';
        $('inputOpcionesCampo').value = '';
        _abrirModal('modalFormulario');
    }
    $('toolFormularioEdit')?.addEventListener('click', () => abrirModalFormulario());
    $('selectTipoCampo')?.addEventListener('change', function() {
        $('filaOpcionesCampo').style.display = this.value === 'lista' ? 'block' : 'none';
    });
    $('btnCerrarFormulario')?.addEventListener('click', () => _cerrarModal('modalFormulario'));
    $('btnCancelarFormulario')?.addEventListener('click', () => _cerrarModal('modalFormulario'));
    $('btnColocarCampo')?.addEventListener('click', () => {
        const subtipo = $('selectTipoCampo').value;
        const opciones = $('inputOpcionesCampo').value;
        if (subtipo === 'lista' && !opciones.trim()) {
            mostrarToast('Indica las opciones de la lista (separadas por coma).', 'error');
            return;
        }
        _contadorCampos++;
        const nombre = ($('inputNombreCampo').value.trim() || (subtipo + '_' + _contadorCampos)).replace(/\s+/g, '_');
        state.campoFormPendiente = { subtipo: subtipo, nombre: nombre, opciones: opciones };
        _cerrarModal('modalFormulario');
        setTool('form');
        mostrarToast('Haz clic en la página donde quieras colocar el campo "' + nombre + '".', 'ok');
    });

    // ==================== COMPARAR DOS PDFs ====================
    $('toolComparar')?.addEventListener('click', () => {
        const chk = $('chkCompararUsarActual');
        if (chk) {
            chk.disabled = !state.pdfDoc;
            chk.checked = !!state.pdfDoc;
        }
        _actualizarFilaComparar();
        _abrirModal('modalComparar');
    });
    function _actualizarFilaComparar() {
        const usar = $('chkCompararUsarActual')?.checked;
        const fila = $('filaCompararOriginal');
        if (fila) fila.style.display = usar ? 'none' : 'block';
    }
    $('chkCompararUsarActual')?.addEventListener('change', _actualizarFilaComparar);
    $('btnCerrarComparar')?.addEventListener('click', () => _cerrarModal('modalComparar'));
    $('btnCancelarComparar')?.addEventListener('click', () => _cerrarModal('modalComparar'));
    $('btnEjecutarComparar')?.addEventListener('click', async function() {
        const usarActual = $('chkCompararUsarActual').checked && state.pdfDoc;
        const fOrig = $('inputCompararOriginal').files[0];
        const fMod  = $('inputCompararModificado').files[0];
        if (!usarActual && !fOrig) { mostrarToast('Selecciona el PDF original.', 'error'); return; }
        if (!fMod) { mostrarToast('Selecciona el PDF modificado.', 'error'); return; }
        this.disabled = true;
        const restaurar = this.innerHTML;
        this.innerHTML = '<i class="bi bi-hourglass-split"></i> Comparando...';
        try {
            const fd = new FormData();
            fd.append('archivo_original', usarActual ? _getPdfBlob() : fOrig, usarActual ? 'documento.pdf' : fOrig.name);
            fd.append('archivo_modificado', fMod, fMod.name);
            const r = await fetch('/api/pdf/operacion/comparar', { method: 'POST', body: fd, credentials: 'same-origin' });
            if (!r.ok) {
                const d = await r.json().catch(() => ({}));
                throw new Error(d.mensaje || 'error ' + r.status);
            }
            _descargarBlob(await r.blob(), 'comparacion.pdf');
            mostrarToast('Reporte de comparación descargado.', 'ok');
            _cerrarModal('modalComparar');
        } catch (err) {
            mostrarToast('Error al comparar: ' + err.message, 'error');
        }
        this.disabled = false;
        this.innerHTML = restaurar;
    });

    // ==================== HERRAMIENTAS PREMIUM: NUMERAR / DIVIDIR / DESBLOQUEAR ====================

    // --- Numerar páginas (backend /operacion/numerar-páginas) ---
    $('toolNumerar')?.addEventListener('click', () => { if (!_necesitaPDF()) _abrirModal('modalNumerar'); });
    $('btnCerrarNumerar')?.addEventListener('click', () => _cerrarModal('modalNumerar'));
    $('btnCancelarNumerar')?.addEventListener('click', () => _cerrarModal('modalNumerar'));
    $('btnEjecutarNumerar')?.addEventListener('click', async function() {
        this.disabled = true;
        const restaurar = this.innerHTML;
        this.innerHTML = '<i class="bi bi-hourglass-split"></i> Numerando...';
        try {
            await _operacionBackend('numerar-paginas', {
                posicion: $('selectPosNumerar').value,
                formato: $('inputFormatoNumerar').value || '{n} de {total}',
                tamano: $('selectTamNumerar').value
            }, 'documento_numerado.pdf', 'errorNumerar', $('chkNumerarAplicar').checked);
            mostrarToast('Números de página aplicados al documento.', 'ok');
            _cerrarModal('modalNumerar');
        } catch (err) {
            mostrarToast('Error al numerar: ' + err.message, 'error');
        }
        this.disabled = false;
        this.innerHTML = restaurar;
    });

    // --- Dividir PDF por rangos (backend /operacion/dividir) ---
    $('toolDividir')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        $('infoTotalDividir').textContent = 'El documento tiene ' + state.totalPages + ' páginas.';
        _abrirModal('modalDividir');
    });
    $('btnCerrarDividir')?.addEventListener('click', () => _cerrarModal('modalDividir'));
    $('btnCancelarDividir')?.addEventListener('click', () => _cerrarModal('modalDividir'));
    $('btnEjecutarDividir')?.addEventListener('click', async function() {
        const rangos = $('inputRangosDividir').value.trim();
        if (!rangos) { mostrarToast('Indica al menos un rango (ej.: 1-3, 5).', 'error'); return; }
        this.disabled = true;
        const restaurar = this.innerHTML;
        this.innerHTML = '<i class="bi bi-hourglass-split"></i> Dividiendo...';
        try {
            // Un solo rango devuelve un PDF; varios rangos devuelven un ZIP
            const nombre = rangos.includes(',') ? 'documento_dividido.zip'
                                                : 'documento_paginas_' + rangos.replace(/\s/g, '') + '.pdf';
            await _operacionBackend('dividir', { rangos: rangos }, nombre, 'errorDividir');
            mostrarToast('División descargada.', 'ok');
            _cerrarModal('modalDividir');
        } catch (err) {
            mostrarToast('Error al dividir: ' + err.message, 'error');
        }
        this.disabled = false;
        this.innerHTML = restaurar;
    });

    // --- Desbloquear PDF (no requiere documento abierto: pide el archivo protegido) ---
    const inputPdfBloqueado = document.createElement('input');
    inputPdfBloqueado.type = 'file';
    inputPdfBloqueado.accept = '.pdf';
    inputPdfBloqueado.style.display = 'none';
    document.body.appendChild(inputPdfBloqueado);
    $('toolDesbloquear')?.addEventListener('click', () => { inputPdfBloqueado.value = ''; inputPdfBloqueado.click(); });
    inputPdfBloqueado.addEventListener('change', async function() {
        const f = this.files && this.files[0];
        if (!f) return;
        const clave = prompt('Contraseña actual de "' + f.name + '":');
        if (clave === null) return;
        mostrarToast('Quitando contraseña…', 'ok');
        try {
            const fd = new FormData();
            fd.append('archivo', f, f.name);
            fd.append('password', clave);
            const r = await fetch('/api/pdf/operacion/desbloquear', { method: 'POST', body: fd, credentials: 'same-origin' });
            if (!r.ok) {
                const d = await r.json().catch(() => ({}));
                throw new Error(d.mensaje || 'error ' + r.status);
            }
            _descargarBlob(await r.blob(), f.name.replace(/\.pdf$/i, '') + '_desbloqueado.pdf');
            mostrarToast('PDF desbloqueado descargado.', 'ok');
        } catch (err) {
            mostrarToast('No se pudo desbloquear: ' + err.message, 'error');
        }
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { abrirModalConvertirPDF, abrirModalFormulario });
};
