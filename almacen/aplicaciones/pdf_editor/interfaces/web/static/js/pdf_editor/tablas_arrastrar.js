/**
 * Mover la tabla entera arrastrándola, como en Word.
 * =================================================================
 * «yo quiero… mover tablas… que esta tabla funcione como un tipo Word, pero sin
 * abrir OnlyOffice» — el usuario, 29-jul-2026.
 *
 * Mover una fila o una columna ya se podía. Esto mueve el conjunto: aparece un
 * asa (✥) en la esquina de la tabla, se agarra y se lleva donde se quiera. Se
 * ve una silueta mientras se arrastra, y al soltar se manda al servidor lo que
 * se ha movido, en puntos del PDF.
 *
 * Va en su propio archivo para no engordar `tablas_columnas.js`, que ya es el
 * que más carga lleva de los controles de tabla.
 *
 * Autoría: Equipo de Tecnología Maquita — 2026-07-29
 */
(function () {
    'use strict';

    /**
     * Pone el asa de una tabla y se encarga de todo el arrastre.
     *
     * @param opciones.capa       dónde colgar el asa (la capa de controles)
     * @param opciones.tabla      la tabla tal como la describe el servidor
     * @param opciones.indice     su número dentro de la página
     * @param opciones.zoom       cuántos píxeles mide un punto del PDF
     * @param opciones.alSoltar   función (indice, dx, dy) en puntos del PDF
     */
    function ponerAsa(opciones) {
        const {capa, tabla, indice, zoom, alSoltar} = opciones;
        const [x0, y0, x1, y1] = tabla.bbox;

        const asa = document.createElement('button');
        asa.type = 'button';
        asa.className = 'tabla-btn tabla-asa';
        asa.textContent = '✥';
        asa.title = 'Arrastra para mover TODA la tabla';
        // Fuera de la tabla, arriba a la izquierda: donde Word pone la suya y
        // donde no estorba a los ➕ de las columnas.
        asa.style.left = (x0 * zoom - 22) + 'px';
        asa.style.top = (y0 * zoom - 22) + 'px';

        let arrastrando = false;
        let desdeX = 0, desdeY = 0;
        let silueta = null;

        function empezar(evento) {
            evento.preventDefault();
            evento.stopPropagation();
            arrastrando = true;
            desdeX = evento.clientX;
            desdeY = evento.clientY;

            silueta = document.createElement('div');
            silueta.className = 'tabla-silueta';
            silueta.style.left = (x0 * zoom) + 'px';
            silueta.style.top = (y0 * zoom) + 'px';
            silueta.style.width = ((x1 - x0) * zoom) + 'px';
            silueta.style.height = ((y1 - y0) * zoom) + 'px';
            capa.appendChild(silueta);

            document.addEventListener('mousemove', mover);
            document.addEventListener('mouseup', soltar);
        }

        function mover(evento) {
            if (!arrastrando || !silueta) return;
            const dx = evento.clientX - desdeX;
            const dy = evento.clientY - desdeY;
            silueta.style.left = (x0 * zoom + dx) + 'px';
            silueta.style.top = (y0 * zoom + dy) + 'px';
        }

        function soltar(evento) {
            if (!arrastrando) return;
            arrastrando = false;
            document.removeEventListener('mousemove', mover);
            document.removeEventListener('mouseup', soltar);
            if (silueta && silueta.parentNode) silueta.parentNode.removeChild(silueta);
            silueta = null;

            // De píxeles de pantalla a puntos del PDF, que es en lo que piensa
            // el servidor.
            const dx = (evento.clientX - desdeX) / zoom;
            const dy = (evento.clientY - desdeY) / zoom;
            if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;   // un clic, no un arrastre
            alSoltar(indice, dx, dy);
        }

        asa.addEventListener('mousedown', empezar);
        // El asa es para arrastrar: un clic suelto no debe hacer nada.
        asa.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); });
        capa.appendChild(asa);
        return asa;
    }

    window.PDFTablasArrastrar = {ponerAsa: ponerAsa};
})();
