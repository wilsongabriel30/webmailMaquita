/* T-101 · Conferencia: aro alrededor de quien está hablando.
 * Pone la clase «hablando» en el mosaico de cada persona que habla. No cambia nada de la conferencia: solo esa clase.
 * El aspecto está en chat-conferencia-hablando.css.
 *
 * Dos fuentes, y vale cualquiera de las dos:
 *   1. El aviso de LiveKit (ActiveSpeakersChanged), si el servidor lo envía.
 *   2. El nivel de sonido medido aquí mismo en la pista de audio de cada persona. Se añadió porque, en las pruebas
 *      del 11/11/2026, el servidor no enviaba ese aviso aunque el audio sí salía.
 * Mosaicos (los crea conferencia.html): yo -> tile_local ; los demás -> tile_<identidad>. */
(function () {
    'use strict';
    var UMBRAL = 0.035;        // nivel (0 a 1) a partir del cual se considera que alguien habla
    var SOSTENER_MS = 700;     // el aro aguanta este tiempo tras el último sonido, para que no parpadee
    var salaEnlazada = null;
    var segunServidor = {};    // id de mosaico -> true, según LiveKit
    var medidores = {};        // id de pista -> { mosaico, analizador, datos, fuente, ultimaVoz }
    var contexto = null;

    function sala() {
        try { return (typeof est !== 'undefined' && est) ? est.room : null; } catch (e) { return null; }
    }
    function idMosaico(persona, s) {
        return (persona.isLocal || (s && persona === s.localParticipant)) ? 'tile_local' : 'tile_' + persona.identity;
    }
    function contextoDeAudio() {
        if (contexto) return contexto;
        var Clase = window.AudioContext || window.webkitAudioContext;
        if (!Clase) return null;
        try { contexto = new Clase(); } catch (e) { contexto = null; }
        return contexto;
    }
    // el navegador puede dejar el contexto en pausa hasta el primer gesto de la persona
    function despertar() { if (contexto && contexto.state === 'suspended') { try { contexto.resume(); } catch (e) {} } }
    document.addEventListener('click', despertar, true);
    document.addEventListener('keydown', despertar, true);

    function pistasDeAudio(s) {
        var lista = [];
        function de(persona) {
            if (!persona || !persona.audioTrackPublications) return;
            persona.audioTrackPublications.forEach(function (pub) {
                var pista = pub && pub.track && pub.track.mediaStreamTrack;
                // la pista «pantalla con sonido» no cuenta como voz de la persona
                if (pista && pista.readyState === 'live' && String(pub.source || '') !== 'screen_share_audio') {
                    lista.push({ pista: pista, mosaico: idMosaico(persona, s) });
                }
            });
        }
        de(s.localParticipant);
        if (s.remoteParticipants) s.remoteParticipants.forEach(de);
        return lista;
    }

    function actualizarMedidores() {
        var s = sala();
        if (!s || s.state !== 'connected') { soltarMedidores({}); return; }
        var ctx = contextoDeAudio();
        if (!ctx) return;
        despertar();
        var vivas = {};
        pistasDeAudio(s).forEach(function (x) {
            vivas[x.pista.id] = true;
            if (medidores[x.pista.id]) { medidores[x.pista.id].mosaico = x.mosaico; return; }
            try {
                var fuente = ctx.createMediaStreamSource(new MediaStream([x.pista]));
                var analizador = ctx.createAnalyser();
                analizador.fftSize = 256;
                fuente.connect(analizador);            // no se conecta a la salida: solo se mide, no se oye dos veces
                medidores[x.pista.id] = { mosaico: x.mosaico, analizador: analizador, fuente: fuente,
                                          datos: new Uint8Array(analizador.fftSize), ultimaVoz: 0 };
            } catch (e) {}
        });
        soltarMedidores(vivas);
    }
    function soltarMedidores(vivas) {
        Object.keys(medidores).forEach(function (id) {
            if (vivas[id]) return;
            try { medidores[id].fuente.disconnect(); } catch (e) {}
            delete medidores[id];
        });
    }

    function medirYPintar() {
        var ahora = Date.now(), hablan = {};
        Object.keys(medidores).forEach(function (id) {
            var m = medidores[id], suma = 0, i, v;
            m.analizador.getByteTimeDomainData(m.datos);
            for (i = 0; i < m.datos.length; i++) { v = (m.datos[i] - 128) / 128; suma += v * v; }
            if (Math.sqrt(suma / m.datos.length) >= UMBRAL) m.ultimaVoz = ahora;
            if (ahora - m.ultimaVoz < SOSTENER_MS) hablan[m.mosaico] = true;
        });
        Object.keys(segunServidor).forEach(function (id) { hablan[id] = true; });
        var mosaicos = document.querySelectorAll('.tile:not(.pantalla)');
        for (var k = 0; k < mosaicos.length; k++) mosaicos[k].classList.toggle('hablando', hablan[mosaicos[k].id] === true);
    }

    function enlazarServidor() {
        var s = sala();
        if (!s || s === salaEnlazada || typeof LivekitClient === 'undefined') return;
        salaEnlazada = s; segunServidor = {};
        s.on(LivekitClient.RoomEvent.ActiveSpeakersChanged, function (personas) {
            segunServidor = {};
            (personas || []).forEach(function (p) { segunServidor[idMosaico(p, s)] = true; });
        });
        s.on(LivekitClient.RoomEvent.Disconnected, function () { segunServidor = {}; });
    }

    setInterval(function () { enlazarServidor(); actualizarMedidores(); }, 500);   // la sala y las pistas cambian
    setInterval(medirYPintar, 150);
    window.__maquitaHablando = { medidores: medidores, contexto: function () { return contexto; } };   // para pruebas
})();
