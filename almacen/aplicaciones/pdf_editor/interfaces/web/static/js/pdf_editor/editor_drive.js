/* ============================================================
   Raíces Maquita — Editor PDF: EL DOCUMENTO ES UN ARCHIVO DEL DRIVE

   Hasta ahora el editor trabajaba siempre sobre una COPIA: el PDF entraba desde
   el equipo de la persona y salía por «Descargar». Quien editaba un documento
   del Drive tenía que bajarlo, editarlo y volver a subirlo a mano —y a menudo
   lo subía al lado del original, con lo que quedaban dos versiones y nadie
   sabía cuál era la buena.

   Con esta parte el documento ES el del Drive: se abre desde su ruta y se
   guarda sobre ella. Cada guardado pasa por el mismo camino que usa OnlyOffice
   (POST /api/almacen/archivos → nucleo.subir), que deja el contenido anterior
   como VERSIÓN antes de escribir el nuevo: nada se pierde y se puede volver
   atrás desde «Versiones» del propio Drive.

   Se guarda cuando la persona lo pide (botón o Ctrl+S), no solo. En un PDF
   guardar significa APLANAR las anotaciones sobre la página, y eso no se
   deshace: hacerlo sin que nadie lo haya pedido sería decidir por el usuario.

   Solo se activa si la página se abrió con ?ruta= (modo 'drive'); en el editor
   normal esta parte no hace absolutamente nada.
   ============================================================ */
(function () {
    'use strict';

    window.PDFEditorPartes = window.PDFEditorPartes || {};

    window.PDFEditorPartes.drive = function (E) {
        const CFG = window.PDF_EDITOR_CFG || {};
        const ruta = (CFG.driveRuta || '').trim();
        if (!ruta) return;   // editor normal: nada que hacer

        const API = '/api/almacen';
        const nombre = ruta.split('/').pop();
        // La carpeta es la ruta sin el nombre. '/informe.pdf' vive en '/'.
        const carpeta = ruta.slice(0, ruta.length - nombre.length).replace(/\/+$/, '') || '/';

        let guardando = false;
        let btn = null;

        // ---------------------------------------------------------------
        // El botón. Se crea aquí y no en el HTML porque en el editor normal
        // no debe existir: un «Guardar en el Drive» que no lleva a ningún
        // Drive confunde más de lo que ayuda.
        // ---------------------------------------------------------------
        function crearBoton() {
            const barra = document.querySelector('.top-actions');
            if (!barra) return null;
            const b = document.createElement('button');
            b.id = 'btnGuardarDrive';
            b.className = 'top-btn';
            b.style.cssText = 'background:#0b7d3f;border-color:#0b7d3f;color:#fff;font-weight:600;';
            b.title = 'Guarda los cambios en «' + nombre + '» dentro del Drive (Ctrl+S). '
                    + 'La versión anterior se conserva.';
            b.innerHTML = '<i class="bi bi-cloud-arrow-up"></i> <span>Guardar en el Drive</span>';
            b.addEventListener('click', guardar);
            barra.insertBefore(b, barra.firstChild);
            return b;
        }

        function pintarBoton(estado) {
            if (!btn) return;
            const texto = btn.querySelector('span');
            if (estado === 'guardando') {
                btn.disabled = true;
                if (texto) texto.textContent = 'Guardando…';
            } else if (estado === 'guardado') {
                btn.disabled = false;
                if (texto) texto.textContent = 'Guardado en el Drive';
                setTimeout(() => pintarBoton('normal'), 2500);
            } else {
                btn.disabled = false;
                if (texto) texto.textContent = 'Guardar en el Drive';
            }
        }

        // ---------------------------------------------------------------
        // Abrir: el PDF se baja del Drive, no se sube desde el equipo.
        // ---------------------------------------------------------------
        async function abrirDesdeDrive() {
            E.showLoading(true, 'Abriendo «' + nombre + '» desde el Drive…');
            try {
                const resp = await fetch(
                    API + '/archivos/descargar?ruta=' + encodeURIComponent(ruta),
                    { credentials: 'same-origin' });
                if (!resp.ok) throw new Error(await motivo(resp));
                const datos = await resp.arrayBuffer();
                if (!datos || datos.byteLength === 0) throw new Error('el archivo llegó vacío');
                await E.loadPDF(datos);
                E.state.hayCambios = false;
                E.mostrarToast('«' + nombre + '» abierto desde el Drive. '
                               + 'Al guardar, el archivo del Drive se actualiza.', 'ok');
            } catch (error) {
                E.showLoading(false);
                E.mostrarToast('No se pudo abrir el documento del Drive: ' + error.message, 'error');
            }
        }

        // ---------------------------------------------------------------
        // Guardar: el mismo camino que usa OnlyOffice al cerrar un documento.
        // ---------------------------------------------------------------
        async function guardar() {
            if (guardando) return;
            if (!E.state.pdfDoc || !E.state.pdfBytes) {
                E.mostrarToast('Espera a que termine de cargar el documento.', 'warn');
                return;
            }
            guardando = true;
            pintarBoton('guardando');
            try {
                // Si hay anotaciones sin aplanar hay que hornearlas: si no, se
                // guardaría el PDF de antes y los cambios se quedarían en la
                // pantalla (mismo criterio que _operacionBackend del núcleo).
                const hayAnotaciones = Object.values(E.state.annotations || {})
                    .some(capa => capa && capa.length);
                const bytes = hayAnotaciones ? await E._hornearPDF() : E.state.pdfBytes;

                const formulario = new FormData();
                formulario.append('carpeta', carpeta);
                formulario.append('archivo',
                                  new Blob([bytes], { type: 'application/pdf' }), nombre);

                const resp = await fetch(API + '/archivos', {
                    method: 'POST', body: formulario, credentials: 'same-origin'
                });
                if (!resp.ok) throw new Error(await motivo(resp));

                E.state.hayCambios = false;
                pintarBoton('guardado');
                E.mostrarToast('Guardado en el Drive. La versión anterior queda en el '
                               + 'historial del archivo.', 'ok');
            } catch (error) {
                pintarBoton('normal');
                E.mostrarToast('No se pudo guardar en el Drive: ' + error.message
                               + '. Puedes bajar el documento con Exportar → Descargar PDF '
                               + 'para no perder el trabajo.', 'error');
            } finally {
                guardando = false;
            }
        }

        /** El motivo que dé el motor del Almacén; si no da ninguno, el código HTTP.
         *  Un 403 aquí casi siempre es «te compartieron el archivo solo para ver». */
        async function motivo(resp) {
            let detalle = '';
            try {
                const datos = await resp.json();
                detalle = datos.error || datos.mensaje || '';
            } catch (e) { /* la respuesta no era JSON */ }
            if (!detalle && resp.status === 403) detalle = 'no tienes permiso para escribir aquí';
            if (!detalle && resp.status === 404) detalle = 'el archivo ya no está en esa ruta';
            return detalle || ('error ' + resp.status);
        }

        // Ctrl+S. En captura y con preventDefault: si no, el navegador abre su
        // «Guardar página como…», que no tiene nada que ver.
        document.addEventListener('keydown', function (evento) {
            if ((evento.ctrlKey || evento.metaKey) && !evento.altKey
                && String(evento.key).toLowerCase() === 's') {
                evento.preventDefault();
                guardar();
            }
        }, true);

        btn = crearBoton();
        abrirDesdeDrive();
    };
})();
