// chat-ficha-persona.js — T-43 (01/09/2026): ficha del compañero al hacer clic en su foto.
// La gente daba clic al avatar esperando ver quién es; hasta hoy no pasaba nada.
// Funciona en la cabecera de la conversación y en la lista de conversaciones directas.
// Los datos vienen del directorio de nómina; los personales solo se muestran a quien
// corresponde (lo decide el servidor, aquí solo se pinta lo que llega).
(function () {
    'use strict';

    var abierto = null;

    function convs() { try { return Array.isArray(conversations) ? conversations : []; } catch (e) { return []; } }

    function idDesdeElemento(el) {
        var item = el.closest('.conversation-item');
        if (item) {
            var c = convs().find(function (x) { return String(x.id) === String(item.getAttribute('data-conv-id')); });
            if (c && c.conversation_type !== 'group' && c.other_user) return c.other_user.id;
            return null;                     // en grupos el avatar no es de una persona
        }
        if (el.closest('.chat-main-header')) {
            try { if (currentConversationType !== 'group' && currentChatTrabajadorId) return currentChatTrabajadorId; } catch (e) {}
        }
        var conId = el.closest('[data-usuario-id]');
        if (conId) return conId.getAttribute('data-usuario-id');
        return null;
    }

    function cerrar() { if (abierto) { abierto.remove(); abierto = null; } }

    function fila(etiqueta, valor, icono) {
        if (!valor) return '';
        return '<div class="fp-fila"><i class="fas ' + icono + '"></i><div><small>' + etiqueta +
               '</small><div>' + String(valor).replace(/</g, '&lt;') + '</div></div></div>';
    }

    function pintar(p, incluyePersonales) {
        cerrar();
        var iniciales = (p.nombre || '?').trim().slice(0, 2).toUpperCase();
        var fondo = document.createElement('div');
        fondo.className = 'fp-fondo';
        fondo.innerHTML =
            '<div class="fp-tarjeta" role="dialog" aria-label="Ficha de ' + (p.nombre || '') + '">' +
              '<button class="fp-cerrar" title="Cerrar">&times;</button>' +
              '<div class="fp-foto">' +
                (p.foto ? '<img src="' + p.foto + '" alt="' + (p.nombre || '') + '" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' : '') +
                '<span class="fp-ini"' + (p.foto ? ' style="display:none"' : '') + '>' + iniciales + '</span>' +
              '</div>' +
              '<h3>' + (p.nombre || 'Sin nombre') + '</h3>' +
              (p.cargo ? '<div class="fp-cargo">' + p.cargo + '</div>' : '') +
              '<div class="fp-datos">' +
                fila('Área', p.area, 'fa-sitemap') +
                fila('Sede', p.sede, 'fa-location-dot') +
                fila('Correo institucional', p.correo_institucional, 'fa-envelope') +
                fila('Teléfono institucional', p.telefono_institucional, 'fa-phone') +
                fila('Extensión', p.extension, 'fa-hashtag') +
                (incluyePersonales ?
                  (fila('Cédula', p.cedula, 'fa-id-card') +
                   fila('Teléfono personal', p.telefono_personal, 'fa-mobile-screen') +
                   fila('Teléfono fijo', p.telefono_fijo, 'fa-phone-volume') +
                   fila('Correo personal', p.correo_personal, 'fa-at')) : '') +
              '</div>' +
              (incluyePersonales ? '' :
                '<p class="fp-nota">Los datos personales (cédula, teléfono y correo personales) ' +
                'solo los ve Talento Humano y cada persona en su propia ficha.</p>') +
            '</div>';
        fondo.addEventListener('click', function (e) { if (e.target === fondo || e.target.classList.contains('fp-cerrar')) cerrar(); });
        document.body.appendChild(fondo);
        abierto = fondo;
    }

    async function abrirFicha(usuarioId) {
        try {
            var r = await fetch('/api/chat/personas/' + encodeURIComponent(usuarioId) + '/ficha',
                                { credentials: 'same-origin' });
            var d = await r.json();
            if (!d.success) {
                if (window.toastr) toastr.info(d.error || 'No se pudo abrir la ficha');
                return;
            }
            pintar(d.persona, d.incluye_personales);
        } catch (e) {
            if (window.toastr) toastr.error('No se pudo abrir la ficha en este momento');
        }
    }
    window.abrirFichaPersona = abrirFicha;

    document.addEventListener('click', function (e) {
        var avatar = e.target.closest('.conversation-avatar, .chat-main-header .avatar, .avatar[data-usuario-id]');
        if (!avatar) return;
        var id = idDesdeElemento(avatar);
        if (!id) return;                     // grupos, «Mis notas» o sin dato: no se abre nada
        e.preventDefault(); e.stopPropagation();
        abrirFicha(id);
    }, true);

    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });
})();
