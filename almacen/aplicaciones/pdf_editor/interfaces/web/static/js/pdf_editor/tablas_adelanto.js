/**
 * «Ve reconociendo esta página, que es la que estoy mirando».
 * =================================================================
 * Reconocer las tablas de una página cuesta entre 0,2 y 0,4 s. Si se hace
 * cuando el usuario pulsa «editar tablas», ese tiempo lo espera él mirando la
 * pantalla («no le reconoce rápidamente lo que es la tabla, se demora
 * bastante»). Si se hace mientras lee la página, no lo espera nadie.
 *
 * Esto es lo único que hace este archivo: cuando el usuario se queda quieto en
 * una página, le pide al servidor que la vaya reconociendo. No espera la
 * respuesta, no muestra nada y, si falla, no pasa absolutamente nada: la
 * consulta de siempre lo calculará como antes.
 *
 * El servidor guarda lo reconocido con el sello del documento de la sesión, el
 * mismo con el que se pregunta después, así que el trabajo adelantado sí se
 * aprovecha (antes del 18-ago-2026 se guardaba con otro sello y se reconocía
 * dos veces).
 *
 * Autoría: Equipo de Tecnología Maquita — 2026-08-18
 */
(function () {
    'use strict';

    // Cuánto tiene que estarse quieto el usuario en una página antes de
    // encargarla. Lo justo para no encargar las veinte páginas por las que
    // pasa de largo cuando va buscando una.
    const ESPERA_MS = 400;

    // Páginas ya encargadas en esta sesión del documento. Si el documento
    // cambia, el servidor lo nota por su sello y lo rehace por su cuenta; aquí
    // solo se evita repetir el encargo mientras nadie toca nada.
    let encargadas = new Set();
    let documento = null;
    let temporizador = null;

    function paginaVisible() {
        const marca = document.getElementById('currentPage');
        const numero = marca ? parseInt(marca.textContent, 10) : NaN;
        return (numero > 0) ? numero : null;
    }

    async function encargar(pagina) {
        // Si el documento se está subiendo, se espera a que termine: encargar
        // sin sesión obligaría a subirlo otra vez entero solo para adelantar
        // trabajo, que costaría más de lo que ahorra.
        const doc = window.PDFSesion && await window.PDFSesion.listo();
        if (!doc || !pagina) return;
        if (doc !== documento) {          // documento nuevo: cuenta desde cero
            documento = doc;
            encargadas = new Set();
        }
        if (encargadas.has(pagina)) return;
        encargadas.add(pagina);
        const cuerpo = new FormData();
        cuerpo.append('doc', doc);
        cuerpo.append('pagina', pagina);
        fetch('/api/pdf/tablas/adelantar', {
            method: 'POST', body: cuerpo, credentials: 'same-origin',
            keepalive: true
        }).catch(() => {
            // Si no llegó, se vuelve a intentar la próxima vez que se pase por
            // aquí. Nadie está esperando esta respuesta.
            encargadas.delete(pagina);
        });
    }

    /** Se llama en cada scroll; solo actúa cuando el usuario se detiene. */
    function alMirar() {
        if (temporizador) clearTimeout(temporizador);
        temporizador = setTimeout(() => {
            temporizador = null;
            encargar(paginaVisible());
        }, ESPERA_MS);
    }

    /** El documento cambió (se editó, se recargó): lo encargado ya no sirve. */
    function olvidar() {
        encargadas = new Set();
    }

    function arrancar() {
        const visor = document.getElementById('viewerScroll');
        if (!visor) return;
        visor.addEventListener('scroll', alMirar, {passive: true});
        // La primera página se encarga en cuanto haya sesión: el servidor ya
        // adelanta las dos primeras al abrir, así que esto solo cubre el caso
        // de que el usuario empiece en otra (documento reabierto, enlace a una
        // página concreta).
        alMirar();
    }

    window.PDFAdelantoTablas = {encargar: encargar, olvidar: olvidar};

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();
