/* ============================================================
   Raíces Maquita — Editor PDF · extraer texto de un ÁREA
   Esta es UNA PARTE del editor (ver el reparto en editor_nucleo.js).

   «En Extraer texto (OCR) debe permitirme escoger y seleccionar un área de texto,
   no por página, y debe salir tal cual está escrito» — el usuario, 31-jul-2026.

   Aquí está solo la parte del navegador: dibujar el recuadro sobre la hoja y pedir
   ese trozo al servidor. Lo de «tal cual está escrito» —volver a colocar las
   palabras en sus renglones y columnas— lo hace el servidor, en texto_area.py.

   Va en su propio archivo a propósito: editor_tablas_ocr.js ya pasa de 280 líneas y
   no se le añade más.
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.ocr_area = function (E) {
    'use strict';

    const { $, _abrirModal, _cerrarModal, _getPdfBlob, _mostrarError, _necesitaPDF,
            _ocultarError, mostrarToast, state } = E;

    // El recuadro que se está dibujando: página, esquina inicial y el div de la vista
    // previa. Mientras `activo` sea false, el ratón no hace nada distinto de siempre.
    const sel = { activo: false, pagina: 0, x0: 0, y0: 0, previa: null, ultimo: null,
                  herramienta: null };

    // Mientras se elige el área, ninguna otra herramienta debe tocar el ratón. La de
    // la MANO era el caso que rompía esto: arrastrar movía el documento en vez de
    // dibujar el recuadro. Se apaga la que hubiera y se devuelve al terminar.
    function _apagarHerramienta() {
        sel.herramienta = state.currentTool;
        state.currentTool = null;
        window.PDFManoDesplazar?.refrescar?.();
    }

    function _devolverHerramienta() {
        if (sel.herramienta !== null) {
            state.currentTool = sel.herramienta;
            sel.herramienta = null;
            window.PDFManoDesplazar?.refrescar?.();
        }
    }

    function _capa(pagina) {
        return document.getElementById('pageWrapper_' + pagina);
    }

    // Puntos del PDF a partir de la posición del ratón. `state.zoom` es la escala con
    // la que se dibujó la hoja, así que dividir por él devuelve las unidades del
    // documento, que son las que entiende el servidor.
    function _puntos(evento, wrapper) {
        const caja = wrapper.getBoundingClientRect();
        return [(evento.clientX - caja.left) / state.zoom,
                (evento.clientY - caja.top)  / state.zoom];
    }

    function _limpiar() {
        sel.activo = false;
        sel.previa?.remove();
        sel.previa = null;
        document.body.classList.remove('ocr-area-eligiendo');
        _devolverHerramienta();
    }

    function empezarSeleccion() {
        if (_necesitaPDF()) return;
        // Con la hoja girada, lo que se ve y lo que guarda el PDF no coinciden, y el
        // recuadro caería en otro sitio. Se avisa en vez de devolver un texto raro.
        if ((state.rotation || {})[state.currentPage]) {
            mostrarToast('Esta página está girada: devuélvela a su posición antes de elegir un área.', 'warn');
            return;
        }
        _cerrarModal('modalOCR');
        sel.activo = true;
        _apagarHerramienta();
        document.body.classList.add('ocr-area-eligiendo');
        mostrarToast('Arrastra sobre la zona que quieras leer. Pulsa Esc para dejarlo.', 'info');
    }

    // En CAPTURA (el `true` del final) y cortando la propagación: así el arrastre no
    // llega a las demás herramientas aunque estén escuchando el mismo elemento.
    $('viewerScroll')?.addEventListener('mousedown', e => {
        if (!sel.activo || sel.previa) return;
        const wrapper = e.target.closest('.page-wrapper');
        if (!wrapper) return;
        e.preventDefault();
        e.stopPropagation();
        sel.pagina = parseInt(wrapper.dataset.page) || state.currentPage;
        [sel.x0, sel.y0] = _puntos(e, wrapper);

        const caja = document.createElement('div');
        caja.className = 'ocr-area-previa';
        wrapper.appendChild(caja);
        sel.previa = caja;
        sel.ultimo = null;
    }, true);

    $('viewerScroll')?.addEventListener('mousemove', e => {
        if (!sel.activo || !sel.previa) return;
        const wrapper = _capa(sel.pagina);
        if (!wrapper) return;
        e.stopPropagation();
        const [x1, y1] = _puntos(e, wrapper);
        const x = Math.min(sel.x0, x1), y = Math.min(sel.y0, y1);
        const ancho = Math.abs(x1 - sel.x0), alto = Math.abs(y1 - sel.y0);
        Object.assign(sel.previa.style, {
            left:   (x * state.zoom) + 'px',
            top:    (y * state.zoom) + 'px',
            width:  (ancho * state.zoom) + 'px',
            height: (alto * state.zoom) + 'px'
        });
        sel.ultimo = { x0: x, y0: y, x1: x + ancho, y1: y + alto };
    }, true);

    document.addEventListener('mouseup', () => {
        if (!sel.activo || !sel.previa) return;
        const area = sel.ultimo;
        const pagina = sel.pagina;
        _limpiar();
        // Un clic suelto o un recuadro de nada: no se hace caso, se sigue eligiendo.
        if (!area || (area.x1 - area.x0) < 4 || (area.y1 - area.y0) < 4) {
            sel.activo = true;
            document.body.classList.add('ocr-area-eligiendo');
            return;
        }
        leerArea(pagina, area);
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && sel.activo) {
            _limpiar();
            mostrarToast('Selección de área cancelada.', 'info');
        }
    });

    async function leerArea(pagina, area) {
        _abrirModal('modalOCR');
        _ocultarError('errorOCR');
        const boton = $('btnEjecutarOCR');
        const textoBoton = boton ? boton.innerHTML : '';
        if (boton) { boton.textContent = 'Leyendo el área…'; boton.disabled = true; }
        try {
            const formData = new FormData();
            formData.append('archivo', _getPdfBlob(), 'documento.pdf');
            formData.append('pagina', pagina);
            formData.append('idioma', $('selectIdioma')?.value || 'spa');
            formData.append('area', [area.x0, area.y0, area.x1, area.y1].join(','));
            const resp = await fetch('/api/pdf/operacion/ocr',
                                     { method: 'POST', body: formData, credentials: 'same-origin' });
            const datos = await resp.json();
            if (!datos.exito) throw new Error(datos.mensaje || 'No se pudo leer el área');

            const texto = datos.datos.texto_total || '';
            if (!texto.trim()) {
                _mostrarError('errorOCR', 'En esa zona no se encontró texto. Prueba a marcar un área un poco más amplia.');
                $('resultadoOCR').style.display = 'none';
                return;
            }
            $('textareaOCR').value = texto;
            $('infoOCR').textContent = 'Área de la página ' + pagina + ' · ' + texto.length +
                ' caracteres' + (datos.datos.ocr_utilizado ? ' (reconocido con OCR)' : ' (texto del documento)');
            $('resultadoOCR').style.display = 'block';
        } catch (err) {
            _mostrarError('errorOCR', 'No se pudo leer el área: ' + err.message);
        } finally {
            if (boton) { boton.innerHTML = textoBoton; boton.disabled = false; }
        }
    }

    // Por DELEGACIÓN y no colgado del botón: así no depende de que el botón exista
    // justo cuando arranca esta parte, ni de que el modal se vuelva a dibujar. Esto
    // era el fallo de «pulso y no pasa nada» del 31-jul-2026.
    document.addEventListener('click', e => {
        if (e.target.closest('#btnAreaOCR')) {
            e.preventDefault();
            empezarSeleccion();
        }
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _empezarSeleccionAreaOCR: empezarSeleccion });
};
