/* =============================================================================
   PENDIENTE-TEAMS punto 3 (14/10/2026) · CREAR REUNIÓN DESDE UN GRUPO
   -----------------------------------------------------------------------------
   QUÉ HACE: en un chat de GRUPO añade al encabezado el botón «Reunión» con dos
   opciones:
     · Reunión ahora: crea una reunión REAL del módulo de reuniones (endpoint
       /api/chat/reuniones/instantanea) con los miembros del grupo como invitados,
       publica en el grupo el aviso con el enlace y abre la sala para quien la
       crea por la intranet (Iniciar: así la sala queda abierta para todos).
     · Programar reunión: abre el formulario de la intranet con el tema y los
       miembros precargados (reciben la invitación con .ics). Cuando la reunión
       se crea, la intranet avisa por Socket.IO y este módulo publica en el
       grupo el bloque de invitación.
   Direcciones desde la configuración (window.MQ_URL_INTRANET / MQ_URL_REUNIONES).
   Va en su propio archivo; no toca chat-encabezado-teams.js ni chat-envio.js.
   ============================================================================= */
(function () {
    'use strict';

    var RAICES = String(window.MQ_URL_INTRANET || '').replace(/\/+$/, '');
    var MEET = String(window.MQ_URL_REUNIONES || '').replace(/\/+$/, '');
    var CLAVE = 'mqReunionGrupoPendiente';
    var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    var socketEscuchado = null;

    function aviso(msg, tipo) {
        if (typeof window.mostrarNotificacion === 'function') window.mostrarNotificacion(msg, tipo || 'info');
        else if (typeof window.showToast === 'function') window.showToast(msg);
        else window.alert(msg);
    }
    function convActual() {
        try { return { id: currentConversationId, tipo: currentConversationType }; } catch (e) { return { id: null, tipo: null }; }
    }
    function nombreGrupo() {
        var h = document.getElementById('chatHeaderName');
        return h ? (h.textContent || '').trim() : 'el grupo';
    }
    function dosD(n) { return (n < 10 ? '0' : '') + n; }
    function fecha(iso) {
        var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || '');
        return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : null;
    }

    async function miembros(convId) {
        var r = await fetch('/api/chat/conversations/' + convId + '/grupo', { credentials: 'same-origin' });
        var d = await r.json();
        if (!d.success) throw new Error(d.error || 'No se pudo leer el grupo');
        return d.grupo.miembros || [];
    }

    async function publicar(convId, texto) {
        var r = await fetch('/api/chat/conversations/' + convId + '/messages', {
            method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: texto, message_type: 'text' })
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
    }

    function textoProgramada(r) {
        var d = fecha(r.inicio), L = ['📅 Reunión programada: ' + r.asunto];
        if (d) L.push(DIAS[d.getDay()] + ' ' + d.getDate() + ' de ' + MESES[d.getMonth()] + ', ' + dosD(d.getHours()) + ':' + dosD(d.getMinutes()) + ' (Ecuador) · ' + (r.duracion_horas || 1) + ' h');
        if (r.mensaje) L.push(r.mensaje);
        L.push('Unirse: ' + (MEET ? MEET + '/' : '') + r.sala);
        L.push('Entrarán cuando quien organiza inicie la reunión. Todos los miembros del grupo están invitados.');
        return L.join('\n');
    }

    /* ---- Reunión ahora ---- */
    async function reunionAhora() {
        var c = convActual();
        if (!c.id || c.tipo !== 'group') return aviso('Abre un chat de grupo para crear la reunión.', 'warning');
        var tema = window.prompt('Tema de la reunión:', 'Reunión de ' + nombreGrupo());
        if (tema === null) return;
        var ventana = window.open('about:blank', '_blank');   // se abre ya, para que el navegador no la bloquee
        try {
            var ms = await miembros(c.id);
            var correos = ms.filter(function (m) { return !m.es_yo && m.email; }).map(function (m) { return m.email; });
            var r = await fetch('/api/chat/reuniones/instantanea', {
                method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ asunto: (tema || '').trim() || ('Reunión de ' + nombreGrupo()), participantes: correos, calendario: false })
            });
            var d = await r.json();
            if (!d.success) throw new Error(d.error || 'No se pudo crear la reunión');
            var reu = d.reunion;
            await publicar(c.id, '🎥 Reunión en curso: ' + reu.asunto + '\nUnirse: ' + (MEET ? MEET + '/' : '') + reu.sala +
                '\nTodos los miembros del grupo están invitados.');
            var destino = RAICES ? RAICES + '/reuniones/acceder/' + reu.id + '?app=1' : (reu.url || reu.url_web);
            if (ventana) ventana.location.href = destino; else window.location.href = destino;
        } catch (e) {
            if (ventana) ventana.close();
            aviso('No se pudo crear la reunión: ' + e.message, 'error');
        }
    }

    /* ---- Programar reunión ---- */
    async function programar() {
        var c = convActual();
        if (!c.id || c.tipo !== 'group') return aviso('Abre un chat de grupo para programar la reunión.', 'warning');
        if (!RAICES) return aviso('Falta la dirección de la intranet en la configuración.', 'error');
        var ventana = window.open('about:blank', '_blank');
        try {
            var ms = await miembros(c.id);
            var correos = ms.filter(function (m) { return !m.es_yo && m.email; }).map(function (m) { return m.email; });
            try { localStorage.setItem(CLAVE, JSON.stringify({ conv: c.id, t: Date.now() })); } catch (e) { /* sin almacenamiento */ }
            var url = RAICES + '/reuniones/nueva?app=1&asunto=' + encodeURIComponent('Reunión de ' + nombreGrupo()) +
                      '&invitados=' + encodeURIComponent(correos.join(','));
            if (ventana) ventana.location.href = url; else window.location.href = url;
            aviso('Completa la fecha y la hora. Al guardar, la invitación se publicará en este grupo.', 'info');
        } catch (e) {
            if (ventana) ventana.close();
            aviso('No se pudo abrir el formulario: ' + e.message, 'error');
        }
    }

    /* Cuando la intranet confirma la reunión creada, se publica en el grupo de origen */
    async function alCrearse(d) {
        if (!d || d.evento !== 'reuniones_cambio' || d.accion !== 'creada' || !d.reunion_id) return;
        var p = null;
        try { p = JSON.parse(localStorage.getItem(CLAVE) || 'null'); } catch (e) { p = null; }
        if (!p || !p.conv || Date.now() - p.t > 3600000) return;
        try { localStorage.removeItem(CLAVE); } catch (e) { /* nada */ }
        try {
            var r = await fetch('/api/chat/reuniones/proximas?limit=60', { credentials: 'same-origin' });
            var j = await r.json();
            var reu = (j.reuniones || []).filter(function (x) { return x.id === d.reunion_id; })[0];
            if (!reu) return;
            await publicar(p.conv, textoProgramada(reu));
            aviso('Invitación publicada en el grupo.', 'success');
        } catch (e) {
            aviso('La reunión se creó, pero no se pudo publicar en el grupo: ' + e.message, 'warning');
        }
    }

    function escucharSocket() {
        var s = null;
        try { s = (typeof chatUltraFast !== 'undefined' && chatUltraFast && chatUltraFast.socket) || (typeof socket !== 'undefined' && socket) || null; } catch (e) { s = null; }
        if (!s || s === socketEscuchado) return;
        socketEscuchado = s;
        s.on('notificacion', alCrearse);
    }

    /* ---- Botón y menú en el encabezado ---- */
    function montarBoton() {
        var caja = document.querySelector('.chat-main-header .chat-actions');
        if (!caja) return false;
        if (!document.getElementById('mq-reunion-grupo')) {
            var envoltura = document.createElement('div');
            envoltura.className = 'dropdown d-inline-block';
            envoltura.id = 'mq-reunion-grupo';
            envoltura.style.display = 'none';
            envoltura.innerHTML =
                '<button type="button" class="meet-btn" data-bs-toggle="dropdown" title="Reunión con este grupo" style="color:#0061a1">' +
                '<i class="fas fa-calendar-plus"></i></button>' +
                '<ul class="dropdown-menu dropdown-menu-end">' +
                '<li><a class="dropdown-item" href="#" data-accion="ahora"><i class="fas fa-video me-2"></i>Reunión ahora</a></li>' +
                '<li><a class="dropdown-item" href="#" data-accion="programar"><i class="fas fa-calendar-alt me-2"></i>Programar reunión</a></li>' +
                '</ul>';
            envoltura.addEventListener('click', function (ev) {
                var a = ev.target.closest('[data-accion]');
                if (!a) return;
                ev.preventDefault();
                if (a.getAttribute('data-accion') === 'ahora') reunionAhora(); else programar();
            });
            var video = document.getElementById('btnLlamadaVideo');
            caja.insertBefore(envoltura, video || caja.firstChild);
        }
        return true;
    }

    function actualizarVisibilidad() {
        var b = document.getElementById('mq-reunion-grupo');
        if (b) b.style.display = convActual().tipo === 'group' ? '' : 'none';
    }

    function iniciar() {
        var intentos = 0;
        var t = setInterval(function () { if (montarBoton() || ++intentos > 40) clearInterval(t); }, 500);
        setInterval(actualizarVisibilidad, 700);
        setInterval(escucharSocket, 3000);
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 1300); });
    window.mqReunionGrupo = { ahora: reunionAhora, programar: programar };   // para pruebas de humo
})();
