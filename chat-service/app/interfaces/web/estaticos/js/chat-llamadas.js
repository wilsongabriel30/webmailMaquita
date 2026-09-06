/* Chat institucional - Llamadas 1:1 y llamadas grupales (2026-08-27)
 * Antes esta lógica vivía en el base.html de Raíces; ahora es parte del SERVICIO para que
 * funcione igual en Raíces, en la burbuja del correo y en la app de escritorio.
 *  - iniciarLlamadaWebRTC / iniciarConferenciaGrupal: las llama chat-page.js (botones del chat).
 *  - Entrantes: 'call_incoming' (1:1) y 'conference_incoming' (grupo) → modal con timbre,
 *    Unirse/Rechazar; la llamada corre en una ventana dedicada (/chat/llamada, /chat/conferencia)
 *    o en una superposición si el navegador bloquea ventanas emergentes.
 *  - Dentro del marco de Raíces (marco=faro) el shell de Raíces ya muestra las entrantes: aquí no se duplican. */
(function () {
    'use strict';

    const Q = new URLSearchParams(location.search);
    const EN_MARCO_FARO = Q.get('marco') === 'faro';
    const estado = { socket: null, timbre: null, timbreIntervalo: null, timeout: null, popupLlamada: null, popupConf: null };

    function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
    function aviso(msg, tipo) { if (window.toastr) toastr[tipo || 'info'](msg); else console.log(msg); }
    function socket() { return estado.socket || window._chatSocketVistos || null; }

    // ---------- Ventanas ----------
    function esApp() { try { return /MaquitaTeams/i.test(navigator.userAgent) || /(^|;\s*)(faro_app|mail_app)=1/.test(document.cookie) || document.documentElement.classList.contains('faro-app') || document.documentElement.classList.contains('modo-app'); } catch (e) { return false; } }
    function abrirVentana(url, nombre, dim, clave) {
        let w = null;
        try { w = window.open(url, nombre, dim); } catch (e) { w = null; }
        // En la app de escritorio el cliente abre la llamada en VENTANA PROPIA y window.open no devuelve la ventana:
        // no mostrar la superposicion interna (el chat sigue siendo chat para seguir pasando archivos).
        if (esApp()) { estado[clave] = null; return null; }
        if (!w || w.closed || typeof w.closed === 'undefined') { abrirSuperposicion(url); return null; }
        estado[clave] = w;
        return w;
    }
    function abrirSuperposicion(url) {
        const previo = document.getElementById('chatCallOverlay');
        if (previo) previo.remove();
        const ov = document.createElement('div');
        ov.id = 'chatCallOverlay';
        ov.style.cssText = 'position:fixed;inset:0;z-index:100200;background:#0f1115;';
        ov.innerHTML = '<iframe src="' + esc(url) + '" allow="camera; microphone; display-capture; autoplay" style="border:0;width:100%;height:100%;"></iframe>' +
            '<button type="button" onclick="document.getElementById(\'chatCallOverlay\').remove()" title="Cerrar" ' +
            'style="position:absolute;top:8px;right:8px;z-index:2;border:0;border-radius:50%;width:34px;height:34px;background:rgba(255,255,255,.15);color:#fff;font-size:1.1rem;">&times;</button>';
        document.body.appendChild(ov);
    }
    window.addEventListener('message', function (ev) {
        if (ev && ev.data && ev.data.faroCall === 'close') { const ov = document.getElementById('chatCallOverlay'); if (ov) ov.remove(); }
    });
    function ocupado() {
        if (estado.popupLlamada && !estado.popupLlamada.closed) return 'llamada';
        if (estado.popupConf && !estado.popupConf.closed) return 'conferencia';
        if (document.getElementById('chatCallOverlay')) return 'llamada';
        return null;
    }
    window.abrirVentanaLlamada = function (role, tipo, peerId, peerName, convId) {
        const url = '/chat/llamada?role=' + role + '&tipo=' + encodeURIComponent(tipo || 'audio') +
            '&peer_id=' + encodeURIComponent(peerId) + '&peer_name=' + encodeURIComponent(peerName || 'Usuario') +
            '&conv=' + encodeURIComponent(convId || '');
        abrirVentana(url, 'maquita_llamada', 'width=1020,height=720,menubar=no,toolbar=no,location=no,status=no', 'popupLlamada');
    };
    window.abrirVentanaConferencia = function (role, roomId, roomName, convId, tipo) {
        const url = '/chat/conferencia?role=' + role + '&room=' + encodeURIComponent(roomId) +
            '&name=' + encodeURIComponent(roomName || 'Conferencia') + '&conv=' + encodeURIComponent(convId || '') +
            (tipo === 'video' ? '&video=1' : '');   // T-15: videollamada grupal entra con camara
        abrirVentana(url, 'maquita_conferencia', 'width=1180,height=760,menubar=no,toolbar=no,location=no,status=no', 'popupConf');
    };

    // ---------- Iniciar (las llama chat-page.js) ----------
    window.iniciarLlamadaWebRTC = async function (chatId, targetUserId, tipo, nombreDestino, convId) {
        const o = ocupado();
        if (o) { aviso('Ya tienes una ' + o + ' en curso', 'warning'); return; }
        window.abrirVentanaLlamada('caller', tipo || 'audio', targetUserId, nombreDestino || 'Usuario', convId || String(chatId).replace('conv_', ''));
    };
    window.iniciarConferenciaGrupal = function (conversationId, participantsList, groupName, tipo) {
        const o = ocupado();
        if (o) { aviso('Ya tienes una ' + o + ' en curso', 'warning'); return; }
        const s = socket();
        if (!s || !s.connected) { aviso('Sin conexión en tiempo real. Recarga la página.', 'error'); return; }
        const roomId = 'conf_' + Date.now() + '_' + Math.random().toString(36).slice(2, 11);
        const roomName = groupName || 'Llamada grupal';
        s.emit('conference_invite', { room_id: roomId, room_name: roomName, conversation_id: conversationId, participants: participantsList, tipo: tipo || 'audio' });
        window.abrirVentanaConferencia('host', roomId, roomName, conversationId, tipo);
    };

    // ---------- Timbre ----------
    function sonarTimbre() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            estado.timbre = ctx;
            const ring = function () {
                if (!document.getElementById('chatIncomingModal')) { pararTimbre(); return; }
                const t = ctx.currentTime;
                [[0, 0.4], [0.55, 0.95]].forEach(function (seg) {
                    [523.25, 659.25].forEach(function (f) {
                        const o = ctx.createOscillator(), g = ctx.createGain();
                        o.type = 'sine'; o.frequency.value = f; o.connect(g); g.connect(ctx.destination);
                        g.gain.setValueAtTime(0, t + seg[0]); g.gain.linearRampToValueAtTime(0.08, t + seg[0] + 0.03);
                        g.gain.setValueAtTime(0.08, t + seg[1] - 0.05); g.gain.linearRampToValueAtTime(0, t + seg[1]);
                        o.start(t + seg[0]); o.stop(t + seg[1] + 0.05);
                    });
                });
            };
            ring(); estado.timbreIntervalo = setInterval(ring, 3000);
        } catch (e) { /* sin audio */ }
    }
    function pararTimbre() {
        if (estado.timbreIntervalo) { clearInterval(estado.timbreIntervalo); estado.timbreIntervalo = null; }
        if (estado.timbre) { try { estado.timbre.close(); } catch (e) {} estado.timbre = null; }
        if (estado.timeout) { clearTimeout(estado.timeout); estado.timeout = null; }
    }
    function cerrarModal() { const m = document.getElementById('chatIncomingModal'); if (m) m.remove(); pararTimbre(); }

    function mostrarEntrante(opts) {
        cerrarModal();
        const m = document.createElement('div');
        m.id = 'chatIncomingModal';
        m.className = 'chat-incoming-modal';
        const avatar = opts.avatar ? '<img src="' + esc(opts.avatar) + '" alt="">' : '<span>' + esc((opts.titulo || 'U').charAt(0).toUpperCase()) + '</span>';
        m.innerHTML = '<div class="chat-incoming-card">' +
            '<div class="chat-incoming-avatar">' + avatar + '</div>' +
            '<div class="chat-incoming-title">' + esc(opts.titulo) + '</div>' +
            '<div class="chat-incoming-sub">' + esc(opts.subtitulo) + '</div>' +
            '<div class="chat-incoming-actions">' +
            '<button type="button" class="chat-incoming-reject" id="chatIncomingReject"><i class="fas fa-phone-slash"></i> Rechazar</button>' +
            '<button type="button" class="chat-incoming-accept" id="chatIncomingAccept"><i class="fas ' + (opts.icono || 'fa-phone') + '"></i> ' + esc(opts.textoAceptar || 'Contestar') + '</button>' +
            '</div></div>';
        document.body.appendChild(m);
        document.getElementById('chatIncomingAccept').onclick = function () { cerrarModal(); opts.aceptar(); };
        document.getElementById('chatIncomingReject').onclick = function () { cerrarModal(); opts.rechazar(); };
        sonarTimbre();
        estado.timeout = setTimeout(function () { if (document.getElementById('chatIncomingModal')) { cerrarModal(); opts.rechazar(); } }, 30000);
    }

    // ---------- Entrantes por Socket.IO ----------
    function engancharSocket(s) {
        if (!s || s.__llamadas) return;
        s.__llamadas = true; estado.socket = s;
        if (EN_MARCO_FARO) return;   // el shell de Raíces ya muestra las entrantes
        s.on('call_incoming', function (d) {
            if (!d) return;
            if (ocupado()) { s.emit('call_reject', { target_user_id: d.caller_id }); return; }
            const tipo = d.tipo === 'video' ? 'video' : 'audio';
            mostrarEntrante({
                titulo: d.caller_name || 'Usuario', subtitulo: tipo === 'video' ? 'Videollamada entrante' : 'Llamada de voz entrante',
                avatar: d.avatar, icono: tipo === 'video' ? 'fa-video' : 'fa-phone', textoAceptar: 'Contestar',
                aceptar: function () { window.abrirVentanaLlamada('callee', tipo, d.caller_id, d.caller_name || 'Usuario', d.chat_id || ''); },
                rechazar: function () { s.emit('call_reject', { target_user_id: d.caller_id }); }
            });
        });
        s.on('conference_incoming', function (d) {
            if (!d) return;
            if (ocupado()) { s.emit('conference_reject', { room_id: d.room_id }); return; }
            mostrarEntrante({
                titulo: d.room_name || 'Llamada grupal', subtitulo: (d.caller_name || 'Alguien') + ' inició una llamada del grupo · te invita a unirte',
                avatar: d.avatar, icono: 'fa-users', textoAceptar: 'Unirse',
                aceptar: function () { window.abrirVentanaConferencia('guest', d.room_id, d.room_name || 'Llamada grupal', d.conversation_id || '', d.tipo); },
                rechazar: function () { s.emit('conference_reject', { room_id: d.room_id }); }
            });
        });
        s.on('call_cancelled', cerrarModal);
        s.on('call_hangup', function () { cerrarModal(); });
        s.on('conference_ended', function (d) { cerrarModal(); });
    }
    function envolver() {
        const Clase = window.ChatUltraFast;
        if (!Clase || !Clase.prototype || Clase.prototype.__llamadas) return false;
        const conectarOriginal = Clase.prototype.connect;
        Clase.prototype.connect = function () {
            const inst = this; const r = conectarOriginal.apply(this, arguments);
            const fin = function () { engancharSocket(inst.socket); };
            if (r && typeof r.then === 'function') r.then(fin, function () {}); else fin();
            setTimeout(fin, 1500);
            return r;
        };
        Clase.prototype.__llamadas = true; return true;
    }
    if (!envolver()) document.addEventListener('DOMContentLoaded', envolver);

    // Abrir directo desde una notificación (?llamada=conf:<room>:<name>:<conv>)
    const auto = Q.get('unirse');
    if (auto) { try { const p = JSON.parse(atob(auto)); if (p.room) setTimeout(function () { window.abrirVentanaConferencia('guest', p.room, p.name, p.conv); }, 800); } catch (e) {} }
})();
