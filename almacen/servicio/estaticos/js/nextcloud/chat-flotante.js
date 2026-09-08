/* Chat institucional dentro del Drive: botón flotante, contador y avisos.
 *
 * El Drive comparte dominio con Raíces, así que el chat que se abre aquí es EL MISMO, con la
 * misma sesión y las mismas conversaciones: no hay un segundo chat que atender.
 *
 * Antes había un botón que aparecía solo si `/api/chat/conversations` respondía. Como el chat
 * pide su propia sesión, en el Drive nunca la había y el botón no salía nunca. Aquí se consigue
 * primero esa sesión por la puerta dedicada (igual que en Raíces) y después se dibuja el botón.
 *
 * Si la instalación no tiene chat, o la persona no tiene sesión de Raíces, no se dibuja nada:
 * el Drive funciona igual y no aparece un botón que llevaría a un error.
 */
(function () {
    'use strict';

    var CLIENTE_SOCKET = '/static/vendor/cdn.socket.io/4.5.4/socket.io.min.js';
    var SONIDO = '/static/sounds/notification.mp3';   // lo sirve Raíces, mismo dominio
    var ESPERA_MS = 5000;
    var ultimoAviso = {};
    var audio = null;
    var boton = null;
    var contador = null;
    var panel = null;
    var marco = null;
    var permisoPedido = false;

    function tieneSesion() {
        return document.cookie.split(';').some(function (c) {
            return c.trim().indexOf('chat_session=') === 0;
        });
    }

    function pedir(url, opciones) {
        return fetch(url, Object.assign({ credentials: 'same-origin' }, opciones || {}));
    }

    /* Consigue la sesión del chat sin abrir el chat. Devuelve true si se puede seguir. */
    function asegurarSesion() {
        if (tieneSesion()) return Promise.resolve(true);
        return pedir('/chat/sesion-url')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
                if (!d || !d.url) return false;
                return pedir(d.url).then(function () { return tieneSesion(); });
            })
            .catch(function () { return false; });
    }

    function sonar() {
        try {
            if (!audio) { audio = new Audio(SONIDO); audio.volume = 0.5; }
            audio.currentTime = 0;
            audio.play().catch(function () { });
        } catch (e) { }
    }


    /* Los navegadores solo dejan sonar tras un gesto de la persona: al primer clic se prepara
       el audio en silencio y a partir de ahí el aviso suena sin pedir nada. */
    function desbloquearSonido() {
        document.addEventListener('click', function preparar() {
            document.removeEventListener('click', preparar);
            try {
                if (!audio) { audio = new Audio(SONIDO); }
                audio.volume = 0;
                audio.play().then(function () {
                    audio.pause();
                    audio.currentTime = 0;
                    audio.volume = 0.5;
                }).catch(function () { });
            } catch (e) { }
        }, { once: true });
    }

    function pedirPermisoAlPrimerClic() {
        if (permisoPedido || !('Notification' in window)) return;
        if (Notification.permission !== 'default') { permisoPedido = true; return; }
        document.addEventListener('click', function pedirlo() {
            document.removeEventListener('click', pedirlo);
            permisoPedido = true;
            try { Notification.requestPermission(); } catch (e) { }
        }, { once: true });
    }

    function avisoDelSistema(titulo, cuerpo) {
        if (!('Notification' in window) || Notification.permission !== 'granted') return;
        try {
            var n = new Notification(titulo, { body: cuerpo, tag: 'chat-drive' });
            n.onclick = function () { window.focus(); abrirPanel(true); n.close(); };
        } catch (e) { }
    }

    function pintarContador(n) {
        if (!contador) return;
        if (n > 0) {
            contador.textContent = n > 99 ? '99+' : String(n);
            contador.style.display = 'flex';
            boton.style.animation = 'chatDrivePulso 1.4s ease-in-out infinite';
        } else {
            contador.style.display = 'none';
            boton.style.animation = '';
        }
    }

    function refrescarContador() {
        pedir('/api/chat/unread/count')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
                if (!d) return;
                var n = d.count != null ? d.count : (d.unread_count || 0);
                pintarContador(n || 0);
            })
            .catch(function () { });
    }

    function abrirPanel(forzar) {
        var abierto = panel.style.display !== 'none';
        if (abierto && !forzar) {
            panel.style.display = 'none';
            boton.textContent = '💬';
            refrescarContador();
            return;
        }
        if (!marco) {
            marco = document.createElement('iframe');
            marco.src = '/chat/app/?embed=1&marco=drive';   // el servicio de chat, no el marco de Raíces
            marco.title = 'Chat institucional';
            marco.setAttribute('allow', 'camera; microphone; autoplay; clipboard-write');
            marco.style.cssText = 'width:100%;height:100%;border:0;';
            panel.appendChild(marco);
        }
        panel.style.display = 'block';
        boton.textContent = '✕';
        pintarContador(0);
    }

    function dibujar() {
        var estilo = document.createElement('style');
        estilo.textContent = '@keyframes chatDrivePulso{0%,100%{box-shadow:0 4px 14px rgba(0,0,0,.3)}50%{box-shadow:0 0 0 8px rgba(0,120,212,.25)}}';
        document.head.appendChild(estilo);

        boton = document.createElement('button');
        boton.id = 'chatFlotanteAlmacen';
        boton.title = 'Chat institucional';
        boton.textContent = '💬';
        boton.style.cssText = 'position:fixed;bottom:20px;right:20px;width:52px;height:52px;' +
            'border-radius:50%;border:0;cursor:pointer;z-index:9999;background:#0078d4;color:#fff;' +
            'font-size:22px;box-shadow:0 4px 14px rgba(0,0,0,.3);';

        contador = document.createElement('span');
        contador.style.cssText = 'position:absolute;top:-4px;right:-4px;min-width:20px;height:20px;' +
            'padding:0 5px;border-radius:10px;background:#d13438;color:#fff;font-size:11px;' +
            'font-weight:700;display:none;align-items:center;justify-content:center;';
        boton.appendChild(contador);

        panel = document.createElement('div');
        panel.style.cssText = 'position:fixed;bottom:84px;right:20px;width:400px;height:560px;' +
            'max-width:calc(100vw - 40px);max-height:calc(100vh - 120px);border-radius:12px;' +
            'box-shadow:0 8px 32px rgba(0,0,0,.35);overflow:hidden;background:#fff;z-index:9999;display:none;';

        boton.onclick = function () { abrirPanel(false); };
        document.body.appendChild(panel);
        document.body.appendChild(boton);
    }

    function avisar(datos) {
        var conv = datos && (datos.conversation_id || datos.conversacion_id);
        var clave = String(conv || 'general');
        var ahora = Date.now();
        if (ultimoAviso[clave] && ahora - ultimoAviso[clave] < ESPERA_MS) return;
        ultimoAviso[clave] = ahora;
        if (panel && panel.style.display === 'block') { return; }   // ya lo tiene abierto
        sonar();
        var quien = (datos && (datos.sender_name || datos.remitente_nombre)) || 'Mensaje nuevo';
        var texto = (datos && (datos.content || datos.contenido)) || 'Te han escrito por el chat';
        avisoDelSistema(quien, String(texto).slice(0, 140));
        refrescarContador();
    }

    function conectarEnVivo() {
        var s = document.createElement('script');
        s.src = CLIENTE_SOCKET;                      // cliente servido por la propia plataforma
        s.onload = function () {
            try {
                var socket = io({ path: '/socket.io', transports: ['websocket', 'polling'] });
                // `aviso_chat` llega a la sala personal: suena aunque no se tenga
                // abierta esa conversación. Los otros dos se mantienen por compatibilidad.
                socket.on('aviso_chat', avisar);
                socket.on('new_message', avisar);
                socket.on('notification', avisar);
            } catch (e) { }
        };
        s.onerror = function () { };                 // sin tiempo real quedan el contador y el botón
        document.head.appendChild(s);
    }

    function arrancar() {
        asegurarSesion().then(function (hay) {
            if (!hay) return;                        // sin chat en esta instalación: no se dibuja nada
            return pedir('/api/chat/unread/count').then(function (r) {
                if (!r.ok) return;
                dibujar();
                pedirPermisoAlPrimerClic();
                desbloquearSonido();
                refrescarContador();
                setInterval(refrescarContador, 60000);
                conectarEnVivo();
            });
        }).catch(function () { });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();
