/* Chat institucional - Vistos en tiempo real (2026-08-27)
 * ✓ enviado -> ✓✓ entregado -> ✓✓ azul leído.
 * El servidor ya soportaba 'delivered' y 'msg_status' pero el cliente nunca los usaba.
 * Se engancha al socket de ChatUltraFast sin modificar chat-page.js. */
(function () {
    'use strict';

    function marcar(id, estado) {
        if (typeof window.updateMessageStatus === 'function') window.updateMessageStatus(id, estado);
    }

    function engancharSocket(inst) {
        const s = inst && inst.socket;
        if (!s || s.__vistos) return;
        s.__vistos = true;
        window._chatSocketVistos = s;

        // Al recibir un mensaje ajeno: confirmar entrega al servidor
        s.on('msg', function (d) {
            if (!d || !d.id || d.from == inst.userId) return;
            s.emit('delivered', { id: d.id, c: d.c });
        });

        // El servidor avisa al remitente: entregado / leído (uno o varios ids)
        s.on('msg_status', function (d) {
            if (!d) return;
            const ids = Array.isArray(d.ids) ? d.ids : (d.id ? [d.id] : []);
            const estado = d.status === 'read' ? 'read' : 'delivered';
            ids.forEach(function (id) {
                const el = document.querySelector('.message.sent[data-message-id="' + id + '"] .message-status');
                if (!el || el.classList.contains('read')) return;
                if (estado === 'delivered' && el.classList.contains('delivered')) return;
                marcar(id, estado);
            });
        });
    }

    function envolver() {
        const Clase = window.ChatUltraFast;
        if (!Clase || !Clase.prototype || Clase.prototype.__vistos) return false;
        const conectarOriginal = Clase.prototype.connect;
        Clase.prototype.connect = function () {
            const inst = this;
            const r = conectarOriginal.apply(this, arguments);
            const fin = function () { engancharSocket(inst); };
            if (r && typeof r.then === 'function') r.then(fin, function () {}); else fin();
            setTimeout(fin, 1500);
            return r;
        };
        Clase.prototype.__vistos = true;
        return true;
    }
    if (!envolver()) document.addEventListener('DOMContentLoaded', envolver);

    // Los mensajes entrantes cargados por listado ya quedan "entregados" en el servidor
    // (registrar_entrega_al_listar); aquí solo el tiempo real.
})();
