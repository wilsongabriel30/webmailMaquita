/* =============================================================================
   T-50 tanda 2 · EL ENCABEZADO DEL CHAT ACTIVO COMO TEAMS
   -----------------------------------------------------------------------------
   QUE HACE: reordena el encabezado de la conversación abierta para que quede
   como el de Teams: avatar con su punto de presencia, nombre, pestañas
   Chat / Archivos / Fotos, y a la derecha —en este orden— videollamada,
   llamada, agregar participantes, buscar y el menú «…».
   POR QUE:  puntos 4, 10, 11, 12, 13 y 14 del requerimiento. Las acciones
   tienen que pertenecer al CHAT ACTIVO, no a un encabezado general.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html. No toca la plantilla ni
   los guiones existentes: reordena lo que ya hay y añade lo que falta, así que
   los botones siguen llamando a las mismas funciones de siempre.
   ============================================================================= */
(function () {
    'use strict';

    var ORDEN = ['btnLlamadaVideo', 'btnLlamadaAudio', 'mq-participantes',
                 'mq-buscar', 'mq-mas'];
    var vista = 'chat';   // chat | archivos | fotos

    function encabezado() {
        return document.querySelector('.chat-main-header');
    }

    /* ---- punto 10: las pestañas bajo el nombre ---- */
    function montarPestanas() {
        var detalles = document.querySelector('.chat-main-header .user-details');
        if (!detalles || detalles.querySelector('.mq-pestanas')) return;
        var barra = document.createElement('div');
        barra.className = 'mq-pestanas';
        [['chat', 'Chat'], ['archivos', 'Archivos'], ['fotos', 'Fotos']].forEach(function (par) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'mq-pestana' + (par[0] === 'chat' ? ' activa' : '');
            b.dataset.vista = par[0];
            b.textContent = par[1];
            b.addEventListener('click', function () { cambiarVista(par[0]); });
            barra.appendChild(b);
        });
        detalles.appendChild(barra);
    }

    /* Archivos y Fotos no piden nada al servidor: filtran lo que ya está en el hilo.
       Es lo que espera la gente («enséñame lo que me mandaron aquí») y evita una
       consulta nueva por cada vez que se pulsa la pestaña. */
    function cambiarVista(cual) {
        vista = cual;
        Array.prototype.forEach.call(document.querySelectorAll('.mq-pestana'), function (b) {
            b.classList.toggle('activa', b.dataset.vista === cual);
        });
        var hilo = document.getElementById('chatMessages');
        if (!hilo) return;
        hilo.classList.toggle('mq-filtrando', cual !== 'chat');
        var mensajes = hilo.querySelectorAll('.message');
        var visibles = 0;
        Array.prototype.forEach.call(mensajes, function (m) {
            var mostrar = true;
            if (cual === 'archivos') mostrar = !!m.querySelector('.message-file');
            else if (cual === 'fotos') mostrar = !!m.querySelector('img.message-media, .message-media img, .message-image');
            m.style.display = mostrar ? '' : 'none';
            if (mostrar) visibles++;
        });
        avisoVacio(hilo, cual, visibles);
    }

    function avisoVacio(hilo, cual, visibles) {
        var previo = hilo.querySelector('.mq-sin-nada');
        if (previo) previo.remove();
        if (cual === 'chat' || visibles) return;
        var d = document.createElement('div');
        d.className = 'mq-sin-nada';
        d.textContent = cual === 'archivos'
            ? 'Todavía no se han compartido archivos en esta conversación.'
            : 'Todavía no se han compartido fotos en esta conversación.';
        hilo.appendChild(d);
    }

    /* ---- puntos 11 y 14: las acciones, en su orden, con "agregar participantes" ---- */
    function montarAcciones() {
        var caja = document.querySelector('.chat-main-header .chat-actions');
        if (!caja) return;

        // buscar y "..." ya existen: se les pone un identificador para poder ordenarlos
        var buscar = caja.querySelector('button[onclick*="searchInChat"]');
        if (buscar) buscar.id = buscar.id || 'mq-buscar';
        var mas = caja.querySelector('button.dropdown-toggle');
        if (mas) mas.id = mas.id || 'mq-mas';

        // agregar participantes: es el que faltaba (punto 14)
        if (!document.getElementById('mq-participantes')) {
            var b = document.createElement('button');
            b.id = 'mq-participantes';
            b.type = 'button';
            b.title = 'Agregar participantes';
            b.innerHTML = '<i class="fas fa-user-plus"></i>';
            b.addEventListener('click', agregarParticipantes);
            caja.insertBefore(b, buscar || null);
        }

        // el orden pedido: videollamada, llamada, participantes, buscar, «…»
        ORDEN.forEach(function (id) {
            var el = document.getElementById(id);
            if (el) caja.appendChild(el);
        });
        var menu = caja.querySelector('.dropdown-menu');
        if (menu) caja.appendChild(menu);   // el desplegable, siempre tras su botón
    }

    /* Se apoya en lo que ya existe para crear grupos; si no estuviera, se avisa en
       vez de fallar en silencio. */
    function agregarParticipantes() {
        if (typeof window.abrirModalNuevoGrupo === 'function') return window.abrirModalNuevoGrupo();
        if (typeof window.openNewGroupModal === 'function') return window.openNewGroupModal();
        if (typeof window.showChatInfo === 'function') return window.showChatInfo();
        if (typeof window.mostrarNotificacion === 'function') {
            window.mostrarNotificacion('Para añadir personas, abre la información del chat', 'info');
        }
    }

    /* ---- punto 6 también aquí: el avatar del encabezado con su presencia ---- */
    function presenciaEnCabecera() {
        var avatar = document.getElementById('chatHeaderAvatar');
        if (avatar) avatar.classList.add('mq-estado');
    }

    /* al cambiar de conversación se vuelve a la pestaña Chat */
    function vigilarCambioDeChat() {
        var nombre = document.getElementById('chatHeaderName');
        if (!nombre || nombre.__mqVigilado) return;
        nombre.__mqVigilado = true;
        new MutationObserver(function () {
            if (vista !== 'chat') cambiarVista('chat');
            presenciaEnCabecera();
        }).observe(nombre, {childList: true, characterData: true, subtree: true});
    }

    function iniciar() {
        if (!encabezado()) return false;
        montarPestanas();
        montarAcciones();
        presenciaEnCabecera();
        vigilarCambioDeChat();
        return true;
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 900); });
    var intentos = 0;
    var reloj = setInterval(function () {
        if (iniciar() || ++intentos > 20) clearInterval(reloj);
    }, 900);

    window.mqCambiarVistaChat = cambiarVista;   // para las pruebas de humo
})();
