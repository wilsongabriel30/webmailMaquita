/* T-101 · Sección «Llamadas»: historial con filtros, llamar a alguien y marcación rápida.
 * Usa las mismas rutas de siempre: /api/chat/llamadas/{historial,frecuentes,favoritos} y /api/chat/users/search. */
(function () {
    'use strict';
    var favoritos = new Set();
    var llamadas = [];
    var grabaciones = null;      // se piden la primera vez que se elige ese filtro
    var filtro = 'todas';

    function texto(v) { var d = document.createElement('div'); d.textContent = v == null ? '' : String(v); return d.innerHTML; }
    function atributo(v) { return texto(v).replace(/"/g, '&quot;'); }
    function pedir(ruta, opciones) {
        return fetch(ruta, Object.assign({ credentials: 'same-origin' }, opciones || {})).then(function (r) { return r.json(); });
    }
    // «NOMBRE APELLIDO» -> «Nombre Apellido»
    function nombrePropio(n) {
        n = (n || 'Usuario').trim();
        if (n !== n.toUpperCase()) return n;
        return n.toLowerCase().replace(/(^|[\s\-'])([a-záéíóúñü])/g, function (m, a, b) { return a + b.toUpperCase(); });
    }
    function nombreCorto(n) { var p = nombrePropio(n).split(/\s+/); return p.length > 2 ? p[0] + ' ' + p[2] : p.join(' '); }
    function iniciales(n) { var p = nombrePropio(n).split(/\s+/); return ((p[0] || '?')[0] + ((p[2] || p[1] || '')[0] || '')).toUpperCase(); }
    function foto(p) {
        var letras = '<div class="llam-foto" aria-hidden="true">' + texto(iniciales(p.nombre)) + '</div>';
        if (!p.foto) return letras;
        return '<img class="llam-foto" src="' + atributo(p.foto) + '" alt="" loading="lazy" data-letras="' + atributo(iniciales(p.nombre)) + '">';
    }
    function cuando(t) {
        var d = new Date(t), hoy = new Date(), ayer = new Date(hoy.getTime() - 864e5);
        if (isNaN(d)) return '';
        var hora = d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
        if (d.toDateString() === hoy.toDateString()) return hora;
        if (d.toDateString() === ayer.toDateString()) return 'Ayer ' + hora;
        return d.toLocaleDateString('es-EC', { day: 'numeric', month: 'short' });
    }
    function duracion(s) {
        if (!s) return '';
        var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
        return h ? h + ' h ' + m + ' min' : (m ? m + ' min ' + r + ' s' : r + ' s');
    }

    // La llamada se abre en la ventana de siempre: la app de escritorio la lleva a su ventana propia.
    // Mismos parámetros que usa el chat (chat-llamadas.js): peer_id, peer_name y conv.
    function llamar(id, nombre, tipo, conversacion) {
        if (!id) return;
        var url = '/chat/llamada?role=caller&tipo=' + encodeURIComponent(tipo) + '&peer_id=' + encodeURIComponent(id) +
                  '&peer_name=' + encodeURIComponent(nombre || 'Usuario') + '&conv=' + encodeURIComponent(conversacion || '');
        window.open(url, 'maquita_llamada', 'width=1020,height=720,menubar=no,toolbar=no,location=no,status=no');
    }
    function abrirChat(conversacion, usuario) {
        if (conversacion) { location.href = '/chat/?conv=' + encodeURIComponent(conversacion); return; }
        pedir('/api/chat/conversations/direct', { method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ usuario_id: usuario }) }).then(function (d) {
            var c = d.conversacion || d.conversation || (d.datos || {}).conversacion || {};
            location.href = c.id ? '/chat/?conv=' + c.id : '/chat/';
        }).catch(function () { location.href = '/chat/'; });
    }
    function alternarFavorito(id) {
        var es = favoritos.has(id);
        var paso = es ? pedir('/api/chat/llamadas/favoritos/' + id, { method: 'DELETE' })
                      : pedir('/api/chat/llamadas/favoritos', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ usuario_id: id }) });
        paso.then(function () { if (es) favoritos.delete(id); else favoritos.add(id); pintarHistorial(); cargarRapidos(); }).catch(function () {});
    }

    function acciones(p, conversacion) {
        var fav = favoritos.has(p.id);
        var datos = ' data-id="' + atributo(p.id) + '" data-nombre="' + atributo(nombrePropio(p.nombre)) + '" data-conv="' + atributo(conversacion || '') + '"';
        return '<div class="llam-acciones">' +
            '<button class="llam-boton" data-accion="audio"' + datos + ' title="Llamar" aria-label="Llamar"><i class="fas fa-phone"></i></button>' +
            '<button class="llam-boton" data-accion="video"' + datos + ' title="Videollamada" aria-label="Videollamada"><i class="fas fa-video"></i></button>' +
            '<button class="llam-boton" data-accion="chat"' + datos + ' title="Abrir el chat" aria-label="Abrir el chat"><i class="far fa-comment"></i></button>' +
            '<button class="llam-boton ' + (fav ? 'activo' : '') + '" data-accion="favorito"' + datos + ' title="' + (fav ? 'Quitar de' : 'Añadir a') +
            ' marcación rápida" aria-label="Marcación rápida"><i class="' + (fav ? 'fas' : 'far') + ' fa-star"></i></button></div>';
    }

    // Grabaciones de llamadas: antes estaban en la ventana de historial del chat.
    function pintarGrabaciones() {
        var caja = document.getElementById('llamHistorial');
        if (grabaciones === null) { caja.innerHTML = '<div class="llam-vacio">Cargando…</div>'; return; }
        if (!grabaciones.length) { caja.innerHTML = '<div class="llam-vacio">Todavía no hay grabaciones.</div>'; return; }
        caja.innerHTML = grabaciones.map(function (g) {
            var grupo = g.es_conferencia === true || g.es_conferencia === 'True';
            var estado = g.estado === 'completada'
                ? '<a class="llam-boton" href="/api/chat/grabacion/descargar/' + encodeURIComponent(g.id) + '" title="Descargar la grabación" aria-label="Descargar la grabación"><i class="fas fa-download"></i></a>'
                : '<span class="llam-detalle">' + (g.estado === 'en_drive' ? 'Guardada en el Drive'
                    : (g.creado_en && Date.now() - new Date(g.creado_en).getTime() > 6 * 3600 * 1000 ? 'Sin finalizar' : 'Grabando…')) + '</span>';
            return '<div class="llam-fila llam-grabacion" role="listitem"><div class="llam-foto" aria-hidden="true"><i class="fas ' + (grupo ? 'fa-users' : 'fa-video') + '"></i></div>' +
                '<div class="llam-quien"><span class="llam-nombre">' + (grupo ? 'Conferencia' : 'Llamada') + '</span>' +
                '<span class="llam-detalle">' + texto(g.archivo || '') + '</span></div>' +
                '<div class="llam-acciones">' + estado + '</div><span class="llam-duracion"></span>' +
                '<span class="llam-fecha" title="' + atributo(g.creado_en ? new Date(g.creado_en).toLocaleString('es-EC') : '') + '">' + texto(g.creado_en ? cuando(g.creado_en) : '') + '</span></div>';
        }).join('');
    }
    function cargarGrabaciones() {
        pedir('/api/chat/grabacion/listar').then(function (d) { grabaciones = d.grabaciones || []; if (filtro === 'grabaciones') pintarGrabaciones(); })
            .catch(function () { grabaciones = []; if (filtro === 'grabaciones') document.getElementById('llamHistorial').innerHTML = '<div class="llam-vacio">No se pudieron cargar las grabaciones.</div>'; });
    }

    function pintarHistorial() {
        var caja = document.getElementById('llamHistorial');
        if (filtro === 'grabaciones') { pintarGrabaciones(); return; }
        var lista = llamadas.filter(function (l) {
            if (filtro === 'perdidas') return l.perdida;
            if (filtro === 'entrantes') return l.direccion !== 'saliente' && !l.perdida;
            if (filtro === 'salientes') return l.direccion === 'saliente';
            return true;
        });
        if (!lista.length) {
            caja.innerHTML = '<div class="llam-vacio">' + (llamadas.length ? 'No hay llamadas con ese filtro.' : 'Todavía no hay llamadas registradas.') + '</div>';
            return;
        }
        caja.innerHTML = lista.map(function (l) {
            var p = l.otro || {}; p.nombre = p.nombre || 'Usuario';
            var saliente = l.direccion === 'saliente';
            var tipo = l.tipo === 'video' ? 'Videollamada' : 'Llamada';
            var detalle = l.perdida ? '<i class="fas fa-phone-slash"></i>' + tipo + ' perdida'
                        : (saliente ? '<i class="fas fa-arrow-up" style="transform: rotate(45deg)"></i>' + tipo + ' saliente'
                                    : '<i class="fas fa-arrow-down" style="transform: rotate(45deg)"></i>' + tipo + ' entrante');
            return '<div class="llam-fila' + (l.perdida ? ' perdida' : '') + '" role="listitem">' + foto(p) +
                '<div class="llam-quien"><span class="llam-nombre">' + texto(nombrePropio(p.nombre)) + '</span><span class="llam-detalle">' + detalle + '</span></div>' +
                acciones(p, l.conversation_id) +
                '<span class="llam-duracion">' + texto(duracion(l.duracion_segundos)) + '</span>' +
                '<span class="llam-fecha" title="' + atributo(new Date(l.creado_en).toLocaleString('es-EC')) + '">' + texto(cuando(l.creado_en)) + '</span></div>';
        }).join('');
    }

    function cargarHistorial() {
        pedir('/api/chat/llamadas/historial?limit=60').then(function (d) {
            llamadas = d.llamadas || d.historial || []; pintarHistorial();
        }).catch(function () {
            if (!llamadas.length) document.getElementById('llamHistorial').innerHTML = '<div class="llam-vacio">No se pudo cargar el historial.</div>';
        });
    }

    function cargarRapidos() {
        Promise.all([pedir('/api/chat/llamadas/favoritos'), pedir('/api/chat/llamadas/frecuentes')]).then(function (r) {
            var favs = r[0].personas || [], vistos = new Set(), lista = [];
            favoritos = new Set(favs.map(function (p) { return p.id; }));
            favs.concat(r[1].personas || []).forEach(function (p) { if (!vistos.has(p.id)) { vistos.add(p.id); lista.push(p); } });
            document.getElementById('llamRapidos').innerHTML = lista.length ? lista.slice(0, 9).map(function (p) {
                return '<div class="llam-rapido" role="button" tabindex="0" data-accion="audio" data-id="' + atributo(p.id) + '" data-nombre="' +
                       atributo(nombrePropio(p.nombre)) + '" title="Llamar a ' + atributo(nombrePropio(p.nombre)) + '">' + foto(p) +
                       '<span>' + texto(nombreCorto(p.nombre)) + '</span></div>';
            }).join('') : '<div class="llam-vacio" style="grid-column: 1 / -1">Marca con la estrella a quien llames seguido.</div>';
            pintarHistorial();
        }).catch(function () {});
    }

    var espera = null;
    function buscar(q) {
        var caja = document.getElementById('llamResultados');
        clearTimeout(espera);
        if (q.length < 2) { caja.innerHTML = ''; return; }
        espera = setTimeout(function () {
            pedir('/api/chat/users/search?q=' + encodeURIComponent(q) + '&limit=8').then(function (d) {
                var lista = (d.users || d.usuarios || []).map(function (u) {
                    return { id: u.id, nombre: u.name || u.nombre || 'Usuario', foto: u.photo || u.foto || '', cargo: u.cargo || u.email || '' };
                });
                caja.innerHTML = lista.length ? lista.map(function (p) {
                    return '<div class="llam-fila">' + foto(p) + '<div class="llam-quien"><span class="llam-nombre">' + texto(nombrePropio(p.nombre)) +
                           '</span><span class="llam-detalle">' + texto(p.cargo) + '</span></div>' + acciones(p, '') + '</div>';
                }).join('') : '<div class="llam-vacio">Nadie con ese nombre.</div>';
            }).catch(function () { caja.innerHTML = '<div class="llam-vacio">No se pudo buscar ahora.</div>'; });
        }, 250);
    }

    document.addEventListener('click', function (e) {
        var b = e.target.closest('[data-accion]');
        if (b) {
            var id = parseInt(b.getAttribute('data-id'), 10), nombre = b.getAttribute('data-nombre'), accion = b.getAttribute('data-accion');
            if (accion === 'audio' || accion === 'video') llamar(id, nombre, accion, b.getAttribute('data-conv'));
            else if (accion === 'chat') abrirChat(b.getAttribute('data-conv'), id);
            else if (accion === 'favorito' && id) alternarFavorito(id);
            return;
        }
        var f = e.target.closest('.llam-filtro');
        if (f) {
            filtro = f.getAttribute('data-filtro');
            document.querySelectorAll('.llam-filtro').forEach(function (x) { x.setAttribute('aria-pressed', x === f ? 'true' : 'false'); });
            if (filtro === 'grabaciones') cargarGrabaciones();
            pintarHistorial();
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('llam-rapido')) e.target.click();
    });
    // si una foto no carga, se cambia por las iniciales
    document.addEventListener('error', function (e) {
        var img = e.target;
        if (img && img.tagName === 'IMG' && img.classList.contains('llam-foto')) {
            var d = document.createElement('div'); d.className = 'llam-foto'; d.textContent = img.getAttribute('data-letras') || '?';
            img.replaceWith(d);
        }
    }, true);
    document.getElementById('llamBuscar').addEventListener('input', function (e) { buscar(e.target.value.trim()); });

    // Volver al chat conservando el modo del panel flotante (?embed=1)
    var incrustado = new URLSearchParams(location.search).get('embed') === '1';
    var volver = document.getElementById('llamVolver');
    if (volver && incrustado) volver.setAttribute('href', '/chat/?embed=1');

    // Abrir «Llamadas» da por vistas las perdidas: el contador de la app vuelve a cero.
    pedir('/api/chat/llamadas/perdidas/vistas', { method: 'POST' }).catch(function () {});

    cargarRapidos(); cargarHistorial();
    setInterval(cargarHistorial, 60000);
})();
