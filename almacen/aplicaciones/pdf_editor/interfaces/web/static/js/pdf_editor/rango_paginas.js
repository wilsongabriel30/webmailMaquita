/* ============================================================
   Raíces Maquita - Editor PDF: lectura de RANGOS DE PÁGINAS
   Utilidad pura, sin interfaz: la usan "Organizar páginas"
   (organizar_rango.js) y "Eliminar páginas" (eliminar_paginas.js).

   Entiende lo que el usuario escribe de verdad: "5-40, 55, 90-120",
   "5 a 40", "150-fin", "150-", "40-5" (al revés), con espacios de más.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio
   aquí exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    // ---------- Análisis del rango escrito por el usuario ----------
    // Acepta: "5-40, 55, 90-120" · "5 a 40" · "7" · "50-fin" · "50-" · "fin"
    // Separadores: coma, punto y coma o salto de línea. Los espacios sobran.
    // Devuelve { páginas:[nums ordenados sin repetir], fuera:[nums inexistentes], error:'' }
    function analizarRango(texto, totalPaginas) {
        const res = { paginas: [], fuera: [], error: '' };
        const limpio = String(texto || '').trim();
        if (!limpio) { res.error = 'Escribe el rango de páginas que quieres marcar. Por ejemplo: 5-40, 55, 90-120'; return res; }

        const esFin = t => /^(fin|final|ultima|última|last)$/i.test(t);
        const aNumero = t => {
            if (esFin(t)) return totalPaginas;
            if (!/^\d+$/.test(t)) return NaN;
            return parseInt(t, 10);
        };

        const vistos = new Set();
        const fuera  = new Set();
        const trozos = limpio.split(/[,;\n]+/).map(t => t.trim()).filter(Boolean);

        for (const trozo of trozos) {
            // "5-40", "5 a 40", "50-" (abierto hasta el final) o una página suelta
            const m = trozo.match(/^(\d+|fin|final|ultima|última|last)\s*(?:-|–|—|\s+a\s+|\.\.)\s*(\d+|fin|final|ultima|última|last)?$/i);
            let desde, hasta;
            if (m) {
                desde = aNumero(m[1]);
                hasta = (m[2] === undefined || m[2] === '') ? totalPaginas : aNumero(m[2]);
            } else {
                desde = hasta = aNumero(trozo);
            }
            if (isNaN(desde) || isNaN(hasta)) {
                res.error = `No entiendo "${trozo}". Usa números y guiones, por ejemplo: 5-40, 55, 90-120`;
                return res;
            }
            if (desde > hasta) { const t = desde; desde = hasta; hasta = t; }  // "40-5" se lee al derecho
            for (let n = desde; n <= hasta; n++) {
                if (n < 1 || n > totalPaginas) fuera.add(n);
                else vistos.add(n);
            }
        }

        res.paginas = Array.from(vistos).sort((a, b) => a - b);
        res.fuera   = Array.from(fuera).sort((a, b) => a - b);
        if (!res.paginas.length && !res.error) {
            res.error = 'Ninguna de esas páginas existe en el documento.';
        }
        return res;
    }

    // Resume una lista de números como rangos: [1,2,3,7,9,10] -> "1-3, 7, 9-10"
    function resumirLista(nums, maxTrozos) {
        const tope = maxTrozos || 6;
        const partes = [];
        for (let i = 0; i < nums.length;) {
            let j = i;
            while (j + 1 < nums.length && nums[j + 1] === nums[j] + 1) j++;
            partes.push(i === j ? String(nums[i]) : `${nums[i]}-${nums[j]}`);
            i = j + 1;
        }
        if (partes.length > tope) {
            return partes.slice(0, tope).join(', ') + ` … (+${partes.length - tope} más)`;
        }
        return partes.join(', ');
    }


    window.PDFRangoPaginas = { analizarRango, resumirLista };
})();
