/* Llamadas 1a1 DIRECTAS PC-a-PC (T-25). Se carga después del script de /chat/llamada y sustituye `empezar`:
 * 1) WebRTC directo con candidatos de red locales (LAN de Maquita: casi siempre conecta sin pasar por el servidor);
 *    señalización por el chat (call_offer / call_answer / ice_candidate, ya existentes). Sin STUN/TURN de terceros.
 * 2) Si no conecta en 10 s, falla o alguno de los dos no puede: cae a LiveKit (SFU, con TURN) — el camino de siempre.
 * 3) Registra la métrica (p2p / sfu + motivo) en POST /api/chat/llamada/metrica. */
(function () {
    if (typeof empezar !== 'function' || typeof est === 'undefined' || typeof socket === 'undefined') return;
    var empezarSFU = empezar, finalizarOrig = finalizar, toggleShareOrig = toggleShare;
    var p = { pc: null, pendientes: [], fallback: false, timer: null, modo: null, ofertaPendiente: null, pantalla: null, negociando: false };
    var ESPERA_MS = 10000;

    function metrica(modo, motivo) {
        try { fetch('/api/chat/llamada/metrica', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
            body: JSON.stringify({ room: ROOM, modo: modo, motivo: motivo || '', tipo: TIPO, role: ROLE }) }).catch(function () {}); } catch (e) {}
    }
    async function mediaLocal() {
        if (est.localStream) return est.localStream;
        est.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: TIPO === 'video' });
        if (TIPO === 'video') { var lv = document.getElementById('localVideo'); lv.srcObject = est.localStream; lv.style.display = ''; }
        return est.localStream;
    }
    function preferirCodecs(pc) {
        try {
            if (!RTCRtpReceiver.getCapabilities) return;
            var caps = RTCRtpReceiver.getCapabilities('video'); if (!caps) return;
            var orden = ['video/AV1', 'video/VP9', 'video/H264', 'video/VP8'];
            var codecs = caps.codecs.slice().sort(function (a, b) { var ia = orden.indexOf(a.mimeType), ib = orden.indexOf(b.mimeType); return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib); });
            pc.getTransceivers().forEach(function (t) { if (t.receiver && t.receiver.track && t.receiver.track.kind === 'video' && t.setCodecPreferences) t.setCodecPreferences(codecs); });
        } catch (e) {}
    }
    function mostrarRemoto(track, stream) {
        if (track.kind === 'audio') {
            var ra = document.getElementById('remoteAudio'); ra.srcObject = stream; ra.play().catch(function () { pedirDesbloqueoMedia(); });
            if (TIPO === 'audio') setDetalle('En llamada (directa)');
        } else {
            var rv = document.getElementById('remoteVideo'); rv.srcObject = stream; rv.style.display = '';
            document.getElementById('vcEstado').style.display = 'none'; rv.play().catch(function () {});
            track.onended = function () { if (!est.finalizada) { rv.style.display = 'none'; document.getElementById('vcEstado').style.display = ''; } };
        }
        iniciarTimer();
    }
    function crearPC() {
        var pc = new RTCPeerConnection({ iceServers: [] });   // solo candidatos directos; fuera de la LAN cae al servidor
        pc.onicecandidate = function (e) { if (e.candidate) socket.emit('ice_candidate', { target_user_id: PEER_ID, candidate: e.candidate.toJSON ? e.candidate.toJSON() : e.candidate }); };
        pc.ontrack = function (e) { var stream = (e.streams && e.streams[0]) || new MediaStream([e.track]); mostrarRemoto(e.track, stream); };
        pc.onconnectionstatechange = function () {
            var s = pc.connectionState;
            if (s === 'connected') { clearTimeout(p.timer); if (p.modo !== 'p2p') { p.modo = 'p2p'; metrica('p2p', 'conectada'); } setDetalle(TIPO === 'video' ? 'Videollamada directa' : 'En llamada (directa)'); }
            else if (s === 'failed') { if (p.modo === 'p2p' && est.timerSeconds > 0) finalizar('Conexión perdida'); else caerASFU('ice_failed'); }
            else if (s === 'disconnected' && p.modo === 'p2p') { setTimeout(function () { if (pc.connectionState === 'disconnected' && !est.finalizada) finalizar('Conexión perdida'); }, 6000); }
        };
        pc.onnegotiationneeded = async function () {
            if (p.negociando || !p.pc || p.pc !== pc || p.fallback) return;
            if (ROLE !== 'caller' && pc.signalingState !== 'stable') return;
            try { p.negociando = true; var o = await pc.createOffer(); await pc.setLocalDescription(o); socket.emit('call_offer', { target_user_id: PEER_ID, sdp: pc.localDescription }); }
            catch (e) { console.warn('[p2p] renegociación:', e); } finally { p.negociando = false; }
        };
        return pc;
    }
    async function vaciarCandidatos() {
        while (p.pendientes.length && p.pc && p.pc.remoteDescription) { var c = p.pendientes.shift(); try { await p.pc.addIceCandidate(c); } catch (e) {} }
    }
    async function responder(sdp) {
        if (!p.pc) return;
        try {
            if (p.pc.signalingState !== 'stable') { await Promise.all([p.pc.setLocalDescription({ type: 'rollback' }).catch(function () {}), p.pc.setRemoteDescription(sdp)]); }
            else await p.pc.setRemoteDescription(sdp);
            await vaciarCandidatos();
            var ans = await p.pc.createAnswer(); await p.pc.setLocalDescription(ans);
            socket.emit('call_answer', { target_user_id: PEER_ID, sdp: p.pc.localDescription });
        } catch (e) { console.warn('[p2p] respuesta:', e); caerASFU('sdp_error'); }
    }
    async function caerASFU(motivo) {
        if (p.fallback || est.finalizada) return;
        p.fallback = true; clearTimeout(p.timer);
        try { if (p.pc) p.pc.close(); } catch (e) {} p.pc = null;
        p.modo = 'sfu'; metrica('sfu', motivo);
        if (motivo !== 'peer_fallback') socket.emit('ice_candidate', { target_user_id: PEER_ID, candidate: { maquita_fallback: true } });
        setDetalle('Conectando por el servidor…');
        est.conectada = false;
        try { await empezarSFU(); } catch (e) { console.error('[p2p] fallback SFU:', e); }
    }

    // ===== empezar(): primero directo =====
    empezar = async function () {
        if (est.conectada || est.finalizada) return;
        if (!window.RTCPeerConnection) return empezarSFU();
        est.conectada = true; pararRingback();
        if (est.ringTimeout) { clearTimeout(est.ringTimeout); est.ringTimeout = null; }
        document.getElementById('vcAvatar').classList.remove('pulsando');
        setDetalle('Conectando (directo)…');
        try { await mediaLocal(); } catch (e) { setDetalle('No se pudo acceder al micrófono' + (TIPO === 'video' ? '/cámara' : '') + '. Revisa los permisos.'); return; }
        p.pc = crearPC();
        est.localStream.getTracks().forEach(function (t) { p.pc.addTrack(t, est.localStream); });
        preferirCodecs(p.pc);
        p.timer = setTimeout(function () { if (p.pc && p.pc.connectionState !== 'connected') caerASFU('timeout'); }, ESPERA_MS);
        if (ROLE === 'caller') {
            try { var o = await p.pc.createOffer(); await p.pc.setLocalDescription(o); socket.emit('call_offer', { target_user_id: PEER_ID, sdp: p.pc.localDescription }); }
            catch (e) { caerASFU('offer_error'); }
        } else if (p.ofertaPendiente) { var sdp = p.ofertaPendiente; p.ofertaPendiente = null; await responder(sdp); }
    };

    // ===== Señalización =====
    socket.on('call_offer', async function (d) {
        if (String(d.from) !== String(PEER_ID) || p.fallback) return;
        if (p.pc && est.localStream) await responder(d.sdp); else p.ofertaPendiente = d.sdp;
    });
    socket.on('call_answer', async function (d) {
        if (String(d.from) !== String(PEER_ID) || !p.pc || p.fallback) return;
        try { await p.pc.setRemoteDescription(d.sdp); await vaciarCandidatos(); } catch (e) { console.warn('[p2p] answer:', e); caerASFU('sdp_error'); }
    });
    socket.on('ice_candidate', async function (d) {
        if (String(d.from) !== String(PEER_ID)) return;
        var c = d.candidate; if (!c) return;
        if (c.maquita_fallback) { caerASFU('peer_fallback'); return; }
        if (p.fallback || !p.pc) return;
        if (p.pc.remoteDescription) { try { await p.pc.addIceCandidate(c); } catch (e) {} } else p.pendientes.push(c);
    });

    // ===== Compartir pantalla en modo directo =====
    toggleShare = async function () {
        if (p.modo !== 'p2p' || !p.pc) return toggleShareOrig();
        var b = document.getElementById('btnShare');
        try {
            if (p.pantalla) {
                var vt = p.pantalla.getVideoTracks()[0]; var s = p.pc.getSenders().find(function (x) { return x.track === vt; });
                var cam = est.localStream.getVideoTracks()[0];
                if (s) { if (cam) await s.replaceTrack(cam); else { p.pc.removeTrack(s); } }
                p.pantalla.getTracks().forEach(function (t) { t.stop(); }); p.pantalla = null;
                b.classList.remove('sharing'); b.title = 'Compartir pantalla'; return;
            }
            var ds = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 30 }, audio: false });
            var track = ds.getVideoTracks()[0]; p.pantalla = ds;
            var sender = p.pc.getSenders().find(function (x) { return x.track && x.track.kind === 'video'; });
            if (sender) await sender.replaceTrack(track); else p.pc.addTrack(track, ds);   // audio-only: añade video → renegociación
            track.onended = function () { if (p.pantalla) toggleShare(); };
            b.classList.add('sharing'); b.title = 'Dejar de compartir';
        } catch (e) { if (e && (e.name === 'NotAllowedError' || /Permission|cancel/i.test(String(e)))) return; console.error('[p2p] pantalla:', e); }
    };

    // ===== Fin =====
    finalizar = async function (motivo) {
        try { if (p.pantalla) p.pantalla.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
        try { if (p.pc) p.pc.close(); } catch (e) {} p.pc = null;
        return finalizarOrig(motivo);
    };
    window.addEventListener('beforeunload', function () { try { if (p.pc) p.pc.close(); } catch (e) {} });
})();
