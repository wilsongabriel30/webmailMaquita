/* ============================================================
   Raíces Maquita — Editor PDF · asistente
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.asistente = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _abrirModal, _cerrarModal, _descargarBlob, _getPdfBlob, _necesitaPDF, mostrarToast, showLoading, state } = E;

    // Funciones que viven en OTRAS partes. No se pueden copiar aquí (puede que
    // aún no estén registradas), así que se piden a `E` al llamarlas:
    const setTool = (...a) => E.setTool(...a);   // parte herramientas
    // ==================== ASISTENTE IA ====================
    // ==================== ASISTENTE DE IA ====================
    // Extrae el texto del documento con pdf.js (sin servidor); si el PDF es
    // escaneado no habrá texto y el llamador recurre al OCR del backend
    async function _extraerTextoPDF(maxCaracteres) {
        let texto = '';
        const tope = Math.min(state.totalPages, 60);
        for (let i = 1; i <= tope && texto.length < maxCaracteres; i++) {
            const page = await state.pdfDoc.getPage(i);
            const tc = await page.getTextContent();
            texto += tc.items.map(it => it.str).join(' ') + '\n';
        }
        return texto.substring(0, maxCaracteres).trim();
    }

    async function _consultarIA(mensaje) {
        const r = await fetch('/api/pdf/ia/consulta', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mensaje })
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || !d.exito) throw new Error(d.mensaje || 'el asistente no está disponible en este momento');
        return d.respuesta;
    }

    async function _textoDelDocumento(maxCaracteres) {
        let texto = await _extraerTextoPDF(maxCaracteres);
        if (!texto) {
            // PDF escaneado: OCR en el servidor
            const fd = new FormData();
            fd.append('archivo', _getPdfBlob(), 'documento.pdf');
            const r = await fetch('/api/pdf/operacion/ocr', { method: 'POST', body: fd });
            const d = await r.json().catch(() => ({}));
            texto = d.exito ? (d.datos.texto_total || '').substring(0, maxCaracteres) : '';
        }
        return texto;
    }

    function abrirAsistenteIA() {
        if (_necesitaPDF()) return;
        $('respuestaIA').innerHTML = '<span style="color:#6d6d6d;">Escribe tu pregunta sobre el documento y pulsa Preguntar.</span>';
        _abrirModal('modalAsistenteIA');
        $('inputPreguntaIA').focus();
    }
    $('btnCerrarIA')?.addEventListener('click', () => _cerrarModal('modalAsistenteIA'));
    $('btnPreguntarIA')?.addEventListener('click', async function() {
        const pregunta = $('inputPreguntaIA').value.trim();
        if (!pregunta) return;
        this.disabled = true;
        // Con el contador se ve que sigue trabajando: un texto fijo durante 30 segundos
        // parece que se quedó colgado.
        const inicio = Date.now();
        const pintarEspera = () => {
            $('respuestaIA').innerHTML = '<i class="bi bi-hourglass-split"></i> Leyendo el documento '
                + 'y consultando al asistente… ' + Math.round((Date.now() - inicio) / 1000) + ' s'
                + '<br><small>Suele tardar entre 15 y 40 segundos.</small>';
        };
        pintarEspera();
        const relojIA = setInterval(pintarEspera, 1000);
        try {
            const textoDoc = await _textoDelDocumento(6000);
            const mensaje = textoDoc
                ? 'Documento PDF:\n' + textoDoc + '\n\nPregunta: ' + pregunta
                : pregunta;
            const respuesta = await _consultarIA(mensaje);
            const div = document.createElement('div');
            div.textContent = respuesta;               // texto plano: sin inyección HTML
            div.style.whiteSpace = 'pre-wrap';
            clearInterval(relojIA);
            $('respuestaIA').innerHTML = '';
            $('respuestaIA').appendChild(div);
        } catch (e) {
            clearInterval(relojIA);
            $('respuestaIA').innerHTML = '<span style="color:#dc2626;">' + e.message + '</span>';
        }
        this.disabled = false;
    });

    $('toolAI')?.addEventListener('click', () => abrirAsistenteIA());
    // Mientras el asistente lee el documento y escribe, no pasa NADA en pantalla: el
    // aviso de «puede tardar unos segundos» se va solo y quedan 20-40 segundos de
    // silencio. Medido el 30-jul-2026: el resumen de una cotización tarda 20 s. El
    // usuario da por hecho que no funciona (dicho tal cual: «resumen generativo no
    // funciona»), cuando por detrás está trabajando. Se hace igual que en la conversión
    // a Office: se bloquea la pantalla, se dice lo que puede tardar y se cuentan los
    // segundos.
    /** El resumen llega en texto con guiones y algún **destacado**, como escribe el
     *  modelo. Pintarlo tal cual (un bloque de texto monoespaciado) se ve mal y cuesta
     *  leerlo, así que se convierte en párrafos y lista de verdad.
     *
     *  Se construye con nodos, NUNCA con innerHTML: el texto viene de fuera y con
     *  innerHTML se podría colar HTML dentro del editor. */
    function _pintarTextoDelResumen(contenedor, texto) {
        let lista = null;
        for (const bruta of String(texto || '').split('\n')) {
            const linea = bruta.trim();
            if (!linea) { lista = null; continue; }

            const esPunto = /^[-*•]\s+/.test(linea);
            if (esPunto) {
                if (!lista) {
                    lista = document.createElement('ul');
                    lista.style.cssText = 'margin:0 0 10px 0;padding-left:20px;';
                    contenedor.appendChild(lista);
                }
                const punto = document.createElement('li');
                punto.style.cssText = 'margin-bottom:5px;';
                _conNegritas(punto, linea.replace(/^[-*•]\s+/, ''));
                lista.appendChild(punto);
                continue;
            }

            lista = null;
            // Los títulos que el modelo marca con # o con **todo en negrita**
            const titulo = /^#{1,6}\s+/.test(linea) || /^\*\*[^*]+\*\*:?$/.test(linea);
            const parrafo = document.createElement(titulo ? 'h4' : 'p');
            parrafo.style.cssText = titulo
                ? 'margin:14px 0 6px;font-size:13px;font-weight:600;color:var(--acrobat-accent, #1473e6);'
                : 'margin:0 0 9px;';
            _conNegritas(parrafo, linea.replace(/^#{1,6}\s+/, ''));
            contenedor.appendChild(parrafo);
        }
        if (!contenedor.childNodes.length) {
            const p = document.createElement('p');
            p.textContent = texto;
            contenedor.appendChild(p);
        }
    }

    /** Escribe el texto respetando los **destacados** del modelo. */
    function _conNegritas(destino, texto) {
        const trozos = String(texto).split(/\*\*([^*]+)\*\*/);
        trozos.forEach((trozo, i) => {
            if (!trozo) return;
            if (i % 2 === 1) {
                const fuerte = document.createElement('strong');
                fuerte.textContent = trozo;
                destino.appendChild(fuerte);
            } else {
                destino.appendChild(document.createTextNode(trozo));
            }
        });
    }

    /** Enseña el resumen en una ventana con la misma pinta que las demás del editor
     *  (antes era un cuadro hecho a mano que desentonaba con todo lo demás). */
    function mostrarResumen(respuesta) {
        document.getElementById('modalResumenIA')?.remove();

        const velo = document.createElement('div');
        velo.className = 'modal-overlay';
        velo.id = 'modalResumenIA';

        const caja = document.createElement('div');
        caja.className = 'modal-content';
        caja.style.maxWidth = '620px';

        const cabecera = document.createElement('div');
        cabecera.className = 'modal-header';
        const titulo = document.createElement('h3');
        const icono = document.createElement('i');
        icono.className = 'bi bi-card-text';
        icono.style.cssText = 'color:var(--acrobat-accent);margin-right:8px;';
        titulo.appendChild(icono);
        titulo.appendChild(document.createTextNode(' Resumen del documento'));
        const cerrar = document.createElement('button');
        cerrar.className = 'modal-close';
        cerrar.title = 'Cierra esta ventana';
        cerrar.innerHTML = '&times;';
        cabecera.appendChild(titulo);
        cabecera.appendChild(cerrar);

        const cuerpo = document.createElement('div');
        cuerpo.className = 'modal-body';
        cuerpo.style.cssText = 'font-size:13px;line-height:1.65;max-height:58vh;overflow-y:auto;';
        _pintarTextoDelResumen(cuerpo, respuesta);

        const aviso = document.createElement('p');
        aviso.style.cssText = 'margin:14px 0 0;font-size:11px;color:#6d6d6d;';
        aviso.textContent = 'Resumen hecho por el asistente a partir del texto del documento. '
                          + 'Conviene repasarlo antes de darlo por bueno.';
        cuerpo.appendChild(aviso);

        const pie = document.createElement('div');
        pie.className = 'modal-footer';
        const copiar = document.createElement('button');
        copiar.className = 'btn-modal secondary';
        copiar.title = 'Copia el resumen al portapapeles';
        copiar.innerHTML = '<i class="bi bi-clipboard"></i> Copiar';
        copiar.addEventListener('click', () => {
            navigator.clipboard.writeText(respuesta)
                .then(() => mostrarToast('Resumen copiado al portapapeles.', 'ok'))
                .catch(() => mostrarToast('No se pudo copiar.', 'warn'));
        });
        const listo = document.createElement('button');
        listo.className = 'btn-modal primary';
        listo.textContent = 'Cerrar';
        pie.appendChild(copiar);
        pie.appendChild(listo);

        caja.appendChild(cabecera);
        caja.appendChild(cuerpo);
        caja.appendChild(pie);
        velo.appendChild(caja);
        document.body.appendChild(velo);

        // Se cierra con el aspa, con el botón, con Escape y pulsando fuera de la caja.
        const quitar = () => {
            velo.remove();
            document.removeEventListener('keydown', porEscape);
        };
        const porEscape = ev => { if (ev.key === 'Escape') quitar(); };
        cerrar.addEventListener('click', quitar);
        listo.addEventListener('click', quitar);
        velo.addEventListener('click', ev => { if (ev.target === velo) quitar(); });
        document.addEventListener('keydown', porEscape);
    }

    let _resumiendo = false;
    $('toolResumen')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        if (_resumiendo) {
            mostrarToast('Ya se está generando el resumen: espera a que termine.', 'warn');
            return;
        }
        (async () => {
            _resumiendo = true;
            const inicio = Date.now();
            const pintar = () => showLoading(true,
                'Generando el resumen… ' + Math.round((Date.now() - inicio) / 1000) + ' s\n' +
                'El asistente lee el documento entero; suele tardar entre 15 y 40 segundos.\n' +
                'No cierres ni recargues la página.');
            pintar();
            const reloj = setInterval(pintar, 1000);
            const terminar = () => { clearInterval(reloj); _resumiendo = false; showLoading(false); };
            try {
                const texto = await _textoDelDocumento(6000);
                if (!texto) {
                    terminar();
                    mostrarToast('No se pudo sacar texto de este documento: si es un escaneo, '
                                 + 'pásalo antes por Digitalizar (OCR).', 'warn');
                    return;
                }
                const respuesta = await _consultarIA('Resume el siguiente documento en bullet points claros y en español:\n\n' + texto);
                terminar();
                mostrarResumen(respuesta);
            } catch(e) {
                terminar();
                mostrarToast('No se pudo generar el resumen: ' + e.message, 'error');
            }
        })();
    });
    $('btnAI')?.addEventListener('click', () => abrirAsistenteIA());

    // ==================== SELLOS DE RELLENA Y FIRMA ====================
    // Botones ✓ ✗ ● ▢ — del panel "Firma electrónica": eligen el sello y cada
    // clic sobre la página lo coloca (arrastrable; doble clic lo elimina)
    const SELLOS_FIRMA = { btnFirmaCheck: 'check', btnFirmaX: 'equis', btnFirmaPunto: 'punto',
                           btnFirmaCuadro: 'cuadro', btnFirmaLinea: 'linea' };
    Object.entries(SELLOS_FIRMA).forEach(([id, subtipo]) => {
        $(id)?.addEventListener('click', () => {
            if (_necesitaPDF()) return;
            if (state.currentTool === 'stamp' && state.selloPendiente === subtipo) {
                state.selloPendiente = null;
                setTool(null);                       // segundo clic al mismo sello: desactivar
                return;
            }
            state.selloPendiente = subtipo;
            if (state.currentTool !== 'stamp') setTool('stamp');
            document.querySelectorAll('.mini-btn').forEach(b => b.classList.remove('active'));
            $(id).classList.add('active');
            mostrarToast('Haz clic en la página donde quieras colocar el sello.', 'ok');
        });
    });
    $('btnFirmaSelect')?.addEventListener('click', () => {
        state.selloPendiente = null;
        setTool(null);
        document.querySelectorAll('.mini-btn').forEach(b => b.classList.remove('active'));
        $('btnFirmaSelect').classList.add('active');
        $('btnSelect')?.classList.add('active');
    });

    // ==================== COPIA CERTIFICADA ====================
    $('btnCopiaCartificada')?.addEventListener('click', () => {
        if (_necesitaPDF()) return;
        // Combinar marca de agua "COPIA CERTIFICADA" + protección
        (async () => {
            if (!confirm('Generará una copia con marca de agua "COPIA CERTIFICADA" y protección. ¿Continuar?')) return;
            showLoading(true);
            try {
                const formData = new FormData();
                formData.append('archivo', _getPdfBlob(), 'documento.pdf');
                formData.append('texto', 'COPIA CERTIFICADA');
                formData.append('opacidad', '0.20');
                formData.append('tamano', '50');
                formData.append('rotacion', '45');
                const resp = await fetch('/api/pdf/operacion/marca-agua', { method: 'POST', body: formData });
                if (!resp.ok) throw new Error('Error al aplicar marca de agua');
                const blob = await resp.blob();
                _descargarBlob(blob, 'copia_certificada.pdf');
                mostrarToast('Copia certificada generada y descargada', 'ok');
            } catch(e) { mostrarToast('Error: ' + e.message, 'error'); }
            finally { showLoading(false); }
        })();
    });

};
