/* =============================================================================
   PENDIENTE-TEAMS punto 1 (14/10/2026) · PESTAÑA «REUNIONES» EN EL TEAMS
   -----------------------------------------------------------------------------
   QUÉ HACE: añade la pestaña «Reuniones» junto a los filtros del panel izquierdo.
   Muestra Hoy / Próximas con el estado real (Sin iniciar · En curso · Finalizada),
   botón Iniciar (quien organiza) / Entrar o Ingresar (invitado) y «Copiar invitación».
   INMEDIATO: Raíces empuja cada cambio (crear, editar, cancelar, iniciar, finalizar)
   por el canal de notificaciones (evento Socket.IO `notificacion`, tipo «reunion»);
   al recibirlo la agenda se recarga al instante. El sondeo de 60 s es solo respaldo.
   DATOS: /api/chat/reuniones/proximas (misma sesión del chat).
   Va en su propio archivo; no toca chat-lista.js ni chat-lista-teams.js.
   ============================================================================= */
(function () {
    'use strict';

    // Direcciones desde la configuración del servidor (plantilla: window.MQ_URL_INTRANET / MQ_URL_REUNIONES).
    var RAICES = String(window.MQ_URL_INTRANET || '').replace(/\/+$/, '');
    var MEET = String(window.MQ_URL_REUNIONES || '').replace(/\/+$/, '');
    var activa = false, items = [], cargando = false, socketEscuchado = null;
    var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

    function dosD(n) { return (n < 10 ? '0' : '') + n; }
    function fecha(iso) {
        var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || '');
        return m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) : null;
    }
    function mismoDia(a, b) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate(); }
    function el(t, c, x) { var n = document.createElement(t); if (c) n.className = c; if (x !== undefined) n.textContent = x; return n; }

    function estilos() {
        if (document.getElementById('mqAgendaCss')) return;
        var s = document.createElement('style');
        s.id = 'mqAgendaCss';
        s.textContent = [
            '#mqAgenda{padding:4px 0 12px;overflow-y:auto}',
            '.mq-ag-dia{padding:10px 14px 4px;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;opacity:.6}',
            '.mq-ag-item{padding:10px 14px;border-bottom:1px solid rgba(127,127,127,.15)}',
            '.mq-ag-cab{display:flex;gap:10px;align-items:baseline}',
            '.mq-ag-hora{font-weight:600;font-variant-numeric:tabular-nums;min-width:42px}',
            '.mq-ag-tit{font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
            '.mq-ag-meta{font-size:12px;opacity:.75;margin:4px 0 8px 52px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}',
            '.mq-ag-tag{display:inline-flex;align-items:center;gap:4px;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:500;background:rgba(0,97,161,.12);color:#0061a1}',
            '.mq-ag-tag.vivo{background:rgba(22,163,74,.14);color:#16a34a}',
            '.mq-ag-tag.vivo:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;animation:mqAgLat 1.6s infinite}',
            '.mq-ag-tag.gris{background:rgba(127,127,127,.15);color:inherit;opacity:.8}',
            '@keyframes mqAgLat{50%{opacity:.3}}',
            '.mq-ag-acc{display:flex;gap:6px;margin-left:52px;flex-wrap:wrap}',
            '.mq-ag-btn{border:1px solid rgba(127,127,127,.35);background:transparent;color:inherit;border-radius:7px;padding:4px 10px;font-size:12.5px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px}',
            '.mq-ag-btn.prim{background:#0061a1;border-color:#0061a1;color:#fff}',
            '.mq-ag-vacio{padding:32px 16px;text-align:center;opacity:.65;font-size:13px}',
            '.mq-ag-vacio a{color:#0061a1;font-weight:500}',
            '.mq-ag-pie{padding:10px 14px;font-size:12px;opacity:.7}',
            '.mq-ag-pie a{color:#0061a1}'
        ].join('\n');
        document.head.appendChild(s);
    }

    function estado(r, ahora) {
        var c = r.config || {}, ini = fecha(r.inicio), fin = fecha(r.fin);
        if (r.estado === 'cancelada') return { t: 'Cancelada', c: 'gris', vigente: false };
        if (c.cerrada_en || (fin && ahora > new Date(fin.getTime() + 2 * 3600000))) return { t: 'Finalizada', c: 'gris', vigente: false };
        if (c.abierta_en) return { t: 'En curso', c: 'vivo', vigente: true, curso: true };
        return { t: 'Sin iniciar', c: '', vigente: true, curso: false, ini: ini };
    }

    function invitacion(r) {
        var d = fecha(r.inicio), c = r.config || {}, L = [];
        L.push('Le invitan a una reunión de Maquita Meet.', '', 'Tema: ' + r.asunto);
        if (d) { L.push('Fecha: ' + DIAS[d.getDay()] + ' ' + d.getDate() + ' de ' + MESES[d.getMonth()] + ' de ' + d.getFullYear()); L.push('Hora: ' + dosD(d.getHours()) + ':' + dosD(d.getMinutes()) + ' · Ecuador (GMT-5)'); }
        if (r.duracion_horas) L.push('Duración: ' + (r.duracion_horas === 8 ? 'Día completo (8 horas)' : r.duracion_horas + (r.duracion_horas === 1 ? ' hora' : ' horas')));
        if (r.mensaje) L.push('', 'Descripción:', r.mensaje);
        L.push('', 'Unirse a la reunión:', (MEET ? MEET + '/' : '') + r.sala, '', 'ID de reunión: ' + r.sala, '');
        if (c.sala_espera) L.push('La reunión tiene sala de espera: quien organiza te admitirá al llegar.');
        L.push(c.unirse_antes ? 'Puedes entrar desde 30 minutos antes de la hora.' : 'Podrás entrar cuando quien organiza inicie la reunión; si llegas antes, la página esperará y entrará sola.');
        L.push('Funciona en el navegador (Chrome o Edge) sin instalar nada, o en la app Jitsi Meet del celular.');
        return L.join('\n');
    }

    function copiar(texto) {
        var ok = function () { if (typeof showToast === 'function') showToast('Invitación copiada'); };
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(texto).then(ok, function () { window.prompt('Copia la invitación:', texto); });
        else window.prompt('Copia la invitación:', texto);
    }

    function fila(r, ahora) {
        var e = estado(r, ahora), d = fecha(r.inicio);
        var li = el('div', 'mq-ag-item');
        var cab = el('div', 'mq-ag-cab');
        cab.appendChild(el('span', 'mq-ag-hora', d ? dosD(d.getHours()) + ':' + dosD(d.getMinutes()) : ''));
        var tit = el('span', 'mq-ag-tit', r.asunto); tit.title = r.asunto;
        cab.appendChild(tit);
        li.appendChild(cab);
        var meta = el('div', 'mq-ag-meta');
        meta.appendChild(el('span', 'mq-ag-tag ' + e.c, e.t));
        meta.appendChild(el('span', 'mq-ag-tag gris', r.es_creador ? 'Organizas' : 'Invitado'));
        meta.appendChild(document.createTextNode((r.duracion_horas || 1) + ' h'));
        li.appendChild(meta);
        if (e.vigente) {
            var acc = el('div', 'mq-ag-acc');
            var a = el('a', 'mq-ag-btn prim');
            a.target = '_blank'; a.rel = 'noopener';
            if (r.es_creador) { a.href = RAICES + '/reuniones/acceder/' + r.id + '?app=1'; a.textContent = '▶ Iniciar'; a.title = 'Al entrar, la sala se abre para los invitados'; }
            else { a.href = RAICES + '/reuniones/unirse?sala=' + encodeURIComponent(r.sala) + '&app=1'; a.textContent = e.curso ? 'Ingresar' : 'Ir a la reunión'; }
            acc.appendChild(a);
            var b = el('button', 'mq-ag-btn', 'Copiar invitación'); b.type = 'button';
            b.addEventListener('click', function () { copiar(invitacion(r)); });
            acc.appendChild(b);
            li.appendChild(acc);
        }
        return li;
    }

    function panel() {
        var p = document.getElementById('mqAgenda');
        if (p) return p;
        var lista = document.getElementById('conversationsList');
        if (!lista) return null;
        p = el('div'); p.id = 'mqAgenda'; p.style.display = 'none';
        lista.parentNode.insertBefore(p, lista.nextSibling);
        return p;
    }

    function pintar() {
        var p = panel(); if (!p) return;
        var ahora = new Date(), hoy = [], prox = [];
        items.forEach(function (r) { var d = fecha(r.inicio); if (!d) return; (mismoDia(d, ahora) ? hoy : prox).push(r); });
        var cuenta = document.getElementById('mqAgendaCuenta');
        if (cuenta) cuenta.textContent = hoy.length ? String(hoy.length) : '';
        if (!activa) return;
        while (p.firstChild) p.removeChild(p.firstChild);
        if (!items.length) {
            var v = el('div', 'mq-ag-vacio', 'No tienes reuniones próximas. ');
            var a = el('a', '', 'Programar una'); a.href = RAICES + '/reuniones/nueva?app=1'; a.target = '_blank';
            v.appendChild(a); p.appendChild(v); return;
        }
        if (hoy.length) { p.appendChild(el('div', 'mq-ag-dia', 'Hoy')); hoy.forEach(function (r) { p.appendChild(fila(r, ahora)); }); }
        var dia = null;
        prox.forEach(function (r) {
            var d = fecha(r.inicio), k = d.toDateString();
            if (k !== dia) { dia = k; p.appendChild(el('div', 'mq-ag-dia', DIAS[d.getDay()] + ', ' + d.getDate() + ' de ' + MESES[d.getMonth()])); }
            p.appendChild(fila(r, ahora));
        });
        var pie = el('div', 'mq-ag-pie');
        var ver = el('a', '', 'Ver todas en Reuniones'); ver.href = RAICES + '/reuniones/mis-reuniones?app=1'; ver.target = '_blank';
        pie.appendChild(ver); p.appendChild(pie);
    }

    function cargar() {
        if (cargando) return;
        cargando = true;
        fetch('/api/chat/reuniones/proximas?limit=40', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (d) { if (d && d.success) { items = (d.reuniones || []).filter(function (r) { return r.estado !== 'cancelada'; }); pintar(); } })
            .catch(function () {})
            .then(function () { cargando = false; });
    }

    function mostrar(si) {
        activa = si;
        var lista = document.getElementById('conversationsList'), p = panel();
        if (lista) lista.style.display = si ? 'none' : '';
        if (p) p.style.display = si ? '' : 'none';
        var tab = document.getElementById('mqAgendaTab');
        if (tab) tab.classList.toggle('active', si);
        if (si) { pintar(); cargar(); }
    }

    function montarPestana() {
        var barra = document.querySelector('.chat-tabs');
        if (!barra || document.getElementById('mqAgendaTab')) return !!barra;
        var b = el('button', 'chat-tab mq-filtro-reuniones');
        b.id = 'mqAgendaTab'; b.type = 'button';
        b.appendChild(document.createTextNode('Reuniones '));
        var c = el('span', 'mq-seccion-cuenta'); c.id = 'mqAgendaCuenta'; b.appendChild(c);
        b.addEventListener('click', function () { mostrar(true); });
        barra.appendChild(b);
        // los otros filtros (Todos, No leído, Chats de reuniones) vuelven a la lista de chats
        barra.addEventListener('click', function (ev) {
            var t = ev.target.closest('.chat-tab');
            if (t && t !== b) mostrar(false);
        });
        return true;
    }

    function escucharSocket() {
        var s = null;
        try { s = (typeof chatUltraFast !== 'undefined' && chatUltraFast && chatUltraFast.socket) || (typeof socket !== 'undefined' && socket) || null; } catch (e) { s = null; }
        if (!s || s === socketEscuchado) return;
        socketEscuchado = s;
        s.on('notificacion', function (d) {
            if (d && (d.tipo === 'reunion' || d.evento === 'reuniones_cambio')) cargar();
        });
    }

    function iniciar() {
        estilos();
        var intentos = 0;
        var t = setInterval(function () {
            intentos++;
            if (montarPestana() || intentos > 40) { clearInterval(t); cargar(); }
        }, 500);
        setInterval(escucharSocket, 3000);            // el socket puede reconectar con otro objeto
        setInterval(cargar, 60000);                    // respaldo
        document.addEventListener('visibilitychange', function () { if (!document.hidden) cargar(); });
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 1200); });
    window.mqAgendaReuniones = { cargar: cargar, mostrar: mostrar };   // para pruebas de humo
})();
