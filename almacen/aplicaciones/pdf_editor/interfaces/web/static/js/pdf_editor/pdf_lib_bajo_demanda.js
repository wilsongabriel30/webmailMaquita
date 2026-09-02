/**
 * pdf-lib, solo cuando de verdad hace falta.
 * =================================================================
 * pdf-lib pesa 512 kB (201 kB comprimidos) y hasta ahora se descargaba y se
 * ejecutaba SIEMPRE, antes de que el editor pudiera arrancar, aunque el usuario
 * solo fuera a mirar un documento. Es la biblioteca más pesada de la página y
 * no se usa para ver: solo para exportar, combinar, organizar, compartir,
 * convertir y recortar imágenes, todas ellas cosas que el usuario pide después.
 *
 * Aquí se carga de otra manera:
 *   · al arrancar no se descarga nada, así que el editor abre antes;
 *   · en cuanto el navegador queda ocioso se descarga sola, en segundo plano,
 *     sin quitarle el turno al dibujado del documento;
 *   · quien la necesite hace `await window.PDFLibListo()` y sigue: si ya está,
 *     devuelve al instante; si no, la carga en ese momento y espera lo justo.
 *
 * Una sola descarga por página, aunque se pida cien veces.
 *
 * Autoría: Equipo de Tecnología Maquita — 2026-08-18
 */
(function () {
    'use strict';

    // La ruta la pone la plantilla, que es la que sabe la versión del vendor.
    const RUTA = (document.currentScript &&
                  document.currentScript.dataset.pdflib) ||
                 '/static/vendor/pdf-lib-1.17.1/pdf-lib.min.js';

    let promesa = null;

    function cargar() {
        if (window.PDFLib) return Promise.resolve(window.PDFLib);
        if (promesa) return promesa;
        promesa = new Promise((resolver, rechazar) => {
            const etiqueta = document.createElement('script');
            etiqueta.src = RUTA;
            etiqueta.async = true;
            etiqueta.onload = () => {
                if (window.PDFLib) resolver(window.PDFLib);
                else rechazar(new Error('pdf-lib se cargó pero no se anunció'));
            };
            etiqueta.onerror = () => {
                // Que un fallo de red no deje la promesa colgada para siempre:
                // el siguiente intento vuelve a probar.
                promesa = null;
                rechazar(new Error('no se pudo cargar pdf-lib'));
            };
            document.head.appendChild(etiqueta);
        });
        return promesa;
    }

    window.PDFLibListo = cargar;

    // Precarga en cuanto haya un hueco: para cuando el usuario pulse «exportar»,
    // casi siempre estará ya. Si el navegador no conoce requestIdleCallback, se
    // espera un par de segundos, que para entonces el documento ya está pintado.
    function precargar() { cargar().catch(() => {}); }
    if (window.requestIdleCallback) {
        window.requestIdleCallback(precargar, {timeout: 5000});
    } else {
        setTimeout(precargar, 2000);
    }
})();
