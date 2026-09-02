/* ============================================================
   Raíces Maquita - Editor PDF: EDITAR POR PÁRRAFO (no por palabra)

   «necesito que me dejes cambiar texto por párrafo no por palabra, igualito
   que si fuera un word» — el usuario, 27-jul-2026.

   Doble clic sobre cualquier texto y se abre el PÁRRAFO ENTERO en un cuadro
   que se apoya sobre él, con su misma letra y su ancho. Se reescribe como se
   quiera —más largo, más corto, con saltos de línea— y al guardar el párrafo
   se recompone solo en el documento: los renglones se reparten dentro del
   mismo ancho, con el interlineado y la tipografía que tenía.

     Ctrl+Enter o el botón ✓  → guardar        Esc → cancelar
     Enter                    → salto de línea, como en cualquier cuadro de texto

   Si en ese punto no hay un párrafo reconocible, se deja pasar el doble clic
   para que siga funcionando la edición palabra por palabra de siempre.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    let api = null;
    let abierto = null;     // {caja, bbox, página, original}

    function cerrar() {
        if (!abierto) return;
        const marco = document.querySelector('.parrafo-marco');
        if (marco) marco.remove();
        abierto = null;
    }

    // ── abrir el párrafo que hay bajo el punto ───────────────────────────
    // Devuelve true si se hizo cargo; false para que siga la vía de siempre.
    async function abrir(puente, pagina, x, y) {
        api = puente || api;
        cerrar();
        let datos;
        try {
            // Consulta pura: no cambia el documento. Con sesión no viaja el
            // PDF, solo el punto donde se hizo doble clic.
            const resp = await window.PDFSesion.consultar(
                '/api/pdf/parrafo/en', {pagina: pagina, x: x, y: y},
                api.getPdfBytes());
            const json = await resp.json();
            if (!json.exito || !json.parrafo) return false;
            datos = json.parrafo;
            // Si el punto cae DENTRO de una tabla, aquí no se abre nada: manda
            // la edición de la celda, que se escribe en su sitio y con la letra
            // del documento. El cuadro de párrafo distorsionaba el estilo.
            if (datos.en_tabla && window.PDFTablasColumnas
                    && window.PDFTablasColumnas.abrirCelda) {
                window.PDFTablasColumnas.abrirCelda(puente, pagina, datos.tabla,
                                                    datos.fila, datos.columna);
                return true;
            }
        } catch (e) {
            return false;       // sin conexión: que siga la edición de siempre
        }

        const envoltorio = document.getElementById('pageWrapper_' + pagina);
        if (!envoltorio) return false;
        const zoom = api.getZoom();
        const [x0, y0, x1, y1] = datos.bbox;

        const marco = document.createElement('div');
        marco.className = 'parrafo-marco';
        marco.style.left = (x0 * zoom - 4) + 'px';
        marco.style.top = (y0 * zoom - 4) + 'px';
        marco.style.width = ((x1 - x0) * zoom + 8) + 'px';

        const caja = document.createElement('textarea');
        caja.className = 'parrafo-caja';
        caja.value = datos.texto;
        caja.style.fontSize = (datos.tam * zoom) + 'px';
        caja.style.minHeight = ((y1 - y0) * zoom + 6) + 'px';
        caja.spellcheck = false;

        const barra = document.createElement('div');
        barra.className = 'parrafo-barra';
        barra.innerHTML = '<span>Párrafo completo · Ctrl+Enter guarda · Esc cancela</span>';
        const guardar = document.createElement('button');
        guardar.type = 'button';
        guardar.className = 'parrafo-ok';
        guardar.textContent = '✓ Guardar';
        barra.appendChild(guardar);

        marco.appendChild(caja);
        marco.appendChild(barra);
        envoltorio.appendChild(marco);

        abierto = {caja: caja, bbox: datos.bbox, pagina: pagina, original: datos.texto};
        caja.focus();
        caja.setSelectionRange(caja.value.length, caja.value.length);
        // Que crezca con lo que se escribe
        const ajustar = () => {
            caja.style.height = 'auto';
            caja.style.height = (caja.scrollHeight + 2) + 'px';
        };
        ajustar();
        caja.addEventListener('input', ajustar);

        guardar.addEventListener('click', aplicar);
        caja.addEventListener('keydown', e => {
            e.stopPropagation();      // que las teclas no lleguen al editor
            if (e.key === 'Escape') { e.preventDefault(); cerrar(); }
            else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                aplicar();
            }
        });
        marco.addEventListener('click', e => e.stopPropagation());
        marco.addEventListener('dblclick', e => e.stopPropagation());
        return true;
    }

    async function aplicar() {
        if (!abierto) return;
        const texto = abierto.caja.value;
        const {bbox, pagina, original} = abierto;
        if (texto === original) { cerrar(); return; }
        cerrar();

        api.showLoading(true, 'Recomponiendo el párrafo…');
        try {
            const {bytes, aviso} = await window.PDFSesion.enviar(
                '/api/pdf/parrafo/reemplazar',
                {pagina: pagina, bbox: bbox.join(','), texto: texto},
                api.getPdfBytes());
            await api.reemplazarPdf(bytes, 'el cambio del párrafo');
            if (api.irAPagina && pagina > 1) api.irAPagina(pagina);
            api.toast('Párrafo actualizado.', 'ok');
            if (aviso) setTimeout(() => api.toast('Aviso: ' + aviso, 'warn'), 1200);
        } catch (e) {
            api.toast('No se pudo cambiar el párrafo: ' + e.message, 'error');
        } finally {
            api.showLoading(false);
        }
    }

    window.PDFEdicionParrafo = {abrir: abrir, cerrar: cerrar, hayAbierto: () => !!abierto};
})();
