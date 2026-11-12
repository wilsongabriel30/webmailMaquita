/* T-101 · Conferencia: micrófono apagado en cada mosaico.
 * Pone la clase «sin-micro» en el mosaico de quien tiene el micrófono apagado (o no tiene). El icono lo pinta
 * chat-conferencia-micro.css junto al nombre. No toca el guion de la conferencia.
 *
 * Para que los DEMÁS sepan que alguien silenció, hace falta avisar al servidor de llamadas: el botón de silenciar
 * solo apagaba la pista en el propio equipo y nadie más se enteraba. Por eso este guion mantiene igualado el estado
 * «silenciado» de la publicación de LiveKit con el del botón (est.muted). Efecto añadido: silenciado, deja de enviarse audio.
 * Mosaicos (los crea conferencia.html): yo -> tile_local ; los demás -> tile_<identidad>. */
(function () {
    'use strict';
    var ocupado = false;

    function estado() { try { return (typeof est !== 'undefined' && est) ? est : null; } catch (e) { return null; } }
    function esPantalla(pub) { return String((pub && pub.source) || '') === 'screen_share_audio'; }

    // Publicaciones de micrófono de una persona (se excluye el sonido de la pantalla compartida)
    function microfonos(persona) {
        var lista = [];
        if (persona && persona.audioTrackPublications) {
            persona.audioTrackPublications.forEach(function (pub) { if (!esPantalla(pub)) lista.push(pub); });
        }
        return lista;
    }
    function sinMicro(persona) {
        var m = microfonos(persona);
        if (!m.length) return true;
        for (var i = 0; i < m.length; i++) if (!m[i].isMuted) return false;
        return true;
    }

    // Iguala la publicación propia con el botón de silenciar, para que el resto lo vea.
    function igualarMiMicrofono(e) {
        if (ocupado || !e.room || e.room.state !== 'connected' || e.sinMic) return;
        var deseado = e.muted === true;
        var pendientes = microfonos(e.room.localParticipant).filter(function (pub) { return pub.isMuted !== deseado; });
        if (!pendientes.length) return;
        ocupado = true;
        Promise.all(pendientes.map(function (pub) {
            try { return Promise.resolve(deseado ? pub.mute() : pub.unmute()); } catch (err) { return Promise.resolve(); }
        })).catch(function () {}).then(function () {
            // la pista local debe quedar como la dejó el botón, pase lo que pase
            try { if (e.localStream) e.localStream.getAudioTracks().forEach(function (t) { t.enabled = !e.muted; }); } catch (err) {}
            ocupado = false;
        });
    }

    function pintar(e) {
        var apagados = {};
        if (e.room && e.room.state === 'connected') {
            apagados.tile_local = e.sinMic === true || e.muted === true || sinMicro(e.room.localParticipant);
            if (e.room.remoteParticipants) {
                e.room.remoteParticipants.forEach(function (p) { apagados['tile_' + p.identity] = sinMicro(p); });
            }
        }
        var mosaicos = document.querySelectorAll('.tile:not(.pantalla)');
        for (var i = 0; i < mosaicos.length; i++) mosaicos[i].classList.toggle('sin-micro', apagados[mosaicos[i].id] === true);
    }

    setInterval(function () {
        var e = estado();
        if (!e) return;
        igualarMiMicrofono(e);
        pintar(e);
    }, 300);
})();
