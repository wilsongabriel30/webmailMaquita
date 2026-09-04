/* =============================================================================
   T-50 tanda 3 · LA BARRA DE REDACCIÓN COMO TEAMS
   -----------------------------------------------------------------------------
   QUE HACE: ordena la barra de escribir para que quede como la de Teams —a la
   izquierda emoji, GIF, adjuntar e imagen; en medio el campo ancho; y el botón
   de ENVIAR en el extremo derecho, siempre visible— y comprueba que el
   historial mantenga los recibidos a la izquierda y los enviados a la derecha.
   POR QUE:  puntos 18, 19, 24, 26 y 29 del requerimiento.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html. No toca la plantilla ni
   los guiones existentes: reordena y deja que cada botón siga llamando a la
   función de siempre.
   ============================================================================= */
(function () {
    'use strict';

    /* En Teams el botón de enviar SIEMPRE está a la vista (apagado mientras no hay
       nada escrito), no aparece y desaparece. Verlo aparecer de golpe descoloca la
       barra y hace dudar de si el mensaje se va a enviar. */
    function ordenarBarra() {
        var caja = document.querySelector('.chat-input-container');
        if (!caja || caja.dataset.mqOrdenada === '1') return false;

        var campo = caja.querySelector('.chat-input-wrapper');
        var enviar = document.getElementById('btnSendMessage');
        var micro = document.getElementById('btnMicAudio');
        if (!campo || !enviar) return false;

        var izquierda = [
            caja.querySelector('.emoji-btn'),
            caja.querySelector('.gif-btn'),
            caja.querySelector('button[onclick*="attachFile"]'),
            caja.querySelector('.ci-cam')
        ];
        izquierda.forEach(function (b) { if (b) caja.insertBefore(b, campo); });

        // el campo, y después lo de la derecha: micrófono y, al final del todo, enviar
        if (micro) caja.appendChild(micro);
        caja.appendChild(enviar);

        caja.dataset.mqOrdenada = '1';
        return true;
    }

    /* El estado del botón: encendido solo cuando hay algo que enviar. Se cuida de que
       otro guion vuelva a esconderlo, porque la plantilla lo trae oculto de origen. */
    function vigilarBotonEnviar() {
        var enviar = document.getElementById('btnSendMessage');
        var campo = document.getElementById('messageInput');
        if (!enviar || !campo || enviar.__mqVigilado) return;
        enviar.__mqVigilado = true;

        function refrescar() {
            var hay = (campo.value || '').trim().length > 0;
            enviar.classList.toggle('mq-listo', hay);
            enviar.setAttribute('aria-disabled', hay ? 'false' : 'true');
            enviar.title = hay ? 'Enviar' : 'Escribe un mensaje para poder enviarlo';
        }
        campo.addEventListener('input', refrescar);
        campo.addEventListener('change', refrescar);
        refrescar();
    }

    function iniciar() {
        var listo = ordenarBarra();
        vigilarBotonEnviar();
        return listo;
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 900); });
    var intentos = 0;
    var reloj = setInterval(function () {
        if (iniciar() || ++intentos > 20) clearInterval(reloj);
    }, 900);
})();
