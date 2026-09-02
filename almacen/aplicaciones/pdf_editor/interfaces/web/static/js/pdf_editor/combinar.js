/* ============================================================
   Raíces Maquita - Editor PDF: combinar PDFs (modal, servidor + fallback pdf-lib)
   Extraido del template pdf_editor/index.html para modularizar el frontend.
   La configuracion que antes inyectaba Jinja llega en window.PDF_EDITOR_CFG
   (definido inline en el template antes de cargar este archivo).
   IMPORTANTE: nginx sirve /static con cache de 1 anio; cualquier
   cambio aqui exige subir la version ?v= en el template.
   ============================================================ */
(function() {
    'use strict';

    // Estado: lista de File objects a combinar
    let archivosACombinar = [];

    // Resultado combinado a la espera de confirmación (descargar o editar)
    let resultadoCombinado = null;

    function ocultarResultadoCombinado() {
        resultadoCombinado = null;
        var el = document.getElementById('resultadoCombinar');
        if (el) el.style.display = 'none';
    }

    function mostrarResultadoCombinado(blob, nombre) {
        resultadoCombinado = { blob: blob, nombre: nombre };
        setProgreso(false);
        var conElAbierto = archivosACombinar.some(function(f) { return f.esDocumentoAbierto; });
        document.getElementById('textoResultadoCombinar').textContent =
            'PDF combinado listo (' + archivosACombinar.length + ' archivos, ' +
            formatearTamano(blob.size) + '). ' +
            (conElAbierto
                ? 'Elige qué hacer: descargarlo, o seguir aquí con él (sustituye a lo que tienes abierto).'
                : '¿Quieres descargarlo ahora o abrirlo aquí para seguir trabajando?');
        var botonEditar = document.getElementById('btnEditarCombinado');
        if (botonEditar) {
            botonEditar.innerHTML = conElAbierto
                ? '<i class="bi bi-pencil-square"></i> Seguir aquí con el combinado'
                : '<i class="bi bi-pencil-square"></i> Abrir en el editor';
        }
        document.getElementById('resultadoCombinar').style.display = 'block';
    }

    function descargarResultadoCombinado() {
        if (!resultadoCombinado) return;
        var url = URL.createObjectURL(resultadoCombinado.blob);
        var a = document.createElement('a');
        a.download = resultadoCombinado.nombre;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        cerrarModal();
    }

    function editarResultadoCombinado() {
        if (!resultadoCombinado) return;
        var nombre = resultadoCombinado.nombre;
        resultadoCombinado.blob.arrayBuffer().then(function(buf) {
            if (window.abrirPDFEnEditor && window.abrirPDFEnEditor(buf, nombre)) cerrarModal();
        });
    }

    // ---------- Funciones globales (necesarias para onclick en HTML dinámico) ----------

    window.moverArchivoCombinar = function(idx, dir) {
        const nuevoIdx = idx + dir;
        if (nuevoIdx < 0 || nuevoIdx >= archivosACombinar.length) return;
        [archivosACombinar[idx], archivosACombinar[nuevoIdx]] = [archivosACombinar[nuevoIdx], archivosACombinar[idx]];
        renderizarLista();
    };

    window.eliminarArchivoCombinar = function(idx) {
        archivosACombinar.splice(idx, 1);
        renderizarLista();
    };

    // ---------- Funciones internas ----------

    function formatearTamano(bytes) {
        if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
        return Math.round(bytes / 1024) + ' KB';
    }

    function renderizarLista() {
        const ul        = document.getElementById('ulArchivosCombinar');
        const contador  = document.getElementById('contadorCombinar');
        const listaCont = document.getElementById('listaCombinar');
        const btnExec   = document.getElementById('btnEjecutarCombinar');

        // Cualquier cambio en la lista invalida un resultado anterior
        ocultarResultadoCombinado();

        if (archivosACombinar.length === 0) {
            listaCont.style.display = 'none';
            btnExec.disabled = true;
            return;
        }

        listaCont.style.display = 'block';
        btnExec.disabled = (archivosACombinar.length < 2);
        contador.textContent = archivosACombinar.length + ' archivo' + (archivosACombinar.length !== 1 ? 's' : '');

        ul.innerHTML = '';
        archivosACombinar.forEach(function(archivo, idx) {
            var li = document.createElement('li');
            li.style.cssText = 'display:flex;align-items:center;padding:9px 12px;border-bottom:1px solid #e5e5e5;gap:8px;background:white;';
            if (idx === archivosACombinar.length - 1) li.style.borderBottom = 'none';
            // El que ya está abierto se distingue a simple vista: es el que el
            // usuario NO ha subido, y saber cuál es evita el susto de creer que
            // se coló un archivo de más.
            var esElAbierto = !!archivo.esDocumentoAbierto;
            var etiqueta = esElAbierto
                ? '<span style="font-size:10px;font-weight:600;color:#166534;background:#dcfce7;border-radius:3px;padding:1px 6px;flex-shrink:0;">documento abierto</span>'
                : '';
            li.innerHTML =
                '<span style="color:#6d6d6d;font-size:11px;min-width:18px;text-align:center;font-weight:600;">' + (idx + 1) + '</span>' +
                '<i class="bi bi-file-earmark-pdf" style="color:#dc2626;flex-shrink:0;font-size:15px;"></i>' +
                '<span style="flex:1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + archivo.name + '">' + archivo.name + '</span>' +
                etiqueta +
                '<span style="font-size:11px;color:#6d6d6d;flex-shrink:0;">' + formatearTamano(archivo.size) + '</span>' +
                '<div style="display:flex;gap:3px;flex-shrink:0;">' +
                    '<button onclick="moverArchivoCombinar(' + idx + ', -1)" style="background:none;border:1px solid #e5e5e5;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:11px;color:#444;" title="Subir"' + (idx === 0 ? ' disabled' : '') + '>↑</button>' +
                    '<button onclick="moverArchivoCombinar(' + idx + ', 1)"  style="background:none;border:1px solid #e5e5e5;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:11px;color:#444;" title="Bajar"' + (idx === archivosACombinar.length - 1 ? ' disabled' : '') + '>↓</button>' +
                    '<button onclick="eliminarArchivoCombinar(' + idx + ')"  style="background:none;border:1px solid #fca5a5;border-radius:3px;padding:2px 6px;cursor:pointer;font-size:11px;color:#dc2626;" title="Quitar">×</button>' +
                '</div>';
            ul.appendChild(li);
        });
    }

    function agregarArchivos(files) {
        var nuevos = Array.from(files).filter(function(f) {
            return f.name.toLowerCase().endsWith('.pdf');
        });
        if (nuevos.length === 0) {
            mostrarError('Solo se aceptan archivos PDF.');
            return;
        }
        archivosACombinar = archivosACombinar.concat(nuevos);
        ocultarError();
        renderizarLista();
    }

    function mostrarError(msg) {
        var el = document.getElementById('errorCombinar');
        el.textContent = msg;
        el.style.display = 'block';
    }

    function ocultarError() {
        document.getElementById('errorCombinar').style.display = 'none';
    }

    function setProgreso(visible, texto, pct) {
        var cont = document.getElementById('progresoCombinar');
        var barra = document.getElementById('barraProgresoCombinar');
        var txtEl = document.getElementById('textoProgresoCombinar');
        cont.style.display = visible ? 'block' : 'none';
        if (visible) {
            barra.style.width = (pct || 0) + '%';
            txtEl.textContent = texto || 'Procesando...';
        }
    }

    // ---------- Abrir / cerrar modal ----------

    // El documento que se está editando entra en la lista el primero, para poder
    // «combinar con el actual» sin tener que guardarlo y volver a subirlo — que
    // era lo que había que hacer antes (pedido del usuario, 17-08-2026). Se coge
    // tal como está AHORA, con los cambios hechos. Se puede quitar de la lista
    // con la × de siempre, así que sigue valiendo para juntar archivos sueltos.
    function _documentoAbierto() {
        try {
            var abierto = window.documentoAbiertoEnEditor && window.documentoAbiertoEnEditor();
            if (!abierto || !abierto.blob) return null;
            var archivo = new File([abierto.blob], abierto.nombre || 'documento.pdf',
                                   { type: 'application/pdf' });
            archivo.esDocumentoAbierto = true;
            return archivo;
        } catch (e) {
            return null;      // sin documento abierto se combina como siempre
        }
    }

    window.abrirModalCombinar = function() {
        archivosACombinar = [];
        var abierto = _documentoAbierto();
        if (abierto) archivosACombinar.push(abierto);
        renderizarLista();
        document.getElementById('inputCombinar').value = '';
        ocultarError();
        setProgreso(false);
        document.getElementById('modalCombinar').classList.remove('hidden');
    };

    function cerrarModal() {
        document.getElementById('modalCombinar').classList.add('hidden');
    }

    // ---------- Ejecutar combinación ----------

    // Fallback client-side: combinar PDFs con pdf-lib cuando el servidor falla
    async function combinarClientSide(archivos) {
        await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
        const { PDFDocument } = PDFLib;
        const pdfFinal = await PDFDocument.create();
        for (let i = 0; i < archivos.length; i++) {
            setProgreso(true, 'Procesando archivo ' + (i+1) + ' de ' + archivos.length + '...', Math.round(20 + (i/archivos.length)*60));
            const bytes = await archivos[i].arrayBuffer();
            try {
                const docOrigen = await PDFDocument.load(bytes);
                const paginas = await pdfFinal.copyPages(docOrigen, docOrigen.getPageIndices());
                paginas.forEach(p => pdfFinal.addPage(p));
            } catch(err) {
                throw new Error('Error en "' + archivos[i].name + '": ' + err.message);
            }
        }
        return await pdfFinal.save();
    }

    async function ejecutarCombinar() {
        if (archivosACombinar.length < 2) return;

        var btnExec = document.getElementById('btnEjecutarCombinar');
        var textoOrig = btnExec.innerHTML;
        btnExec.innerHTML = '<i class="bi bi-hourglass-split"></i> Combinando...';
        btnExec.disabled = true;
        ocultarError();
        ocultarResultadoCombinado();

        var nombreBase = archivosACombinar[0].name.replace(/\.pdf$/i, '');
        var usarServidor = true;

        try {
            // Intentar primero con el servidor (más rápido para PDFs grandes)
            setProgreso(true, 'Enviando archivos al servidor...', 20);
            var formData = new FormData();
            archivosACombinar.forEach(function(f) {
                formData.append('archivos', f);
            });
            var resp = await fetch('/api/pdf/combinar', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });

            if (!resp.ok) {
                var datos = {};
                try { datos = await resp.json(); } catch(e) {}
                // Si el servidor falla, usar fallback client-side
                throw new Error(datos.mensaje || 'Servidor: ' + resp.status);
            }

            setProgreso(true, 'Preparando el resultado...', 90);
            var blob = await resp.blob();
            mostrarResultadoCombinado(blob, nombreBase + '_combinado.pdf');

        } catch(errServidor) {
            // Fallback: combinar en el navegador con pdf-lib
            console.warn('Combinar servidor falló, usando client-side:', errServidor.message);
            usarServidor = false;
            try {
                setProgreso(true, 'Combinando en el navegador...', 30);
                var pdfBytes = await combinarClientSide(archivosACombinar);
                setProgreso(true, 'Preparando el resultado...', 90);
                var blob = new Blob([pdfBytes], { type: 'application/pdf' });
                mostrarResultadoCombinado(blob, nombreBase + '_combinado.pdf');
            } catch(errLocal) {
                setProgreso(false);
                mostrarError('Error al combinar: ' + errLocal.message);
                btnExec.innerHTML = textoOrig;
                btnExec.disabled = (archivosACombinar.length < 2);
                return;
            }
        }

        // El resultado queda a la espera de que el usuario elija descargar o editar
        btnExec.innerHTML = textoOrig;
        btnExec.disabled = (archivosACombinar.length < 2);
    }

    // ---------- Inicializar eventos cuando el DOM esté listo ----------

    // Inicializar combinar - usar optional chaining para evitar errores null
    (function initCombinar() {
        var dropZona = document.getElementById('dropZonaCombinar');
        var inputCombinar = document.getElementById('inputCombinar');
        var btnAgregar = document.getElementById('btnAgregarMasCombinar');
        var btnEjecutar = document.getElementById('btnEjecutarCombinar');
        var btnCancelar = document.getElementById('btnCancelarCombinar');
        var btnCerrar = document.getElementById('btnCerrarCombinar');
        var modalEl = document.getElementById('modalCombinar');

        if (!dropZona || !inputCombinar) return;

        dropZona.addEventListener('click', function() { inputCombinar.click(); });
        inputCombinar.addEventListener('change', function(e) { agregarArchivos(e.target.files); e.target.value = ''; });
        if (btnAgregar) btnAgregar.addEventListener('click', function() { inputCombinar.click(); });
        if (btnEjecutar) btnEjecutar.addEventListener('click', ejecutarCombinar);
        if (btnCancelar) btnCancelar.addEventListener('click', cerrarModal);
        if (btnCerrar) btnCerrar.addEventListener('click', cerrarModal);
        var btnDescargarComb = document.getElementById('btnDescargarCombinado');
        var btnEditarComb = document.getElementById('btnEditarCombinado');
        if (btnDescargarComb) btnDescargarComb.addEventListener('click', descargarResultadoCombinado);
        if (btnEditarComb) btnEditarComb.addEventListener('click', editarResultadoCombinado);
        if (modalEl) modalEl.addEventListener('click', function(e) { if (e.target === this) cerrarModal(); });

        dropZona.addEventListener('dragover', function(e) { e.preventDefault(); this.style.borderColor = '#1473e6'; this.style.background = '#e8f0fe'; });
        dropZona.addEventListener('dragleave', function() { this.style.borderColor = '#e5e5e5'; this.style.background = '#fafafa'; });
        dropZona.addEventListener('drop', function(e) { e.preventDefault(); this.style.borderColor = '#e5e5e5'; this.style.background = '#fafafa'; agregarArchivos(e.dataTransfer.files); });
    })();

})();
