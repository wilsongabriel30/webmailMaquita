/* ============================================================
   Raíces Maquita - Editor PDF: herramienta "Eliminar páginas"

   Antes borraba la página en la que estabas, sin preguntar cuál. Ahora abre
   una ventana donde se escribe QUÉ páginas quitar: la actual (ya propuesta),
   un rango ("5-40, 55, 90-120") o lo que se quiera conservar.

   La lectura del texto está en rango_paginas.js; el borrado de verdad lo hace
   el núcleo (window.PDFEliminarPaginasAPI).

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    const $ = id => document.getElementById(id);
    const { analizarRango, resumirLista } = window.PDFRangoPaginas;
    let api = null;
    let conectado = false;

    function avisar(msg, tipo) {
        const info = $('infoElimPag');
        if (!info) return;
        info.textContent = msg || '';
        info.style.color = tipo === 'error' ? '#dc2626' : (tipo === 'ok' ? '#15803d' : '#6d6d6d');
    }

    // Lee el campo. Devuelve la lista de páginas o null (ya avisado).
    function leerCampo() {
        const total = api.getTotal();
        const r = analizarRango($('inpElimPag').value, total);
        if (r.error) { avisar(r.error, 'error'); return null; }
        if (r.fuera.length) {
            avisar(`El documento solo llega a la página ${total}: se tomarán ${resumirLista(r.paginas)}.`);
        }
        return r.paginas;
    }

    function refrescarCuenta() {
        const total = api.getTotal();
        const r = analizarRango($('inpElimPag').value, total);
        const btn = $('btnEjecutarElimPag');
        if (r.error || !r.paginas.length) {
            if (btn) btn.disabled = true;
            avisar(($('inpElimPag').value || '').trim() ? r.error : `El documento tiene ${total} páginas.`,
                   ($('inpElimPag').value || '').trim() ? 'error' : '');
            return;
        }
        if (btn) btn.disabled = false;
        const conservar = $('chkElimConservar')?.checked;
        const n = conservar ? total - r.paginas.length : r.paginas.length;
        if (conservar) {
            avisar(`Se conservarán ${r.paginas.length} página(s) — ${resumirLista(r.paginas)} — y se eliminarán las otras ${n}.`);
        } else {
            avisar(`Se eliminarán ${n} página(s): ${resumirLista(r.paginas)}. Quedarán ${total - n}.`);
        }
    }

    async function ejecutar() {
        const pedidas = leerCampo();
        if (!pedidas) return;
        const total = api.getTotal();
        let aQuitar = pedidas;
        if ($('chkElimConservar')?.checked) {
            const dejar = new Set(pedidas);
            aQuitar = [];
            for (let n = 1; n <= total; n++) if (!dejar.has(n)) aQuitar.push(n);
        }
        if (!aQuitar.length) { avisar('No hay páginas que eliminar con esa indicación.', 'error'); return; }
        if (aQuitar.length >= total) {
            avisar('Tiene que quedar al menos una página en el documento.', 'error');
            api.toast('No puedes eliminar todas las páginas', 'warn');
            return;
        }
        const quedan = total - aQuitar.length;
        if (!confirm(`¿Eliminar ${aQuitar.length} página(s)?\n\n${resumirLista(aQuitar, 12)}\n\n`
                   + `Quedarán ${quedan} página(s). Esto se aplica al documento abierto.`)) return;
        api.cerrarModal();
        await api.eliminar(aQuitar);
    }

    // El núcleo llama a esto cuando se pulsa la herramienta "Eliminar páginas".
    window.PDFEliminarPaginas = {
        abrir(apiNucleo) {
            api = apiNucleo;
            const inp = $('inpElimPag');
            if (!inp) { api.eliminarPaginaActual(); return; }   // plantilla antigua: comportamiento de antes
            if (!conectado) {
                $('btnEjecutarElimPag')?.addEventListener('click', ejecutar);
                $('btnCancelarElimPag')?.addEventListener('click', () => api.cerrarModal());
                $('btnCerrarElimPag')?.addEventListener('click', () => api.cerrarModal());
                inp.addEventListener('input', refrescarCuenta);
                $('chkElimConservar')?.addEventListener('change', refrescarCuenta);
                inp.addEventListener('keydown', e => {
                    e.stopPropagation();                       // no navegar el documento mientras se escribe
                    if (e.key === 'Enter') { e.preventDefault(); ejecutar(); }
                });
                $('btnElimPagActual')?.addEventListener('click', () => {
                    $('inpElimPag').value = String(api.getPaginaActual());
                    if ($('chkElimConservar')) $('chkElimConservar').checked = false;
                    refrescarCuenta();
                });
                conectado = true;
            }
            const total = api.getTotal();
            $('lblTotalElimPag').textContent = total;
            $('btnElimPagActual').textContent = 'Página actual (' + api.getPaginaActual() + ')';
            if ($('chkElimConservar')) $('chkElimConservar').checked = false;
            inp.value = String(api.getPaginaActual());          // lo más pedido, ya escrito
            inp.placeholder = `Ej.: 5-40, 55, 90-${Math.min(120, total)}`;
            api.abrirModal();
            refrescarCuenta();
            inp.focus();
            inp.select();
        }
    };
})();
