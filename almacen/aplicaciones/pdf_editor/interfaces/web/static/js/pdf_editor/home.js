/* ============================================================
   Raíces Maquita - Editor PDF: logica del home (abrir/crear/combinar y traspaso al editor)
   Extraido del template pdf_editor/home.html para modularizar el frontend.
   La configuracion que antes inyectaba Jinja llega en window.PDF_HOME_CFG
   (definido inline en el template antes de cargar este archivo).
   IMPORTANTE: nginx sirve /static con cache de 1 anio; cualquier
   cambio aqui exige subir la version ?v= en el template.
   ============================================================ */
var MAX_PDF_MB = 2048;

// PDFs grandes no caben en sessionStorage (~5 MB): se pasan al editor via IndexedDB
function _guardarPDFGrande(file) {
    return new Promise(function(res, rej) {
        const rq = indexedDB.open('faroPdfEditor', 1);
        rq.onupgradeneeded = function() { rq.result.createObjectStore('pending'); };
        rq.onsuccess = function() {
            const tx = rq.result.transaction('pending', 'readwrite');
            tx.objectStore('pending').put(file, 'pendingPDF');
            tx.oncomplete = function() { res(); };
            tx.onerror = function() { rej(tx.error); };
        };
        rq.onerror = function() { rej(rq.error); };
    });
}

function _irAlEditorConPDFGrande(file) {
    _guardarPDFGrande(file).then(function() {
        sessionStorage.setItem('pendingPDFGrande', '1');
        window.location.href = (window.PDF_HOME_CFG || {}).urlEditorNuevo || '/herramientas/editor-pdf/editor/nuevo';
    }).catch(function(err) {
        alert('No se pudo preparar el PDF para abrirlo (' + (err && err.message ? err.message : err) + '). Intenta abrirlo desde el editor con el botón "Abrir archivo".');
    });
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        alert('Solo se aceptan archivos PDF. Para crear un PDF desde imagenes o texto usa la herramienta "Crear un PDF".');
        return;
    }
    if (file.size > MAX_PDF_MB * 1024 * 1024) {
        alert('El PDF pesa ' + (file.size / 1024 / 1024).toFixed(1) + ' MB y supera el máximo admitido (' + MAX_PDF_MB + ' MB).\n\nComprímelo primero (herramienta "Comprimir un PDF" del editor u otra herramienta) e inténtalo de nuevo.');
        return;
    }
    if (file.size > 3 * 1024 * 1024) {
        // Grande: via IndexedDB (sessionStorage no soporta este tamaño)
        _irAlEditorConPDFGrande(file);
        return;
    }
    // Pequeño: sessionStorage (camino rápido)
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            sessionStorage.setItem('pendingPDF', JSON.stringify({
                name: file.name,
                size: file.size,
                data: e.target.result
            }));
            window.location.href = (window.PDF_HOME_CFG || {}).urlEditorNuevo || '/herramientas/editor-pdf/editor/nuevo';
        } catch (err) {
            // Cuota de sessionStorage excedida: usar IndexedDB
            _irAlEditorConPDFGrande(file);
        }
    };
    reader.readAsDataURL(file);
}

// Crear PDF desde imágenes o TXT (client-side con pdf-lib)
async function handleCrearPDF(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (files.length === 0) return;
    const validos = files.filter(f => f.type.startsWith('image/') || f.name.toLowerCase().endsWith('.txt'));
    const rechazados = files.filter(f => !validos.includes(f));
    if (validos.length === 0) {
        alert('Solo se aceptan imagenes (JPG, PNG, GIF, BMP, WEBP) o archivos TXT.');
        return;
    }
    if (rechazados.length > 0) {
        alert('Se omitieron archivos no soportados: ' + rechazados.map(f => f.name).join(', '));
    }
    try {
        await window.PDFLibListo();   // pdf-lib se carga la primera vez que se usa
        const { PDFDocument, StandardFonts } = PDFLib;
        const pdfDoc = await PDFDocument.create();
        for (const archivo of validos) {
            if (archivo.type.startsWith('image/')) {
                const bytes = await archivo.arrayBuffer();
                let img;
                const nombre = archivo.name.toLowerCase();
                if (nombre.endsWith('.png')) {
                    img = await pdfDoc.embedPng(bytes);
                } else if (nombre.endsWith('.jpg') || nombre.endsWith('.jpeg')) {
                    img = await pdfDoc.embedJpg(bytes);
                } else {
                    // GIF, BMP, WEBP: convertir a PNG via canvas
                    const blob = new Blob([bytes], { type: archivo.type });
                    const url = URL.createObjectURL(blob);
                    const imgEl = new Image();
                    await new Promise((res, rej) => { imgEl.onload = res; imgEl.onerror = rej; imgEl.src = url; });
                    const cvs = document.createElement('canvas');
                    cvs.width = imgEl.naturalWidth; cvs.height = imgEl.naturalHeight;
                    cvs.getContext('2d').drawImage(imgEl, 0, 0);
                    URL.revokeObjectURL(url);
                    const pngBlob = await new Promise(r => cvs.toBlob(r, 'image/png'));
                    img = await pdfDoc.embedPng(await pngBlob.arrayBuffer());
                }
                const page = pdfDoc.addPage([img.width, img.height]);
                page.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
            } else {
                const texto = await archivo.text();
                const font = await pdfDoc.embedFont(StandardFonts.Helvetica);
                let page = pdfDoc.addPage([595, 842]); // A4
                let y = 800;
                for (const line of texto.split('\n')) {
                    if (y < 40) { page = pdfDoc.addPage([595, 842]); y = 800; }
                    page.drawText(line.substring(0, 100), { x: 40, y, size: 11, font });
                    y -= 16;
                }
            }
        }
        const dataUri = await pdfDoc.saveAsBase64({ dataUri: true });
        sessionStorage.setItem('pendingPDF', JSON.stringify({
            name: 'nuevo-documento.pdf',
            size: dataUri.length,
            data: dataUri
        }));
        window.location.href = (window.PDF_HOME_CFG || {}).urlEditorNuevo || '/herramientas/editor-pdf/editor/nuevo';
    } catch (err) {
        alert('Error al crear el PDF: ' + err.message);
    }
}

document.getElementById('btnCombinar').addEventListener('click', function() {
    const modal = document.getElementById('modalCombinar');
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
});

function cerrarModalCombinar() {
    const modal = document.getElementById('modalCombinar');
    modal.classList.add('hidden');
    modal.style.display = 'none';
}

function combinarPDFs() {
    const input = document.getElementById('combineInput');
    if (input.files.length < 2) {
        alert('Selecciona al menos 2 archivos PDF');
        return;
    }

    const formData = new FormData();
    for (let i = 0; i < input.files.length; i++) {
        formData.append('archivos', input.files[i]);
    }

    // Deshabilitar botón mientras procesa
    const btnCombinar = document.querySelector('#modalCombinar button[onclick="combinarPDFs()"]');
    const textoOriginal = btnCombinar.textContent;
    btnCombinar.textContent = 'Combinando...';
    btnCombinar.disabled = true;

    fetch('/api/pdf/combinar', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.mensaje || 'Error al combinar PDFs');
            });
        }
        return response.blob();
    })
    .then(blob => {
        // Cerrar modal de selección y preguntar: ¿descargar o editar?
        cerrarModalCombinar();
        const cuantos = input.files.length;
        input.value = '';
        _blobCombinado = blob;
        var tamano = blob.size >= 1024 * 1024 ? (blob.size / 1024 / 1024).toFixed(1) + ' MB' : Math.round(blob.size / 1024) + ' KB';
        document.getElementById('textoCombinadoListo').textContent =
            'Se combinaron ' + cuantos + ' archivos (' + tamano + '). ¿Quieres descargar el PDF ahora o editarlo?';
        const m = document.getElementById('modalCombinadoListo');
        m.classList.remove('hidden');
        m.style.display = 'flex';
    })
    .catch(error => {
        alert('Error: ' + error.message);
    })
    .finally(() => {
        btnCombinar.textContent = textoOriginal;
        btnCombinar.disabled = false;
    });
}

// Cerrar modal con clic fuera
document.getElementById('modalCombinar').addEventListener('click', function(e) {
    if (e.target === this) {
        cerrarModalCombinar();
    }
});

// ---- Confirmación tras combinar: descargar o editar ----
var _blobCombinado = null;

function cerrarModalCombinadoListo() {
    var m = document.getElementById('modalCombinadoListo');
    m.classList.add('hidden');
    m.style.display = 'none';
    _blobCombinado = null;
}

function descargarCombinado() {
    if (!_blobCombinado) return;
    var url = URL.createObjectURL(_blobCombinado);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'combinado.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    cerrarModalCombinadoListo();
}

function editarCombinado() {
    if (!_blobCombinado) return;
    var file = new File([_blobCombinado], 'combinado.pdf', { type: 'application/pdf' });
    // Via IndexedDB (funciona para cualquier tamaño); navega al editor
    _irAlEditorConPDFGrande(file);
}

document.getElementById('modalCombinadoListo').addEventListener('click', function(e) {
    if (e.target === this) {
        cerrarModalCombinadoListo();
    }
});

// Ocultar clase hidden correctamente
document.querySelectorAll('.hidden').forEach(el => {
    el.style.display = 'none';
});

// Tarjetas "Utilizar ahora": guardan la acción elegida para que el editor
// active esa herramienta apenas termine de cargar el documento
window.abrirConAccion = function (accion) {
    try { sessionStorage.setItem('pendingAccion', accion); } catch (e) { /* modo privado */ }
    document.getElementById('fileInputHome').click();
};

// Ctrl+O: abre el selector de PDF del home (la ayuda rápida lo anuncia).
// preventDefault porque el navegador tiene su propio Ctrl+O, que abriria el
// PDF en su visor nativo en vez de cargarlo en el editor.
document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        document.getElementById('fileInputHome').click();
    }
});
