/* ============================================================
   Raíces Maquita — Editor PDF · ventana
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.ventana = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _necesitaPDF, mostrarToast, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const _aplicarDisposicionPaginas = (...a) => E._aplicarDisposicionPaginas(...a);   // parte render_vista
    const _aplicarEstiloForzado = (...a) => E._aplicarEstiloForzado(...a);   // parte texto_pdf
    const _hornearPDF = (...a) => E._hornearPDF(...a);   // parte compartir
    const downloadPDF = (...a) => E.downloadPDF(...a);   // parte compartir
    const renderVisiblePages = (...a) => E.renderVisiblePages(...a);   // parte render_vista
    // ==================== MENU "EXPORTAR" DE LA BARRA SUPERIOR ====================
    // Un solo botón reune lo que antes eran tres entradas sueltas del panel
    // ("Exportar a Word / Excel / PowerPoint"). Cada opción delega en la
    // herramienta real de la pestaña Convertir, que es la que hace el trabajo:
    // así no se duplica nada y cualquier arreglo alli vale para las dos vias.
    (function _menuExportar() {
        const btn  = $('btnExportarMenu');
        const menu = $('menuExportar');
        if (!btn || !menu) return;

        function cerrar() { menu.classList.add('hidden'); }

        btn.addEventListener('click', e => {
            e.stopPropagation();
            menu.classList.toggle('hidden');
        });

        menu.querySelectorAll('.menu-exportar-item').forEach(item => {
            item.addEventListener('click', () => {
                cerrar();
                const destino = document.getElementById(item.dataset.destino);
                if (destino) destino.click();
                else mostrarToast('Esa opción de exportación no está disponible.', 'warn');
            });
        });

        // Se cierra al hacer clic fuera o con Escape
        document.addEventListener('click', cerrar);
        document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrar(); });
        menu.addEventListener('click', e => e.stopPropagation());
    })();

    // ==================== PANELES QUE SE ENCOGEN ====================
    // Izquierda: separador arrastrable que cambia el ancho del panel de herramientas.
    // Derecha: tirador que oculta o muestra la barra de iconos.
    // Al cambiar cualquiera de los dos, el visor cambia de ancho: hay que recalcular
    // las columnas de la vista de varias páginas y lo que toca renderizar.
    const ANCHO_PANEL_MIN = 150, ANCHO_PANEL_MAX = 480, ANCHO_PANEL_COLAPSA = 110;

    function _tocoElAnchoDelVisor() {
        _aplicarDisposicionPaginas();
        if (state.pdfDoc) renderVisiblePages();
    }

    (function _resizerPanelIzquierdo() {
        const resizer = $('panelResizer');
        const panel = $('leftPanel');
        if (!resizer || !panel) return;
        let arrastrando = false;

        resizer.addEventListener('mousedown', e => {
            e.preventDefault();
            arrastrando = true;
            resizer.classList.add('arrastrando');
            // sin la transicion CSS el panel sigue al mouse sin retraso
            panel.style.transition = 'none';
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
        });

        document.addEventListener('mousemove', e => {
            if (!arrastrando) return;
            const ancho = e.clientX - panel.getBoundingClientRect().left;
            if (ancho < ANCHO_PANEL_COLAPSA) {
                // arrastrado casi hasta el borde = ocultar el panel
                panel.classList.add('collapsed');
                return;
            }
            panel.classList.remove('collapsed');
            const w = Math.min(ANCHO_PANEL_MAX, Math.max(ANCHO_PANEL_MIN, ancho));
            panel.style.width = w + 'px';
            panel.style.minWidth = w + 'px';
        });

        document.addEventListener('mouseup', () => {
            if (!arrastrando) return;
            arrastrando = false;
            resizer.classList.remove('arrastrando');
            panel.style.transition = '';
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
            _tocoElAnchoDelVisor();
        });

        // Doble clic en el separador: ocultar o restaurar el panel de un golpe
        resizer.addEventListener('dblclick', () => {
            panel.classList.toggle('collapsed');
            _tocoElAnchoDelVisor();
        });
    })();

    $('btnTiradorDerecho')?.addEventListener('click', () => {
        const oculto = document.body.classList.toggle('sin-panel-derecho');
        const btn = $('btnTiradorDerecho');
        btn.innerHTML = oculto ? '<i class="bi bi-chevron-left"></i>' : '<i class="bi bi-chevron-right"></i>';
        btn.title = oculto ? 'Mostrar la barra de iconos de la derecha'
                           : 'Ocultar la barra de iconos de la derecha para ganar espacio';
        _tocoElAnchoDelVisor();
    });

    // ==================== ALTO EXACTO DEL EDITOR ====================
    // El editor debe empezar justo debajo de la barra Raíces y terminar justo en el
    // borde inferior de la ventana. Se mide su posición real en vez de restar una
    // altura fija de barra: así no sobra franja gris arriba ni aparece la barra de
    // desplazamiento de la ventana (que además robaba ancho al documento).
    function _ajustarAltoEditor() {
        const app = document.querySelector('.pdf-editor-app');
        if (!app) return;
        const arriba = Math.max(0, Math.round(app.getBoundingClientRect().top + window.scrollY));
        app.style.height = 'calc(100vh - ' + arriba + 'px)';
    }
    _ajustarAltoEditor();
    let _altoTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(_altoTimer);
        _altoTimer = setTimeout(_ajustarAltoEditor, 100);
    });

    // ==================== MODO PANTALLA COMPLETA ====================
    // Oculta la barra Raíces y el panel de herramientas para dar todo el
    // espacio al documento; segundo clic restaura la vista normal
    $('btnMaximizar')?.addEventListener('click', () => {
        const activo = document.body.classList.toggle('editor-maximo');
        $('btnMaximizar').innerHTML = activo ? '<i class="bi bi-fullscreen-exit"></i>' : '<i class="bi bi-arrows-fullscreen"></i>';
        $('btnMaximizar').title = activo ? 'Salir de pantalla completa' : 'Pantalla completa - Oculta los menús para aprovechar toda la pantalla';
        $('leftPanel').classList.toggle('collapsed', activo);
        // al ocultarse la barra Raíces el editor sube: hay que recalcular su alto
        _ajustarAltoEditor();
        // el área visible cambió: re-renderizar las páginas que entran en vista
        setTimeout(() => {
            _ajustarAltoEditor();
            _aplicarDisposicionPaginas();
            $('viewerScroll')?.dispatchEvent(new Event('scroll'));
        }, 350);
    });

    // ==================== BOTONES HOME/PRINT ====================
    // ==================== SALIR SIN PERDER EL TRABAJO ====================
    // El editor no guarda solo: lo que no se descarga, se pierde. Y hasta ahora se
    // salía sin más —el botón Inicio navegaba directamente y no había ni el aviso del
    // navegador—, así que una tarde de correcciones se podía perder con un clic.
    // Ahora, al salir con un documento abierto, se pregunta qué hacer.
    let _salidaAutorizada = false;

    function _preguntarAntesDeSalir(salir) {
        if (!state.pdfDoc) { salir(); return; }        // sin documento no hay nada que perder
        const hay = !!state.hayCambios;

        const fondo = document.createElement('div');
        fondo.id = 'dialogoSalidaEditor';
        _aplicarEstiloForzado(fondo, {
            position: 'fixed', inset: '0', background: 'rgba(0,0,0,.45)',
            'z-index': '10000', display: 'flex', 'align-items': 'center',
            'justify-content': 'center'
        });
        const caja = document.createElement('div');
        _aplicarEstiloForzado(caja, {
            background: '#fff', 'border-radius': '10px', padding: '22px 24px',
            'max-width': '460px', 'box-shadow': '0 10px 40px rgba(0,0,0,.3)',
            'font-family': 'inherit', color: '#222'
        });
        caja.innerHTML =
            '<h3 style="margin:0 0 10px;font-size:18px">' +
            (hay ? '¿Guardar los cambios antes de salir?' : '¿Salir del editor?') + '</h3>' +
            '<p style="margin:0 0 18px;font-size:14px;line-height:1.5;color:#444">' +
            (hay ? 'Tiene cambios que <b>todavía no ha descargado</b>. Si sale sin guardarlos, se pierden.'
                 : 'No hay cambios pendientes de descargar en este documento.') +
            '</p><div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap"></div>';
        const botones = caja.querySelector('div');

        const boton = (texto, estilo, accion) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.textContent = texto;
            _aplicarEstiloForzado(b, Object.assign({
                padding: '8px 14px', border: '1px solid #ccc', 'border-radius': '6px',
                background: '#fff', cursor: 'pointer', 'font-size': '14px'
            }, estilo));
            b.addEventListener('click', accion);
            botones.appendChild(b);
            return b;
        };

        const cerrar = () => fondo.remove();
        boton('Cancelar', {}, cerrar);
        if (hay) {
            boton('Salir sin guardar', { color: '#b02a37', 'border-color': '#b02a37' }, () => {
                cerrar(); _salidaAutorizada = true; salir();
            });
            boton('Descargar y salir', { background: '#0d6efd', color: '#fff', 'border-color': '#0d6efd' },
                async () => {
                    cerrar();
                    await downloadPDF();          // hornea las anotaciones y descarga
                    _salidaAutorizada = true;
                    salir();
                });
        } else {
            boton('Salir', { background: '#0d6efd', color: '#fff', 'border-color': '#0d6efd' }, () => {
                cerrar(); _salidaAutorizada = true; salir();
            });
        }

        fondo.appendChild(caja);
        fondo.addEventListener('click', e => { if (e.target === fondo) cerrar(); });
        document.addEventListener('keydown', function esc(e) {
            if (e.key === 'Escape') { cerrar(); document.removeEventListener('keydown', esc); }
        });
        document.body.appendChild(fondo);
        botones.lastChild.focus();
    }

    // Cerrar la pestaña, recargar o irse a otra dirección no lo puede interceptar la
    // página: ahí solo cabe el aviso del navegador. No lo había, así que una recarga
    // se llevaba por delante el trabajo (y, si estaba convirtiendo, la conversión).
    window.addEventListener('beforeunload', e => {
        if (_salidaAutorizada || !state.pdfDoc || !state.hayCambios) return;
        e.preventDefault();
        e.returnValue = '';       // Chrome exige asignarlo para mostrar el aviso
    });

    $('btnHome').addEventListener('click', () => {
        _preguntarAntesDeSalir(() => {
            window.location.href = (window.PDF_EDITOR_CFG || {}).urlHome || '/herramientas/editor-pdf/';
        });
    });

    // Imprimir: imprime el PDF EN EDICIÓN (con sus anotaciones horneadas), no la página web.
    // Se hornea el documento y se envía a imprimir dentro de un iframe oculto.
    $('btnPrint').addEventListener('click', async () => {
        if (_necesitaPDF()) return;
        showLoading(true);
        let url = null;
        try {
            const bytes = await _hornearPDF();
            const blob  = new Blob([bytes], { type: 'application/pdf' });
            url = URL.createObjectURL(blob);
            let iframe = document.getElementById('_printFrame');
            if (!iframe) {
                iframe = document.createElement('iframe');
                iframe.id = '_printFrame';
                iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;';
                document.body.appendChild(iframe);
            }
            iframe.onload = () => {
                try {
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                } catch (e) {
                    // Si eso no sale, se abre el PDF en una pestaña nueva para imprimir desde ahí
                    window.open(url, '_blank');
                }
                // El diálogo de impresión es asíncrono: liberamos el blob después
                setTimeout(() => { if (url) URL.revokeObjectURL(url); }, 60000);
            };
            iframe.src = url;
        } catch (e) {
            console.error('Error al imprimir:', e);
            mostrarToast('Error al imprimir: ' + e.message, 'error');
            if (url) URL.revokeObjectURL(url);
        } finally { showLoading(false); }
    });

};
