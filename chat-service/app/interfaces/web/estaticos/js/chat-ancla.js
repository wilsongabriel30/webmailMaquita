/* =============================================================================
   T-54a · LLEGAR AL MENSAJE SIN PASEO
   -----------------------------------------------------------------------------
   QUE HACE: al abrir una conversación, coloca la vista DE GOLPE donde toca —en el
   primer mensaje sin leer si lo hay, y si no al final— sin recorrer animadamente
   toda la historia por el camino.
   POR QUE:  abrir un chat con cientos de mensajes y ver pasar volando meses de
   conversación es molesto y desorienta; en Teams la vista simplemente ya está
   donde tiene que estar.
   EL CULPABLE ERA UN ESTILO: `.chat-messages` tenía `scroll-behavior: smooth`
   (puesto en T-45), y con eso el navegador ANIMA hasta los saltos directos que
   hace el propio código. Se quitó de ahí y quedó solo donde se pide a mano.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html después de los guiones del
   chat, porque se apoya en lo que ellos pintan.
   ============================================================================= */
(function (global) {
    'use strict';

    function contenedor() {
        return document.getElementById('chatMessages');
    }

    /* Coloca la vista sin animación, pase lo que pase: se apaga el desplazamiento
       suave mientras dura el salto y se vuelve a dejar como estaba. */
    function saltarA(cont, arriba) {
        var previo = cont.style.scrollBehavior;
        cont.style.scrollBehavior = 'auto';
        cont.scrollTop = arriba;
        // se restituye en el siguiente ciclo, para que el salto ya haya ocurrido
        requestAnimationFrame(function () { cont.style.scrollBehavior = previo || ''; });
    }

    /* El hilo se pinta más de una vez —primero lo guardado en el equipo y después lo que
       llega del servidor— y el propio chat se coloca al final cada vez que carga mensajes.
       Si solo se anclara una vez, ganaría quien llegase el último y la vista acabaría abajo:
       pasaba una de cada cuatro veces. Así que, cuando se pidió un mensaje concreto, se
       REAFIRMA la posición durante unos segundos. Se deja de insistir en cuanto la persona
       toca el scroll: mandar sobre quien está leyendo sería peor que el problema. */
    function mantener(cont, elemento) {
        var hasta = Date.now() + 4000;
        var soltar = function () { hasta = 0; };
        cont.addEventListener('wheel', soltar, {once: true, passive: true});
        cont.addEventListener('touchstart', soltar, {once: true, passive: true});
        var reloj = setInterval(function () {
            if (Date.now() > hasta || !elemento.isConnected) {
                clearInterval(reloj);
                cont.removeEventListener('wheel', soltar);
                cont.removeEventListener('touchstart', soltar);
                return;
            }
            var quiero = elemento.offsetTop - cont.clientHeight / 3;
            if (Math.abs(cont.scrollTop - quiero) > 40) saltarA(cont, quiero);
        }, 250);
    }

    /* Dónde hay que quedarse:
         1. el mensaje concreto que se pidió (?msg=), si viene;
         2. el primer mensaje sin leer (la línea «Mensajes nuevos»);
         3. el final, que es lo normal cuando no hay nada pendiente. */
    function anclar() {
        var cont = contenedor();
        if (!cont || !cont.querySelector('.message')) return false;

        var pedido = new URLSearchParams(location.search).get('msg');
        if (pedido) {
            var ese = cont.querySelector('.message[data-message-id="' + pedido + '"]');
            if (ese) {
                saltarA(cont, ese.offsetTop - cont.clientHeight / 3);
                ese.classList.add('msg-resaltado');
                setTimeout(function () { ese.classList.remove('msg-resaltado'); }, 2000);
                mantener(cont, ese);
                return true;
            }
        }

        var marca = cont.querySelector('.mq-nuevos');
        if (marca) {
            // un poco por encima de la línea, para que se vea de dónde viene
            saltarA(cont, Math.max(0, marca.offsetTop - 60));
            return true;
        }

        saltarA(cont, cont.scrollHeight);
        return true;
    }

    /* Se ancla en cuanto hay mensajes pintados. Se vigila el hilo porque los mensajes
       llegan de forma asíncrona: primero los del equipo (caché) y luego los del
       servidor, y hay que quedar bien colocado en ambos casos. */
    function vigilar() {
        var cont = contenedor();
        if (!cont || cont.__mqAncla) return;
        cont.__mqAncla = true;
        var hecho = false;
        var obs = new MutationObserver(function () {
            if (hecho) return;
            if (anclar()) {
                hecho = true;
                // se deja de vigilar: a partir de aquí manda la persona
                setTimeout(function () { obs.disconnect(); }, 1200);
            }
        });
        obs.observe(cont, {childList: true});
    }

    /* Al cambiar de conversación hay que volver a anclar */
    function vigilarCambioDeChat() {
        var nombre = document.getElementById('chatHeaderName');
        if (!nombre || nombre.__mqAncla) return;
        nombre.__mqAncla = true;
        new MutationObserver(function () {
            var cont = contenedor();
            if (cont) { cont.__mqAncla = false; vigilar(); }
        }).observe(nombre, {childList: true, characterData: true, subtree: true});
    }

    function iniciar() {
        vigilar();
        vigilarCambioDeChat();
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 600); });
    var intentos = 0;
    var reloj = setInterval(function () {
        iniciar();
        if (++intentos > 20) clearInterval(reloj);
    }, 700);

    global.MaquitaAncla = {anclar: anclar};   // para las pruebas de humo
})(window);
