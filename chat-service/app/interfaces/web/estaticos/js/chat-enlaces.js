/* Enlaces dentro de los mensajes del chat.
 *
 * El texto de los mensajes se pintaba solo con escapeHtml(): quien pegaba una dirección
 * (un archivo del Drive, un acta, una noticia) se la veía como texto muerto y la otra
 * persona tenía que copiarla a mano. Aquí se escapa igual —el texto NUNCA se interpreta
 * como HTML— y después se convierten en enlaces las direcciones http:// y https://.
 *
 * Se escapa PRIMERO y se enlaza DESPUÉS, sobre el texto ya escapado: así ninguna parte
 * del mensaje puede colarse como etiqueta. Solo http y https: nada de javascript:, data:
 * ni otros esquemas.
 *
 * Creado el 21/09/2026 al arreglar los enlaces del chat.
 */
(function () {
    'use strict';

    // Signos finales que casi siempre son puntuación de la frase, no de la dirección.
    var COLA = /[.,;:!?)\]}'"]+$/;

    function escapar(texto) {
        var d = document.createElement('div');
        d.textContent = texto == null ? '' : String(texto);
        return d.innerHTML;
    }

    /* Texto de un mensaje → HTML seguro con las direcciones ya enlazadas. */
    function enlazarTexto(texto) {
        var escapado = escapar(texto);
        // Las comillas quedan FUERA de la dirección: `escapar()` no las toca y dentro del
        // atributo href lo cerrarían. Una dirección de verdad no las lleva sin codificar.
        return escapado.replace(/https?:\/\/[^\s<"']+/g, function (url) {
            var cola = '';
            var m = url.match(COLA);
            if (m) { cola = m[0]; url = url.slice(0, -cola.length); }
            if (!url) return cola;
            return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>' + cola;
        });
    }

    window.enlazarTexto = enlazarTexto;
})();
