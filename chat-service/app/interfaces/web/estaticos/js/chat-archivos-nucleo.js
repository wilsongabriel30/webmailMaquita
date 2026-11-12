/* T-101 · Lista de archivos del chat: lo común a la pestaña «Archivos» de una conversación y a la sección «Archivos».
 * Pide la lista al servidor (/api/chat/conversations/<id>/archivos o /api/chat/archivos) y la pinta: tabla para
 * documentos, rejilla para fotos. Expone window.MaquitaArchivos.crear(contenedor, opciones). */
(function () {
    'use strict';

    function texto(v) { var d = document.createElement('div'); d.textContent = v == null ? '' : String(v); return d.innerHTML; }
    function atributo(v) { return texto(v).replace(/"/g, '&quot;'); }
    function tamano(n) {
        n = Number(n || 0); if (!n) return '';
        var u = ['B', 'KB', 'MB', 'GB'], i = 0;
        while (n >= 1024 && i < 3) { n /= 1024; i++; }
        return (i ? n.toFixed(1).replace('.', ',') : n) + ' ' + u[i];
    }
    function fecha(t) {
        var d = new Date(t), hoy = new Date();
        if (!t || isNaN(d)) return '';
        if (d.toDateString() === hoy.toDateString()) return d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
        var op = { day: 'numeric', month: 'short' };
        if (d.getFullYear() !== hoy.getFullYear()) op.year = 'numeric';
        return d.toLocaleDateString('es-EC', op);
    }
    function nombrePropio(n) {
        n = (n || '').trim();
        if (!n || n !== n.toUpperCase()) return n;
        return n.toLowerCase().replace(/(^|[\s\-'])([a-záéíóúñü])/g, function (m, a, b) { return a + b.toUpperCase(); });
    }
    function icono(a) {
        var m = (a.tipo_mime || '').toLowerCase(), n = (a.nombre || '').toLowerCase();
        if (a.clase === 'image') return 'fa-image';
        if (a.clase === 'video') return 'fa-video';
        if (a.clase === 'audio' || m.indexOf('audio/') === 0) return 'fa-microphone';
        return 'fa-file';
    }
    function extension(nombre) {
        var p = String(nombre || '').split('.'); return p.length > 1 ? p.pop().slice(0, 5).toUpperCase() : '';
    }

    /* opciones: { conversacion: id | null, clase: 'archivos'|'fotos'|'todos', verEnChat: function(archivo) | null,
                   mostrarConversacion: bool, vacio: { archivos: '…', fotos: '…' } } */
    function crear(contenedor, opciones) {
        var est = { clase: opciones.clase || 'archivos', q: '', siguiente: null, cargando: false, pedido: 0, lista: [] };
        contenedor.classList.add('mq-arch');
        contenedor.innerHTML =
            '<div class="mq-arch-barra">' +
              '<div class="mq-arch-buscar"><i class="fas fa-search" aria-hidden="true"></i>' +
              '<input type="text" placeholder="Buscar por nombre" aria-label="Buscar por nombre" autocomplete="off"></div>' +
              '<span class="mq-arch-cuenta" aria-live="polite"></span>' +
            '</div>' +
            '<div class="mq-arch-cuerpo" role="list"></div>' +
            '<div class="mq-arch-pie"><button type="button" class="mq-arch-mas" hidden>Cargar más</button></div>';
        var cuerpo = contenedor.querySelector('.mq-arch-cuerpo'), mas = contenedor.querySelector('.mq-arch-mas');
        var cuenta = contenedor.querySelector('.mq-arch-cuenta'), campo = contenedor.querySelector('input');

        function ruta() {
            var base = opciones.conversacion ? '/api/chat/conversations/' + encodeURIComponent(opciones.conversacion) + '/archivos' : '/api/chat/archivos';
            var p = ['clase=' + encodeURIComponent(est.clase), 'limite=50'];
            if (est.q) p.push('q=' + encodeURIComponent(est.q));
            if (est.siguiente) p.push('desde=' + encodeURIComponent(est.siguiente));
            return base + '?' + p.join('&');
        }
        function filaArchivo(a) {
            var sub = [];
            sub.push(a.propio ? 'Tú' : nombrePropio(a.remitente));
            if (opciones.mostrarConversacion && a.conversacion) sub.push('en ' + nombrePropio(a.conversacion));
            var drive = a.ruta_drive ? '<span class="mq-arch-drive" title="' + atributo('En tu Drive: ' + a.ruta_drive) + '"><i class="fas fa-cloud-upload-alt" aria-hidden="true"></i></span>' : '';
            var ver = '<button type="button" class="mq-arch-boton" data-ver="' + atributo(a.id) + '" title="Ver en el chat" aria-label="Ver en el chat"><i class="far fa-comment" aria-hidden="true"></i></button>';
            return '<div class="mq-arch-fila" role="listitem">' +
                '<span class="mq-arch-icono" aria-hidden="true"><i class="fas ' + icono(a) + '"></i></span>' +
                '<span class="mq-arch-quien"><a class="mq-arch-nombre" href="' + atributo(a.url) + '" target="_blank" rel="noopener" title="' + atributo(a.nombre) + '">' + texto(a.nombre) + '</a>' +
                '<span class="mq-arch-detalle">' + texto(sub.join(' · ')) + '</span></span>' +
                '<span class="mq-arch-tipo">' + texto(extension(a.nombre)) + '</span>' +
                '<span class="mq-arch-peso">' + texto(tamano(a.bytes)) + '</span>' +
                '<span class="mq-arch-fecha" title="' + atributo(a.fecha ? new Date(a.fecha).toLocaleString('es-EC') : '') + '">' + texto(fecha(a.fecha)) + '</span>' +
                '<span class="mq-arch-acciones">' + drive + ver +
                '<a class="mq-arch-boton" href="' + atributo(a.url) + '" download="' + atributo(a.nombre) + '" title="Descargar" aria-label="Descargar"><i class="fas fa-download" aria-hidden="true"></i></a></span></div>';
        }
        function mosaicoFoto(a) {
            var dentro = a.clase === 'video'
                ? '<span class="mq-arch-video"><i class="fas fa-video" aria-hidden="true"></i></span>'
                : '<img src="' + atributo(a.url) + '" alt="' + atributo(a.nombre) + '" loading="lazy" decoding="async">';
            return '<a class="mq-arch-foto" role="listitem" href="' + atributo(a.url) + '" target="_blank" rel="noopener" title="' +
                atributo(a.nombre + ' · ' + (a.propio ? 'Tú' : nombrePropio(a.remitente)) + ' · ' + fecha(a.fecha)) + '">' + dentro + '</a>';
        }
        function pintar() {
            var rejilla = est.clase === 'fotos';
            cuerpo.classList.toggle('mq-arch-rejilla', rejilla);
            if (!est.lista.length) {
                var v = opciones.vacio || {};
                cuerpo.innerHTML = '<div class="mq-arch-vacio">' + texto(est.q ? 'Nada con ese nombre.' :
                    (rejilla ? (v.fotos || 'Todavía no se han compartido fotos.') : (v.archivos || 'Todavía no se han compartido archivos.'))) + '</div>';
            } else {
                cuerpo.innerHTML = est.lista.map(rejilla ? mosaicoFoto : filaArchivo).join('');
            }
            cuenta.textContent = est.lista.length ? est.lista.length + (est.siguiente ? ' o más' : '') + (rejilla ? ' fotos' : ' archivos') : '';
            mas.hidden = !est.siguiente;
        }
        function cargar(reiniciar) {
            if (reiniciar) { est.siguiente = null; est.lista = []; cuerpo.innerHTML = '<div class="mq-arch-vacio">Cargando…</div>'; mas.hidden = true; }
            var mio = ++est.pedido; est.cargando = true;
            fetch(ruta(), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
                if (mio !== est.pedido) return;
                est.lista = est.lista.concat(d.archivos || []);
                est.siguiente = d.hay_mas ? d.siguiente : null;
                pintar();
            }).catch(function () {
                if (mio !== est.pedido) return;
                if (!est.lista.length) cuerpo.innerHTML = '<div class="mq-arch-vacio">No se pudo cargar la lista.</div>';
            }).then(function () { if (mio === est.pedido) est.cargando = false; });
        }

        var espera = null;
        campo.addEventListener('input', function () {
            clearTimeout(espera);
            espera = setTimeout(function () { est.q = campo.value.trim(); cargar(true); }, 300);
        });
        mas.addEventListener('click', function () { if (!est.cargando) cargar(false); });
        cuerpo.addEventListener('click', function (e) {
            var b = e.target.closest('[data-ver]');
            if (!b || !opciones.verEnChat) return;
            var id = String(b.getAttribute('data-ver'));
            for (var i = 0; i < est.lista.length; i++) if (String(est.lista[i].id) === id) { opciones.verEnChat(est.lista[i]); break; }
        });

        cargar(true);
        return {
            clase: function (c) { if (c !== est.clase) { est.clase = c; cargar(true); } },
            conversacion: function (id) { opciones.conversacion = id; campo.value = ''; est.q = ''; cargar(true); },
            recargar: function () { cargar(true); }
        };
    }

    window.MaquitaArchivos = { crear: crear };
})();
