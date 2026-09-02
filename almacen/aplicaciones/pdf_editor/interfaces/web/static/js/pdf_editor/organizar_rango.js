/* ============================================================
   Raíces Maquita - Editor PDF: eliminar/seleccionar páginas POR RANGO
   Módulo aparte de editor_nucleo.js (regla: no engordar el monolito).

   Resuelve el caso de los documentos enormes: marcar cientos de páginas
   una por una con el ratón no es viable. Aquí se escribe el rango
   ("5-40, 55, 90-120") y se marca, se elimina o se conserva de golpe.

   El núcleo expone las primitivas en window.PDFOrganizarAPI; aquí vive
   TODO lo demás: el análisis del texto, la interfaz y los avisos.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio
   aquí exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    // El análisis del texto vive en rango_paginas.js (lo comparten los dos modales)
    const { analizarRango, resumirLista } = window.PDFRangoPaginas;

    // ---------- Interfaz ----------
    const $ = id => document.getElementById(id);
    let api = null;          // primitivas del núcleo
    let conectado = false;   // los oyentes se cuelgan una sola vez

    // Números de página que HOY siguen en el documento (el orden puede estar cambiado)
    function paginasVivas() {
        return api.getOrden().map(idx => idx + 1);
    }

    function avisar(msg, tipo) {
        const info = $('infoRangoOrganizar');
        if (!info) return;
        info.textContent = msg || '';
        info.style.color = tipo === 'error' ? '#dc2626' : (tipo === 'ok' ? '#15803d' : '#6d6d6d');
    }

    // Lee el campo y devuelve las páginas pedidas que además siguen en el documento.
    // Si algo no cuadra, avisa y devuelve null.
    function paginasPedidas() {
        const vivas = paginasVivas();
        const total = api.getTotalOriginal();
        const r = analizarRango($('inpRangoOrganizar').value, total);
        if (r.error) { avisar(r.error, 'error'); return null; }

        const setVivas = new Set(vivas);
        const pedidas  = r.paginas.filter(n => setVivas.has(n));
        const yaFuera  = r.paginas.filter(n => !setVivas.has(n));

        if (!pedidas.length) {
            avisar('Esas páginas ya no están en el documento (las quitaste antes).', 'error');
            return null;
        }
        const notas = [];
        if (r.fuera.length)  notas.push(`el documento solo llega a la página ${total}`);
        if (yaFuera.length)  notas.push(`${yaFuera.length} ya estaban quitadas`);
        return { pedidas, notas };
    }

    function alMarcar() {
        const r = paginasPedidas();
        if (!r) return;
        const n = api.marcarPaginas(r.pedidas);
        const cola = r.notas.length ? ` (${r.notas.join('; ')})` : '';
        avisar(`${n} página${n === 1 ? '' : 's'} marcada${n === 1 ? '' : 's'}: ${resumirLista(r.pedidas)}${cola}`, 'ok');
    }

    function alEliminar() {
        const r = paginasPedidas();
        if (!r) return;
        quitar(r.pedidas, r.notas, false);
    }

    function alConservar() {
        const r = paginasPedidas();
        if (!r) return;
        const conservar = new Set(r.pedidas);
        const aQuitar = paginasVivas().filter(n => !conservar.has(n));
        if (!aQuitar.length) { avisar('El rango ya es todo el documento: no hay nada que quitar.', 'error'); return; }
        quitar(aQuitar, r.notas, true);
    }

    function quitar(paginas, notas, esConservar) {
        const vivas = paginasVivas();
        if (paginas.length >= vivas.length) {
            api.toast('No puedes eliminar todas las páginas', 'warn');
            avisar('Tiene que quedar al menos una página.', 'error');
            return;
        }
        const quedan = vivas.length - paginas.length;
        const texto = esConservar
            ? `Se conservarán ${quedan} página(s) y se eliminarán las otras ${paginas.length}:\n\n${resumirLista(paginas, 12)}\n\n¿Continuar?`
            : `¿Eliminar ${paginas.length} página(s)?\n\n${resumirLista(paginas, 12)}\n\nQuedarán ${quedan} página(s).`;
        if (!confirm(texto)) return;

        api.quitarPaginas(paginas);   // el núcleo re-dibuja el grid
        $('inpRangoOrganizar').value = '';
        const cola = notas && notas.length ? ` (${notas.join('; ')})` : '';
        avisar(`${paginas.length} página(s) marcadas para eliminar. Pulsa "Aplicar cambios" para confirmarlo.${cola}`, 'ok');
        api.toast(`${paginas.length} página(s) marcadas para eliminar. Haz clic en "Aplicar cambios" para confirmar.`, 'info');
    }

    // ---------- Enganche con el núcleo ----------
    // El núcleo llama a esto cada vez que abre "Organizar páginas".
    window.PDFOrganizarRango = {
        iniciar(apiNucleo) {
            api = apiNucleo;
            const inp = $('inpRangoOrganizar');
            if (!inp) return;                       // plantilla antigua: no rompe nada
            if (!conectado) {
                $('btnRangoMarcar')?.addEventListener('click', alMarcar);
                $('btnRangoEliminar')?.addEventListener('click', alEliminar);
                $('btnRangoConservar')?.addEventListener('click', alConservar);
                inp.addEventListener('keydown', e => {
                    if (e.key === 'Enter') { e.preventDefault(); alMarcar(); }
                });
                // Las flechas ↑ ↓ mueven la ficha seleccionada del grid: escribiendo
                // en el campo NO deben hacerlo, ni tampoco navegar por el documento.
                inp.addEventListener('keydown', e => {
                    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') e.stopPropagation();
                });
                conectado = true;
            }
            const total = api.getTotalOriginal();
            inp.value = '';
            inp.placeholder = `Ej.: 5-40, 55, 90-${Math.min(120, total)}`;
            avisar(`El documento tiene ${total} páginas. Separa con comas, usa guión para los rangos (5-40) `
                 + `y "fin" para llegar a la última (150-fin).`);
        },
        // expuesto para las pruebas
        _analizarRango: analizarRango,
        _resumirLista: resumirLista
    };
})();
