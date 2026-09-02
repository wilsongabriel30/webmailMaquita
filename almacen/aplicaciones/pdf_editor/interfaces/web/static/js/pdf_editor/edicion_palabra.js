/* ============================================================
   Raíces Maquita - Editor PDF: la PALABRA COMPLETA bajo el doble clic

   El problema real (proforma DJI, 24-jul-2026): pdf.js parte el texto en
   trozos donde el PDF cambia el espaciado, y los PDF hechos con Word parten
   los importes. El valor "2.200" llegaba a la página como TRES trozos
   —"2" · ".2" · "00"— así que el doble clic solo cogía un pedazo y el
   usuario "no podía editar los valores": cambiaba el 2 y el resto seguía ahí.

   Aquí se reconstruye la palabra tal como se VE: se cruzan los trozos
   contiguos del mismo renglón que están pegados (sin espacio real entre
   ellos), y se devuelve el recuadro y el texto de todo el conjunto.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    const spanDe = nodo => {
        const el = nodo && nodo.nodeType === 3 ? nodo.parentElement : nodo;
        return el && el.closest ? el.closest('.textLayer span') : null;
    };

    // Nodo de texto útil de un trozo (pdf.js mete el texto directo en el span)
    const textoDe = span => (span && span.firstChild && span.firstChild.nodeType === 3)
        ? span.firstChild : null;

    // ¿Están pegados? Mismo renglón y sin hueco de espacio entre ellos.
    function pegados(izq, der) {
        const a = izq.getBoundingClientRect(), b = der.getBoundingClientRect();
        if (!a.width || !b.width) return false;
        const alto = Math.max(a.height, b.height) || 12;
        if (Math.abs(a.top - b.top) > alto * 0.5) return false;   // renglones distintos
        const hueco = b.left - a.right;
        // Un espacio de verdad mide bastante más que esto; se es deliberadamente
        // estricto para no fusionar dos palabras separadas.
        return hueco <= Math.max(1.2, alto * 0.18);
    }

    const acabaEnEspacio   = s => /\s$/.test(s.textContent || '');
    const empiezaEnEspacio = s => /^\s/.test(s.textContent || '');

    window.PDFEdicionPalabra = {
        /**
         * Palabra completa que contiene el punto pulsado, cruzando trozos pegados.
         * @param {Text} nodoTexto nodo de texto donde cayó el doble clic
         * @param {number} desde,hasta offsets ya expandidos DENTRO de ese nodo
         * @returns {{rect: DOMRect, texto: string}|null} null si no aporta nada
         */
        expandir(nodoTexto, desde, hasta) {
            try {
                const span = spanDe(nodoTexto);
                if (!span || !span.parentElement) return null;
                const txt = nodoTexto.textContent || '';
                let ini = span, fin = span;
                let a = Math.max(0, Math.min(desde, txt.length));
                let b = Math.max(a, Math.min(hasta, txt.length));

                // Hacia la izquierda: solo si la palabra llega al borde del trozo
                if (a === 0 && !empiezaEnEspacio(span)) {
                    let prev = ini.previousElementSibling;
                    while (prev && prev.matches('span') && (prev.textContent || '').length
                           && !acabaEnEspacio(prev) && pegados(prev, ini)) {
                        ini = prev;
                        prev = ini.previousElementSibling;
                    }
                }
                // Hacia la derecha, igual
                if (b === txt.length && !acabaEnEspacio(span)) {
                    let sig = fin.nextElementSibling;
                    while (sig && sig.matches('span') && (sig.textContent || '').length
                           && !empiezaEnEspacio(sig) && pegados(fin, sig)) {
                        fin = sig;
                        sig = fin.nextElementSibling;
                    }
                }
                if (ini === span && fin === span) return null;   // no hubo nada que unir

                const nIni = textoDe(ini), nFin = textoDe(fin);
                if (!nIni || !nFin) return null;
                const r = document.createRange();
                r.setStart(nIni, ini === span ? a : 0);
                r.setEnd(nFin, fin === span ? b : (nFin.textContent || '').length);
                const rect = r.getBoundingClientRect();
                const texto = r.toString();
                if (!texto.trim() || rect.width <= 2) return null;
                return { rect, texto };
            } catch (e) {
                return null;   // ante cualquier duda, que siga el camino de siempre
            }
        }
    };
})();
