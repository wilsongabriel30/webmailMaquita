/* ============================================================
   Raíces Maquita - Editor PDF: BARRITAS DESLIZANTES de la tabla

   «necesito que me pongas unas barritas deslizantes como esta de aquí para
   esta parte de las columnas y las filas, yo poder ponerle al tamaño que yo
   quiero» — el usuario, 28-jul-2026.

   Sobre cada raya de la tabla se pone una barrita: se coge con el ratón y se
   lleva donde uno quiera, como en Word.

     ‖ raya vertical   → cambia el ANCHO de las columnas que separa
     ═ raya horizontal → cambia el ALTO de las filas que separa

   Mientras se arrastra solo se mueve una guía (nada toca el PDF); al soltar se
   manda el desplazamiento al servidor, que borra la tabla y la vuelve a dibujar
   con la medida nueva conservando la letra (`tablas_medidas.py`).

   La primera raya de arriba y la de la izquierda no llevan barrita: son las que
   anclan la tabla a su sitio en la página.

   Va en su propio archivo para no engordar `tablas_columnas.js`, que ya tiene
   los ➕ ✕ ‹ › y la escritura en las celdas.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    // Por debajo de esto no se deja encoger desde el navegador; el servidor
    // vuelve a recortar por su cuenta, esto es solo para que la guía no mienta.
    const MINIMO_COLUMNA = 12;      // puntos PDF
    const MINIMO_FILA = 9;
    const AIRE_TEXTO = 2.5;      // el aire que se le deja al texto en su celda

    let arrastrando = null;

    function guiaDe(capa) {
        let guia = capa.querySelector('.tabla-guia');
        if (!guia) {
            guia = document.createElement('div');
            guia.className = 'tabla-guia';
            capa.appendChild(guia);
        }
        return guia;
    }

    function etiquetaDe(capa) {
        let etiqueta = capa.querySelector('.tabla-medida-nota');
        if (!etiqueta) {
            etiqueta = document.createElement('div');
            etiqueta.className = 'tabla-medida-nota';
            capa.appendChild(etiqueta);
        }
        return etiqueta;
    }

    // Hacia la derecha se puede llevar la raya hasta el margen de la hoja: si la
    // columna de al lado ya está en su mínimo, el servidor ensancha la tabla en
    // vez de negarse. Hacia la izquierda manda el mínimo de la columna anterior.
    function limitesColumna(columnas, indice, tope) {
        const bajo = columnas[indice - 1] + MINIMO_COLUMNA;
        return [bajo, Math.max(bajo, tope)];
    }

    // El suelo de una fila es su texto: la raya no puede subir por encima de
    // donde acaba lo escrito, o el contenido se saldría de la celda.
    function limitesFila(filas, indice, fondoTexto, tope) {
        const suelo = fondoTexto[indice - 1];
        const bajo = Math.max(filas[indice - 1] + MINIMO_FILA,
                              (suelo || 0) + AIRE_TEXTO);
        return [bajo, Math.max(bajo, tope)];
    }

    function barrita(clase, titulo, estilo, alSoltar) {
        const b = document.createElement('div');
        b.className = 'tabla-barrita ' + clase;
        b.title = titulo;
        Object.keys(estilo).forEach(k => { b.style[k] = estilo[k]; });
        b.addEventListener('mousedown', alSoltar);
        return b;
    }

    /* Pinta las barritas de una tabla. Lo llama `tablas_columnas.js` cuando
       dibuja el resto de controles, con el mismo zoom y la misma capa. */
    function pintar(capa, tabla, indiceTabla, zoom, contexto) {
        const columnas = tabla.columnas || [];
        const filas = tabla.filas_y || [];
        if (columnas.length < 2 || filas.length < 2) return;
        const [x0, y0, x1, y1] = tabla.bbox;
        const anchoHoja = tabla.ancho_pagina || (x1 + 200);
        const topeColumna = Math.max(columnas[columnas.length - 2] + MINIMO_COLUMNA,
                                     anchoHoja - 20);
        // Hacia ABAJO se puede llevar la raya todo lo que se quiera: si la fila
        // siguiente ya no da más, el servidor alarga la tabla (y hace sitio
        // debajo). Lo que no se puede es subirla por encima del texto que ya
        // hay en la celda: por eso `fondo_texto`.
        const altoHoja = tabla.alto_pagina || (filas[filas.length - 1] + 300);
        const topeFila = altoHoja - 30;
        const fondoTexto = tabla.fondo_texto || [];

        // Las barritas HORIZONTALES solo se ponen en las rayas que el documento
        // tiene DIBUJADAS. Cuando una tabla no separa sus filas con rayas, el
        // servidor las deduce del texto y devuelve una "fila" por cada renglón;
        // arrastrar una de esas descolocaba los renglones, que acababan
        // pisándose. Las verticales se mantienen todas: cambiar el ancho reparte
        // el texto por columnas y tiene sentido aunque no haya bordes. Si el
        // servidor no manda el dato (documento reconocido antes de este cambio),
        // se permiten todas, como se hacía siempre.
        const filasReales = tabla.filas_reales || null;
        const seArrastra = (lista, i) => !lista || lista[i] !== false;

        // ── rayas verticales: ancho de columna ──
        for (let i = 1; i < columnas.length; i++) {
            const anchoIzquierda = Math.round(columnas[i] - columnas[i - 1]);
            const ultima = i === columnas.length - 1;
            capa.appendChild(barrita('tabla-barrita-v',
                ultima ? 'Arrastra para alargar o acortar la tabla (columna ' + i +
                         ': ' + anchoIzquierda + ' pt)'
                       : 'Arrastra para cambiar el ancho de las columnas ' + i +
                         ' y ' + (i + 1) + ' (la ' + i + ' mide ' + anchoIzquierda + ' pt)',
                {left: (columnas[i] * zoom) + 'px', top: (y0 * zoom) + 'px',
                 height: ((y1 - y0) * zoom) + 'px'},
                e => empezar(e, {
                    capa: capa, zoom: zoom, contexto: contexto,
                    indiceTabla: indiceTabla, que: 'columna', borde: i,
                    eje: 'x', desde: columnas[i],
                    limites: limitesColumna(columnas, i, topeColumna),
                    sinCrecer: ultima ? Infinity : columnas[i + 1] - MINIMO_COLUMNA,
                    largoDesde: y0, largoHasta: y1, vecinoAnterior: columnas[i - 1]
                })));
        }

        // ── rayas horizontales: alto de fila ──
        for (let j = 1; j < filas.length; j++) {
            if (!seArrastra(filasReales, j)) continue;
            const altoArriba = Math.round(filas[j] - filas[j - 1]);
            const ultima = j === filas.length - 1;
            capa.appendChild(barrita('tabla-barrita-h',
                ultima ? 'Arrastra para hacer más alta o más baja la última fila (' +
                         altoArriba + ' pt)'
                       : 'Arrastra para cambiar el alto de las filas ' + j + ' y ' +
                         (j + 1) + ' (la ' + j + ' mide ' + altoArriba + ' pt)',
                {left: (x0 * zoom) + 'px', top: (filas[j] * zoom) + 'px',
                 width: ((x1 - x0) * zoom) + 'px'},
                e => empezar(e, {
                    capa: capa, zoom: zoom, contexto: contexto,
                    indiceTabla: indiceTabla, que: 'fila', borde: j,
                    eje: 'y', desde: filas[j],
                    limites: limitesFila(filas, j, fondoTexto, topeFila),
                    sinCrecer: ultima ? Infinity
                        : Math.max(filas[j], (fondoTexto[j] || filas[j]) + AIRE_TEXTO),
                    largoDesde: x0, largoHasta: x1, vecinoAnterior: filas[j - 1]
                })));
        }
    }

    // ── el arrastre ──────────────────────────────────────────────────────
    function empezar(evento, datos) {
        evento.preventDefault();
        evento.stopPropagation();
        if (arrastrando) return;
        arrastrando = Object.assign({}, datos, {
            inicioRaton: datos.eje === 'x' ? evento.clientX : evento.clientY,
            actual: datos.desde
        });
        document.body.classList.add(datos.eje === 'x' ? 'redimensionando-col'
                                                      : 'redimensionando-fila');
        mostrarGuia();
        document.addEventListener('mousemove', mover);
        document.addEventListener('mouseup', soltar);
    }

    function mostrarGuia() {
        const d = arrastrando;
        const guia = guiaDe(d.capa);
        const etiqueta = etiquetaDe(d.capa);
        guia.className = 'tabla-guia ' + (d.eje === 'x' ? 'tabla-guia-v' : 'tabla-guia-h');
        if (d.eje === 'x') {
            guia.style.left = (d.actual * d.zoom) + 'px';
            guia.style.top = (d.largoDesde * d.zoom) + 'px';
            guia.style.height = ((d.largoHasta - d.largoDesde) * d.zoom) + 'px';
            guia.style.width = '';
            etiqueta.style.left = (d.actual * d.zoom + 8) + 'px';
            etiqueta.style.top = (d.largoDesde * d.zoom + 6) + 'px';
        } else {
            guia.style.top = (d.actual * d.zoom) + 'px';
            guia.style.left = (d.largoDesde * d.zoom) + 'px';
            guia.style.width = ((d.largoHasta - d.largoDesde) * d.zoom) + 'px';
            guia.style.height = '';
            etiqueta.style.left = (d.largoDesde * d.zoom + 8) + 'px';
            etiqueta.style.top = (d.actual * d.zoom + 6) + 'px';
        }
        guia.style.display = 'block';
        etiqueta.style.display = 'block';
        const medida = Math.round(d.actual - d.vecinoAnterior);
        etiqueta.textContent = medida + ' pt'
            + (d.actual > (d.sinCrecer || Infinity) + 0.5
               ? (d.que === 'fila' ? ' · la tabla se alarga' : ' · la tabla se ensancha')
               : '');
    }

    function mover(evento) {
        if (!arrastrando) return;
        const d = arrastrando;
        const raton = d.eje === 'x' ? evento.clientX : evento.clientY;
        const propuesto = d.desde + (raton - d.inicioRaton) / d.zoom;
        d.actual = Math.min(Math.max(propuesto, d.limites[0]), d.limites[1]);
        mostrarGuia();
    }

    async function soltar() {
        const d = arrastrando;
        arrastrando = null;
        document.removeEventListener('mousemove', mover);
        document.removeEventListener('mouseup', soltar);
        document.body.classList.remove('redimensionando-col', 'redimensionando-fila');
        if (!d) return;
        const guia = d.capa.querySelector('.tabla-guia');
        const etiqueta = d.capa.querySelector('.tabla-medida-nota');
        if (guia) guia.style.display = 'none';
        if (etiqueta) etiqueta.style.display = 'none';

        const delta = d.actual - d.desde;
        if (Math.abs(delta) < 0.5) return;      // un clic suelto no cambia nada
        await d.contexto.enviar('/api/pdf/tablas/medida', d.indiceTabla,
            {que: d.que, borde: d.borde, delta: delta.toFixed(2)},
            d.que === 'columna' ? 'Ajustando el ancho…' : 'Ajustando el alto…',
            d.que === 'columna' ? 'Ancho de columna ajustado.' : 'Alto de fila ajustado.');
    }

    window.PDFTablasMedidas = {pintar: pintar};
})();
