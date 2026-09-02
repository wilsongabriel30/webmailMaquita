/**
 * El pellizco de dos dedos del touchpad hace zoom.
 * =================================================================
 * «que el scroll siga desplazando; con el touch de la laptop, dos dedos, ahí
 * debe hacer el zoom» — el usuario, 18-ago-2026.
 *
 * La rueda del ratón y el deslizar de dos dedos siguen desplazando el documento
 * como siempre: aquí no se toca nada de eso. Lo que se atiende es el
 * **pellizco**: juntar o separar dos dedos sobre el touchpad.
 *
 * Los navegadores no tienen un evento propio para el pellizco: lo mandan como
 * una rueda con la tecla Ctrl puesta (así lo hacen Chrome, Firefox y Edge), y
 * Safari además avisa con sus `gesture*`. Se atienden las dos formas. De paso,
 * quien use ratón puede hacer zoom con Ctrl y la rueda, que es lo que ya hacen
 * Acrobat y el visor del navegador.
 *
 * Dos cuidados para que se sienta bien:
 *
 * · **El zoom va al punto donde está el cursor**, no al centro de la pantalla:
 *   lo que se está mirando se queda quieto mientras el resto crece o encoge.
 * · Redibujar la página cuesta, y un pellizco manda decenas de avisos por
 *   segundo. El zoom se acumula y se dibuja **una sola vez** cuando el gesto se
 *   calma; mientras tanto se ve el rótulo con el porcentaje.
 *
 * Autoría: Equipo de Tecnología Maquita — 2026-08-18
 */
(function () {
    'use strict';

    const MINIMO = 0.1;
    const MAXIMO = 4;
    // Cuánto se espera desde el último aviso para redibujar. Lo justo para no
    // dibujar cincuenta veces en un pellizco y que aun así responda al momento.
    const CALMA_MS = 90;

    let pendiente = null;        // el zoom al que se quiere llegar
    let anclaje = null;          // qué punto del documento hay que dejar quieto
    let temporizador = null;
    let dibujando = false;

    function vista() {
        return window.PDFVista;
    }

    function visor() {
        const v = vista();
        return v ? v.visor() : null;
    }

    /** Qué punto del documento está bajo el cursor, en tanto por uno. */
    function anclarEn(evento) {
        const caja = visor();
        if (!caja) return null;
        const marco = caja.getBoundingClientRect();
        const x = evento.clientX - marco.left;
        const y = evento.clientY - marco.top;
        return {
            // Dónde cae el cursor dentro del documento entero (0 = principio).
            proporcionX: (caja.scrollLeft + x) / Math.max(1, caja.scrollWidth),
            proporcionY: (caja.scrollTop + y) / Math.max(1, caja.scrollHeight),
            // Y en qué punto de la ventana estaba, para volver a ponerlo ahí.
            dentroX: x,
            dentroY: y
        };
    }

    function devolverElPunto(punto) {
        const caja = visor();
        if (!caja || !punto) return;
        caja.scrollLeft = punto.proporcionX * caja.scrollWidth - punto.dentroX;
        caja.scrollTop = punto.proporcionY * caja.scrollHeight - punto.dentroY;
    }

    function anunciar(zoom) {
        const rotulo = document.getElementById('zoomIndicador');
        if (rotulo) rotulo.textContent = Math.round(zoom * 100) + '%';
    }

    async function dibujar() {
        temporizador = null;
        if (dibujando || pendiente === null) return;
        const destino = pendiente;
        const punto = anclaje;
        pendiente = null;
        dibujando = true;
        try {
            await vista().ponerZoom(destino);
            devolverElPunto(punto);
        } catch (e) {
            /* si algo falla, el zoom se queda como estaba */
        } finally {
            dibujando = false;
            // Si mientras se dibujaba el usuario siguió pellizcando, se atiende.
            if (pendiente !== null) programar();
        }
    }

    function programar() {
        if (temporizador) clearTimeout(temporizador);
        temporizador = setTimeout(dibujar, CALMA_MS);
    }

    /** Aplica un factor de zoom (1,05 = un pelín más grande). */
    function acercar(factor, evento) {
        const v = vista();
        if (!v || !v.hayDocumento()) return;
        const desde = pendiente === null ? v.zoom() : pendiente;
        const destino = Math.min(MAXIMO, Math.max(MINIMO,
                                 Math.round(desde * factor * 100) / 100));
        if (destino === desde) return;
        pendiente = destino;
        if (evento) anclaje = anclarEn(evento);
        anunciar(destino);
        programar();
    }

    function alRodar(evento) {
        // Sin Ctrl es un desplazamiento de los de toda la vida: no se toca.
        if (!evento.ctrlKey && !evento.metaKey) return;
        evento.preventDefault();
        acercar(Math.exp(-_pasoDe(evento) * 0.01), evento);
    }

    /**
     * Cuánto se ha movido el gesto, en una medida que sirva para los dos.
     *
     * El pellizco del touchpad manda muchos avisos pequeños y la rueda del
     * ratón manda pocos y enormes (100 de golpe, o «líneas» y «páginas» en vez
     * de puntos, según el navegador). Se pasa todo a puntos y se recorta a 30:
     * así una muesca de rueda agranda un tercio —que es un paso cómodo— en vez
     * de casi triplicar el tamaño de un salto, y el pellizco, que va sumando
     * avisos pequeños, sigue igual de fino.
     */
    function _pasoDe(evento) {
        const porModo = evento.deltaMode === 1 ? 16      // por líneas
                      : evento.deltaMode === 2 ? 100     // por pantallas
                      : 1;                               // por puntos
        const movido = (evento.deltaY || 0) * porModo;
        return Math.max(-30, Math.min(30, movido));
    }

    // Safari (y iPadOS) avisan del pellizco con sus propios eventos.
    let escalaPrevia = 1;

    function alEmpezarGesto(evento) {
        evento.preventDefault();
        escalaPrevia = 1;
        anclaje = anclarEn(evento);
    }

    function alCambiarGesto(evento) {
        evento.preventDefault();
        const escala = evento.scale || 1;
        if (!escalaPrevia) escalaPrevia = 1;
        acercar(escala / escalaPrevia, evento);
        escalaPrevia = escala;
    }

    function arrancar() {
        const caja = visor();
        if (!caja) return;
        // `passive: false` es imprescindible: si no, el navegador no deja
        // impedir su propio zoom de la página entera y acabaría agrandando el
        // editor completo en vez del documento.
        caja.addEventListener('wheel', alRodar, {passive: false});
        caja.addEventListener('gesturestart', alEmpezarGesto, {passive: false});
        caja.addEventListener('gesturechange', alCambiarGesto, {passive: false});
        caja.addEventListener('gestureend', e => e.preventDefault(), {passive: false});
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();
