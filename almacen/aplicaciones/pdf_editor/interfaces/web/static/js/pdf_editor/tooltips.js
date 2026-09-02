/* ============================================================
   Raíces Maquita - Editor PDF: mensajes emergentes (tooltips)
   Convierte el atributo title de cualquier elemento en un mensaje
   emergente estilizado que aparece al instante (el tooltip nativo
   del navegador tarda ~1 segundo y es poco visible).
   Lo usan home.html e index.html del editor PDF.
   ============================================================ */
(function () {
    'use strict';

    const tip = document.createElement('div');
    tip.className = 'faro-tooltip';
    tip.setAttribute('role', 'tooltip');
    document.addEventListener('DOMContentLoaded', () => document.body.appendChild(tip));
    if (document.body) document.body.appendChild(tip);

    let elActual = null;

    function mostrar(el) {
        // mover title -> data-tip para suprimir el tooltip nativo duplicado
        if (el.getAttribute('title')) {
            el.dataset.tip = el.getAttribute('title');
            el.removeAttribute('title');
        }
        const texto = el.dataset.tip;
        if (!texto) return;
        elActual = el;
        tip.textContent = texto;
        tip.classList.add('visible');

        const r = el.getBoundingClientRect();
        const margen = 8;
        // medir ya visible
        const tw = tip.offsetWidth, th = tip.offsetHeight;
        let x = r.left + r.width / 2 - tw / 2;
        x = Math.max(6, Math.min(x, window.innerWidth - tw - 6));
        let y = r.bottom + margen;                      // preferir debajo
        let arriba = false;
        if (y + th > window.innerHeight - 6) {          // sin espacio: encima
            y = r.top - th - margen;
            arriba = true;
        }
        tip.style.left = x + 'px';
        tip.style.top = Math.max(6, y) + 'px';
        tip.classList.toggle('arriba', arriba);
    }

    function ocultar() {
        elActual = null;
        tip.classList.remove('visible');
    }

    document.addEventListener('mouseover', e => {
        const el = e.target.closest('[title], [data-tip]');
        if (!el) return;
        mostrar(el);
    });

    document.addEventListener('mouseout', e => {
        if (!elActual) return;
        if (e.relatedTarget && elActual.contains(e.relatedTarget)) return;
        ocultar();
    });

    // el mensaje estorbaría al hacer clic o desplazar
    document.addEventListener('mousedown', ocultar, true);
    document.addEventListener('scroll', ocultar, true);
})();
