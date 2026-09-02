/**
 * Las flechas del teclado desplazan el documento.
 * =================================================================
 * «activa las letras de dirección del teclado para bajarlas con ella» — el
 * usuario, 18-ago-2026.
 *
 * Antes solo respondían la flecha izquierda y la derecha, y lo que hacían era
 * cambiar de página. Arriba y abajo no hacían nada: para bajar por el documento
 * había que llevar el ratón a la barra o arrastrar con la mano.
 *
 *   ↑ / ↓        bajar y subir por el documento, poco a poco
 *   ← / →        a los lados cuando el documento no cabe de ancho (zoom grande);
 *                si cabe entero, siguen cambiando de página como siempre
 *   Inicio / Fin  al principio y al final del documento
 *
 * No se estorba a nadie: si se está escribiendo en una casilla, en una nota o
 * en una celda de tabla, las flechas son suyas y aquí no se tocan.
 *
 * Autoría: Equipo de Tecnología Maquita — 2026-08-18
 */
(function () {
    'use strict';

    const PASO = 80;             // lo que baja una pulsación (puntos de pantalla)

    function visor() {
        return window.PDFVista ? window.PDFVista.visor() : null;
    }

    /** ¿El teclado es de otro en este momento? */
    function escribiendo(destino) {
        if (!destino) return false;
        const etiqueta = (destino.tagName || '').toUpperCase();
        if (etiqueta === 'INPUT' || etiqueta === 'TEXTAREA' || etiqueta === 'SELECT') {
            return true;
        }
        if (destino.isContentEditable) return true;
        return !!(destino.closest && destino.closest('.modal-overlay, [role="dialog"]'));
    }

    /**
     * ¿Hay una ventana abierta encima?
     *
     * Con «Organizar páginas» abierto, por ejemplo, las flechas ↑ ↓ mueven la
     * página seleccionada y son suyas. Y como aquí se escucha en captura —para
     * llegar antes que el atajo de pasar página—, si no se mirara esto se
     * desplazaría el documento por detrás de la ventana.
     */
    function hayVentanaAbierta() {
        const abiertas = document.querySelectorAll('.modal-overlay');
        for (const ventana of abiertas) {
            if (ventana.classList.contains('hidden')) continue;
            if (getComputedStyle(ventana).display === 'none') continue;
            return true;
        }
        return false;
    }

    function desplazar(caja, dx, dy, evento) {
        caja.scrollBy({top: dy, left: dx, behavior: 'auto'});
        // Que nadie más atienda esta tecla: sin esto, con el documento ampliado
        // la flecha derecha movería a un lado Y pasaría de página a la vez.
        if (evento) evento.stopPropagation();
    }

    function cabeDeAncho(caja) {
        return caja.scrollWidth <= caja.clientWidth + 4;
    }

    function alPulsar(evento) {
        if (evento.ctrlKey || evento.metaKey || evento.altKey) return;
        if (escribiendo(evento.target) || hayVentanaAbierta()) return;
        const vista = window.PDFVista;
        if (!vista || !vista.hayDocumento()) return;
        const caja = visor();
        if (!caja) return;

        switch (evento.key) {
            case 'ArrowDown':
                evento.preventDefault();
                desplazar(caja, 0, PASO, evento);
                return;
            case 'ArrowUp':
                evento.preventDefault();
                desplazar(caja, 0, -PASO, evento);
                return;
            case 'ArrowRight':
                // Con el documento entero a la vista, la flecha sigue pasando de
                // página (como hasta ahora); si está ampliado, mueve a la derecha.
                if (cabeDeAncho(caja)) return;
                evento.preventDefault();
                desplazar(caja, PASO, 0, evento);
                return;
            case 'ArrowLeft':
                if (cabeDeAncho(caja)) return;
                evento.preventDefault();
                desplazar(caja, -PASO, 0, evento);
                return;
            case 'Home':
                evento.preventDefault();
                caja.scrollTo({top: 0, behavior: 'auto'});
                return;
            case 'End':
                evento.preventDefault();
                caja.scrollTo({top: caja.scrollHeight, behavior: 'auto'});
                return;
            default:
                return;
        }
    }

    // En captura, para llegar antes que el atajo de «página siguiente» del
    // núcleo: si no, la flecha derecha cambiaría de página en vez de mover el
    // documento a los lados cuando está ampliado.
    document.addEventListener('keydown', alPulsar, true);
})();
