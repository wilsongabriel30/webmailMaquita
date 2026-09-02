/* ============================================================
   Raíces Maquita - Editor PDF: herramienta MANO (desplazar el documento)

   El botón de la manito existía y se marcaba como activo, pero no hacía
   absolutamente nada: no había ningún manejador de arrastre en todo el
   módulo, y el clic en el visor con la mano puesta terminaba en un `return`.
   El usuario lo reportó el 27-jul-2026 ("no ejecuta la acción correspondiente").

   Aquí está la acción que faltaba: con la mano activa, arrastrar mueve el
   documento igual que en Acrobat — y el puntero lo dice (mano abierta al
   pasar, cerrada al arrastrar). También se puede desplazar con la rueda del
   ratón pulsada, esté la mano activa o no, que es como mucha gente lo espera.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    let api = null;
    let zona = null;
    let arrastrando = false;
    let conRueda = false;       // arrastre con el botón central
    let inicio = { x: 0, y: 0, izq: 0, arriba: 0 };

    function manoActiva() {
        return !!api && api.getHerramienta() === 'hand';
    }

    function pintarCursor() {
        if (!zona) return;
        zona.classList.toggle('cursor-mano', manoActiva() && !arrastrando);
        zona.classList.toggle('cursor-mano-cerrada', arrastrando);
    }

    function empezar(evento) {
        const central = evento.button === 1;
        if (!central && !(evento.button === 0 && manoActiva())) return;
        // Sobre una anotación manda la anotación (moverla, editarla): la mano
        // solo desplaza cuando se agarra el documento, no sus elementos.
        if (!central && evento.target.closest('.annotation')) return;

        arrastrando = true;
        conRueda = central;
        inicio = {
            x: evento.clientX, y: evento.clientY,
            izq: zona.scrollLeft, arriba: zona.scrollTop
        };
        pintarCursor();
        evento.preventDefault();
    }

    function mover(evento) {
        if (!arrastrando) return;
        zona.scrollLeft = inicio.izq - (evento.clientX - inicio.x);
        zona.scrollTop = inicio.arriba - (evento.clientY - inicio.y);
        evento.preventDefault();
    }

    function terminar() {
        if (!arrastrando) return;
        arrastrando = false;
        conRueda = false;
        pintarCursor();
    }

    function iniciar(puente) {
        api = puente;
        zona = document.getElementById('viewerScroll');
        if (!zona) return;

        zona.addEventListener('mousedown', empezar);
        // En window, no en la zona: si el puntero se sale mientras arrastra,
        // el documento tiene que seguir moviéndose y soltarse donde sea.
        window.addEventListener('mousemove', mover);
        window.addEventListener('mouseup', terminar);
        zona.addEventListener('mouseleave', () => { if (!arrastrando) pintarCursor(); });
        // El botón central del ratón abre el "autoscroll" del navegador: estorba
        zona.addEventListener('auxclick', e => { if (e.button === 1) e.preventDefault(); });

        // Táctil: en tabletas el desplazamiento nativo ya funciona, no se toca.
        pintarCursor();
    }

    window.PDFManoDesplazar = { iniciar: iniciar, refrescar: pintarCursor };
})();
