/* ============================================================
   Raíces Maquita - Editor PDF: TABLAS en el propio PDF

   «no necesito que me transformes a word sino que ahí mismo me permitas hacer
   esos cambios» · «también debe permitirme agregar filas» · «y quitarlas» ·
   «y agregar texto en esas filas o columnas agregadas» — el usuario, 27-jul-2026.

   Al pulsar "Digitalizar y OCR" el editor reconoce las tablas de la página y
   las señala:

     ➕ arriba, sobre cada raya vertical  → mete una COLUMNA ahí
     ✕  abajo, bajo cada columna          → quita esa COLUMNA
     ➕ a la izquierda, en cada raya       → mete una FILA ahí
     ✕  a la derecha, junto a cada fila    → quita esa FILA
     ‹ › bajo cada columna                 → la MUEVE de sitio
     ↑ ↓ junto a cada fila                 → la MUEVE de sitio
     clic en cualquier CELDA               → se escribe DENTRO de la celda
                                              (Enter guarda · Tab pasa a la siguiente · Esc cancela)

   La edición de texto de siempre NO se pierde: el mismo botón la enciende, así
   que fuera de la tabla se sigue corrigiendo con doble clic sobre la palabra.
   Dentro de la tabla manda el campo de la celda.

   El documento sigue siendo el mismo PDF en todo momento. Reconocer la tabla,
   respetar la letra y volver a dibujarla lo hace el servidor
   (infraestructura/externos/tablas_pdf.py).

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    let api = null;
    let tablas = [];
    let pagina = 0;
    let activo = false;

    function capaDe(numeroPagina) {
        const envoltorio = document.getElementById('pageWrapper_' + numeroPagina);
        if (!envoltorio) return null;
        let capa = envoltorio.querySelector('.capa-tablas');
        if (!capa) {
            capa = document.createElement('div');
            capa.className = 'capa-tablas';
            envoltorio.appendChild(capa);
        }
        return capa;
    }

    function limpiar() {
        cerrarCampo(false);
        document.querySelectorAll('.capa-tablas').forEach(c => c.remove());
        activo = false;
        tablas = [];
    }

    function boton(clase, texto, titulo, izquierda, arriba, alPulsar) {
        const b = document.createElement('button');
        b.className = 'tabla-btn ' + clase;
        b.type = 'button';
        b.textContent = texto;
        b.title = titulo;
        b.style.left = izquierda + 'px';
        b.style.top = arriba + 'px';
        b.addEventListener('click', e => { e.stopPropagation(); alPulsar(); });
        return b;
    }

    // ── dibujar los controles sobre la tabla ─────────────────────────────
    function pintar() {
        const capa = capaDe(pagina);
        if (!capa) return;
        capa.innerHTML = '';
        const zoom = api.getZoom();

        tablas.forEach((tabla, indiceTabla) => {
            const columnas = tabla.columnas;
            const filas = tabla.filas_y || [];
            const [x0, y0, x1, y1] = tabla.bbox;

            const marco = document.createElement('div');
            marco.className = 'tabla-marco';
            marco.style.left = (x0 * zoom) + 'px';
            marco.style.top = (y0 * zoom) + 'px';
            marco.style.width = ((x1 - x0) * zoom) + 'px';
            marco.style.height = ((y1 - y0) * zoom) + 'px';
            capa.appendChild(marco);

            // El asa para llevarse la tabla entera a otro sitio de la hoja.
            if (window.PDFTablasArrastrar) {
                window.PDFTablasArrastrar.ponerAsa({
                    capa: capa, tabla: tabla, indice: indiceTabla, zoom: zoom,
                    alSoltar: moverTablaEntera
                });
            }

            // COLUMNAS: ➕ arriba en cada raya · ✕ abajo en cada columna
            columnas.forEach((x, posicion) => {
                capa.appendChild(boton('tabla-mas', '+',
                    posicion === 0 ? 'Agregar una columna al principio'
                        : (posicion === columnas.length - 1 ? 'Agregar una columna al final'
                            : 'Agregar una columna aquí'),
                    x * zoom, y0 * zoom - 20,
                    () => insertarColumna(indiceTabla, posicion)));
            });
            for (let i = 0; i < columnas.length - 1; i++) {
                const centro = (columnas[i] + columnas[i + 1]) / 2;
                const nombre = (tabla.encabezados || [])[i];
                const etiqueta = nombre ? ' "' + nombre + '"' : ' ' + (i + 1);
                capa.appendChild(boton('tabla-quitar', '×',
                    'Quitar la columna' + etiqueta,
                    centro * zoom, y1 * zoom + 4,
                    () => quitarColumna(indiceTabla, i, nombre)));
                // Mover de sitio: ‹ a la izquierda · › a la derecha. Si la
                // columna es estrecha las dos no caben lado a lado: se apilan,
                // pero NO se ocultan (antes desaparecían y parecía que faltaban).
                const anchoColumna = (columnas[i + 1] - columnas[i]) * zoom;
                const apretada = anchoColumna < 46;
                if (i > 0) {
                    capa.appendChild(boton('tabla-mover', '‹',
                        'Mover la columna' + etiqueta + ' a la izquierda',
                        apretada ? centro * zoom : (centro - 12) * zoom,
                        y1 * zoom + 26,
                        () => moverColumna(indiceTabla, i, i - 1)));
                }
                if (i < columnas.length - 2) {
                    capa.appendChild(boton('tabla-mover', '›',
                        'Mover la columna' + etiqueta + ' a la derecha',
                        apretada ? centro * zoom : (centro + 12) * zoom,
                        y1 * zoom + (apretada ? 46 : 26),
                        () => moverColumna(indiceTabla, i, i + 1)));
                }
            }

            // FILAS: ➕ a la izquierda en cada raya · ✕ a la derecha de cada fila
            filas.forEach((y, posicion) => {
                capa.appendChild(boton('tabla-mas tabla-fila-mas', '+',
                    posicion === 0 ? 'Agregar una fila arriba del todo'
                        : (posicion === filas.length - 1 ? 'Agregar una fila al final'
                            : 'Agregar una fila aquí'),
                    x0 * zoom - 20, y * zoom - 10,
                    () => insertarFila(indiceTabla, posicion)));
            });
            for (let i = 0; i < filas.length - 1; i++) {
                const centro = (filas[i] + filas[i + 1]) / 2;
                capa.appendChild(boton('tabla-quitar tabla-fila-quitar', '×',
                    'Quitar la fila ' + (i + 1) + ' con su contenido',
                    x1 * zoom + 14, centro * zoom - 10,
                    () => quitarFila(indiceTabla, i)));
                // Mover de sitio: ↑ y ↓. Antes solo salían si la fila medía
                // más de 26 px en pantalla, así que en una proforma normal
                // (SUBTOTAL, IVA, TOTAL) no aparecían y parecía que faltaban.
                // Ahora salen siempre: si la fila es baja, van lado a lado.
                const altoFila = (filas[i + 1] - filas[i]) * zoom;
                const filaApretada = altoFila <= 30;
                if (i > 0) {
                    capa.appendChild(boton('tabla-mover tabla-fila-mover', '↑',
                        'Subir la fila ' + (i + 1),
                        x1 * zoom + 36,
                        filaApretada ? (centro * zoom) - 9 : (centro * zoom) - 21,
                        () => moverFila(indiceTabla, i, i - 1)));
                }
                if (i < filas.length - 2) {
                    capa.appendChild(boton('tabla-mover tabla-fila-mover', '↓',
                        'Bajar la fila ' + (i + 1),
                        x1 * zoom + (filaApretada ? 56 : 36),
                        filaApretada ? (centro * zoom) - 9 : (centro * zoom) + 1,
                        () => moverFila(indiceTabla, i, i + 1)));
                }
            }

            // BARRITAS DESLIZANTES: ancho de columna y alto de fila. Viven en
            // su propio archivo (tablas_medidas.js) y usan este mismo envio.
            if (window.PDFTablasMedidas) {
                window.PDFTablasMedidas.pintar(capa, tabla, indiceTabla, zoom,
                                               {enviar: enviar});
            }

            // CELDAS: clic para escribir DENTRO, sobre la celda misma
            for (let f = 0; f < filas.length - 1; f++) {
                for (let c = 0; c < columnas.length - 1; c++) {
                    const zona = document.createElement('div');
                    zona.className = 'tabla-celda';
                    zona.style.left = (columnas[c] * zoom) + 'px';
                    zona.style.top = (filas[f] * zoom) + 'px';
                    zona.style.width = ((columnas[c + 1] - columnas[c]) * zoom) + 'px';
                    zona.style.height = ((filas[f + 1] - filas[f]) * zoom) + 'px';
                    zona.title = 'Escribir aquí';
                    zona.dataset.tabla = indiceTabla;
                    zona.dataset.fila = f;
                    zona.dataset.columna = c;
                    zona.addEventListener('click', () => abrirCampo(zona, indiceTabla, f, c));
                    capa.appendChild(zona);
                }
            }
        });
    }

    // ── acciones ─────────────────────────────────────────────────────────
    async function insertarColumna(indiceTabla, posicion) {
        const titulo = window.prompt('Nombre de la columna nueva (puedes dejarlo vacío):', '');
        if (titulo === null) return;
        await enviar('/api/pdf/tablas/columna', indiceTabla,
                     {accion: 'insertar', posicion: posicion, titulo: titulo},
                     'Agregando la columna…', 'Columna agregada.');
    }

    async function quitarColumna(indiceTabla, posicion, nombre) {
        if (!window.confirm('Se va a quitar la columna' +
                (nombre ? ' "' + nombre + '"' : ' ' + (posicion + 1)) +
                ' con todo su contenido.\n\n¿Seguimos?')) return;
        await enviar('/api/pdf/tablas/columna', indiceTabla,
                     {accion: 'eliminar', posicion: posicion},
                     'Quitando la columna…', 'Columna quitada.');
    }

    async function insertarFila(indiceTabla, posicion) {
        // Si la tabla llega pegada a lo que hay debajo, la fila solo cabe
        // apretando la propia tabla. Se pregunta en vez de decidir por él.
        const tabla = tablas[indiceTabla] || {};
        let empujar = false;
        if ((tabla.sitio_abajo || 0) < 8) {
            empujar = window.confirm(
                'Debajo de esta tabla no queda sitio en la página.\n\n' +
                'Aceptar: BAJAR el texto que hay debajo para hacerle sitio a la fila ' +
                '(si algo no cabe, pasa a una página nueva; el resto del documento no se toca).\n\n' +
                'Cancelar: dejar el resto donde está y hacer hueco dentro de la propia tabla.');
        }
        await enviar('/api/pdf/tablas/fila', indiceTabla,
                     {accion: 'insertar', posicion: posicion, empujar: empujar ? '1' : '0'},
                     empujar ? 'Agregando la fila y bajando lo de abajo…' : 'Agregando la fila…',
                     'Fila agregada: haz clic en sus celdas para escribir.');
    }

    async function quitarFila(indiceTabla, posicion) {
        if (!window.confirm('Se va a quitar la fila ' + (posicion + 1) +
                            ' con todo su contenido.\n\n¿Seguimos?')) return;
        await enviar('/api/pdf/tablas/fila', indiceTabla,
                     {accion: 'eliminar', posicion: posicion},
                     'Quitando la fila…', 'Fila quitada.');
    }

    async function moverColumna(indiceTabla, desde, hasta) {
        await enviar('/api/pdf/tablas/mover', indiceTabla,
                     {que: 'columna', desde: desde, hasta: hasta},
                     'Moviendo la columna…', 'Columna movida.');
    }

    async function moverFila(indiceTabla, desde, hasta) {
        await enviar('/api/pdf/tablas/mover', indiceTabla,
                     {que: 'fila', desde: desde, hasta: hasta},
                     'Moviendo la fila…', 'Fila movida.');
    }

    // Escribir DENTRO de la celda: un campo que se coloca justo encima, con el
    // texto que ya había y con su misma letra y alineación, para que el usuario
    // vea lo que está corrigiendo. Nada de ventanas.
    function datosDeCelda(indiceTabla, fila, columna) {
        const tabla = tablas[indiceTabla] || {};
        const matriz = tabla.celdas || [];
        return (matriz[fila] || [])[columna] || {texto: '', tam: 0, alineacion: 'centro'};
    }

    function cerrarCampo(guardando) {
        const campo = document.querySelector('.tabla-campo');
        if (!campo) return;
        campo.dataset.cerrando = '1';
        if (!guardando) campo.remove();
    }

    function abrirCampo(zona, indiceTabla, fila, columna) {
        cerrarCampo(false);
        const datos = datosDeCelda(indiceTabla, fila, columna);
        const zoom = api.getZoom();
        const tabla = tablas[indiceTabla];
        const alto = (tabla.filas_y[fila + 1] - tabla.filas_y[fila]) * zoom;

        // textarea, no input: una celda puede tener varios renglones (una lista
        // con viñetas, por ejemplo) y con un input se aplastaban en una línea.
        const campo = document.createElement('textarea');
        campo.rows = Math.max(1, (datos.texto || '').split('\n').length);
        campo.className = 'tabla-campo';
        campo.value = datos.texto || '';
        campo.style.left = zona.style.left;
        campo.style.top = zona.style.top;
        campo.style.width = zona.style.width;
        campo.style.height = zona.style.height;
        campo.style.textAlign = datos.alineacion === 'derecha' ? 'right'
            : (datos.alineacion === 'centro' ? 'center' : 'left');
        // El cuerpo de la celda, o uno que quepa en la fila si estaba vacía
        const cuerpo = datos.tam > 0 ? datos.tam : Math.min(11, Math.max(6, alto / zoom * 0.6));
        campo.style.fontSize = (cuerpo * zoom) + 'px';

        // ── Se edita EN EL SITIO, no en un cuadro aparte ──
        // El texto editable se pinta con la misma letra, el mismo color y en la
        // misma posición que el del documento, así que al entrar en edición
        // nada se mueve: solo aparece el cursor. («debe editarse ahí mismo,
        // solo transformándose a texto editable» — el usuario, 28-jul-2026.)
        campo.style.color = datos.color || '#111';
        campo.style.fontWeight = datos.negrita ? '700' : '400';
        campo.style.fontStyle = datos.cursiva ? 'italic' : 'normal';
        if (datos.mono) campo.style.fontFamily = 'monospace';
        const interlineado = (datos.interlineado > 0 ? datos.interlineado : cuerpo * 1.15);
        campo.style.lineHeight = (interlineado * zoom) + 'px';
        // Dónde empieza el texto dentro de la celda: arriba y a la izquierda
        const filaArriba = tabla.filas_y[fila];
        const hueco = Math.max(0, (datos.arriba || filaArriba) - filaArriba - interlineado * 0.18);
        campo.style.paddingTop = (hueco * zoom) + 'px';
        if (datos.alineacion === 'izquierda' && datos.izquierda) {
            const sangria = Math.max(0, datos.izquierda - tabla.columnas[columna]);
            campo.style.paddingLeft = (sangria * zoom) + 'px';
        }
        campo.dataset.original = datos.texto || '';

        campo.addEventListener('keydown', e => {
            // Enter hace salto de línea (la celda puede tener varios renglones);
            // se guarda con Ctrl+Enter, con Tab o saliendo del campo.
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault(); guardarCampo(campo, indiceTabla, fila, columna);
            }
            else if (e.key === 'Escape') { e.preventDefault(); cerrarCampo(false); }
            else if (e.key === 'Tab') {
                e.preventDefault();
                const siguiente = celdaVecina(indiceTabla, fila, columna, e.shiftKey ? -1 : 1);
                guardarCampo(campo, indiceTabla, fila, columna, siguiente);
            }
            e.stopPropagation();     // que las teclas no lleguen al editor de detrás
        });
        campo.addEventListener('blur', () => {
            if (campo.dataset.cerrando) return;
            guardarCampo(campo, indiceTabla, fila, columna);
        });
        campo.addEventListener('click', e => e.stopPropagation());

        zona.parentNode.appendChild(campo);
        campo.focus();
        campo.select();
    }

    // La celda de al lado, para moverse con el tabulador
    function celdaVecina(indiceTabla, fila, columna, sentido) {
        const tabla = tablas[indiceTabla];
        if (!tabla) return null;
        const columnas = tabla.columnas.length - 1;
        const filas = tabla.filas_y.length - 1;
        let f = fila, c = columna + sentido;
        if (c < 0) { f -= 1; c = columnas - 1; }
        if (c >= columnas) { f += 1; c = 0; }
        if (f < 0 || f >= filas) return null;
        return {fila: f, columna: c};
    }

    async function guardarCampo(campo, indiceTabla, fila, columna, siguiente) {
        const texto = campo.value;
        const original = campo.dataset.original || '';
        cerrarCampo(true);
        campo.remove();
        if (texto === original) {
            // No cambió nada: no se molesta al servidor ni se recarga el documento
            if (siguiente) abrirCampoPorIndice(indiceTabla, siguiente.fila, siguiente.columna);
            return;
        }
        await enviar('/api/pdf/tablas/celda', indiceTabla,
                     {fila: fila, columna: columna, texto: texto},
                     'Guardando…', 'Celda actualizada.');
        if (siguiente) abrirCampoPorIndice(indiceTabla, siguiente.fila, siguiente.columna);
    }

    function abrirCampoPorIndice(indiceTabla, fila, columna) {
        const zona = document.querySelector(
            '.tabla-celda[data-tabla="' + indiceTabla + '"][data-fila="' + fila +
            '"][data-columna="' + columna + '"]');
        if (zona) abrirCampo(zona, indiceTabla, fila, columna);
    }

    async function moverTablaEntera(indiceTabla, dx, dy) {
        await enviar('/api/pdf/tablas/mover-tabla', indiceTabla,
                     {dx: dx.toFixed(2), dy: dy.toFixed(2)},
                     'Moviendo la tabla…', 'Tabla movida.');
    }

    // ── el envío, común a todas ──────────────────────────────────────────
    async function enviar(url, indiceTabla, campos, mensajeEspera, mensajeExito) {
        api.showLoading(true, mensajeEspera);
        try {
            const camposTodos = Object.assign({pagina: pagina, tabla: indiceTabla},
                                             campos);
            // El documento ya está en el servidor: solo viaja el cambio, y solo
            // vuelve lo añadido. Si no hubiera sesión, `enviar` manda el PDF
            // entero como se hacía siempre.
            const {bytes, aviso} = await window.PDFSesion.enviar(
                url, camposTodos, api.getPdfBytes());
            const dondeEstaba = pagina;
            await api.reemplazarPdf(bytes);
            // Al recargar, el visor se va al principio: se vuelve a la página
            // de la tabla, que es donde el usuario estaba trabajando.
            if (api.irAPagina) api.irAPagina(dondeEstaba);
            api.toast(mensajeExito, 'ok');
            if (aviso) setTimeout(() => api.toast('Aviso: ' + aviso, 'warn'), 1200);
            await esperarPagina(dondeEstaba);
            await activar(api, true, dondeEstaba);
        } catch (e) {
            api.toast('No se pudo: ' + e.message, 'error');
        } finally {
            api.showLoading(false);
        }
    }

    // ── encender / apagar ────────────────────────────────────────────────
    // El documento acaba de recargarse: la página tarda un momento en estar
    // dibujada, y sin ella no hay dónde colgar los controles.
    function esperarPagina(numero) {
        return new Promise(resolve => {
            let intentos = 0;
            const mirar = () => {
                if (document.getElementById('pageWrapper_' + numero) || ++intentos > 60) resolve();
                else setTimeout(mirar, 250);
            };
            mirar();
        });
    }

    async function activar(puente, silencioso, forzarPagina) {
        api = puente || api;
        if (activo && !silencioso) {
            limpiar();
            if (api.apagarTexto) api.apagarTexto();
            api.toast('Edición desactivada.', 'ok');
            return;
        }
        limpiar();
        pagina = forzarPagina || api.getPagina();
        try {
            const resp = await window.PDFSesion.consultar(
                '/api/pdf/tablas/detectar', {pagina: pagina}, api.getPdfBytes());
            const json = await resp.json();
            if (!json.exito) throw new Error(json.mensaje);
            tablas = json.tablas || [];
            if (!tablas.length) {
                if (!silencioso) {
                    // Aunque no haya tabla, la edición de texto SÍ quedó encendida:
                    // decirlo, o el usuario cree que no pasó nada.
                    api.toast(api.hayTexto && api.hayTexto()
                        ? 'Edición de texto activada: haz doble clic sobre la palabra ' +
                          'que quieras cambiar. En esta página no se reconoció ninguna tabla.'
                        : 'En esta página no se reconoció ninguna tabla ni texto editable.',
                        'warn');
                }
                return;
            }
            activo = true;
            pintar();
            if (!silencioso) {
                api.toast('Listo: en la tabla, ➕ agrega columna o fila, ✕ la quita y el ' +
                          'clic en una celda escribe dentro (Enter guarda, Tab pasa a la ' +
                          'siguiente). Fuera de la tabla, doble clic para corregir el texto.',
                          'ok');
            }
        } catch (e) {
            api.toast('No se pudieron reconocer las tablas: ' + e.message, 'error');
        }
    }

    // Al cambiar el zoom o de página, los controles se recolocan
    function refrescar() {
        if (!activo) return;
        if (api.getPagina() !== pagina) { limpiar(); return; }
        pintar();
    }

    // Tras un deshacer o un rehacer el documento es otro: si los controles
    // estaban puestos, se vuelven a reconocer las tablas de esa página.
    async function refrescarTrasCambio() {
        if (!activo || !api) return;
        const donde = pagina;
        await esperarPagina(donde);
        await activar(api, true, donde);
    }

    // Doble clic dentro de una tabla: se edita ESA celda, en su sitio. Si los
    // controles no estaban puestos se ponen primero, sin decir nada, para que
    // el usuario solo vea aparecer el cursor donde pulsó. (28-jul-2026: antes
    // saltaba el cuadro de «párrafo completo» y el estilo se distorsionaba.)
    async function abrirCelda(puente, numeroPagina, indiceTabla, fila, columna) {
        api = puente || api;
        if (!activo || pagina !== numeroPagina) {
            await activar(api, true, numeroPagina);
        }
        if (!activo) return false;
        abrirCampoPorIndice(indiceTabla, fila, columna);
        return true;
    }

    window.PDFTablasColumnas = {
        activar: activar, refrescar: refrescar, limpiar: limpiar,
        refrescarTrasCambio: refrescarTrasCambio, abrirCelda: abrirCelda
    };
})();
