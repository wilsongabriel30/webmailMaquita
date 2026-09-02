/* ============================================================
   Raíces Maquita — Editor PDF · comentarios
   Al activar la herramienta de comentario se despliega ARRIBA, sobre el documento,
   una barra con sus opciones: con qué marca se pega el comentario (nota, bocadillo,
   visto, equis, estrella…) y de qué color. Se pulsa en la hoja, aparece la marca y se
   abre una notita para escribir.

   Va arriba y no en el panel de la izquierda porque así lo pidió el usuario el
   30-jul-2026, enseñando un vídeo de otro editor donde las opciones se despliegan en
   una fila horizontal encima del documento.

   Antes solo había una nota adhesiva amarilla, sin poder elegir marca ni color, y
   para releer o cambiar el texto salía el cuadro gris del navegador (`prompt`).

   Esta es UNA PARTE del editor: se registra aquí y el núcleo la arranca pasándole
   `E`, el objeto con lo que se comparte entre partes.
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.comentarios = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo:
    const { $, _currentAnnotLayer, state } = E;

    // Funciones que viven en otras partes:
    const renderAnnotations = (...a) => E.renderAnnotations(...a);   // parte render_vista
    const setTool = (...a) => E.setTool(...a);                       // parte herramientas

    /** Las marcas que se pueden pegar. La `clave` es lo que se guarda en la anotación
     *  (no se traduce nunca: es un dato, no un texto para leer) y el `icono` es el de
     *  Bootstrap Icons, que la página ya carga. */
    const MARCAS = [
        { clave: 'nota',    icono: 'bi-sticky-fill',      nombre: 'Nota adhesiva' },
        { clave: 'globo',   icono: 'bi-chat-fill',        nombre: 'Bocadillo' },
        { clave: 'cuadro',  icono: 'bi-chat-square-fill', nombre: 'Bocadillo cuadrado' },
        { clave: 'visto',   icono: 'bi-check-lg',         nombre: 'Visto' },
        { clave: 'equis',   icono: 'bi-x-lg',             nombre: 'Equis' },
        { clave: 'punto',   icono: 'bi-circle-fill',      nombre: 'Punto' },
        { clave: 'flecha',  icono: 'bi-arrow-right',      nombre: 'Flecha' },
        { clave: 'estrella',icono: 'bi-star-fill',        nombre: 'Estrella' },
        { clave: 'duda',    icono: 'bi-question-lg',      nombre: 'Interrogación' },
        { clave: 'llave',   icono: 'bi-key-fill',         nombre: 'Llave' },
    ];

    // Los colores que se ofrecen. Son los mismos que usa el resto del editor para las
    // herramientas sólidas, más un amarillo de nota, que es lo típico de un comentario.
    const COLORES = ['#f59e0b', '#dc2626', '#1473e6', '#16a34a', '#7c3aed', '#000000'];

    let _marcaElegida = 'nota';
    // El color del comentario se guarda AQUÍ y no en el `annotColor` que comparten las
    // demás herramientas: si no, cambiar el color del lápiz cambiaría el del comentario.
    let _colorElegido = COLORES[0];

    /** El icono de Bootstrap de una marca (o el de la nota, si la clave no se conoce
     *  porque venga de un documento hecho con una versión anterior). */
    function iconoDeLaMarca(clave) {
        const m = MARCAS.find(x => x.clave === clave);
        return (m || MARCAS[0]).icono;
    }

    function marcaElegida() { return _marcaElegida; }
    function colorElegido() { return _colorElegido; }

    /** Rellena la barra de arriba: primero los colores, luego las marcas. */
    function pintarMarcas() {
        const barra = $('barraComentarios');
        if (!barra) return;
        barra.innerHTML = '';

        for (const color of COLORES) {
            const punto = document.createElement('button');
            punto.type = 'button';
            punto.className = 'color-comentario' + (color === _colorElegido ? ' activo' : '');
            punto.style.background = color;
            punto.title = 'Color del comentario';
            punto.addEventListener('click', () => { _colorElegido = color; pintarMarcas(); });
            barra.appendChild(punto);
        }

        const sep = document.createElement('div');
        sep.className = 'sep-comentarios';
        barra.appendChild(sep);

        for (const marca of MARCAS) {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'mini-btn' + (marca.clave === _marcaElegida ? ' activo' : '');
            boton.title = marca.nombre;
            // El icono se pinta del color elegido: así se ve cómo va a quedar.
            boton.innerHTML = '<i class="bi ' + marca.icono + '" style="color:' + _colorElegido + ';"></i>';
            boton.addEventListener('click', () => { _marcaElegida = marca.clave; pintarMarcas(); });
            barra.appendChild(boton);
        }

        const ayuda = document.createElement('span');
        ayuda.className = 'ayuda-comentarios';
        ayuda.textContent = 'Elige la marca y el color, y pulsa en la hoja donde quieras dejarlo.';
        barra.appendChild(ayuda);
    }

    /** Muestra u oculta la barra. La llama setTool al cambiar de herramienta. */
    function mostrarBarraComentarios(activo) {
        const barra = $('barraComentarios');
        if (!barra) return;
        barra.classList.toggle('hidden', !activo);
        if (activo) pintarMarcas();
    }

    /** La notita para escribir o releer el comentario. Se abre pegada a la marca.
     *  Devuelve el elemento, por si hay que quitarlo desde fuera. */
    function abrirNota(ann, elemento, alGuardar) {
        // Si ya había una abierta, se cierra: dos notas a la vez confunden.
        document.querySelectorAll('.nota-comentario').forEach(n => n.remove());

        const color = ann.color || '#f59e0b';
        const caja = document.createElement('div');
        caja.className = 'nota-comentario';
        caja.style.cssText = 'position:absolute;z-index:900;width:230px;border-radius:8px;' +
            'box-shadow:0 4px 14px rgba(0,0,0,.3);overflow:hidden;background:#fff;' +
            'border:2px solid ' + color + ';';

        const cabecera = document.createElement('div');
        cabecera.style.cssText = 'display:flex;align-items:center;gap:6px;padding:5px 8px;' +
            'font-size:12px;font-weight:600;color:#fff;background:' + color + ';';
        cabecera.innerHTML = '<i class="bi ' + iconoDeLaMarca(ann.marca) + '"></i><span>Comentario</span>';

        const cerrar = document.createElement('button');
        cerrar.type = 'button';
        cerrar.textContent = '✕';
        cerrar.title = 'Cerrar';
        cerrar.style.cssText = 'margin-left:auto;border:0;background:transparent;color:#fff;' +
            'cursor:pointer;font-size:13px;line-height:1;padding:0 2px;';
        cabecera.appendChild(cerrar);

        const texto = document.createElement('textarea');
        texto.value = ann.text || '';
        texto.placeholder = 'Escribe tu comentario…';
        texto.style.cssText = 'display:block;width:100%;height:90px;border:0;outline:none;' +
            'resize:vertical;padding:7px;font-size:12px;font-family:inherit;background:#fff;';

        caja.appendChild(cabecera);
        caja.appendChild(texto);

        // Se coloca justo debajo de la marca, dentro de la misma capa.
        const capa = elemento ? elemento.parentElement : _currentAnnotLayer();
        if (!capa) return null;
        caja.style.left = (parseFloat(elemento?.style.left || 0)) + 'px';
        caja.style.top = (parseFloat(elemento?.style.top || 0) + 26) + 'px';
        capa.appendChild(caja);
        texto.focus();

        // Que escribir dentro no arrastre la anotación ni la borre.
        for (const evento of ['mousedown', 'click', 'dblclick']) {
            caja.addEventListener(evento, ev => ev.stopPropagation());
        }

        const guardar = () => {
            const valor = texto.value.trim();
            caja.remove();
            if (typeof alGuardar === 'function') alGuardar(valor);
        };
        cerrar.addEventListener('click', guardar);
        texto.addEventListener('blur', guardar);
        texto.addEventListener('keydown', ev => {
            if (ev.key === 'Escape') { caja.remove(); if (typeof alGuardar === 'function') alGuardar(null); }
            if (ev.key === 'Enter' && ev.ctrlKey) { ev.preventDefault(); guardar(); }
        });
        return caja;
    }

    /** Pega un comentario nuevo en (x, y) —en puntos del PDF— y abre la nota. */
    function crearComentario(x, y) {
        const pagina = state.currentPage;
        const ann = { type: 'note', x: x, y: y, text: '', marca: _marcaElegida, color: _colorElegido };
        if (!state.annotations[pagina]) state.annotations[pagina] = [];
        state.annotations[pagina].push(ann);
        state.hayCambios = true;
        renderAnnotations(pagina);

        // La marca ya está pintada: se busca para colgarle la nota al lado.
        const capa = _currentAnnotLayer();
        const marcas = capa ? capa.querySelectorAll('.annotation-note') : [];
        const elemento = marcas.length ? marcas[marcas.length - 1] : null;
        abrirNota(ann, elemento, valor => {
            if (valor === null || valor === '') {
                // Un comentario vacío no pinta nada en la hoja: se descarta.
                const lista = state.annotations[pagina] || [];
                const i = lista.indexOf(ann);
                if (i >= 0) lista.splice(i, 1);
            } else {
                ann.text = valor;
            }
            renderAnnotations(pagina);
        });
        // La herramienta se queda puesta: se suelen dejar varios comentarios seguidos.
    }


    /** Cómo se dibuja cada marca en el PDF que se descarga.
     *
     *  En pantalla la marca es un icono de una tipografía; en el PDF no se puede usar esa
     *  tipografía (es un archivo .woff, y pdf-lib solo admite TTF/OTF), así que cada marca
     *  se dibuja con vectores. Se hace para que lo que se descarga sea lo que se ve: antes
     *  cualquier comentario salía en el PDF como un cuadrado naranja, dijera lo que dijera
     *  la pantalla.
     *
     *  Los trazados están en una cuadrícula de 16x16, como los iconos originales, y se
     *  escalan al tamaño que toque. `relleno: false` significa que se dibuja la línea. */
    const TRAZADOS = {
        // Nota adhesiva: papelito con la esquina doblada (no es igual que el bocadillo).
        nota:     { d: 'M 2.5 2.5 L 13.5 2.5 L 13.5 9.5 L 9.5 13.5 L 2.5 13.5 Z', relleno: true },
        globo:    { d: 'M 3 3 L 13 3 L 13 10 L 9 10 L 6 13.5 L 6 10 L 3 10 Z', relleno: true },
        cuadro:   { d: 'M 2.5 3 L 13.5 3 L 13.5 11 L 8 11 L 4.5 14 L 5 11 L 2.5 11 Z', relleno: true },
        punto:    { d: 'M 8 3 C 10.76 3 13 5.24 13 8 C 13 10.76 10.76 13 8 13 C 5.24 13 3 10.76 3 8 C 3 5.24 5.24 3 8 3 Z', relleno: true },
        visto:    { d: 'M 2.5 8.5 L 6.5 12.5 L 13.5 3.5', relleno: false, grosor: 2.2 },
        equis:    { d: 'M 3.5 3.5 L 12.5 12.5 M 12.5 3.5 L 3.5 12.5', relleno: false, grosor: 2.2 },
        flecha:   { d: 'M 2 8 L 12.5 8 M 12.5 8 L 8.5 4.5 M 12.5 8 L 8.5 11.5', relleno: false, grosor: 2 },
        estrella: { d: 'M 8 1.5 L 10 6 L 14.8 6.4 L 11.2 9.6 L 12.3 14.3 L 8 11.8 L 3.7 14.3 L 4.8 9.6 L 1.2 6.4 L 6 6 Z', relleno: true },
        llave:    { d: 'M 5.5 5.5 C 6.9 5.5 8 6.6 8 8 C 8 9.4 6.9 10.5 5.5 10.5 C 4.1 10.5 3 9.4 3 8 C 3 6.6 4.1 5.5 5.5 5.5 Z M 8 8 L 14 8 M 11.5 8 L 11.5 10.5 M 14 8 L 14 10.8', relleno: false, grosor: 1.8 },
        // La interrogación se dibuja con letra Helvetica: es lo que mejor se lee, y esa
        // tipografía va incrustada en el PDF sin tener que añadir nada.
        duda:     { texto: '?' },
    };

    /** Dibuja la marca de un comentario en la página del PDF que se está descargando.
     *  `ayudas` trae lo que hace falta de pdf-lib: {rgb, colorRgb, tamano, fuente}.
     *  Devuelve true si la dibujó; false si esa marca no se conoce (el que llama pinta
     *  entonces lo de siempre). */
    function hornearMarca(pagina, ann, ayudas) {
        const trazado = TRAZADOS[ann.marca || 'nota'];
        if (!trazado) return false;
        const color = ayudas.colorRgb;
        const tam = ayudas.tamano || 20;

        if (trazado.texto) {
            pagina.drawText(trazado.texto, {
                x: ayudas.x + tam * 0.25, y: ayudas.y + tam * 0.1,
                size: tam, color: color, font: ayudas.fuente,
            });
            return true;
        }

        const escala = tam / 16;
        // pdf-lib dibuja el trazado hacia abajo desde el punto que se le da, igual que
        // en un SVG: por eso la `y` es la de ARRIBA de la marca.
        const opciones = { x: ayudas.x, y: ayudas.y + tam, scale: escala };
        if (trazado.relleno) {
            opciones.color = color;
        } else {
            opciones.borderColor = color;
            opciones.borderWidth = (trazado.grosor || 2) * escala;
        }
        pagina.drawSvgPath(trazado.d, opciones);
        return true;
    }

    pintarMarcas();

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { crearComentario, abrirNota, marcaElegida, colorElegido,
                       iconoDeLaMarca, pintarMarcas, mostrarBarraComentarios, hornearMarca });
};
